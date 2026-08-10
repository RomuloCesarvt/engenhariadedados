"""
Monitor ao Vivo de Leads — Verificação Automática no CV CRM.

Servidor FastAPI que roda em background, detecta leads novos nas fontes de mídia
(Meta Ads, Google Ads, RD Station, BeeViral) e verifica automaticamente se cada
lead chegou no CRM Construtor de Vendas (CV) dentro de ~10 minutos.

Uso:
    cd engine
    uvicorn lead_monitor:app --host 0.0.0.0 --port 8765 --reload
"""

import asyncio
import json
import os
import sys
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

# Configura codificação UTF-8 para stdout no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Carrega variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from engine.extractors import (
    MetaAdsExtractor,
    GoogleAdsExtractor,
    RDStationExtractor,
    BeeViralExtractor,
    CVCRMExtractor,
)
from engine.normalizer import clean_email, clean_phone, normalize_channel_alias
from engine.config import OriginChannel


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Modelo de Lead Monitorado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATUS_WAITING = "WAITING"
STATUS_FOUND = "FOUND"
STATUS_LOST = "LOST"
STATUS_MISMATCH = "MISMATCH"

# Tempo máximo de espera para o lead cair no CV (10 minutos)
MAX_WAIT_SECONDS = 600

# Intervalo de polling em segundos
POLL_INTERVAL_SECONDS = 60

# Intervalo de simulação de novos leads (modo demo)
DEMO_NEW_LEAD_INTERVAL = 20


@dataclass
class TrackedLead:
    lead_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    email_clean: Optional[str] = None
    phone_clean: Optional[str] = None
    origin_channel: str = ""
    campaign_name: Optional[str] = None
    source_created_at: str = ""
    detected_at: str = ""
    status: str = STATUS_WAITING
    cv_data: Optional[Dict] = None
    cv_origin: Optional[str] = None
    attempts: int = 0
    last_check_at: Optional[str] = None
    resolved_at: Optional[str] = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items()}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Estado Global do Monitor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

tracker: Dict[str, TrackedLead] = {}
known_lead_ids: set = set()
sse_clients: List[asyncio.Queue] = []
monitor_task: Optional[asyncio.Task] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dados de Simulação (modo demo)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEMO_LEADS_POOL = [
    {"email": "joao.silva@gmail.com", "phone": "11988881111", "channel": "meta_ads", "campaign": "Lançamento Residencial Sol"},
    {"email": "maria.santos@outlook.com", "phone": "21977772222", "channel": "google_ads", "campaign": "Search - Apartamentos SP"},
    {"email": "pedro.oliveira@hotmail.com", "phone": "31966663333", "channel": "rd_station", "campaign": "Ebook Guia Financiamento"},
    {"email": "ana.costa@yahoo.com.br", "phone": "11955554444", "channel": "beeviral", "campaign": "Programa Indique e Ganhe"},
    {"email": "lucas.ferreira@gmail.com", "phone": "41944445555", "channel": "meta_ads", "campaign": "Condomínio Horizonte"},
    {"email": "julia.almeida@icloud.com", "phone": "11933336666", "channel": "google_ads", "campaign": "Performance Max"},
    {"email": "rafael.souza@uol.com.br", "phone": "21922227777", "channel": "rd_station", "campaign": "Webinar Simulador Crédito"},
    {"email": "camila.lima@gmail.com", "phone": "31911118888", "channel": "meta_ads", "campaign": "Retargeting Instagram"},
    {"email": "bruno.pereira@outlook.com", "phone": "41900009999", "channel": "beeviral", "campaign": "Membro Indica Membro"},
    {"email": "fernanda.rocha@hotmail.com", "phone": "11988880000", "channel": "google_ads", "campaign": "Display Remarketing"},
    {"email": "gabriel.martins@gmail.com", "phone": "21977771111", "channel": "meta_ads", "campaign": "Lançamento Residencial Sol"},
    {"email": "larissa.gomes@yahoo.com", "phone": "31966662222", "channel": "rd_station", "campaign": "Landing Page Cadastro VIP"},
    {"email": "diego.nascimento@gmail.com", "phone": "11955553333", "channel": "meta_ads", "campaign": "Condomínio Horizonte"},
    {"email": "isabela.carvalho@outlook.com", "phone": "41944444444", "channel": "beeviral", "campaign": "Programa Indique e Ganhe"},
    {"email": "thiago.ribeiro@uol.com.br", "phone": "11933335555", "channel": "google_ads", "campaign": "Search - Lançamentos RJ"},
    {"email": "natalia.mendes@gmail.com", "phone": "21922226666", "channel": "meta_ads", "campaign": "Retargeting Facebook"},
    {"email": "felipe.barbosa@icloud.com", "phone": "31911117777", "channel": "rd_station", "campaign": "Ebook Guia Financiamento"},
    {"email": "patricia.dias@hotmail.com", "phone": "41900008888", "channel": "google_ads", "campaign": "Performance Max"},
    {"email": "rodrigo.andrade@gmail.com", "phone": "11988889999", "channel": "beeviral", "campaign": "Membro Indica Membro"},
    {"email": "amanda.moreira@outlook.com", "phone": "21977770000", "channel": "meta_ads", "campaign": "Condomínio Horizonte"},
]

# CV origins para simular (algumas corretas, algumas erradas para gerar MISMATCH)
DEMO_CV_ORIGINS = {
    "meta_ads": ["Facebook Ads", "Facebook Ads", "Facebook Ads", "Google Ads"],  # 75% correto
    "google_ads": ["Google Ads", "Google Ads", "Google Ads", "Google Ads"],      # 100% correto
    "rd_station": ["RD Station", "RD Station", "RD Station", "RD Station"],     # 100% correto
    "beeviral": ["BeeViral", "BeeViral", "BeeViral", "Orgânico"],              # 75% correto
}

demo_lead_index = 0


def is_demo_mode() -> bool:
    """Verifica se está no modo demo (sem APIs reais configuradas)."""
    has_meta = bool(os.getenv("META_ACCESS_TOKEN"))
    has_google = bool(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"))
    has_rd = bool(os.getenv("RD_STATION_API_TOKEN"))
    has_bee = bool(os.getenv("BEEVIRAL_API_KEY"))
    # Se nenhuma API de fonte está configurada, usa modo demo
    return not (has_meta or has_google or has_rd or has_bee)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Broadcast SSE para todos os clientes conectados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def broadcast_event(event_type: str, data: dict):
    """Envia evento para todos os clientes SSE conectados."""
    message = json.dumps(data, ensure_ascii=False, default=str)
    disconnected = []
    for i, queue in enumerate(sse_clients):
        try:
            await queue.put({"event": event_type, "data": message})
        except Exception:
            disconnected.append(i)
    # Remove clientes desconectados
    for i in reversed(disconnected):
        sse_clients.pop(i)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Lógica de Monitoramento
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_lead_in_cv(lead: TrackedLead, cv_leads_cache: list) -> Optional[dict]:
    """Tenta encontrar o lead na lista de leads do CV."""
    for cv in cv_leads_cache:
        # Match por email
        if lead.email_clean and cv.email_clean and lead.email_clean == cv.email_clean:
            return {
                "cv_id": cv.cv_id,
                "origem_cv": cv.origem_cv,
                "midia_cv": cv.midia_cv,
                "created_at": cv.created_at.isoformat(),
            }
        # Match por telefone
        if lead.phone_clean and cv.phone_clean and lead.phone_clean == cv.phone_clean:
            return {
                "cv_id": cv.cv_id,
                "origem_cv": cv.origem_cv,
                "midia_cv": cv.midia_cv,
                "created_at": cv.created_at.isoformat(),
            }
    return None


def validate_origin(lead_channel: str, cv_origin: str) -> bool:
    """Verifica se a origem registrada no CV bate com o canal real."""
    try:
        cv_normalized = normalize_channel_alias(cv_origin)
        lead_ch = OriginChannel(lead_channel)
        return cv_normalized == lead_ch
    except (ValueError, KeyError):
        return False


async def demo_generate_new_lead() -> Optional[TrackedLead]:
    """Gera um lead fictício para simulação (modo demo)."""
    global demo_lead_index

    if demo_lead_index >= len(DEMO_LEADS_POOL):
        demo_lead_index = 0  # Reinicia o pool

    lead_data = DEMO_LEADS_POOL[demo_lead_index]
    demo_lead_index += 1

    now = datetime.now(timezone.utc)
    lead_id = f"demo_{now.strftime('%H%M%S')}_{random.randint(100, 999)}"

    if lead_id in known_lead_ids:
        return None

    return TrackedLead(
        lead_id=lead_id,
        email=lead_data["email"],
        phone=lead_data["phone"],
        email_clean=clean_email(lead_data["email"]),
        phone_clean=clean_phone(lead_data["phone"]),
        origin_channel=lead_data["channel"],
        campaign_name=lead_data["campaign"],
        source_created_at=now.isoformat(),
        detected_at=now.isoformat(),
        status=STATUS_WAITING,
        attempts=0,
    )


async def demo_check_cv(lead: TrackedLead) -> Optional[dict]:
    """Simula verificação no CV com probabilidade de encontrar o lead."""
    now = datetime.now(timezone.utc)
    detected = datetime.fromisoformat(lead.detected_at)
    elapsed = (now - detected).total_seconds()

    # Leads mais antigos têm mais chance de serem encontrados
    # Chance cresce de 0% (imediato) a 85% (após 5 min)
    probability = min(0.85, elapsed / 300 * 0.85)

    if random.random() < probability:
        # Simula dados do CV
        origins = DEMO_CV_ORIGINS.get(lead.origin_channel, ["Desconhecido"])
        cv_origin = random.choice(origins)
        return {
            "cv_id": f"cv_{random.randint(10000, 99999)}",
            "origem_cv": cv_origin,
            "midia_cv": "cpc" if "ads" in lead.origin_channel.lower() else "referral",
            "created_at": now.isoformat(),
        }
    return None


async def fetch_new_source_leads() -> List[TrackedLead]:
    """Busca novos leads nas fontes de mídia."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=15)

    new_leads = []

    if is_demo_mode():
        # Modo demo: gera 1 lead fictício
        demo_lead = await demo_generate_new_lead()
        if demo_lead:
            new_leads.append(demo_lead)
        return new_leads

    # Modo real: busca das APIs configuradas
    try:
        extractors = []
        if os.getenv("META_ACCESS_TOKEN"):
            extractors.append(MetaAdsExtractor())
        if os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"):
            extractors.append(GoogleAdsExtractor())
        if os.getenv("RD_STATION_API_TOKEN"):
            extractors.append(RDStationExtractor())
        if os.getenv("BEEVIRAL_API_KEY"):
            extractors.append(BeeViralExtractor())

        for extractor in extractors:
            try:
                leads = extractor.fetch_leads(window_start, now)
                for lead in leads:
                    if lead.source_lead_id not in known_lead_ids:
                        new_leads.append(TrackedLead(
                            lead_id=lead.source_lead_id,
                            email=lead.email,
                            phone=lead.phone,
                            email_clean=lead.email_clean,
                            phone_clean=lead.phone_clean,
                            origin_channel=lead.origin_channel.value,
                            campaign_name=lead.campaign_name,
                            source_created_at=lead.created_at.isoformat(),
                            detected_at=now.isoformat(),
                            status=STATUS_WAITING,
                            attempts=0,
                        ))
            except Exception as e:
                print(f"  [Monitor] Erro ao extrair de {extractor.__class__.__name__}: {e}")
    except Exception as e:
        print(f"  [Monitor] Erro geral na extração: {e}")

    return new_leads


async def check_waiting_leads_in_cv():
    """Verifica todos os leads WAITING contra o CV CRM."""
    now = datetime.now(timezone.utc)
    waiting_leads = [t for t in tracker.values() if t.status == STATUS_WAITING]

    if not waiting_leads:
        return

    cv_leads_cache = []

    if not is_demo_mode():
        # Busca leads recentes do CV (o extractor faz fallback para simulação se a API não estiver configurada)
        try:
            window_start = now - timedelta(minutes=20)
            cv_extractor = CVCRMExtractor()
            cv_leads_cache = cv_extractor.fetch_cv_leads(window_start, now)
        except Exception as e:
            print(f"  [Monitor] Erro ao buscar CV: {e}")

    for lead in waiting_leads:
        lead.attempts += 1
        lead.last_check_at = now.isoformat()

        cv_match = None

        if is_demo_mode():
            cv_match = await demo_check_cv(lead)
        else:
            cv_match = check_lead_in_cv(lead, cv_leads_cache)

        if cv_match:
            lead.cv_data = cv_match
            lead.cv_origin = cv_match.get("origem_cv", "")
            lead.resolved_at = now.isoformat()

            # Verifica se a origem bate
            origin_ok = validate_origin(lead.origin_channel, lead.cv_origin)
            lead.status = STATUS_FOUND if origin_ok else STATUS_MISMATCH

            print(f"  [Monitor] Lead {lead.lead_id} → {lead.status} (CV origin: {lead.cv_origin})")
            await broadcast_event("lead_update", lead.to_dict())
        else:
            # Verifica timeout de 10 minutos
            detected = datetime.fromisoformat(lead.detected_at)
            elapsed = (now - detected).total_seconds()

            if elapsed >= MAX_WAIT_SECONDS:
                lead.status = STATUS_LOST
                lead.resolved_at = now.isoformat()
                print(f"  [Monitor] Lead {lead.lead_id} → LOST (timeout após {int(elapsed)}s)")
                await broadcast_event("lead_update", lead.to_dict())
            else:
                # Ainda aguardando — notifica progresso
                await broadcast_event("lead_update", lead.to_dict())


async def monitor_loop():
    """Loop principal do monitor — roda indefinidamente em background."""
    print("\n" + "=" * 70)
    print("🔴 MONITOR AO VIVO INICIADO")
    demo = is_demo_mode()
    mode_label = "DEMO (dados simulados)" if demo else "PRODUÇÃO (APIs reais)"
    print(f"   Modo: {mode_label}")
    print(f"   Polling: a cada {POLL_INTERVAL_SECONDS}s | Timeout: {MAX_WAIT_SECONDS // 60} min")
    print("=" * 70 + "\n")

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%H:%M:%S")

        # 1. Buscar novos leads das fontes
        new_leads = await fetch_new_source_leads()

        for lead in new_leads:
            known_lead_ids.add(lead.lead_id)
            tracker[lead.lead_id] = lead
            print(f"  [{now_str}] 🆕 Novo lead detectado: {lead.email or lead.phone} ({lead.origin_channel})")
            await broadcast_event("lead_new", lead.to_dict())

        # 2. Verificar leads WAITING no CV
        await check_waiting_leads_in_cv()

        # 3. Broadcast de stats
        stats = get_stats()
        await broadcast_event("stats", stats)

        waiting_count = stats["waiting"]
        found_count = stats["found"]
        lost_count = stats["lost"]
        mismatch_count = stats["mismatch"]

        if new_leads or waiting_count > 0:
            print(f"  [{now_str}] Ciclo #{cycle}: "
                  f"⏳{waiting_count} aguardando · ✅{found_count} encontrados · "
                  f"❌{lost_count} perdidos · ⚠️{mismatch_count} mismatch")

        # Esperar até próximo ciclo
        interval = DEMO_NEW_LEAD_INTERVAL if demo else POLL_INTERVAL_SECONDS
        await asyncio.sleep(interval)


def get_stats() -> dict:
    """Retorna estatísticas atuais do tracker."""
    all_leads = list(tracker.values())
    return {
        "total": len(all_leads),
        "waiting": sum(1 for t in all_leads if t.status == STATUS_WAITING),
        "found": sum(1 for t in all_leads if t.status == STATUS_FOUND),
        "lost": sum(1 for t in all_leads if t.status == STATUS_LOST),
        "mismatch": sum(1 for t in all_leads if t.status == STATUS_MISMATCH),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FastAPI App
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicia o monitor em background quando o servidor sobe."""
    global monitor_task
    monitor_task = asyncio.create_task(monitor_loop())
    yield
    # Cleanup ao desligar
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Lead Monitor — Verificação ao Vivo no CV CRM",
    description="Monitor em tempo real que detecta leads novos e verifica se chegaram no Construtor de Vendas.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/monitor/status")
async def get_monitor_status():
    """Retorna o estado atual de todos os leads monitorados."""
    all_leads = [t.to_dict() for t in tracker.values()]
    # Ordena por detected_at descendente (mais recentes primeiro)
    all_leads.sort(key=lambda x: x["detected_at"], reverse=True)
    return {
        "mode": "demo" if is_demo_mode() else "production",
        "stats": get_stats(),
        "leads": all_leads,
        "config": {
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "max_wait_seconds": MAX_WAIT_SECONDS,
        },
    }


@app.get("/api/monitor/stream")
async def stream_events(request: Request):
    """SSE endpoint — envia atualizações em tempo real para o dashboard."""
    queue: asyncio.Queue = asyncio.Queue()
    sse_clients.append(queue)

    async def event_generator():
        try:
            # Envia estado inicial
            all_leads = [t.to_dict() for t in tracker.values()]
            all_leads.sort(key=lambda x: x["detected_at"], reverse=True)
            initial = json.dumps({
                "mode": "demo" if is_demo_mode() else "production",
                "stats": get_stats(),
                "leads": all_leads,
            }, ensure_ascii=False, default=str)
            yield {"event": "initial", "data": initial}

            # Fica escutando por novos eventos
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield event
                except asyncio.TimeoutError:
                    # Heartbeat para manter conexão viva
                    yield {"event": "heartbeat", "data": "ping"}
        except asyncio.CancelledError:
            pass
        finally:
            if queue in sse_clients:
                sse_clients.remove(queue)

    return EventSourceResponse(event_generator())


@app.get("/api/monitor/reset")
async def reset_monitor():
    """Limpa o tracker para recomeçar o monitoramento."""
    tracker.clear()
    known_lead_ids.clear()
    await broadcast_event("reset", {})
    return {"message": "Monitor resetado com sucesso."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("lead_monitor:app", host="0.0.0.0", port=8765, reload=True)
