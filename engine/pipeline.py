"""
Pipeline único da análise: vendas → leads → CV → reconciliação → auditoria → exportação.

A CLI (main.py) e a API (api.py) usam exatamente este caminho, então o que roda no
terminal é o mesmo que roda pelo botão do dashboard.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple

from engine.config import GlobalReconciliationReport, SourceStatus
from engine.exporter import ReportExporter
from engine.extractors import (
    BeeViralExtractor,
    CVCRMExtractor,
    GoogleAdsExtractor,
    MetaAdsExtractor,
    RDStationExtractor,
    SheetsBIExtractor,
)
from engine.extractors.base import in_period, to_naive_utc
from engine.extractors.sales import SalesExtractor
from engine.integrations import build_status
from engine.reconciler import LeadReconciler
from engine.sales_auditor import DEFAULT_ATTRIBUTION_WINDOW_DAYS, SalesAuditor

# Um lead pode entrar no CV um pouco depois do fim do período analisado
CV_GRACE = timedelta(days=1)

# Histórico do CV consultado no cruzamento: a pessoa indicada hoje pode ser lead há meses
CV_LOOKBACK_DAYS = int(os.getenv("CV_LOOKBACK_DAYS", "365"))


@dataclass
class PipelineResult:
    report: GlobalReconciliationReport
    json_path: Optional[str] = None
    csv_path: Optional[str] = None
    sales_csv_path: Optional[str] = None
    firebase_saved: bool = False


def resolve_period(start: Optional[str], end: Optional[str]) -> Tuple[datetime, datetime]:
    """Período em UTC sem fuso. Data final sem horário vale pelo dia inteiro."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_dt = to_naive_utc(datetime.fromisoformat(start)) if start else now - timedelta(days=7)
    end_dt = to_naive_utc(datetime.fromisoformat(end)) if end else now
    if end and len(end.strip()) <= 10:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    return start_dt, end_dt


def _safe_fetch(extractor, fetch: Callable[[], list], log: Callable[[str], None]) -> list:
    """Um extrator com defeito nunca derruba a análise inteira."""
    try:
        registros = fetch()
    except Exception as e:  # noqa: BLE001 — qualquer falha vira estado de erro visível
        registros = []
        extractor._set_status("erro", 0, f"Falha inesperada no extrator: {e}")
    if extractor.status is None:
        extractor._set_status("erro", len(registros), "O extrator não informou o estado da consulta.")
    return registros


def _firebase_status(saved: bool) -> SourceStatus:
    if not os.getenv("FIREBASE_CREDENTIALS_PATH"):
        return build_status(
            "firebase",
            "nao_configurado",
            message="Histórico salvo apenas no disco do servidor (opcional).",
            action="Para guardar o histórico na nuvem, gere a chave do Admin SDK e aponte FIREBASE_CREDENTIALS_PATH para o arquivo JSON.",
        )
    if saved:
        return build_status("firebase", "real", 1, "Relatório salvo no Firestore.")
    return build_status(
        "firebase",
        "erro",
        message="FIREBASE_CREDENTIALS_PATH configurado, mas o envio falhou.",
        action="Confira se o arquivo JSON existe e se o pacote firebase-admin está instalado.",
    )


def run_pipeline(
    start_dt: datetime,
    end_dt: datetime,
    sales_file: Optional[str] = None,
    attribution_window_days: int = DEFAULT_ATTRIBUTION_WINDOW_DAYS,
    empreendimento: Optional[str] = None,
    skip_sales_audit: bool = False,
    output_dir: str = "output",
    export: bool = True,
    log: Callable[[str], None] = print,
    cv_lookback_days: int = CV_LOOKBACK_DAYS,
) -> PipelineResult:
    start_str, end_str = start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
    sources: List[SourceStatus] = []

    # 1. Vendas primeiro: elas definem até quando é preciso olhar leads para trás.
    sales = []
    if not skip_sales_audit:
        log("\n[1/5] Carregando a base de VENDAS...")
        sales_extractor = SalesExtractor(file_path=sales_file)
        sales = _safe_fetch(sales_extractor, lambda: sales_extractor.fetch_sales(start_dt, end_dt), log)
        sources.append(sales_extractor.status)
        log(f"  -> {len(sales)} venda(s). {sales_extractor.status.message}")

    # Uma venda do período pode vir de um lead captado meses antes; buscar leads só
    # dentro do período transformaria essas vendas em falsas "vendas sem lead".
    lead_start, lead_end = start_dt, end_dt
    if sales:
        datas = [to_naive_utc(s.sale_date) for s in sales]
        lead_start = min(start_dt, min(datas) - timedelta(days=attribution_window_days))
        lead_end = max(end_dt, max(datas) + timedelta(days=1))
        if lead_start < start_dt:
            log(f"  -> Leads serão buscados desde {lead_start:%d/%m/%Y} para cobrir a janela de atribuição.")

    # 2. Leads das origens
    log("\n[2/5] Extraindo leads das origens...")
    all_source_leads = []
    for extractor in (MetaAdsExtractor(), GoogleAdsExtractor(), RDStationExtractor(), BeeViralExtractor(), SheetsBIExtractor()):
        leads = _safe_fetch(extractor, lambda ex=extractor: ex.fetch_leads(lead_start, lead_end), log)
        sources.append(extractor.status)
        all_source_leads.extend(leads)
        log(f"     - {extractor.status.label}: {len(leads)} [{extractor.status.mode}] {extractor.status.message}")

    # 3. CV CRM — catálogo oficial de empreendimentos e leads
    log("\n[3/5] Consultando o CRM Construtor de Vendas (CV)...")
    cv = CVCRMExtractor()
    catalogo_oficial = cv.fetch_empreendimentos()
    sources.append(cv.empreendimentos_status)
    log(f"     - {cv.empreendimentos_status.label}: [{cv.empreendimentos_status.mode}] {cv.empreendimentos_status.message}")
    cv_start = min(lead_start, start_dt - timedelta(days=cv_lookback_days))
    cv_leads_all = _safe_fetch(cv, lambda: cv.fetch_cv_leads(cv_start, lead_end + CV_GRACE), log)
    sources.append(cv.status)
    log(f"     - {cv.status.label}: {len(cv_leads_all)} [{cv.status.mode}] {cv.status.message}")
    cv_available = cv.status.mode in ("real", "simulado")

    # 4. Reconciliação (só o período) e auditoria de vendas (com a janela completa)
    log("\n[4/5] Reconciliando leads x CV e auditando vendas...")
    period_leads = [lead for lead in all_source_leads if in_period(lead.created_at, start_dt, end_dt)]
    period_cv = [lead for lead in cv_leads_all if in_period(lead.created_at, start_dt, end_dt + CV_GRACE)]
    report = LeadReconciler(period_leads, cv_leads_all, cv_period_leads=period_cv).reconcile(
        start_str, end_str, cv_available=cv_available
    )

    if not skip_sales_audit:
        auditor = SalesAuditor(
            sales=sales,
            source_leads=all_source_leads,
            cv_leads=cv_leads_all,
            attribution_window_days=attribution_window_days,
            empreendimento=empreendimento,
            catalogo_oficial=catalogo_oficial,
            sales_available=sales_extractor.status.mode in ("real", "simulado"),
        )
        report.sales_audit = auditor.audit(start_str, end_str)

    # 5. Persistência
    result = PipelineResult(report=report)
    if export:
        log("\n[5/5] Gerando relatórios...")
        exporter = ReportExporter(output_dir=output_dir)
        report.sources = sources
        result.firebase_saved = exporter.save_to_firebase(report)
        sources.append(_firebase_status(result.firebase_saved))

    report.sources = sources
    report.simulated_data = any(s.mode == "simulado" for s in sources)

    if export:
        result.json_path = exporter.export_json(report)
        result.csv_path = exporter.export_divergences_csv(report)
        result.sales_csv_path = exporter.export_sales_audit_csv(report)

    return result


def check_integrations(log: Callable[[str], None] = lambda *_: None) -> List[SourceStatus]:
    """Teste rápido e ao vivo de todas as integrações (últimas 48h, sem exportar nada)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Só testa a conexão: sem o histórico de 12 meses do CV, que é o que demora
    result = run_pipeline(now - timedelta(days=2), now, export=False, log=log, cv_lookback_days=0)
    return result.report.sources
