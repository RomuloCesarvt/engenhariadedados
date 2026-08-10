"""
API HTTP da engine — consumida pelo dashboard Next.js.

Executar a partir da raiz do repositório:
    uvicorn engine.api:app --port 8001
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone
from datetime import date, timedelta
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Sem isto a API rodava sem nenhuma credencial e toda fonte parecia "não configurada"
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import anuncios, bases, bi, conferencias, criativos, diagnosticos, verificacao
from engine.extractors import CVCRMExtractor
from engine.extractors.sales import SALES_EXTENSIONS, UPLOAD_DIR, latest_uploaded_sales_file, read_sales_file
from engine.normalizer import match_empreendimento
from engine.pipeline import check_integrations, resolve_period, run_pipeline
from engine.sales_auditor import DEFAULT_ATTRIBUTION_WINDOW_DAYS

app = FastAPI(
    title="Lead Recon Engine API",
    description="Extração, reconciliação de leads e auditoria de vendas por empreendimento",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
LATEST_REPORT = os.path.join(OUTPUT_DIR, "latest_report.json")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class ReconcileRequest(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    salesFile: Optional[str] = None
    attributionWindowDays: Optional[int] = None
    skipSalesAudit: bool = False
    empreendimento: Optional[str] = None


def _read_latest_report() -> Optional[dict]:
    if not os.path.exists(LATEST_REPORT):
        return None
    with open(LATEST_REPORT, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Lead Recon Engine API is running"}


@app.post("/api/reconcile")
def run_reconciliation(payload: ReconcileRequest):
    try:
        start_dt, end_dt = resolve_period(payload.startDate, payload.endDate)
        result = run_pipeline(
            start_dt,
            end_dt,
            sales_file=payload.salesFile,
            attribution_window_days=payload.attributionWindowDays or DEFAULT_ATTRIBUTION_WINDOW_DAYS,
            empreendimento=payload.empreendimento,
            skip_sales_audit=payload.skipSalesAudit,
            output_dir=OUTPUT_DIR,
        )
        return {
            "report": result.report.model_dump(),
            "meta": {
                "source": "engine_execution",
                "executedAt": datetime.now(timezone.utc).isoformat(),
                "firebase_saved": result.firebase_saved,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/latest")
def get_latest_report():
    try:
        data = _read_latest_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler relatório: {e}")
    if data is None:
        raise HTTPException(status_code=404, detail="Nenhum relatório encontrado.")
    return {"report": data, "meta": {"source": "disk", "readAt": datetime.now(timezone.utc).isoformat()}}


@app.get("/api/reports")
def list_reports():
    try:
        files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "report_*.json")), key=os.path.getmtime, reverse=True)
        reports = []
        for file in files[:50]:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop("divergences", None)
            data.pop("sales_audit", None)
            reports.append(data)
        return {"reports": reports, "total": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar relatórios: {e}")


@app.get("/api/sales-audit/latest")
def get_latest_sales_audit():
    data = _read_latest_report()
    if data is None:
        raise HTTPException(status_code=404, detail="Nenhum relatório encontrado.")
    if not data.get("sales_audit"):
        raise HTTPException(status_code=404, detail="O relatório mais recente não inclui auditoria de vendas.")
    return {
        "sales_audit": data["sales_audit"],
        "meta": {"source": "disk", "execution_id": data.get("execution_id"), "readAt": datetime.now(timezone.utc).isoformat()},
    }


@app.get("/api/empreendimentos")
def list_empreendimentos():
    """Empreendimentos oficiais do CV, com os números do relatório mais recente quando houver."""
    cv = CVCRMExtractor()
    oficiais = cv.fetch_empreendimentos()

    stats = {}
    data = _read_latest_report() or {}
    for e in (data.get("sales_audit") or {}).get("empreendimentos", []):
        stats[e.get("empreendimento")] = e

    nomes = oficiais or list(stats)
    return {
        "empreendimentos": [
            {
                "empreendimento": nome,
                "total_leads": stats.get(nome, {}).get("total_leads", 0),
                "total_sales": stats.get(nome, {}).get("total_sales", 0),
                "is_consistent": stats.get(nome, {}).get("is_consistent", True),
            }
            for nome in nomes
        ],
        "status": cv.empreendimentos_status.model_dump(),
        "meta": {"execution_id": data.get("execution_id")},
    }


@app.get("/api/integrations")
def integrations(live: bool = False):
    """
    Estado das integrações. Por padrão lê o da última análise; com ?live=true
    consulta cada API agora (leva alguns segundos).
    """
    try:
        if not live:
            data = _read_latest_report()
            if data and data.get("sources"):
                return {"sources": data["sources"], "checked": "last_report", "execution_id": data.get("execution_id")}
        sources = check_integrations()
        return {"sources": [s.model_dump() for s in sources], "checked": "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao verificar integrações: {e}")


def _describe_sales_file(path: str) -> dict:
    vendas = read_sales_file(path)
    datas = sorted(v.sale_date for v in vendas)

    # Mostra, antes de rodar a análise, como cada nome da planilha será lido no CV
    catalogo = CVCRMExtractor().fetch_empreendimentos()
    mapeados = [
        {"planilha": nome, "oficial": match_empreendimento(nome, catalogo) if catalogo else None}
        for nome in sorted({v.empreendimento for v in vendas if v.empreendimento})
    ]
    return {
        "filename": os.path.basename(path),
        "uploaded_at": datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat(),
        "rows": len(vendas),
        "empreendimentos": sorted({m["oficial"] or m["planilha"] for m in mapeados}),
        "empreendimentos_mapeados": mapeados,
        "empreendimentos_nao_reconhecidos": [m["planilha"] for m in mapeados if catalogo and not m["oficial"]],
        "catalogo_disponivel": bool(catalogo),
        "first_sale": datas[0].isoformat() if datas else None,
        "last_sale": datas[-1].isoformat() if datas else None,
        "declared_online": sum(1 for v in vendas if v.declared_is_online),
        "without_empreendimento": sum(1 for v in vendas if not v.empreendimento),
    }


@app.post("/api/sales/upload")
async def upload_sales_file(file: UploadFile = File(...)):
    """Recebe a planilha de vendas (CSV/XLSX) usada quando as reservas do CV não estão acessíveis."""
    nome = file.filename or ""
    ext = os.path.splitext(nome)[1].lower()
    if ext not in SALES_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv, .xlsx ou .xls.")

    conteudo = await file.read()
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo maior que 20 MB.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    destino = os.path.join(UPLOAD_DIR, f"vendas_{datetime.now():%Y%m%d_%H%M%S}{ext}")
    with open(destino, "wb") as f:
        f.write(conteudo)

    try:
        info = _describe_sales_file(destino)
    except Exception as e:
        os.remove(destino)
        raise HTTPException(status_code=400, detail=f"Não foi possível ler a planilha: {e}")

    if info["rows"] == 0:
        os.remove(destino)
        raise HTTPException(
            status_code=400,
            detail="Nenhuma venda encontrada. A planilha precisa de colunas como cliente, email/telefone/cpf, "
            "origem, data_venda e empreendimento.",
        )
    info["original_filename"] = nome
    return info


@app.get("/api/sales/upload/latest")
def latest_sales_file():
    path = latest_uploaded_sales_file()
    if not path:
        raise HTTPException(status_code=404, detail="Nenhuma planilha de vendas carregada.")
    try:
        return _describe_sales_file(path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler a planilha carregada: {e}")


# ===========================================================================
# Bases salvas
# ===========================================================================

AGENDADOR_INTERVALO_MIN = int(os.getenv("BASES_INTERVALO_MINUTOS", "60"))
AGENDADOR_MAX_IDADE_H = float(os.getenv("BASES_MAX_IDADE_HORAS", "1"))


@app.on_event("startup")
def _iniciar_agendador():
    if os.getenv("BASES_AGENDADOR", "true").lower() != "false":
        bases.iniciar_agendador(AGENDADOR_INTERVALO_MIN, AGENDADOR_MAX_IDADE_H)

    # Aquece os cálculos pesados em segundo plano: a primeira tela aberta já encontra tudo pronto
    def aquecer():
        from datetime import date as _date, timedelta as _td

        try:
            hoje = _date.today()
            bi.leads_preparados()
            bi.calcular_bi(hoje - _td(days=29), hoje, escopo="online")
            diagnosticos.calcular(hoje - _td(days=29), hoje)
        except Exception as e:  # aquecimento nunca derruba a API
            print(f"  [Aquecimento] {e}")

    import threading

    threading.Thread(target=aquecer, daemon=True, name="aquecimento").start()


@app.get("/api/bases")
def listar_bases():
    return {"bases": bases.listar(), "atualizacao": bases.estado_atualizacao()}


@app.post("/api/bases/atualizar")
def atualizar_bases(payload: dict = Body(default={})):
    escolhidas = payload.get("bases") or None
    desconhecidas = [b for b in (escolhidas or []) if b not in bases.BASES]
    if desconhecidas:
        raise HTTPException(status_code=400, detail=f"Bases desconhecidas: {', '.join(desconhecidas)}")
    return bases.iniciar_atualizacao(escolhidas)


# ===========================================================================
# BI
# ===========================================================================


def _periodo(inicio: Optional[str], fim: Optional[str]):
    hoje = date.today()
    try:
        d_fim = date.fromisoformat(fim) if fim else hoje
        d_ini = date.fromisoformat(inicio) if inicio else d_fim - timedelta(days=29)
    except ValueError:
        raise HTTPException(status_code=400, detail="Datas devem estar no formato AAAA-MM-DD.")
    if d_ini > d_fim:
        raise HTTPException(status_code=400, detail="A data inicial é posterior à final.")
    return d_ini, d_fim


def _exigir_base_cv():
    if not bases.registros("cv_leads"):
        info = bases.resumo("cv_leads")
        raise HTTPException(
            status_code=409,
            detail="A base de leads do CV ainda não foi baixada. "
            f"Estado: {info['status'].get('message')}. Atualize as bases na tela Bases.",
        )


@app.get("/api/bi")
def indicadores(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
    grupo: Optional[List[str]] = Query(None),
    canal: Optional[List[str]] = Query(None),
    escopo: str = "online",
):
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    try:
        return bi.calcular_bi(d_ini, d_fim, empreendimento, praca, grupo, canal, escopo=escopo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao calcular o BI: {e}")


@app.get("/api/bi/leads")
def detalhe_leads(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[str] = None,
    canal: Optional[str] = None,
    grupo: Optional[str] = None,
    etapa_minima: Optional[int] = None,
    vendidos: bool = False,
    limite: int = 500,
    escopo: str = "online",
    criterio: str = "interesse",
    so_outro_empreendimento: bool = False,
):
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return bi.leads_detalhe(d_ini, d_fim, empreendimento, canal, grupo, etapa_minima, vendidos, min(limite, 5000),
                            escopo=escopo, criterio=criterio, so_outro_empreendimento=so_outro_empreendimento)


@app.get("/api/vendas/auditoria")
def auditoria_de_vendas(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[str] = None,
    praca: Optional[str] = None,
):
    """Vendas × leads: cada venda cruzada com os sinais de origem online de todas as bases."""
    from engine import auditoria_vendas

    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    try:
        return auditoria_vendas.auditar(d_ini, d_fim, empreendimento, praca)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na auditoria de vendas: {e}")


@app.get("/api/analista")
def analista_digital(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
):
    """Achados do período (alertas, oportunidades, destaques) com números, recomendação e onde conferir."""
    from engine import analista

    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    try:
        return analista.analisar(d_ini, d_fim, empreendimento, praca)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {e}")


@app.get("/api/analista/vendas-online")
def vendas_online_do_periodo(inicio: Optional[str] = None, fim: Optional[str] = None):
    """
    Vendas do período que são online mas não estão registradas assim no CV (casos para
    investigar), e as que vieram do online mas o cliente comprou com outro corretor.

    Devolve a última análise gravada do período, com as leituras revisadas aplicadas. Quando o
    período ainda não foi analisado, devolve `disponivel: false` — a análise é pedida por POST
    porque lê o CV venda a venda.
    """
    from engine import relatorio_vendas, vendas_online

    d_ini, d_fim = _periodo(inicio, fim)
    salva = vendas_online.analise_salva(d_ini, d_fim)
    estado = vendas_online.estado_execucao()
    # Análise gravada com a regra anterior (sem a leitura da conversa) precisa ser refeita
    if not vendas_online.regra_atual(salva):
        return {"disponivel": False, "periodo": {"inicio": d_ini.isoformat(), "fim": d_fim.isoformat()},
                "execucao": estado, "regra_desatualizada": bool(salva)}
    try:
        dados = relatorio_vendas.para_a_tela(salva["analise"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao montar a análise de vendas online: {e}")
    return {"disponivel": True, "execucao": estado, "gerado_em": salva.get("gerado_em"),
            "relatorio": salva.get("relatorio"), **dados}


class AnaliseVendasOnlinePedido(BaseModel):
    inicio: Optional[str] = None
    fim: Optional[str] = None


@app.post("/api/analista/vendas-online")
def analisar_vendas_online(pedido: AnaliseVendasOnlinePedido = Body(default=AnaliseVendasOnlinePedido())):
    """Refaz a análise do período (lê o CV venda a venda) e gera a planilha, em segundo plano."""
    from engine import vendas_online

    _exigir_base_cv()
    d_ini, d_fim = _periodo(pedido.inicio, pedido.fim)
    return vendas_online.iniciar_analise(d_ini, d_fim)


@app.get("/api/analista/vendas-online/relatorio")
def baixar_relatorio_vendas_online(inicio: Optional[str] = None, fim: Optional[str] = None):
    """A planilha do período, para baixar."""
    from fastapi.responses import FileResponse

    from engine import relatorio_vendas, vendas_online

    d_ini, d_fim = _periodo(inicio, fim)
    salva = vendas_online.analise_salva(d_ini, d_fim)
    if not vendas_online.regra_atual(salva):
        raise HTTPException(status_code=404, detail="Esse período ainda não foi analisado com a regra atual.")
    # A planilha sai na hora, para levar as leituras revisadas depois da análise
    caminho = relatorio_vendas.gerar(salva["analise"])
    return FileResponse(caminho, filename=os.path.basename(caminho),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


class LeituraConversaPedido(BaseModel):
    idreserva: str
    leitura: str
    texto: Optional[str] = None


@app.post("/api/analista/vendas-online/leitura")
def revisar_leitura_da_conversa(pedido: LeituraConversaPedido):
    """O analista corrige a leitura da conversa de uma venda: vale para a tela e para a planilha."""
    from engine import leitura_conversa

    try:
        return {"idreserva": pedido.idreserva, **leitura_conversa.revisar(pedido.idreserva, pedido.leitura, pedido.texto)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/analista/vendas-online/leitura")
def desfazer_revisao_da_leitura(idreserva: str):
    """Volta a valer a leitura automática da conversa."""
    from engine import leitura_conversa

    return {"idreserva": idreserva, "desfeita": leitura_conversa.desfazer(idreserva)}


@app.get("/api/analista/origem-rd")
def origem_dos_leads_na_rd():
    """Quantos leads sem origem no CV já tiveram a origem recuperada na RD Station."""
    from engine import origem_rd

    return {**origem_rd.resumo(), "base": bases.resumo("origem_rd")}


# ===========================================================================
# Conferências
# ===========================================================================


@app.get("/api/conferencias/beeviral")
def conferir_beeviral(inicio: Optional[str] = None, fim: Optional[str] = None, empreendimento: Optional[str] = None):
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return conferencias.conferencia_beeviral(d_ini, d_fim, empreendimento)


@app.get("/api/conferencias/plataforma/{plataforma}")
def conferir_plataforma(plataforma: str, inicio: Optional[str] = None, fim: Optional[str] = None, empreendimento: Optional[str] = None):
    if plataforma not in conferencias.PLATAFORMAS:
        raise HTTPException(status_code=404, detail="Plataforma deve ser meta ou google.")
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return conferencias.conferencia_plataforma(d_ini, d_fim, plataforma, empreendimento)


@app.get("/api/bi/opcoes")
def opcoes_filtro():
    _exigir_base_cv()
    return {**bi.opcoes(), "bases": bases.listar(), "atualizacao": bases.estado_atualizacao()}


@app.get("/api/conferencias/rd")
def conferir_rd(inicio: Optional[str] = None, fim: Optional[str] = None):
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return conferencias.conferencia_rd(d_ini, d_fim)


class VerificarLeadPedido(BaseModel):
    email: Optional[str] = None
    telefone: Optional[str] = None


@app.post("/api/verificar-lead")
def verificar_lead(pedido: VerificarLeadPedido):
    """Procura o lead AO VIVO no CV (todos os leads) e no RD Station. POST para não pôr contato na URL."""
    if not (pedido.email or pedido.telefone):
        raise HTTPException(status_code=400, detail="Informe e-mail ou telefone.")
    return verificacao.verificar_lead(pedido.email, pedido.telefone)


@app.get("/api/anuncios")
def auditoria_anuncios(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
):
    """Cada anúncio: plataforma × CV (leads, SQL, vendas, custos) e os campeões de cada critério."""
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return anuncios.auditoria(d_ini, d_fim, empreendimento, praca)


@app.get("/api/anuncios/palavras")
def palavras_por_praca(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
    limite: int = 5,
):
    """
    As palavras que trazem gente no período.

    `google`: as melhores palavras-chave dos anúncios do Google em cada empreendimento.
    `ga4`: as palavras mais buscadas de cada praça, segundo o Google Analytics.
    """
    from engine import palavras

    d_ini, d_fim = _periodo(inicio, fim)
    n = max(1, min(limite, 50))
    return {
        "periodo": {"inicio": d_ini.isoformat(), "fim": d_fim.isoformat()},
        "google": palavras.por_empreendimento(d_ini, d_fim, empreendimento, praca, n),
        "ga4": palavras.por_praca(d_ini, d_fim, empreendimento, praca, n),
    }


@app.get("/api/site/audiencia")
def audiencia_do_site(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
    limite: int = 12,
):
    """
    A audiência do site no período, segundo o Google Analytics, comparada com o período anterior
    de mesmo tamanho: origem das sessões, aparelho, cidade, empreendimento procurado — e a leitura
    do que a comparação mostra.
    """
    from engine import audiencia

    d_ini, d_fim = _periodo(inicio, fim)
    return audiencia.compilar(d_ini, d_fim, empreendimento, praca, max(1, min(limite, 50)))


class QamarManualPedido(BaseModel):
    mes: str
    imprensa: List[str] = []
    observacoes: str = ""


@app.get("/api/qamar")
def qamar_relatorio(mes: Optional[str] = None, atualizar: bool = False, comparar: bool = False):
    """Relatório mensal da agência de comunicação (Qamar): redes sociais, site, blog, imprensa e tráfego pago."""
    from engine import qamar

    if not mes:
        hoje = date.today()
        mes = qamar.mes_anterior(f"{hoje.year}-{hoje.month:02d}")  # abre no último mês fechado
    try:
        return qamar.compilar(mes, atualizar, comparar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/qamar/comparativo")
def qamar_comparativo(meses: List[str] = Query(...), atualizar: bool = False):
    """Números de cada mês escolhido, lado a lado (insights, sem as listas de conteúdos)."""
    from engine import qamar

    try:
        return qamar.comparativo(meses, atualizar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/qamar/manual")
def qamar_salvar_manual(pedido: QamarManualPedido):
    """Texto digitado do relatório (imprensa e observações): não existe API para isso."""
    from engine import qamar

    return qamar.salvar_manual(pedido.mes, {"imprensa": pedido.imprensa, "observacoes": pedido.observacoes})


@app.post("/api/concorrencia/coleta")
async def concorrencia_coleta(request: Request):
    """Recebe a coleta da Biblioteca de Anúncios (texto JSON simples, enviado pela página lida no navegador) e junta ao que já existe."""
    from engine import concorrencia

    corpo = (await request.body()).decode("utf-8")[:500000]
    try:
        return concorrencia.guardar(corpo)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Coleta inválida: {e}")


@app.get("/api/apresentacao")
def apresentacao_semanal(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
):
    """
    Tudo o que a reunião de segunda apresenta, no período (mês em andamento) e comparado com o mesmo
    intervalo do mês anterior: leads por fonte, origem dos orgânicos, campeões de anúncio, Google e site.
    """
    from engine import apresentacao

    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return apresentacao.compilar(d_ini, d_fim, empreendimento, praca)


@app.get("/api/cenario")
def cenario_do_cpl(
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
):
    """Por que o CPL mudou: preço do leilão, clique e conversão; teste da eleição; concorrência por praça."""
    from engine import cenario

    d_ini, d_fim = _periodo(inicio, fim)
    return cenario.compilar(d_ini, d_fim, empreendimento, praca)


@app.get("/api/anuncios/criativo")
def criativo_do_anuncio(anuncio_id: str):
    """Pré-visualização por formato, imagens, vídeos e textos do anúncio, buscados na hora na Meta."""
    if not anuncio_id.isdigit():
        raise HTTPException(status_code=400, detail="anuncio_id inválido.")
    return criativos.criativo(anuncio_id)


@app.get("/api/anuncios/capa")
def capa_do_anuncio(anuncio_id: str):
    """Capa grande do anúncio (capa do vídeo ou imagem original) para os cards de campeões."""
    if not anuncio_id.isdigit():
        raise HTTPException(status_code=400, detail="anuncio_id inválido.")
    return criativos.capa(anuncio_id)


@app.get("/api/anuncios/leads")
def leads_do_anuncio(
    chave: str,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    empreendimento: Optional[List[str]] = Query(None),
    praca: Optional[List[str]] = Query(None),
):
    _exigir_base_cv()
    d_ini, d_fim = _periodo(inicio, fim)
    return anuncios.leads_do_anuncio(d_ini, d_fim, chave, empreendimento, praca)


@app.get("/api/diagnosticos")
def listar_diagnosticos(inicio: Optional[str] = None, fim: Optional[str] = None):
    """Problemas de dados identificados: o que, por quê, período, situação e como resolver."""
    d_ini, d_fim = _periodo(inicio, fim)
    return diagnosticos.calcular(d_ini, d_fim)


class ResolverDiagnosticoPedido(BaseModel):
    id: str
    nota: Optional[str] = None


@app.post("/api/diagnosticos/resolver")
def resolver_diagnostico(pedido: ResolverDiagnosticoPedido):
    try:
        return diagnosticos.resolver_manual(pedido.id, pedido.nota)
    except KeyError:
        raise HTTPException(status_code=404, detail="Diagnóstico não encontrado.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("engine.api:app", host="0.0.0.0", port=8001, reload=True)
