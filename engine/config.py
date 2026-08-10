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
