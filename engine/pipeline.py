"""
Pipeline de reconciliação reutilizável (CLI, GitHub Actions e API na Vercel).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from engine.config import GlobalReconciliationReport
from engine.extractors import (
    MetaAdsExtractor,
    GoogleAdsExtractor,
    RDStationExtractor,
    BeeViralExtractor,
    SheetsBIExtractor,
    CVCRMExtractor,
)
from engine.extractors.base import STATUS_LIVE, STATUS_SIMULATED
from engine.reconciler import LeadReconciler


class CVUnavailableError(RuntimeError):
    """O CRM CV não pôde ser consultado; reconciliar assim marcaria todos os leads como perdidos."""


@dataclass
class PipelineResult:
    report: GlobalReconciliationReport
    leads_by_source: Dict[str, int] = field(default_factory=dict)
    total_cv_leads: int = 0
    sources: List[dict] = field(default_factory=list)


def run_reconciliation(start_dt: datetime, end_dt: datetime) -> PipelineResult:
    # 1. Extração das fontes de dados
    extractors = [
        MetaAdsExtractor(),
        GoogleAdsExtractor(),
        RDStationExtractor(),
        BeeViralExtractor(),
        SheetsBIExtractor(),
    ]
    all_source_leads = []
    leads_by_source: Dict[str, int] = {}
    for extractor in extractors:
        leads = extractor.fetch_leads(start_dt, end_dt)
        leads_by_source[extractor.source_name] = len(leads)
        all_source_leads.extend(leads)

    # 2. Extração do CRM Construtor de Vendas (CV)
    cv_extractor = CVCRMExtractor()
    cv_leads = cv_extractor.fetch_cv_leads(start_dt, end_dt)
    if cv_extractor.status not in (STATUS_LIVE, STATUS_SIMULATED):
        raise CVUnavailableError(
            f"CRM CV indisponível ({cv_extractor.status}): {cv_extractor.detail}. "
            "Sem a lista do CV todos os leads apareceriam como perdidos."
        )

    # 3. Processamento de Reconciliação
    report = LeadReconciler(all_source_leads, cv_leads).reconcile(
        start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
    )

    return PipelineResult(
        report=report,
        leads_by_source=leads_by_source,
        total_cv_leads=len(cv_leads),
        sources=[e.status_dict() for e in extractors] + [cv_extractor.status_dict()],
    )
