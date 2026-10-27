"""
CLI Entrypoint para execução da Reconciliação Sob Demanda.
"""

import argparse
import json
import os
import sys

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

from engine.extractors import CVCRMExtractor
from engine.pipeline import resolve_period, run_pipeline
from engine.sales_auditor import DEFAULT_ATTRIBUTION_WINDOW_DAYS

MODE_ICON = {"real": "✅", "simulado": "🧪", "erro": "❌", "nao_configurado": "⚪"}
LINHA = "========================================================================"


def main():
    parser = argparse.ArgumentParser(description="Engine de Monitoramento e Reconciliação de Leads por Origem vs CV CRM")
    parser.add_argument("--start-date", type=str, help="Data inicial ISO (ex: 2026-07-01)")
    parser.add_argument("--end-date", type=str, help="Data final ISO (ex: 2026-07-27)")
    parser.add_argument("--output-dir", type=str, default="output", help="Diretório de exportação dos relatórios")
    parser.add_argument("--json-stdout", action="store_true", help="Imprime o relatório como JSON no stdout (para integração com API)")
    parser.add_argument("--sales-file", type=str, help="Caminho de um CSV/XLSX com a base de vendas a auditar")
    parser.add_argument("--attribution-window", type=int, default=DEFAULT_ATTRIBUTION_WINDOW_DAYS, help="Janela de atribuição em dias: quanto tempo antes da venda um lead ainda explica a origem")
    parser.add_argument("--skip-sales-audit", action="store_true", help="Pula o cruzamento da base de vendas")
    parser.add_argument("--empreendimento", type=str, help="Confere apenas as vendas deste empreendimento (os leads dos demais seguem disponíveis para match)")
    parser.add_argument("--listar-empreendimentos", action="store_true", help="Lista os empreendimentos oficiais cadastrados no CV e encerra")
    args = parser.parse_args()

    if args.listar_empreendimentos:
        cv = CVCRMExtractor()
        nomes = cv.fetch_empreendimentos()
        status = cv.empreendimentos_status
        print(f"{MODE_ICON.get(status.mode, '')} {status.label}: {status.message}")
        for nome in nomes:
            print(f"  • {nome}")
        return

    start_dt, end_dt = resolve_period(args.start_date, args.end_date)

    print(LINHA)
    print("🚀 INICIANDO ANÁLISE SOB DEMANDA DE RECONCILIAÇÃO DE LEADS")
    print(f"📅 Período: {start_dt:%Y-%m-%d} até {end_dt:%Y-%m-%d}")
    print(LINHA)

    result = run_pipeline(
        start_dt,
        end_dt,
        sales_file=args.sales_file,
        attribution_window_days=args.attribution_window,
        empreendimento=args.empreendimento,
        skip_sales_audit=args.skip_sales_audit,
        output_dir=args.output_dir,
    )
    report = result.report

    # ------------------------------------------------------------------ integrações
    print("\n" + LINHA)
    print("🔌 INTEGRAÇÕES")
    for fonte in report.sources:
        print(f"  {MODE_ICON.get(fonte.mode, '?')} {fonte.label}: {fonte.message}")
        if fonte.mode != "real":
            if fonte.action:
                print(f"       → {fonte.action}")
            for link in fonte.help_links:
                print(f"       🔗 {link.label}: {link.url}")
    if report.simulated_data:
        print("\n  🧪 ATENÇÃO: há DADOS SIMULADOS neste relatório (ALLOW_SIMULATED_DATA ligado).")

    # ------------------------------------------------------------------ reconciliação
    print("\n" + LINHA)
    print(f"📊 RESUMO DA RECONCILIAÇÃO (Execução ID: {report.execution_id})")
    print(f"  • Leads das origens no período: {report.total_source_leads}")
    if report.cv_available:
        print(f"  • Saúde Geral: {report.overall_health.value}")
        print(f"  • Taxa de Aderência Global: {report.overall_adherence_rate}%")
        print(f"  • Leads Reconciliados (MATCH_OK): {report.total_reconciled_ok}")
        print(f"  • Leads Perdidos (MISSING_IN_CV): {report.total_missing_in_cv}")
        print(f"  • Origem Incorreta (ORIGIN_MISMATCH): {report.total_origin_mismatch}")
    else:
        print("  • Conferência com o CV INDISPONÍVEL: os leads do CV não puderam ser lidos,")
        print("    então nenhum lead foi acusado de ausente no CRM. Veja a seção de integrações.")

    # ------------------------------------------------------------------ vendas
    if report.sales_audit:
        sa = report.sales_audit
        print("------------------------------------------------------------------------")
        print("🧾 AUDITORIA DE VENDAS (Base de Vendas x Base de Leads)")
        print(f"  • Vendas no período: {sa.total_sales}")
        if sa.total_sales:
            print(f"  • Online declarado: {sa.declared_online}  |  Online comprovado: {sa.verified_online}  ({sa.online_delta:+d})")
            print(f"  • Acurácia da atribuição: {sa.attribution_accuracy}% [{sa.health_status.value}]")
            print(f"  • Falso online: {sa.online_unproven} | Online não declarado: {sa.online_not_declared} | Canal errado: {sa.channel_mismatch}")
        if sa.leads_sem_empreendimento:
            print(f"  • {sa.leads_sem_empreendimento} lead(s) sem empreendimento identificável.")
        if sa.empreendimentos:
            print("------------------------------------------------------------------------")
            print("🏗️  CONFERÊNCIA POR EMPREENDIMENTO")
            for emp in sa.empreendimentos:
                marca = "OK " if emp.is_consistent else "!! "
                print(
                    f"  {marca}{emp.empreendimento}: {emp.total_leads} leads | {emp.total_sales} vendas | "
                    f"online {emp.declared_online} declarado x {emp.verified_online} comprovado | "
                    f"conversão {emp.conversion_rate}%"
                )
                for problema in emp.inconsistencies:
                    print(f"       - {problema}")

    print(LINHA)
    if result.json_path:
        print(f"📁 Arquivo JSON: {result.json_path}")
        print(f"📁 Arquivo CSV: {result.csv_path}")
    if result.sales_csv_path:
        print(f"📁 Auditoria de Vendas CSV: {result.sales_csv_path}")
    print(LINHA + "\n")

    if args.json_stdout:
        print("\n__JSON_REPORT_START__")
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False, default=str))
        print("__JSON_REPORT_END__")


if __name__ == "__main__":
    main()
