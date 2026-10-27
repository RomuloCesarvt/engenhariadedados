"""
Configurações e Schemas Pydantic para a Engine de Reconciliação de Leads.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class OriginChannel(str, Enum):
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    RD_STATION = "rd_station"
    BEEVIRAL = "beeviral"
    SHEETS_BI = "sheets_bi"
    CV_CRM = "cv_crm"


class DivergenceType(str, Enum):
    MATCH_OK = "MATCH_OK"
    MISSING_IN_CV = "MISSING_IN_CV"
    ORIGIN_MISMATCH = "ORIGIN_MISMATCH"
    VOLUME_GAP = "VOLUME_GAP"
    LATENCY_DELAY = "LATENCY_DELAY"
    DUPLICATE_SOURCE = "DUPLICATE_SOURCE"
    PENDING_SYNC = "PENDING_SYNC"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"      # >= 98%
    WARNING = "WARNING"      # 93% - 97.9%
    CRITICAL = "CRITICAL"    # < 93%


class LeadRecord(BaseModel):
    source_lead_id: str
    email: Optional[str] = None
    email_clean: Optional[str] = None
    phone: Optional[str] = None
    phone_clean: Optional[str] = None
    origin_channel: OriginChannel
    campaign_name: Optional[str] = None
    empreendimento: Optional[str] = None  # produto/obra a que o lead se refere
    created_at: datetime
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    integration_id: Optional[str] = None  # gclid, fbclid, bee_id, rd_id
    raw_payload: Optional[Dict[str, Any]] = None


class CVLeadRecord(BaseModel):
    cv_id: str
    email: Optional[str] = None
    email_clean: Optional[str] = None
    phone: Optional[str] = None
    phone_clean: Optional[str] = None
    origem_cv: str
    midia_cv: Optional[str] = None
    empreendimento: Optional[str] = None
    created_at: datetime
    id_externo: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class DivergenceRecord(BaseModel):
    id: str
    source_lead_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    origin_channel: OriginChannel
    divergence_type: DivergenceType
    severity: str  # HIGH, MEDIUM, LOW
    details: str
    source_created_at: str
    cv_created_at: Optional[str] = None
    origem_no_cv: Optional[str] = None
    integration_id: Optional[str] = None


class ChannelSummary(BaseModel):
    channel: OriginChannel
    total_source_leads: int
    total_cv_leads: int
    match_ok_count: int
    missing_in_cv_count: int
    origin_mismatch_count: int
    latency_delay_count: int
    pending_sync_count: int
    adherence_rate: float
    health_status: HealthStatus


class HelpLink(BaseModel):
    """Link direto para a página onde se obtém ou corrige uma credencial."""

    label: str
    url: str


class SourceStatus(BaseModel):
    """
    Como uma fonte entregou os dados nesta execução. Existe para que o relatório
    nunca apresente simulação ou falha de integração como se fosse dado real.
    """

    source: str   # meta_ads, google_ads, rd_station, beeviral, sheets_bi, cv_crm, cv_empreendimentos, vendas, firebase
    label: str
    mode: str     # real | simulado | erro | nao_configurado
    records: int = 0
    message: str = ""
    action: Optional[str] = None          # o que precisa ser feito para a fonte funcionar
    help_links: List[HelpLink] = []
    checked_at: str


class GlobalReconciliationReport(BaseModel):
    execution_id: str
    timestamp: str
    start_date: str
    end_date: str
    total_source_leads: int
    total_cv_leads: int
    total_reconciled_ok: int
    total_missing_in_cv: int
    total_origin_mismatch: int
    overall_adherence_rate: float
    overall_health: HealthStatus
    channels: List[ChannelSummary]
    divergences: List[DivergenceRecord]
    sales_audit: Optional["SalesAuditReport"] = None
    # Estado de cada integração nesta execução
    sources: List[SourceStatus] = []
    # True quando alguma fonte entregou dados simulados (modo demonstração)
    simulated_data: bool = False
    # False quando os leads do CV não puderam ser lidos: sem eles não há como
    # afirmar que um lead "faltou" no CRM
    cv_available: bool = True


# ==============================================================================
# AUDITORIA DE VENDAS — Cruzamento da base de Vendas x base de Leads
# ==============================================================================


class SaleVerdict(str, Enum):
    """Veredito da auditoria de cada venda contra a base de leads."""

    ONLINE_CONFIRMED = "ONLINE_CONFIRMED"        # Declarada online e comprovada na base de leads
    ONLINE_UNPROVEN = "ONLINE_UNPROVEN"          # Declarada online, sem lead digital correspondente (infla o online)
    ONLINE_NOT_DECLARED = "ONLINE_NOT_DECLARED"  # Declarada offline, mas o comprador existe na base de leads digital
    OFFLINE_CONFIRMED = "OFFLINE_CONFIRMED"      # Declarada offline e sem lead digital — coerente
    CHANNEL_MISMATCH = "CHANNEL_MISMATCH"        # Online confirmado, porém em canal diferente do declarado
    LEAD_AFTER_SALE = "LEAD_AFTER_SALE"          # Lead encontrado, porém criado depois da venda (atribuição inválida)


class MatchKey(str, Enum):
    """Chave que produziu o match entre a venda e a base de leads."""

    DOCUMENT = "document"              # CPF/CNPJ — chave mais forte
    INTEGRATION_ID = "integration_id"  # gclid / fbclid / bee_id / rd_id
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"                      # nome normalizado — confiança baixa, usado por último
    NONE = "none"


class SaleRecord(BaseModel):
    """Uma venda/reserva conforme reportada pela fonte (CV CRM, planilha de vendas, BI)."""

    sale_id: str
    client_name: Optional[str] = None
    document: Optional[str] = None          # CPF/CNPJ bruto
    document_clean: Optional[str] = None    # apenas dígitos
    email: Optional[str] = None
    email_clean: Optional[str] = None
    phone: Optional[str] = None
    phone_clean: Optional[str] = None
    sale_date: datetime
    value: Optional[float] = None
    declared_channel_raw: str = "desconhecido"   # o que a fonte diz (ex.: "Facebook Ads", "Estande")
    declared_channel: Optional[OriginChannel] = None
    declared_is_online: bool = False
    empreendimento: Optional[str] = None
    unidade: Optional[str] = None
    integration_id: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class SaleAuditRecord(BaseModel):
    """Resultado da auditoria de uma venda individual."""

    sale_id: str
    client_name: Optional[str] = None
    document: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    sale_date: str
    value: Optional[float] = None
    empreendimento: Optional[str] = None
    declared_channel_raw: str
    declared_is_online: bool
    verified_is_online: bool
    verdict: SaleVerdict
    severity: str  # HIGH, MEDIUM, LOW, NONE
    matched_by: MatchKey
    matched_lead_id: Optional[str] = None
    matched_channel: Optional[OriginChannel] = None
    lead_created_at: Optional[str] = None
    days_lead_to_sale: Optional[int] = None
    lead_empreendimento: Optional[str] = None
    # True  = lead do mesmo empreendimento da venda
    # False = lead veio de outro empreendimento (cliente migrou de produto)
    # None  = sem lead, ou empreendimento não identificado em uma das pontas
    empreendimento_match: Optional[bool] = None
    details: str


class SalesChannelAudit(BaseModel):
    """Declarado x comprovado por canal."""

    channel: OriginChannel
    declared_sales: int
    verified_sales: int
    delta: int


class EmpreendimentoAudit(BaseModel):
    """Conferência fechada de um único empreendimento: seus leads, suas vendas, suas divergências."""

    empreendimento: str

    # Volume de leads atribuídos a este empreendimento
    total_leads: int
    leads_by_channel: Dict[str, int]
    total_cv_leads: int

    # Volume de vendas
    total_sales: int
    total_value: float

    # Online declarado x comprovado, dentro deste empreendimento
    declared_online: int
    verified_online: int
    online_delta: int

    online_confirmed: int
    online_unproven: int
    online_not_declared: int
    offline_confirmed: int
    channel_mismatch: int

    # Vendas cujo comprador tinha lead de OUTRO empreendimento
    cross_empreendimento_sales: int
    # Vendas sem nenhum lead na base
    sales_without_lead: int

    conversion_rate: float       # vendas / leads deste empreendimento (%)
    attribution_accuracy: float
    health_status: HealthStatus
    is_consistent: bool
    inconsistencies: List[str]   # diagnósticos legíveis, prontos para exibição

    sales: List[SaleAuditRecord]


class SalesAuditReport(BaseModel):
    """Relatório consolidado do cruzamento Vendas x Leads."""

    start_date: str
    end_date: str
    attribution_window_days: int

    total_sales: int
    declared_online: int
    declared_offline: int
    verified_online: int
    verified_offline: int

    online_confirmed: int
    online_unproven: int
    online_not_declared: int
    offline_confirmed: int
    channel_mismatch: int
    lead_after_sale: int
    duplicate_buyers: int

    online_delta: int           # verified_online - declared_online
    attribution_accuracy: float # % de vendas cujo online/offline declarado bate com o comprovado
    health_status: HealthStatus

    matched_by_document: int
    matched_by_integration_id: int
    matched_by_email: int
    matched_by_phone: int
    matched_by_name: int
    unmatched: int
    low_confidence_matches: int  # matches obtidos apenas por nome

    # Conferência fechada por empreendimento — a visão que o comercial usa no dia a dia
    empreendimentos: List[EmpreendimentoAudit]
    # Leads cujo empreendimento não pôde ser identificado (impedem a conferência por produto)
    leads_sem_empreendimento: int
    # Vendas sem empreendimento informado na base de origem
    vendas_sem_empreendimento: int
    # Filtro aplicado nesta execução, quando houver
    empreendimento_filtro: Optional[str] = None
    # False quando nenhuma base de vendas pôde ser lida nesta execução
    sales_base_available: bool = True

    channels: List[SalesChannelAudit]
    sales: List[SaleAuditRecord]


# Resolve a referência adiantada de SalesAuditReport em GlobalReconciliationReport
GlobalReconciliationReport.model_rebuild()
