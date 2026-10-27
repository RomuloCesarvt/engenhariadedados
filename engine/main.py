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

from engine.pipeline import CVUnavailableError, run_reconciliation
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

    # 1-3. Extração das fontes, extração do CV e reconciliação
    print("\n[1/2] Extraindo, cruzando e reconciliando leads de todas as origens e do CRM Construtor de Vendas (CV)...")
    try:
        result = run_reconciliation(start_dt, end_dt)
    except CVUnavailableError as e:
        print(f"❌ {e}")
        sys.exit(1)

    report = result.report
    print(f"  -> Total de leads capturados nas origens: {sum(result.leads_by_source.values())}")
    labels = {
        "meta_ads": "Meta Ads",
        "google_ads": "Google Ads",
        "rd_station": "RD Station",
        "beeviral": "BeeViral",
        "sheets_bi": "Planilhas BI",
    }
    for channel, count in result.leads_by_source.items():
        print(f"     - {labels.get(channel, channel)}: {count}")
    print(f"  -> Total de leads encontrados no CV: {result.total_cv_leads}")
    for src in result.sources:
        if src["status"] != "live":
            print(f"  ⚠️  {src['source']}: {src['status']} ({src['detail']})")

    # 4. Exportação dos Relatórios
    print("\n[2/2] Gerando relatórios e estatísticas...")
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
