"""
CLI Entrypoint para execução da Reconciliação Sob Demanda.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# Configura codificação UTF-8 para stdout no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Adiciona o diretório raiz ao sys.path para garantir resolução dos módulos do pacote engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Carrega variáveis de ambiente de um arquivo .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from engine.extractors import (
    MetaAdsExtractor,
    GoogleAdsExtractor,
    RDStationExtractor,
    BeeViralExtractor,
    SheetsBIExtractor,
    CVCRMExtractor,
)
from engine.reconciler import LeadReconciler
from engine.exporter import ReportExporter


def main():
    parser = argparse.ArgumentParser(description="Engine de Monitoramento e Reconciliação de Leads por Origem vs CV CRM")
    parser.add_argument("--start-date", type=str, help="Data inicial ISO (ex: 2026-07-01)")
    parser.add_argument("--end-date", type=str, help="Data final ISO (ex: 2026-07-27)")
    parser.add_argument("--output-dir", type=str, default="output", help="Diretório de exportação dos relatórios")

    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    start_dt = datetime.fromisoformat(args.start_date) if args.start_date else now - timedelta(days=7)
    end_dt = datetime.fromisoformat(args.end_date) if args.end_date else now

    print("========================================================================")
    print("🚀 INICIANDO ANÁLISE SOB DEMANDA DE RECONCILIAÇÃO DE LEADS")
    print(f"📅 Período: {start_dt.strftime('%Y-%m-%d')} até {end_dt.strftime('%Y-%m-%d')}")
    print("========================================================================")

    # 1. Extração das fontes de dados
    print("\n[1/4] Extraindo leads de todas as origens...")
    meta_leads = MetaAdsExtractor().fetch_leads(start_dt, end_dt)
    gads_leads = GoogleAdsExtractor().fetch_leads(start_dt, end_dt)
    rd_leads = RDStationExtractor().fetch_leads(start_dt, end_dt)
    bee_leads = BeeViralExtractor().fetch_leads(start_dt, end_dt)
    sheets_leads = SheetsBIExtractor().fetch_leads(start_dt, end_dt)

    all_source_leads = meta_leads + gads_leads + rd_leads + bee_leads + sheets_leads
    print(f"  -> Total de leads capturados nas origens: {len(all_source_leads)}")
    print(f"     - Meta Ads: {len(meta_leads)}")
    print(f"     - Google Ads: {len(gads_leads)}")
    print(f"     - RD Station: {len(rd_leads)}")
    print(f"     - BeeViral: {len(bee_leads)}")
    print(f"     - Planilhas BI: {len(sheets_leads)}")

    # 2. Extração do CRM Construtor de Vendas (CV)
    print("\n[2/4] Extraindo leads do CRM Construtor de Vendas (CV)...")
    cv_leads = CVCRMExtractor().fetch_cv_leads(start_dt, end_dt)
    print(f"  -> Total de leads encontrados no CV: {len(cv_leads)}")

    # 3. Processamento de Reconciliação
    print("\n[3/4] Executando Algoritmo Híbrido de Matching e Detecção de Divergências...")
    reconciler = LeadReconciler(all_source_leads, cv_leads)
    report = reconciler.reconcile(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))

    # 4. Exportação dos Relatórios
    print("\n[4/4] Gerando relatórios e estatísticas...")
    exporter = ReportExporter(output_dir=args.output_dir)
    json_path = exporter.export_json(report)
    csv_path = exporter.export_divergences_csv(report)

    print("\n========================================================================")
    print(f"📊 RESUMO DA RECONCILIAÇÃO (Execução ID: {report.execution_id})")
    print(f"  • Saúde Geral: {report.overall_health.value}")
    print(f"  • Taxa de Aderência Global: {report.overall_adherence_rate}%")
    print(f"  • Leads Reconciliados (MATCH_OK): {report.total_reconciled_ok}")
    print(f"  • Leads Perdidos (MISSING_IN_CV): {report.total_missing_in_cv}")
    print(f"  • Origem Incorreta (ORIGIN_MISMATCH): {report.total_origin_mismatch}")
    print("========================================================================")
    print(f"📁 Arquivo JSON: {json_path}")
    print(f"📁 Arquivo CSV: {csv_path}")
    print("========================================================================\n")


if __name__ == "__main__":
    main()
