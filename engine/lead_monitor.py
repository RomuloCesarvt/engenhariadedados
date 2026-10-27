"""
Monitor ao Vivo de Leads — Verificação Automática no CV CRM.

Detecta leads novos nas fontes de mídia (Meta Ads, Google Ads, RD Station, BeeViral)
e verifica se cada lead chegou no CRM Construtor de Vendas (CV) dentro de ~10 minutos.

Este módulo não guarda estado em memória: cada chamada de `run_cycle` recebe o
estado (um dict serializável em JSON), avança um ciclo de monitoramento e devolve o
estado atualizado. Quem persiste esse estado (Upstash Redis na Vercel) é o `app.py`,
o que permite rodar em funções serverless, onde nenhum processo fica vivo entre as
requisições.
"""

import os
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from engine.extractors import (
    MetaAdsExtractor,
    GoogleAdsExtractor,
    RDStationExtractor,
    BeeViralExtractor,
    CVCRMExtractor,
)
from engine.extractors.base import (
    STATUS_LIVE,
    STATUS_NOT_CONFIGURED,
    STATUS_SIMULATED,
    simulation_allowed,
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

# Intervalo mínimo entre ciclos (evita estourar rate limit das APIs quando
# vários dashboards ou crons chamam o monitor ao mesmo tempo)
POLL_INTERVAL_SECONDS = 60

# Janela inicial de busca de leads novos, e limite do quanto voltar no tempo
# depois de um período sem ciclos
INITIAL_LOOKBACK = timedelta(minutes=15)
MAX_LOOKBACK = timedelta(hours=24)

# Retenção do histórico no estado persistido
RETENTION = timedelta(hours=48)
MAX_TRACKED_LEADS = 300


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


# Variável de ambiente que habilita cada fonte de leads no monitor
SOURCE_ENV_VARS = {
    "meta_ads": "META_ACCESS_TOKEN",
    "google_ads": "GOOGLE_ADS_DEVELOPER_TOKEN",
    "rd_station": "RD_STATION_API_TOKEN",
    "beeviral": "BEEVIRAL_API_KEY",
}

SOURCE_EXTRACTORS = {
    "meta_ads": MetaAdsExtractor,
    "google_ads": GoogleAdsExtractor,
    "rd_station": RDStationExtractor,
    "beeviral": BeeViralExtractor,
}


def configured_sources() -> List[str]:
    return [name for name, var in SOURCE_ENV_VARS.items() if os.getenv(var)]


def is_demo_mode() -> bool:
    """Modo demo: nenhuma API de fonte configurada e simulação permitida (só local)."""
    return not configured_sources() and simulation_allowed()


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


def demo_generate_new_lead(index: int, now: datetime) -> TrackedLead:
    """Gera um lead fictício para simulação (modo demo)."""
    lead_data = DEMO_LEADS_POOL[index % len(DEMO_LEADS_POOL)]
    lead_id = f"demo_{now.strftime('%H%M%S')}_{random.randint(100, 999)}"

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


def demo_check_cv(lead: TrackedLead, now: datetime) -> Optional[dict]:
    """Simula verificação no CV com probabilidade de encontrar o lead."""
    detected = datetime.fromisoformat(lead.detected_at)
    elapsed = (now - detected).total_seconds()

    # Leads mais antigos têm mais chance de serem encontrados
    # Chance cresce de 0% (imediato) a 85% (após 5 min)
    probability = min(0.85, elapsed / 300 * 0.85)

    if random.random() < probability:
        origins = DEMO_CV_ORIGINS.get(lead.origin_channel, ["Desconhecido"])
        cv_origin = random.choice(origins)
        return {
            "cv_id": f"cv_{random.randint(10000, 99999)}",
            "origem_cv": cv_origin,
            "midia_cv": "cpc" if "ads" in lead.origin_channel.lower() else "referral",
            "created_at": now.isoformat(),
        }
    return None


def fetch_new_source_leads(
    known_lead_ids: set, since: datetime, now: datetime
) -> Tuple[List[TrackedLead], List[dict]]:
    """Busca nas fontes de mídia configuradas os leads ainda não conhecidos."""
    new_leads: List[TrackedLead] = []
    statuses: List[dict] = []

    for name, extractor_cls in SOURCE_EXTRACTORS.items():
        if name not in configured_sources():
            statuses.append({"source": name, "status": STATUS_NOT_CONFIGURED,
                             "detail": f"{SOURCE_ENV_VARS[name]} ausente", "count": 0})
            continue

        extractor = extractor_cls()
        try:
            leads = extractor.fetch_leads(since, now)
        except Exception as e:
            print(f"  [Monitor] Erro ao extrair de {extractor_cls.__name__}: {e}")
            statuses.append({"source": name, "status": "error", "detail": str(e), "count": 0})
            continue

        statuses.append(extractor.status_dict())
        for lead in leads:
            if lead.source_lead_id in known_lead_ids:
                continue
            known_lead_ids.add(lead.source_lead_id)
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

    return new_leads, statuses


def resolve_waiting_leads(leads: Dict[str, TrackedLead], now: datetime) -> dict:
    """
    Verifica todos os leads WAITING contra o CV CRM e atualiza o status deles.
    Retorna o status da consulta ao CV.
    """
    waiting = [t for t in leads.values() if t.status == STATUS_WAITING]
    demo = is_demo_mode()
    cv_status = {"source": OriginChannel.CV_CRM.value, "status": STATUS_SIMULATED if demo else STATUS_NOT_CONFIGURED,
                 "detail": None, "count": 0}
    if not waiting:
        return cv_status

    cv_leads_cache = []
    cv_ok = True
    if not demo:
        try:
            oldest = min(datetime.fromisoformat(t.detected_at) for t in waiting)
            window_start = min(now - timedelta(minutes=20), oldest - timedelta(minutes=5))
            cv_extractor = CVCRMExtractor()
            cv_leads_cache = cv_extractor.fetch_cv_leads(window_start, now)
            cv_status = cv_extractor.status_dict()
            cv_ok = cv_extractor.status in (STATUS_LIVE, STATUS_SIMULATED)
        except Exception as e:
            print(f"  [Monitor] Erro ao buscar CV: {e}")
            cv_status = {"source": OriginChannel.CV_CRM.value, "status": "error", "detail": str(e), "count": 0}
            cv_ok = False

    for lead in waiting:
        lead.attempts += 1
        lead.last_check_at = now.isoformat()

        cv_match = demo_check_cv(lead, now) if demo else check_lead_in_cv(lead, cv_leads_cache)

        if cv_match:
            lead.cv_data = cv_match
            lead.cv_origin = cv_match.get("origem_cv", "")
            lead.resolved_at = now.isoformat()
            origin_ok = validate_origin(lead.origin_channel, lead.cv_origin)
            lead.status = STATUS_FOUND if origin_ok else STATUS_MISMATCH
            print(f"  [Monitor] Lead {lead.lead_id} → {lead.status} (CV origin: {lead.cv_origin})")
        elif cv_ok:
            elapsed = (now - datetime.fromisoformat(lead.detected_at)).total_seconds()
            if elapsed >= MAX_WAIT_SECONDS:
                lead.status = STATUS_LOST
                lead.resolved_at = now.isoformat()
                print(f"  [Monitor] Lead {lead.lead_id} → LOST (timeout após {int(elapsed)}s)")
        # Se o CV não respondeu, o lead segue WAITING: não dá para afirmar que foi perdido.

    return cv_status


def get_stats(leads) -> dict:
    """Estatísticas de uma coleção de TrackedLead ou de dicts equivalentes."""
    statuses = [l["status"] if isinstance(l, dict) else l.status for l in leads]
    return {
        "total": len(statuses),
        "waiting": statuses.count(STATUS_WAITING),
        "found": statuses.count(STATUS_FOUND),
        "lost": statuses.count(STATUS_LOST),
        "mismatch": statuses.count(STATUS_MISMATCH),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ciclo de monitoramento sobre um estado serializável
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def new_state() -> dict:
    return {
        "leads": {},
        "last_cycle_at": None,
        "last_poll_at": None,
        "demo_index": 0,
        "sources": [],
    }


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def cycle_is_due(state: dict, now: datetime) -> bool:
    last = _parse_iso(state.get("last_cycle_at"))
    return last is None or (now - last).total_seconds() >= POLL_INTERVAL_SECONDS


def run_cycle(state: dict, now: Optional[datetime] = None) -> dict:
    """Executa um ciclo completo (detectar leads novos + verificar pendentes no CV)."""
    now = now or datetime.now(timezone.utc)
    leads = {lead_id: TrackedLead(**data) for lead_id, data in state.get("leads", {}).items()}
    demo = is_demo_mode()

    # 1. Buscar novos leads das fontes
    if demo:
        index = state.get("demo_index", 0)
        new_leads = [demo_generate_new_lead(index, now)]
        state["demo_index"] = index + 1
        source_statuses = [{"source": name, "status": STATUS_SIMULATED, "detail": "modo demo", "count": 0}
                           for name in SOURCE_EXTRACTORS]
    else:
        since = _parse_iso(state.get("last_poll_at")) or (now - INITIAL_LOOKBACK)
        since = max(since - timedelta(minutes=2), now - MAX_LOOKBACK)  # 2 min de sobreposição
        new_leads, source_statuses = fetch_new_source_leads(set(leads), since, now)
        # Só avança a janela se nenhuma fonte falhou; assim as falhas são reprocessadas
        if all(s["status"] != "error" for s in source_statuses):
            state["last_poll_at"] = now.isoformat()

    for lead in new_leads:
        leads[lead.lead_id] = lead
        print(f"  [Monitor] Novo lead detectado: {lead.email or lead.phone} ({lead.origin_channel})")

    # 2. Verificar leads WAITING no CV
    cv_status = resolve_waiting_leads(leads, now)

    # 3. Poda do histórico para manter o estado pequeno
    cutoff = now - RETENTION
    kept = [l for l in leads.values()
            if l.status == STATUS_WAITING or datetime.fromisoformat(l.detected_at) >= cutoff]
    kept.sort(key=lambda l: l.detected_at, reverse=True)
    kept = kept[:MAX_TRACKED_LEADS]

    state["leads"] = {l.lead_id: l.to_dict() for l in kept}
    state["sources"] = source_statuses + [cv_status]
    state["last_cycle_at"] = now.isoformat()
    return state


def build_status_payload(state: dict) -> dict:
    """Formato consumido pelo dashboard."""
    all_leads = sorted(state.get("leads", {}).values(), key=lambda l: l["detected_at"], reverse=True)
    return {
        "mode": "demo" if is_demo_mode() else "production",
        "stats": get_stats(all_leads),
        "leads": all_leads,
        "sources": state.get("sources", []),
        "last_cycle_at": state.get("last_cycle_at"),
        "config": {
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "max_wait_seconds": MAX_WAIT_SECONDS,
        },
    }
