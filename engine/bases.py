"""
Bases de dados baixadas das integrações e guardadas em disco.

Cada base é baixada de uma fonte (CV, BeeViral, Meta, Google...) e salva com a data da
atualização e o estado da consulta. BI e conferências leem as bases salvas — segundos em
vez de minutos — e a atualização roda em segundo plano.

Regra: uma atualização que falha NUNCA apaga dados bons. A base anterior é mantida e o
estado passa a mostrar o erro e a data dos dados em uso.
"""

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine.config import SourceStatus
from engine.integrations import build_status

BASES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output", "bases"))

# Histórico mantido nas bases: 13 meses permitem comparar o mês atual com o do ano anterior
HISTORICO_DIAS = int(os.getenv("BASES_HISTORICO_DIAS", "400"))


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _jsonable(registros: List[Any]) -> List[Any]:
    saida = []
    for r in registros:
        if hasattr(r, "model_dump"):
            saida.append(r.model_dump(mode="json"))
        else:
            saida.append(r)
    return saida


# ---------------------------------------------------------------------------
# Baixadores — cada um devolve (registros, estado)
# ---------------------------------------------------------------------------


def _baixar_cv_leads(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import CVCRMExtractor

    ex = CVCRMExtractor()
    return ex.fetch_raw(inicio, fim), ex.status


def _baixar_cv_indice(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import CVCRMExtractor

    ex = CVCRMExtractor()
    anterior = carregar("cv_indice") or {}
    return ex.fetch_indice(anterior.get("registros") or None), ex.status


def _baixar_cv_reservas(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import CVCRMExtractor

    ex = CVCRMExtractor()
    anterior = carregar("cv_reservas") or {}
    return ex.fetch_reservas(anterior.get("registros") or None), ex.status


def _baixar_cv_conversoes(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.cv_conversoes import CVConversoesExtractor

    ex = CVConversoesExtractor()
    # O ano corrente inteiro (as metas de leads por mês precisam de janeiro em diante), no mínimo 150 dias. As atualizações seguintes só leem o
    # que é mais novo que o guardado, mas se o guardado começa DEPOIS do início pedido a leitura incremental nunca volta para completar:
    # nesse caso relê tudo uma vez.
    inicio = min(max(inicio, fim - timedelta(days=150)), datetime(fim.year, 1, 1))
    anterior = (carregar("cv_conversoes") or {}).get("registros") or []

    def _parcial(linhas: list) -> None:
        # Leitura longa (o ano inteiro): guarda o que já veio, para uma interrupção não perder o trabalho.
        # Guarda o progresso SEM marcar a base como atualizada: se `dados_de` virasse "agora", as próximas atualizações achariam que ela está fresca
        # e a pulariam, deixando a leitura sem terminar (foi o que deixou o CV 7 dias atrasado).
        agora_iso = datetime.now(timezone.utc).isoformat()
        antes = carregar("cv_conversoes") or {}
        st = build_status("cv_conversoes", "real", records=len(linhas), message=f"Leitura do ano em andamento: {len(linhas)} conversões até agora.")
        _salvar("cv_conversoes", {"base": "cv_conversoes", "label": BASES["cv_conversoes"].label, "atualizado_em": agora_iso, "dados_de": antes.get("dados_de"),
                                  "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()}, "total": len(linhas), "status": st.model_dump(),
                                  "registros": _jsonable(linhas)})

    return ex.fetch(inicio, fim, anterior or None, _parcial), ex.status


def _baixar_cv_leads_dw(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.cv_leads_dw import CVLeadsDWExtractor

    ex = CVLeadsDWExtractor()
    anterior = carregar("cv_leads_dw") or {}
    return ex.fetch(inicio, fim, anterior.get("registros") or None), ex.status


def _baixar_cv_leads_historico(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.cv_leads_historico import CVLeadsHistoricoExtractor

    ex = CVLeadsHistoricoExtractor()
    anterior = carregar("cv_leads_historico") or {}
    return ex.fetch(inicio, fim, anterior.get("registros") or None), ex.status


def _baixar_cv_empreendimentos(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import CVCRMExtractor

    ex = CVCRMExtractor()
    nomes = ex.fetch_empreendimentos()
    return nomes, ex.empreendimentos_status


def _baixar_beeviral(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import BeeViralExtractor

    ex = BeeViralExtractor()
    return ex.fetch_raw(inicio, fim), ex.status


def _baixar_meta_insights(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import MetaInsightsExtractor

    ex = MetaInsightsExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_meta_anuncios(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import MetaAnunciosExtractor

    ex = MetaAnunciosExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_google_insights(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import GoogleInsightsExtractor

    ex = GoogleInsightsExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_google_palavras(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import GooglePalavrasExtractor

    ex = GooglePalavrasExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_google_termos(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import GoogleTermosExtractor

    ex = GoogleTermosExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_google_anuncios(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import GoogleAnunciosExtractor

    ex = GoogleAnunciosExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_google_detalhes(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ads_insights import GoogleDetalhesExtractor

    ex = GoogleDetalhesExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_ga4_palavras(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ga4 import GA4PalavrasExtractor

    ex = GA4PalavrasExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_ga4_trafego(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ga4 import GA4TrafegoExtractor

    ex = GA4TrafegoExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_ga4_cidades(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.ga4 import GA4CidadesExtractor

    ex = GA4CidadesExtractor()
    return ex.fetch(inicio, fim), ex.status


def _baixar_meta_leads(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import MetaAdsExtractor

    ex = MetaAdsExtractor()
    leads = ex.fetch_leads(inicio, fim)
    return _jsonable(leads), ex.status


def _baixar_rd_leads(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors import RDStationExtractor

    ex = RDStationExtractor()
    leads = ex.fetch_leads(inicio, fim)
    return _jsonable(leads), ex.status


def _baixar_rd_conversoes(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine import rd_conversoes

    return rd_conversoes.baixar(inicio, fim)


def _baixar_origem_rd(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine import origem_rd

    return origem_rd.baixar(inicio, fim)


def _baixar_vendas_planilha(inicio: datetime, fim: datetime) -> Tuple[list, SourceStatus]:
    from engine.extractors.sales import latest_uploaded_sales_file, read_sales_file

    path = latest_uploaded_sales_file() or (os.getenv("SALES_FILE_PATH") or None)
    if not path or not os.path.exists(path):
        return [], build_status(
            "vendas", "nao_configurado",
            message="Nenhuma planilha carregada. Não é necessária: as vendas e reservas vêm direto do CV "
                    "(base 'CV — Reservas e vendas'). Use só se quiser conferir o CV com um controle externo.",
            action=None,
        )
    vendas = read_sales_file(path)
    return _jsonable(vendas), build_status(
        "vendas", "real", len(vendas), f"Planilha '{os.path.basename(path)}': {len(vendas)} venda(s)."
    )


@dataclass(frozen=True)
class BaseDef:
    chave: str
    label: str
    descricao: str
    baixar: Callable[[datetime, datetime], Tuple[list, SourceStatus]]
    essencial: bool = True
    # Bases por dia e muito grandes: depois da primeira carga, baixa só os últimos N dias e mescla com o
    # histórico. Sem isso, cada atualização refaz 14 meses de consultas e estoura a cota diária da API.
    incremental_dias: Optional[int] = None


BASES: Dict[str, BaseDef] = {
    b.chave: b
    for b in (
        BaseDef("cv_leads", "CV — Leads", "Todos os leads do CRM com mídia, UTMs, tags, situação e venda.", _baixar_cv_leads),
        BaseDef(
            "cv_indice",
            "CV — Índice de todos os leads",
            "Todos os leads do CV, de qualquer data, com os dados para achar a pessoa. Evita dar como "
            "\"não chegou\" um lead cadastrado há anos.",
            _baixar_cv_indice,
        ),
        BaseDef(
            "cv_reservas",
            "CV — Reservas e vendas",
            "Todas as reservas do CV: situação, data da venda, empreendimento e unidade comprados, valor, corretor e lead associado.",
            _baixar_cv_reservas,
        ),
        BaseDef(
            "cv_conversoes",
            "CV — Conversões dos leads",
            "Cada conversão de lead com a mídia, a origem e o empreendimento daquela conversão: é a base de MQL e origem do Power BI da gestão.",
            _baixar_cv_conversoes,
        ),
        BaseDef(
            "cv_leads_dw",
            "CV — Leads alterados (situação e data)",
            "Leads do CV em ordem de última alteração, com a situação atual e a data: base do SQL do Power BI da gestão.",
            _baixar_cv_leads_dw,
        ),
        BaseDef(
            "cv_leads_historico",
            "CV — Histórico de situações dos leads",
            "Cada mudança de situação do lead com a data e a hora (Novo Lead, Qualificado, Agendado...): base do SQL do Power BI da gestão.",
            _baixar_cv_leads_historico,
        ),
        BaseDef("cv_empreendimentos", "CV — Empreendimentos", "Catálogo oficial de empreendimentos.", _baixar_cv_empreendimentos),
        BaseDef("beeviral", "BeeViral — Indicações", "Indicações do Indique e Ganhe.", _baixar_beeviral),
        BaseDef("meta_insights", "Meta Ads — Investimento e leads", "Por conta de anúncio, campanha e dia, segundo a Meta.", _baixar_meta_insights),
        BaseDef(
            "meta_anuncios",
            "Meta Ads — Anúncios",
            "Investimento, impressões, cliques e leads de cada anúncio, por dia, com miniatura e status.",
            _baixar_meta_anuncios,
        ),
        BaseDef("google_insights", "Google Ads — Investimento e conversões", "Por conta, campanha e dia, segundo o Google.", _baixar_google_insights),
        BaseDef(
            "google_palavras",
            "Google Ads — Palavras-chave",
            "Investimento, impressões, cliques e conversões de cada palavra-chave, por mês e campanha.",
            _baixar_google_palavras,
        ),
        BaseDef(
            "google_termos",
            "Google Ads — Termos de pesquisa",
            "O termo exato que as pessoas digitaram (pesquisa e Performance Max), por campanha e dia, com custo e conversões.",
            _baixar_google_termos,
            incremental_dias=35,
        ),
        BaseDef(
            "google_anuncios",
            "Google Ads — Anúncios",
            "Cada anúncio de pesquisa (com os títulos) e cada grupo de recursos do Performance Max, por dia, com custo e conversões.",
            _baixar_google_anuncios,
            incremental_dias=35,
        ),
        BaseDef(
            "google_detalhes",
            "Google Ads — Conversões, aparelho e impressões",
            "Por campanha e dia: ações de conversão (formulário, WhatsApp), aparelho e participação de impressões perdida.",
            _baixar_google_detalhes,
            incremental_dias=35,
        ),
        BaseDef(
            "ga4_palavras",
            "Google Analytics — Palavras buscadas",
            "Palavra do Google Ads e utm_term de cada sessão, por mês, campanha e página de entrada.",
            _baixar_ga4_palavras,
            essencial=False,
        ),
        BaseDef(
            "ga4_trafego",
            "Google Analytics — Origem das sessões",
            "De onde vem cada sessão do site e em que aparelho, por dia e página de entrada.",
            _baixar_ga4_trafego,
            essencial=False,
        ),
        BaseDef(
            "ga4_cidades",
            "Google Analytics — Cidades de quem acessa",
            "De que cidade vem cada sessão do site, por dia e página de entrada.",
            _baixar_ga4_cidades,
            essencial=False,
        ),
        BaseDef("meta_leads", "Meta Ads — Leads de formulário", "Cada lead dos formulários nativos da Meta.", _baixar_meta_leads),
        BaseDef("rd_leads", "RD Station — Contatos", "Contatos criados na RD Station.", _baixar_rd_leads),
        BaseDef(
            "rd_conversoes",
            "RD Station — Entrada dos contatos fora do CV",
            "Primeira conversão de cada contato da RD que não está no CV: formulário, lista importada ou disparo.",
            _baixar_rd_conversoes,
        ),
        BaseDef(
            "origem_rd",
            "RD Station — Origem dos leads sem origem no CV",
            "Para cada lead que chega ao CV sem mídia, UTM nem origem, a conversão na RD que mostra de onde ele veio: "
            "formulário do site, landing page, anúncio ou disparo do comercial.",
            _baixar_origem_rd,
        ),
        BaseDef("vendas_planilha", "Vendas — Planilha comercial (opcional)", "Só para conferir o CV com um controle externo; as vendas já vêm das reservas do CV.", _baixar_vendas_planilha, essencial=False),
    )
}


# ---------------------------------------------------------------------------
# Leitura e gravação
# ---------------------------------------------------------------------------


def _path(chave: str) -> str:
    return os.path.join(BASES_DIR, f"{chave}.json")


_cache_leitura: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def carregar(chave: str) -> Optional[Dict[str, Any]]:
    """Lê a base do disco; só relê quando o arquivo muda (a de leads do CV tem ~10 mil registros)."""
    path = _path(chave)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    em_cache = _cache_leitura.get(path)
    if em_cache and em_cache[0] == mtime:
        return em_cache[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
    except ValueError:
        # Arquivo vazio ou cheio de zeros (queda do computador no meio da gravação): vira "base ausente" e a próxima atualização o refaz.
        # Antes, um único arquivo assim derrubava todas as telas com erro 500.
        try:
            os.replace(path, path + ".corrompido")
        except OSError:
            pass
        _cache_leitura.pop(path, None)
        return None
    _cache_leitura[path] = (mtime, conteudo)
    return conteudo


def registros(chave: str) -> List[Any]:
    base = carregar(chave)
    return (base or {}).get("registros") or []


def _salvar(chave: str, conteudo: Dict[str, Any]) -> None:
    os.makedirs(BASES_DIR, exist_ok=True)
    tmp = _path(chave) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())  # força o conteúdo ao disco antes da troca: sem isso, uma queda deixa o arquivo novo cheio de zeros
    os.replace(tmp, _path(chave))  # troca atômica: leitor nunca vê arquivo pela metade


def atualizar(chave: str, dias: Optional[int] = None) -> Dict[str, Any]:
    """Baixa uma base de novo. Se falhar, mantém os dados anteriores e registra o erro."""
    definicao = BASES[chave]
    fim = _agora()
    inicio = fim - timedelta(days=dias or HISTORICO_DIAS)
    anterior = carregar(chave)

    incremental = bool(definicao.incremental_dias and not dias and anterior and anterior.get("registros"))
    inicio_baixa = max(inicio, fim - timedelta(days=definicao.incremental_dias)) if incremental else inicio

    try:
        novos, status = definicao.baixar(inicio_baixa, fim)
    except Exception as e:  # noqa: BLE001
        novos, status = [], build_status(chave, "erro", message=f"Falha inesperada: {e}")

    if incremental and status.mode == "real":
        corte = inicio_baixa.date().isoformat()
        novos = [r for r in anterior["registros"] if str(r.get("data") or "")[:10] < corte and str(r.get("data") or "")[:10] >= inicio.date().isoformat()] + list(novos)
    agora_iso = datetime.now(timezone.utc).isoformat()

    if status.mode == "real":
        conteudo = {
            "base": chave,
            "label": definicao.label,
            "atualizado_em": agora_iso,
            "dados_de": agora_iso,
            "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
            "total": len(novos),
            "status": status.model_dump(),
            "registros": _jsonable(novos),
        }
    elif anterior and anterior.get("registros"):
        # Falhou: preserva os dados bons e deixa claro de quando eles são
        status.message = f"{status.message} — mantidos os dados de {anterior.get('dados_de', '')[:16].replace('T', ' ')}."
        conteudo = {**anterior, "atualizado_em": agora_iso, "status": status.model_dump()}
    else:
        conteudo = {
            "base": chave,
            "label": definicao.label,
            "atualizado_em": agora_iso,
            "dados_de": None,
            "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
            "total": 0,
            "status": status.model_dump(),
            "registros": [],
        }

    _salvar(chave, conteudo)
    return resumo(chave, conteudo)


def resumo(chave: str, conteudo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Metadados da base sem os registros (para listagem)."""
    conteudo = conteudo if conteudo is not None else carregar(chave)
    definicao = BASES[chave]
    if not conteudo:
        return {
            "base": chave, "label": definicao.label, "descricao": definicao.descricao, "essencial": definicao.essencial,
            "atualizado_em": None, "dados_de": None, "total": 0, "idade_horas": None,
            "status": build_status(chave, "nao_configurado", message="Base ainda não baixada.").model_dump(),
        }
    dados_de = conteudo.get("dados_de")
    idade = None
    if dados_de:
        idade = round((datetime.now(timezone.utc) - datetime.fromisoformat(dados_de)).total_seconds() / 3600, 1)
    return {
        "base": chave,
        "label": definicao.label,
        "descricao": definicao.descricao,
        "essencial": definicao.essencial,
        "atualizado_em": conteudo.get("atualizado_em"),
        "dados_de": dados_de,
        "total": conteudo.get("total", 0),
        "idade_horas": idade,
        "periodo": conteudo.get("periodo"),
        "status": conteudo.get("status"),
    }


def listar() -> List[Dict[str, Any]]:
    return [resumo(chave) for chave in BASES]


# ---------------------------------------------------------------------------
# Atualização em segundo plano
# ---------------------------------------------------------------------------

_trava = threading.Lock()
_estado: Dict[str, Any] = {"em_andamento": False, "base_atual": None, "iniciado_em": None, "concluido_em": None, "fila": []}


def estado_atualizacao() -> Dict[str, Any]:
    return dict(_estado)


def iniciar_atualizacao(chaves: Optional[List[str]] = None) -> Dict[str, Any]:
    """Dispara a atualização das bases em uma thread. Ignora o pedido se já houver uma rodando."""
    chaves = [c for c in (chaves or list(BASES)) if c in BASES]
    if not _trava.acquire(blocking=False):
        return {**estado_atualizacao(), "aceito": False}

    def rodar():
        try:
            _estado.update(em_andamento=True, iniciado_em=datetime.now(timezone.utc).isoformat(), concluido_em=None, fila=list(chaves))
            for chave in chaves:
                _estado["base_atual"] = chave
                atualizar(chave)
                _estado["fila"] = [c for c in _estado["fila"] if c != chave]
        finally:
            _estado.update(em_andamento=False, base_atual=None, concluido_em=datetime.now(timezone.utc).isoformat())
            _trava.release()

    threading.Thread(target=rodar, daemon=True, name="atualizacao-bases").start()
    return {**estado_atualizacao(), "em_andamento": True, "fila": chaves, "aceito": True}


def bases_desatualizadas(max_idade_horas: float) -> List[str]:
    """Bases essenciais nunca baixadas ou mais antigas que o limite."""
    saida = []
    for info in listar():
        if not info["essencial"]:
            continue
        if info["dados_de"] is None or (info["idade_horas"] or 0) >= max_idade_horas:
            saida.append(info["base"])
    return saida


_agendador_iniciado = False


def iniciar_agendador(intervalo_minutos: int = 60, max_idade_horas: float = 1.0) -> None:
    """Verifica periodicamente a idade das bases e atualiza as vencidas em segundo plano."""
    global _agendador_iniciado
    if _agendador_iniciado:
        return
    _agendador_iniciado = True

    def ciclo():
        import time

        while True:
            vencidas = bases_desatualizadas(max_idade_horas)
            if vencidas:
                iniciar_atualizacao(vencidas)
            time.sleep(intervalo_minutos * 60)

    threading.Thread(target=ciclo, daemon=True, name="agendador-bases").start()
