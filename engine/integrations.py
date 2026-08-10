"""
Registro das integrações: nome legível, links diretos para obter credenciais e o
estado de cada fonte em uma execução.

Regra do sistema: dado simulado nunca se passa por real. Uma integração com
problema aparece como erro, com o link para resolver — só vira simulação se
ALLOW_SIMULATED_DATA estiver explicitamente ligado (modo demonstração).
"""

import os
from datetime import datetime, timezone
from typing import List, Optional

from engine.config import HelpLink, SourceStatus


def simulated_data_allowed() -> bool:
    """Modo demonstração: só com ALLOW_SIMULATED_DATA=true no ambiente."""
    return os.getenv("ALLOW_SIMULATED_DATA", "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _cv_links() -> List[dict]:
    base = (os.getenv("CV_CRM_URL") or "").rstrip("/")
    links = []
    if base:
        links.append({"label": "Painel do CV (tokens de API e permissões)", "url": f"{base}/gestor"})
    links.append({"label": "Documentação da API do CV", "url": "https://desenvolvedor.cvcrm.com.br/reference"})
    return links


SOURCE_REGISTRY = {
    "meta_ads": {
        "label": "Meta Ads (Facebook / Instagram)",
        "links": lambda: [
            {"label": "Gerar token permanente (Usuário do sistema)", "url": "https://business.facebook.com/settings/system-users"},
            {"label": "Graph API Explorer", "url": "https://developers.facebook.com/tools/explorer/"},
            {"label": "Validar token atual", "url": "https://developers.facebook.com/tools/debug/accesstoken/"},
            {"label": "Guia: ler leads do Lead Ads", "url": "https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving"},
        ],
    },
    "google_ads": {
        "label": "Google Ads",
        "links": lambda: [
            {"label": "Developer token (Central de API)", "url": "https://ads.google.com/aw/apicenter"},
            {"label": "Criar Client ID OAuth", "url": "https://console.cloud.google.com/apis/credentials"},
            {"label": "Gerar refresh token (OAuth Playground)", "url": "https://developers.google.com/oauthplayground/"},
            {"label": "Guia da primeira chamada", "url": "https://developers.google.com/google-ads/api/docs/first-call/overview"},
        ],
    },
    "ga4": {
        "label": "Google Analytics (GA4)",
        "links": lambda: [
            {"label": "ID da propriedade (Administrador → Detalhes da propriedade)", "url": "https://analytics.google.com/analytics/web/#/admin"},
            {"label": "Dar acesso de leitura à conta de serviço", "url": "https://analytics.google.com/analytics/web/#/admin/property/access-management"},
            {"label": "Criar conta de serviço e baixar a chave", "url": "https://console.cloud.google.com/iam-admin/serviceaccounts"},
            {"label": "Documentação da Data API", "url": "https://developers.google.com/analytics/devguides/reporting/data/v1"},
        ],
    },
    "rd_station": {
        "label": "RD Station Marketing",
        "links": lambda: [
            {"label": "Criar app e obter client_id / client_secret", "url": "https://appstore.rdstation.com/pt-BR/publisher"},
            {"label": "Documentação da API RD Station Marketing", "url": "https://developers.rdstation.com/reference/introducao-rdsm"},
        ],
    },
    "beeviral": {
        "label": "BeeViral (Indicações)",
        "links": lambda: [
            {"label": "Painel BeeViral", "url": "https://account.beeviral.app/"},
        ],
    },
    "sheets_bi": {
        "label": "Planilhas / Eventos (BI interno)",
        "links": lambda: [],
    },
    "cv_crm": {
        "label": "CV CRM — Leads",
        "links": _cv_links,
    },
    "cv_empreendimentos": {
        "label": "CV CRM — Empreendimentos",
        "links": _cv_links,
    },
    "vendas": {
        "label": "Base de Vendas (reservas do CV ou planilha)",
        "links": _cv_links,
    },
    "firebase": {
        "label": "Firebase (histórico na nuvem)",
        "links": lambda: [
            {"label": "Console do Firebase (Contas de serviço)", "url": "https://console.firebase.google.com/"},
            {"label": "Como gerar a chave do Admin SDK", "url": "https://firebase.google.com/docs/admin/setup#initialize_the_sdk_in_non-google_environments"},
        ],
    },
}


def build_status(
    source: str,
    mode: str,
    records: int = 0,
    message: str = "",
    action: Optional[str] = None,
) -> SourceStatus:
    info = SOURCE_REGISTRY.get(source, {"label": source, "links": lambda: []})
    return SourceStatus(
        source=source,
        label=info["label"],
        mode=mode,
        records=records,
        message=message,
        action=action,
        help_links=[HelpLink(**link) for link in info["links"]()],
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
