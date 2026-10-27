"""
API do Lead Recon Engine para a Vercel (FastAPI).

Rotas (todas sob /api):
    GET  /api/health              Estado das integrações (sem dados de leads)
    POST /api/reconcile           Executa a reconciliação sob demanda
    GET  /api/report/latest       Último relatório gerado
    GET  /api/monitor/status      Estado do monitor ao vivo (?tick=true avança um ciclo)
    POST /api/monitor/tick        Avança um ciclo do monitor
    POST /api/monitor/reset       Limpa o monitor
    GET  /api/cron/monitor        Alvo do Vercel Cron

Desenvolvimento local:
    uvicorn app:app --port 8765 --reload
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "engine", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from engine.extractors.base import simulation_allowed
from engine.lead_monitor import (
    SOURCE_ENV_VARS,
    build_status_payload,
    cycle_is_due,
    is_demo_mode,
    new_state,
    run_cycle,
)
from engine.pipeline import CVUnavailableError, run_reconciliation
from engine.store import get_store

MONITOR_STATE_KEY = "leadrecon:monitor:state"
MONITOR_LOCK = "leadrecon:monitor"
REPORT_KEY = "leadrecon:report:latest"

app = FastAPI(title="Lead Recon Engine API", version="2.0.0")


# ━━━ Autenticação ━━━
# A API expõe e-mails e telefones de leads, então só responde com a chave correta.
# O dashboard envia ENGINE_API_KEY pelo servidor (nunca pelo navegador); o Vercel Cron
# envia CRON_SECRET como Bearer token.

def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    accepted = [k for k in (os.getenv("ENGINE_API_KEY"), os.getenv("CRON_SECRET")) if k]
    if not accepted:
        if os.getenv("VERCEL"):
            raise HTTPException(status_code=503, detail="ENGINE_API_KEY não configurada no servidor.")
        return  # desenvolvimento local sem chave
    provided = x_api_key or (authorization[7:] if authorization and authorization.startswith("Bearer ") else None)
    if not provided or not any(secrets.compare_digest(provided, k) for k in accepted):
        raise HTTPException(status_code=401, detail="Não autorizado.")


# ━━━ Monitor ━━━

def _load_state() -> dict:
    return get_store().get_json(MONITOR_STATE_KEY) or new_state()


def _tick(force: bool = False) -> dict:
    """Avança um ciclo do monitor, no máximo um por vez e no máximo um por minuto."""
    store = get_store()
    if not store.acquire_lock(MONITOR_LOCK, ttl_seconds=55):
        return _load_state()
    try:
        state = _load_state()
        if force or cycle_is_due(state, datetime.now(timezone.utc)):
            state = run_cycle(state)
            store.set_json(MONITOR_STATE_KEY, state)
        return state
    finally:
        store.release_lock(MONITOR_LOCK)


def _monitor_response(state: dict) -> dict:
    payload = build_status_payload(state)
    store = get_store()
    payload["persistence"] = {"kind": store.kind, "persistent": store.persistent}
    return payload


@app.get("/api/monitor/status", dependencies=[Depends(require_api_key)])
def monitor_status(tick: bool = Query(default=False)):
    return _monitor_response(_tick() if tick else _load_state())


@app.post("/api/monitor/tick", dependencies=[Depends(require_api_key)])
def monitor_tick():
    return _monitor_response(_tick())


@app.post("/api/monitor/reset", dependencies=[Depends(require_api_key)])
def monitor_reset():
    get_store().set_json(MONITOR_STATE_KEY, new_state())
    return {"message": "Monitor resetado com sucesso."}


@app.get("/api/cron/monitor", dependencies=[Depends(require_api_key)])
def cron_monitor():
    payload = _monitor_response(_tick())
    return {"stats": payload["stats"], "sources": payload["sources"]}


# ━━━ Reconciliação sob demanda ━━━

class ReconcileRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _parse_day(value: Optional[str], default: datetime) -> datetime:
    if not value:
        return default
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Data inválida: {value!r} (use YYYY-MM-DD).")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@app.post("/api/reconcile", dependencies=[Depends(require_api_key)])
def reconcile(body: ReconcileRequest = ReconcileRequest()):
    now = datetime.now(timezone.utc)
    start_dt = _parse_day(body.start_date, now - timedelta(days=7))
    end_dt = _parse_day(body.end_date, now)
    if end_dt.hour == 0 and end_dt.minute == 0 and body.end_date:
        end_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)  # inclui o dia final inteiro
    if start_dt > end_dt:
        raise HTTPException(status_code=422, detail="A data inicial deve ser anterior à final.")

    try:
        result = run_reconciliation(start_dt, end_dt)
    except CVUnavailableError as e:
        raise HTTPException(status_code=424, detail=str(e))

    saved = {
        "saved_at": now.isoformat(),
        "report": result.report.model_dump(mode="json"),
        "sources": result.sources,
    }
    store = get_store()
    if store.persistent:
        store.set_json(REPORT_KEY, saved)
    return saved


@app.get("/api/report/latest", dependencies=[Depends(require_api_key)])
def latest_report():
    return get_store().get_json(REPORT_KEY) or {"saved_at": None, "report": None, "sources": []}


# ━━━ Saúde ━━━

@app.get("/api/health")
def health():
    store = get_store()
    return {
        "ok": True,
        "persistence": {"kind": store.kind, "persistent": store.persistent},
        "simulation_allowed": simulation_allowed(),
        "monitor_mode": "demo" if is_demo_mode() else "production",
        "sources_configured": {
            **{name: bool(os.getenv(var)) for name, var in SOURCE_ENV_VARS.items()},
            "sheets_bi": bool(os.getenv("SHEETS_BI_CSV_URL") or os.getenv("SHEETS_BI_FILE")),
            "cv_crm": bool(os.getenv("CV_CRM_URL") and os.getenv("CV_CRM_TOKEN")),
        },
    }
