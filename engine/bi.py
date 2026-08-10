"""
BI de leads online e vendas, calculado a partir das bases salvas.

Princípios:
  - Todo número vem de uma regra explícita (taxonomia de origem, etapas do funil) e cada
    agregado carrega o que precisa para ser auditado: evidência, confiança, link do lead.
  - Leads são contados pela data de cadastro; vendas, pela data da venda. As duas
    populações são diferentes e o BI nunca divide uma pela outra sem dizer isso.
  - O que não tem evidência aparece como "Não rastreado" — é indicador de qualidade,
    não algo escondido dentro de outro canal.
"""

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Callable, Any, Dict, Iterable, List, Optional

from engine import bases, origem_rd
from engine.normalizer import (
    EMPREENDIMENTO_DESCONHECIDO, clean_email, clean_phone, match_empreendimento, unificar_empreendimento,
)
from engine.taxonomy import CANAIS, GRUPOS, GRUPOS_ONLINE, classificar_lead_cv

ETAPAS = [
    ("mql", "Lead (MQL)"),
    ("sal", "Tentativa de contato (SAL)"),
    ("sql", "Qualificado (SQL)"),
    ("agendamento", "Visita agendada (OPPS)"),
    ("atendimento", "Atendimento realizado"),
    ("venda", "Venda"),
]

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _nome(valor: Any) -> Optional[str]:
    if isinstance(valor, dict):
        return valor.get("nome") or valor.get("descricao")
    return valor


def _limpo(texto: Any) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower().strip()


def _data(valor: Any) -> Optional[date]:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _pct(parte: float, total: float) -> Optional[float]:
    return round(parte / total * 100, 1) if total else None


def _variacao(atual: float, anterior: float) -> Optional[float]:
    return round((atual - anterior) / anterior * 100, 1) if anterior else None


def praca_do_empreendimento(nome: Optional[str]) -> Optional[str]:
    """Cidade do empreendimento, pelo padrão do CV "Cidade - Nome - Código"."""
    if not nome:
        return None
    return re.split(r"\s*-\s*", str(nome).strip(), maxsplit=1)[0].strip() or None


def etapa_alcancada(raw: Dict[str, Any]) -> int:
    """
    Etapa mais avançada que o lead atingiu (0 = MQL ... 5 = venda).

    A situação atual do CV perde o histórico — um lead "Cancelado" pode ter chegado a
    SQL. Por isso a regra olha também as tags e tarefas, que acumulam a trajetória.
    """
    situacao = _limpo(_nome(raw.get("situacao")))
    tags = {_limpo(_nome(t)) for t in raw.get("tags") or []}
    tarefas = {_limpo(_nome(t)) for t in raw.get("tarefa") or [] if isinstance(t, dict)}

    if raw.get("data_venda") or situacao == "vendido":
        return 5
    nivel = 0
    if situacao in ("atendimento realizado", "reserva") or "atendimento realizado" in tags:
        nivel = 4
    if (
        nivel < 3
        and ("agendado" in situacao or "opps" in situacao or situacao == "atendimento nao realizado"
             or any("agendad" in t for t in tarefas) or any("agendamento" in t for t in tags))
    ):
        nivel = 3
    if nivel < 2 and ("sql" in situacao or "mia-qualificado" in tags or any("(sql)" in t for t in tags)):
        nivel = 2
    if nivel < 1 and (
        "sal" in situacao.split("(")[-1] or "tratativa" in situacao or "vinculado ao corretor" in situacao
        or any("(sal" in t for t in tags) or "em tratativa corretor" in tags
    ):
        nivel = 1
    return nivel


# ---------------------------------------------------------------------------
# Preparação (com cache por versão da base)
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {"chave": None, "leads": []}


_ao_limpar: List[Callable[[], None]] = []


def ao_limpar_cache(funcao: Callable[[], None]) -> None:
    """Registra um cache que depende dos leads preparados (ex.: índice de identidade)."""
    _ao_limpar.append(funcao)


def limpar_cache() -> None:
    _cache.update(chave=None, leads=[])
    _cache_vendas.update(chave=None, vendas=None)
    _cache_insights.update(chave=None, linhas=[])
    for funcao in _ao_limpar:
        funcao()


def preparar_lead(raw: Dict[str, Any]) -> Dict[str, Any]:
    c = origem_rd.aplicar(classificar_lead_cv(raw), raw.get("idlead"))
    # O lead pode ter interesse em vários empreendimentos: o primeiro é o principal (atribui a venda)
    # e o último é o interesse mais recente (atribui o lead, como o BI gerencial).
    lista = raw.get("empreendimento")
    nomes: List[str] = []
    for item in (lista if isinstance(lista, list) else [lista]):
        nome = unificar_empreendimento(_nome(item))
        if nome and nome not in nomes:
            nomes.append(nome)
    emp = nomes[0] if nomes else None
    data_venda = _data(raw.get("data_venda"))
    try:
        valor = float(raw.get("valor_venda") or 0)
    except (TypeError, ValueError):
        valor = 0.0

    return {
        "id": raw.get("idlead"),
        # O lead conta na data de CADASTRO e em cada interesse, como no BI da gestão (ver
        # _expandir_por_interesse). "data_conversao" guarda a última conversão, usada nas telas que
        # olham o lead que voltou a converter.
        "data": _data(raw.get("data_cad")) or _data(raw.get("ultima_data_conversao")),
        "data_conversao": _data(raw.get("ultima_data_conversao")) or _data(raw.get("data_cad")),
        "data_cadastro": _data(raw.get("data_cad")),
        "empreendimento_lead": nomes[-1] if nomes else EMPREENDIMENTO_DESCONHECIDO,
        "praca_lead": (praca_do_empreendimento(nomes[-1]) if nomes else None) or "Não identificada",
        "empreendimento": emp or EMPREENDIMENTO_DESCONHECIDO,
        "praca": praca_do_empreendimento(emp) or "Não identificada",
        # Sem a base de reservas não se sabe a unidade comprada: fica o empreendimento principal
        "empreendimento_comprado": emp or EMPREENDIMENTO_DESCONHECIDO,
        "praca_comprada": praca_do_empreendimento(emp) or "Não identificada",
        "empreendimentos": nomes or [EMPREENDIMENTO_DESCONHECIDO],
        "pracas": list(dict.fromkeys(praca_do_empreendimento(n) or "Não identificada" for n in nomes)) or ["Não identificada"],
        "canal": c.canal,
        "canal_label": c.canal_label,
        "grupo": c.grupo,
        "online": c.online,
        "confianca": c.confianca,
        "evidencia": c.evidencia,
        "campanha": c.campanha,
        "etapa": etapa_alcancada(raw),
        "vendido": bool(data_venda),
        "data_venda": data_venda,
        "valor_venda": valor if data_venda else 0.0,
        "situacao": _nome(raw.get("situacao")),
        "motivo_perda": _nome(raw.get("motivo_cancelamento")),
        "tem_email": bool(raw.get("email")),
        "tem_utm": bool(c.utm_source),
        "link": raw.get("link_interesses") or raw.get("link_interacoes"),
    }


def leads_preparados() -> List[Dict[str, Any]]:
    base = bases.carregar("cv_leads") or {}
    chave = f"{base.get('dados_de')}|{base.get('atualizado_em')}|{base.get('total')}|{origem_rd.versao()}"
    if _cache["chave"] != chave:
        _cache.update(chave=chave, leads=[preparar_lead(r) for r in base.get("registros") or []])
    return _cache["leads"]


# ---------------------------------------------------------------------------
# Vendas (reservas do CV)
# ---------------------------------------------------------------------------

_cache_vendas: Dict[str, Any] = {"chave": None, "vendas": None}

SEM_LEAD_EVIDENCIA = "A reserva não tem lead associado e o e-mail e o telefone do titular não estão em nenhum lead do CV."


def _lead_da_reserva(reserva: Dict[str, Any], idx: Any) -> tuple:
    """Lead de quem comprou: o associado à reserva; senão, o lead com o e-mail ou o telefone do titular."""
    for idlead in reserva.get("leads_associados") or []:
        if idx.tem(idlead):
            return idx.lead(str(idlead)), "lead_associado"
    for tipo, rotulo, valor in (
        ("email", "email", clean_email(reserva.get("titular_email"))),
        ("fone", "telefone", clean_phone(reserva.get("titular_telefone"))),
    ):
        achados = idx.mapa(tipo).get(valor) if valor else None
        if achados:
            return max(achados, key=lambda l: l["data"] or date.min), rotulo  # a pessoa pode ter mais de um lead
    return None, "sem_lead"


def preparar_venda(reserva: Dict[str, Any], idx: Any) -> Dict[str, Any]:
    """
    Uma venda por reserva vendida, com a data, a unidade e o valor do contrato. Carrega os dois empreendimentos:
    o da unidade comprada e o de interesse do lead (onde o BI gerencial conta a venda).
    Nunca leva os dados do titular.
    """
    comprado = unificar_empreendimento(reserva.get("empreendimento")) or EMPREENDIMENTO_DESCONHECIDO
    praca_comprada = praca_do_empreendimento(comprado) or "Não identificada"
    lead, ligacao = _lead_da_reserva(reserva, idx)
    venda = {
        "idreserva": str(reserva.get("idreserva")),
        "data_venda": _data(reserva.get("data_venda")),
        "valor_venda": float(reserva.get("valor_contrato") or reserva.get("vgv_tabela") or 0),
        "vendido": True,
        "etapa": len(ETAPAS) - 1,
        "empreendimento_comprado": comprado,
        "praca_comprada": praca_comprada,
        "unidade": " · ".join(str(p) for p in (reserva.get("bloco"), reserva.get("unidade")) if p) or None,
        "midia_reserva": reserva.get("midia"),
        "tipo_venda": reserva.get("tipo_venda"),
        "corretor": reserva.get("corretor"),
        "situacao": reserva.get("situacao"),
        "motivo_perda": None,
        "ligacao": ligacao,
    }
    if not lead:
        return {
            **venda, "id": None, "data": None, "data_cadastro": None,
            "empreendimento": comprado, "praca": praca_comprada, "empreendimentos": [comprado],
            "canal": "sem_lead", "canal_label": "Venda sem lead no CV", "grupo": "nao_rastreado", "online": False,
            "confianca": "nenhuma", "evidencia": SEM_LEAD_EVIDENCIA, "campanha": None, "link": None,
            "outro_empreendimento": False,
        }
    return {
        **venda,
        **{k: lead[k] for k in ("id", "data", "data_cadastro", "empreendimento", "praca", "empreendimentos", "canal",
                                "canal_label", "grupo", "online", "confianca", "evidencia", "campanha", "link")},
        "outro_empreendimento": lead["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO and comprado != lead["empreendimento"],
    }


def vendas_preparadas() -> Optional[List[Dict[str, Any]]]:
    """Vendas das reservas do CV. None quando a base de reservas não existe (as vendas vêm da data de venda do lead)."""
    base = bases.carregar("cv_reservas") or {}
    registros = base.get("registros") or []
    if not registros:
        return None
    from engine import identidade  # identidade depende deste módulo

    idx = identidade.indice()
    chave = f"{base.get('dados_de')}|{base.get('atualizado_em')}|{base.get('total')}|{id(idx)}"
    if _cache_vendas["chave"] != chave:
        vendas = [preparar_venda(r, idx) for r in registros if r.get("vendida") and _data(r.get("data_venda"))]
        _cache_vendas.update(chave=chave, vendas=vendas)
    return _cache_vendas["vendas"]


# ---------------------------------------------------------------------------
# Investimento das plataformas
# ---------------------------------------------------------------------------


_cache_insights: Dict[str, Any] = {"chave": None, "linhas": []}


def _insights_com_empreendimento(catalogo: List[str]) -> List[Dict[str, Any]]:
    """Linhas de investimento com o empreendimento. Guardado até a base ou o catálogo mudarem (era o maior custo do BI)."""
    chave = "|".join(
        f"{(bases.carregar(k) or {}).get('atualizado_em')}:{(bases.carregar(k) or {}).get('total')}" for k in ("meta_insights", "google_insights")
    ) + "#" + "|".join(catalogo)
    if _cache_insights["chave"] == chave:
        return _cache_insights["linhas"]
    linhas = []
    for chave in ("meta_insights", "google_insights"):
        for row in bases.registros(chave):
            texto_conta = re.sub(r"[-_]", " ", row.get("conta_nome") or "")
            texto_camp = re.sub(r"[-_]", " ", row.get("campanha_nome") or "")
            emp = match_empreendimento(texto_conta, catalogo) or match_empreendimento(texto_camp, catalogo)
            linhas.append({**row, "empreendimento": emp or EMPREENDIMENTO_DESCONHECIDO, "data_d": _data(row.get("data"))})
    _cache_insights.update(chave=chave, linhas=linhas)
    return linhas


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------


def _granularidade(inicio: date, fim: date) -> str:
    return "mes" if (fim - inicio).days > 92 else "semana"


def _chave_periodo(d: date, granularidade: str) -> str:
    if granularidade == "mes":
        return f"{d.year}-{d.month:02d}"
    segunda = d - timedelta(days=d.weekday())
    return segunda.isoformat()


def _rotulo_periodo(chave: str, granularidade: str) -> str:
    if granularidade == "mes":
        ano, mes = chave.split("-")
        return f"{MESES[int(mes) - 1]}/{ano[2:]}"
    d = date.fromisoformat(chave)
    return f"{d.day:02d}/{d.month:02d}"


def _funil(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    total = len(leads)
    etapas = []
    anterior = total
    for nivel, (chave, label) in enumerate(ETAPAS):
        qtd = sum(1 for l in leads if l["etapa"] >= nivel)
        etapas.append({
            "etapa": chave,
            "label": label,
            "leads": qtd,
            "pct_do_topo": _pct(qtd, total),
            "pct_da_etapa_anterior": _pct(qtd, anterior) if nivel else None,
        })
        anterior = qtd
    return etapas


def _unicos_por_id(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove a expansão por interesse sem perder a etapa mais avançada da pessoa."""
    unicos: Dict[Any, Dict[str, Any]] = {}
    for lead in leads:
        chave = lead.get("id")
        if chave not in unicos or lead["etapa"] > unicos[chave]["etapa"]:
            unicos[chave] = lead
    return list(unicos.values())


REGRA_LEADS = (
    "O KPI de leads usa a data de cadastro no CV e conta um interesse por empreendimento. "
    "Pessoas únicas remove a duplicidade de quem tem interesse em mais de um produto; última conversão "
    "é exibida separadamente e não substitui a data de cadastro."
)


def _expandir_por_interesse(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Um lead vira uma linha por empreendimento de interesse.

    É assim que o BI da gestão conta, e é o que faz a soma das praças fechar com o total. O lead
    sem interesse registrado continua valendo por um.
    """
    saida: List[Dict[str, Any]] = []
    for l in leads:
        nomes = l.get("empreendimentos") or [EMPREENDIMENTO_DESCONHECIDO]
        for nome in nomes:
            saida.append({**l, "empreendimento_lead": nome,
                          "praca_lead": praca_do_empreendimento(nome) or "Não identificada"})
    return saida


def calcular_bi(
    inicio: date,
    fim: date,
    empreendimentos: Optional[Iterable[str]] = None,
    pracas: Optional[Iterable[str]] = None,
    grupos: Optional[Iterable[str]] = None,
    canais: Optional[Iterable[str]] = None,
    escopo: str = "tudo",
) -> Dict[str, Any]:
    """escopo="online" restringe leads, vendas, funil e tabelas aos leads de mídia online."""
    todos = leads_preparados()
    emp_f = set(empreendimentos or [])
    praca_f = set(pracas or [])
    grupo_f = set(grupos or [])
    canal_f = set(canais or [])
    so_online = escopo == "online"

    def passa(l: Dict[str, Any], so_principal: bool = False) -> bool:
        # Lead: empreendimento de interesse mais recente. Venda: empreendimento principal.
        emps_l = [l["empreendimento"]] if so_principal else [l["empreendimento_lead"]]
        pracas_l = [l["praca"]] if so_principal else [l["praca_lead"]]
        return (
            (not so_online or l["online"])
            and (not emp_f or any(e in emp_f for e in emps_l))
            and (not praca_f or any(p in praca_f for p in pracas_l))
            and (not grupo_f or l["grupo"] in grupo_f)
            and (not canal_f or l["canal"] in canal_f)
        )

    dias = (fim - inicio).days + 1
    ant_fim = inicio - timedelta(days=1)
    ant_inicio = ant_fim - timedelta(days=dias - 1)

    # Leads online: a mesma regra do Power BI da gestão e da apresentação (conversão do período, origem da mídia da
    # conversão), para as telas, a apresentação e o BI mostrarem o mesmo número. Sem a base de conversões, ou fora do
    # escopo online, vale a regra antiga (data de cadastro, uma linha por interesse).
    usa_regra_bi = so_online and bool(bases.registros("cv_conversoes"))
    if usa_regra_bi:
        from engine import leads_bi

        def _leads_regra_bi(ini: date, fi: date) -> List[Dict[str, Any]]:
            return [
                l for l in leads_bi.leads_do_bi(ini, fi, emp_f, praca_f, completo=True)
                if (not grupo_f or l["grupo"] in grupo_f) and (not canal_f or l["canal"] in canal_f)
            ]

        leads, leads_ant = _leads_regra_bi(inicio, fim), _leads_regra_bi(ant_inicio, ant_fim)
        filtrados = leads + leads_ant
    else:
        # Cada interesse vira uma linha antes do filtro para permitir a leitura por produto.
        filtrados = [l for l in _expandir_por_interesse(todos) if passa(l)]
        leads = [l for l in filtrados if l["data"] and inicio <= l["data"] <= fim]
        leads_ant = [l for l in filtrados if l["data"] and ant_inicio <= l["data"] <= ant_fim]
    pessoas_unicas = len({l["id"] for l in leads})
    ultimas_conversoes = [
        l for l in filtrados
        if l["data_conversao"] and inicio <= l["data_conversao"] <= fim
    ]
    # A definição do MQL do Power BI Moura Leite é sempre online. Ela não deve mudar quando o usuário
    # alterna o escopo geral da página para incluir canais offline.
    movimentacoes = _unicos_por_id([l for l in ultimas_conversoes if l["online"]])
    # Vendas das reservas do CV (data, unidade e valor de cada venda); sem essa base, da data de venda do lead
    reservas = vendas_preparadas()
    fonte_vendas = "reservas" if reservas is not None else "leads"
    todas_vendas = reservas if reservas is not None else [l for l in todos if l["vendido"]]
    # Regra do BI gerencial: a venda conta no empreendimento de interesse do lead que comprou
    vendidos = [v for v in todas_vendas if passa(v, so_principal=True)]
    vendas = [v for v in vendidos if inicio <= v["data_venda"] <= fim]
    vendas_ant = [v for v in vendidos if ant_inicio <= v["data_venda"] <= ant_fim]
    # Unidades vendidas: a venda conta no empreendimento da unidade comprada e respeita o escopo online.
    unidades = [
        v for v in todas_vendas
        if inicio <= v["data_venda"] <= fim
        and (not so_online or v["online"])
        and (not emp_f or v["empreendimento_comprado"] in emp_f)
        and (not praca_f or v["praca_comprada"] in praca_f)
    ]

    def resumo_leads(lista):
        por_grupo = Counter(l["grupo"] for l in lista)
        online = sum(1 for l in lista if l["online"])
        return {
            "leads": len(lista),
            "online": online,
            "pct_online": _pct(online, len(lista)),
            "pago": por_grupo["online_pago"],
            "organico": por_grupo["online_organico"],
            "indicacao_digital": por_grupo["indicacao_digital"],
            "offline": por_grupo["offline"],
            "nao_rastreado": por_grupo["nao_rastreado"],
            "pct_nao_rastreado": _pct(por_grupo["nao_rastreado"], len(lista)),
        }

    def resumo_vendas(lista):
        online = [l for l in lista if l["online"]]
        return {
            "vendas": len(lista),
            "vgv": round(sum(l["valor_venda"] for l in lista), 2),
            "vendas_online": len(online),
            "vgv_online": round(sum(l["valor_venda"] for l in online), 2),
            "pct_vendas_online": _pct(len(online), len(lista)),
            "vendas_nao_rastreadas": sum(1 for l in lista if l["grupo"] == "nao_rastreado"),
        }

    atual = {**resumo_leads(leads), **resumo_vendas(vendas)}
    anterior = {**resumo_leads(leads_ant), **resumo_vendas(vendas_ant)}
    kpis = {
        **atual,
        "anterior": anterior,
        "variacao": {k: _variacao(atual[k], anterior[k]) for k in ("leads", "online", "vendas", "vgv", "vendas_online")},
        # Coorte: dos leads online cadastrados no período, quantos já viraram venda
        "conversao_coorte_online": _pct(sum(1 for l in leads if l["online"] and l["vendido"]), atual["online"]),
        "conversao_coorte_geral": _pct(sum(1 for l in leads if l["vendido"]), len(leads)),
        "fonte_vendas": fonte_vendas,
        # Vendas contadas pela regra do BI que foram de unidades de outro empreendimento
        "vendas_outro_empreendimento": sum(1 for v in vendas if v.get("outro_empreendimento")),
        "unidades_vendidas": len(unidades),
        "vgv_unidades": round(sum(v["valor_venda"] for v in unidades), 2),
        "unidades_vendidas_online": sum(1 for v in unidades if v["online"]),
        "vgv_unidades_online": round(sum(v["valor_venda"] for v in unidades if v["online"]), 2),
        "unidades_sem_lead": sum(1 for v in unidades if v.get("ligacao") == "sem_lead"),
        "pessoas_unicas": pessoas_unicas,
        "interesses_adicionais": len(leads) - pessoas_unicas,
        # Sinal de reconciliação com relatórios que usam data de conversão. Como a base do CV guarda
        # somente a última conversão, isto não reconstrói o histórico completo de eventos.
        "ultima_conversao_pessoas": len({l["id"] for l in ultimas_conversoes}),
    }

    unidades_online = [v for v in unidades if v["online"]]
    vendas_tipo_sdr = [v for v in unidades if _limpo(v.get("tipo_venda")) == "vendas sdr"]
    vendas_tipo_sdr_online = [v for v in unidades_online if _limpo(v.get("tipo_venda")) == "vendas sdr"]
    vendas_especialistas = [v for v in unidades_online if _limpo(v.get("corretor")).startswith("especialista -")]
    vendas_sem_tipo = [v for v in unidades_online if not _nome(v.get("tipo_venda"))]
    equivalencias_bi = {
        # O Power BI Moura Leite chama de MQL o lead online cuja última conversão caiu no período.
        # Como a API do CV guarda só a última conversão, etapas anteriores continuam sendo uma
        # estimativa pelo histórico de tags/situação, não uma cópia das fatos do modelo semântico.
        "mql_ultima_conversao": len(movimentacoes),
        "sql_historico": sum(1 for l in movimentacoes if l["etapa"] >= 2),
        "opps_historico": sum(1 for l in movimentacoes if l["etapa"] >= 3),
        "atendimentos_historico": sum(1 for l in movimentacoes if l["etapa"] >= 4),
        "unidades_vendidas": len(unidades_online),
        "vgv_unidades": round(sum(v["valor_venda"] for v in unidades_online), 2),
        "vendas_tipo_sdr": len(vendas_tipo_sdr),
        "vendas_tipo_sdr_online": len(vendas_tipo_sdr_online),
        "vgv_tipo_sdr_online": round(sum(v["valor_venda"] for v in vendas_tipo_sdr_online), 2),
        "vendas_especialistas": len(vendas_especialistas),
        "vendas_sem_tipo": len(vendas_sem_tipo),
        "vgv_sem_tipo": round(sum(v["valor_venda"] for v in vendas_sem_tipo), 2),
        "cv_leads_atualizado_em": (bases.carregar("cv_leads") or {}).get("dados_de"),
        "cv_reservas_atualizado_em": (bases.carregar("cv_reservas") or {}).get("dados_de"),
        "sql_certificado": False,
        "novo_lead_mql_certificado": False,
        "regra_novo_lead_mql": (
            "O Power BI FM&D conta a mudança para a etapa Novo Lead MQL ocorrida no período. "
            "A API atual do CV fornece o estado e a última conversão, mas não o histórico completo dessas mudanças."
        ),
        "regra_sql": (
            "Estimativa pela etapa mais avançada detectada em situação, tags e tarefas do lead. "
            "O SQL certificado dos Power BIs vem da fato de qualificações, que não está disponível na API do CV."
        ),
    }

    # ---- série temporal ----
    gran = _granularidade(inicio, fim)
    serie_map: Dict[str, Dict[str, Any]] = {}
    cursor = inicio
    while cursor <= fim:
        chave = _chave_periodo(cursor, gran)
        serie_map.setdefault(chave, {"periodo": chave, "rotulo": _rotulo_periodo(chave, gran),
                                      **{g: 0 for g in GRUPOS}, "vendas": 0, "vendas_online": 0, "vgv": 0.0})
        cursor += timedelta(days=1)
    for l in leads:
        serie_map[_chave_periodo(l["data"], gran)][l["grupo"]] += 1
    for l in vendas:
        ponto = serie_map[_chave_periodo(l["data_venda"], gran)]
        ponto["vendas"] += 1
        ponto["vendas_online"] += int(l["online"])
        ponto["vgv"] = round(ponto["vgv"] + l["valor_venda"], 2)
    serie = [serie_map[k] for k in sorted(serie_map)]

    # ---- por grupo e canal ----
    def agrupar(chave_fn, rotulo_fn):
        itens: Dict[str, Dict[str, Any]] = {}
        for l in leads:
            k = chave_fn(l)
            it = itens.setdefault(k, {"chave": k, **rotulo_fn(l), "leads": 0, "vendas_coorte": 0,
                                      "confianca": Counter(), "vendas": 0, "vgv": 0.0})
            it["leads"] += 1
            it["vendas_coorte"] += int(l["vendido"])
            it["confianca"][l["confianca"]] += 1
        for l in vendas:
            k = chave_fn(l)
            it = itens.setdefault(k, {"chave": k, **rotulo_fn(l), "leads": 0, "vendas_coorte": 0,
                                      "confianca": Counter(), "vendas": 0, "vgv": 0.0})
            it["vendas"] += 1
            it["vgv"] = round(it["vgv"] + l["valor_venda"], 2)
        saida = []
        for it in itens.values():
            saida.append({
                **it,
                "confianca": dict(it["confianca"]),
                "pct_leads": _pct(it["leads"], len(leads)),
                "conversao_coorte": _pct(it["vendas_coorte"], it["leads"]),
            })
        return sorted(saida, key=lambda x: (-x["leads"], -x["vendas"]))

    por_grupo = agrupar(lambda l: l["grupo"], lambda l: {"label": GRUPOS[l["grupo"]], "online": l["online"]})
    por_canal = agrupar(
        lambda l: l["canal"],
        lambda l: {"label": l["canal_label"], "grupo": l["grupo"], "grupo_label": GRUPOS[l["grupo"]], "online": l["online"]},
    )

    # ---- investimento das plataformas ----
    catalogo = bases.registros("cv_empreendimentos")
    brutos_ins = _insights_com_empreendimento(catalogo)
    if usa_regra_bi:
        # Mesmo custo da apresentação: campanha que atende mais de um produto é repartida pelo custo de cada grupo de recursos
        # (ou, sem isso, pelos leads de cada produto), para o produto não ficar com lead e sem custo.
        from engine import apresentacao as _ap, leads_bi as _lb

        janela = [r for r in _ap.insights_resolvidos(brutos_ins) if r["data_d"] and inicio <= r["data_d"] <= fim]
        brutos_ins, _ = _ap.ratear_sem_produto(janela, _lb.leads_do_bi(inicio, fim, set(), set()), _ap._grupos_de_recursos())
    insights = [
        r for r in brutos_ins
        if r["data_d"] and inicio <= r["data_d"] <= fim and (not emp_f or r["empreendimento"] in emp_f)
        and (not praca_f or (praca_do_empreendimento(r["empreendimento"]) or "Não identificada") in praca_f)
    ]
    invest_emp: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in insights:
        invest_emp[r["empreendimento"]][f"invest_{r['plataforma']}"] += r["investimento"]
        invest_emp[r["empreendimento"]][f"leads_plat_{r['plataforma']}"] += r["leads_plataforma"]

    # ---- por empreendimento ----
    emps: Dict[str, Dict[str, Any]] = {}

    def emp_item(nome: str, praca: str) -> Dict[str, Any]:
        return emps.setdefault(nome, {
            "empreendimento": nome, "praca": praca, "leads": 0, "online": 0, "pago": 0, "organico": 0,
            "nao_rastreado": 0, "meta": 0, "google": 0, "vendas_coorte": 0, "vendas": 0, "vendas_online": 0, "vgv": 0.0,
            "vendas_outro_empreendimento": 0, "unidades_vendidas": 0, "unidades_vendidas_online": 0, "vgv_unidades": 0.0,
        })

    for l in leads:
        for nome in [l["empreendimento_lead"]]:
            praca = praca_do_empreendimento(nome) or "Não identificada"
            if (emp_f and nome not in emp_f) or (praca_f and praca not in praca_f):
                continue
            e = emp_item(nome, praca)
            e["leads"] += 1
            e["online"] += int(l["online"])
            e["pago"] += int(l["grupo"] == "online_pago")
            e["organico"] += int(l["grupo"] == "online_organico")
            e["nao_rastreado"] += int(l["grupo"] == "nao_rastreado")
            e["meta"] += int(l["canal"] == "meta")
            e["google"] += int(l["canal"] == "google")
            e["vendas_coorte"] += int(l["vendido"])
    for v in vendas:
        e = emp_item(v["empreendimento"], v["praca"])
        e["vendas"] += 1
        e["vendas_online"] += int(v["online"])
        e["vgv"] = round(e["vgv"] + v["valor_venda"], 2)
        e["vendas_outro_empreendimento"] += int(bool(v.get("outro_empreendimento")))
    for v in unidades:
        e = emp_item(v["empreendimento_comprado"], v["praca_comprada"])
        e["unidades_vendidas"] += 1
        e["unidades_vendidas_online"] += int(v["online"])
        e["vgv_unidades"] = round(e["vgv_unidades"] + v["valor_venda"], 2)

    por_empreendimento = []
    for nome, e in emps.items():
        inv = invest_emp.get(nome, {})
        invest_meta, invest_google = round(inv.get("invest_meta", 0), 2), round(inv.get("invest_google", 0), 2)
        por_empreendimento.append({
            **e,
            "pct_online": _pct(e["online"], e["leads"]),
            "pct_nao_rastreado": _pct(e["nao_rastreado"], e["leads"]),
            "conversao_coorte": _pct(e["vendas_coorte"], e["leads"]),
            "investimento_meta": invest_meta,
            "investimento_google": invest_google,
            "leads_segundo_meta": int(inv.get("leads_plat_meta", 0)),
            "leads_segundo_google": int(inv.get("leads_plat_google", 0)),
            # Custo por lead que CHEGOU no CRM — o custo real, não o que a plataforma reporta
            "cpl_meta_crm": round(invest_meta / e["meta"], 2) if invest_meta and e["meta"] else None,
            "cpl_google_crm": round(invest_google / e["google"], 2) if invest_google and e["google"] else None,
        })
    por_empreendimento.sort(key=lambda x: (x["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO, -x["leads"]))

    # ---- campanhas (UTM) ----
    camp: Dict[str, Dict[str, Any]] = {}
    for l in leads:
        if not l["campanha"]:
            continue
        c = camp.setdefault(l["campanha"], {"campanha": l["campanha"], "canal": l["canal_label"],
                                            "empreendimentos": Counter(), "leads": 0, "vendas_coorte": 0})
        c["leads"] += 1
        c["vendas_coorte"] += int(l["vendido"])
        c["empreendimentos"][l["empreendimento"]] += 1
    campanhas = sorted(
        ({**c, "empreendimento": c["empreendimentos"].most_common(1)[0][0], "empreendimentos": None,
          "conversao_coorte": _pct(c["vendas_coorte"], c["leads"])} for c in camp.values()),
        key=lambda x: -x["leads"],
    )[:20]

    # ---- qualidade dos dados ----
    qualidade = {
        "leads": len(leads),
        "nao_rastreado": atual["nao_rastreado"],
        "pct_nao_rastreado": atual["pct_nao_rastreado"],
        "whatsapp_sem_rastreio": sum(1 for l in leads if l["canal"] == "whatsapp_nao_rastreado"),
        "sem_origem": sum(1 for l in leads if l["canal"] == "nao_rastreado"),
        "sem_empreendimento": sum(1 for l in leads if l["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO),
        "sem_email": sum(1 for l in leads if not l["tem_email"]),
        "com_utm": sum(1 for l in leads if l["tem_utm"]),
        "pct_com_utm": _pct(sum(1 for l in leads if l["tem_utm"]), len(leads)),
        "confianca": dict(Counter(l["confianca"] for l in leads)),
        "vendas_sem_origem": atual["vendas_nao_rastreadas"],
        "pct_vendas_sem_origem": _pct(atual["vendas_nao_rastreadas"], atual["vendas"]),
    }

    motivos = Counter(l["motivo_perda"] for l in leads if l["online"] and l["motivo_perda"])
    total_motivos = sum(motivos.values())

    # ---- avisos de interpretação ----
    avisos = []
    base_cv = bases.carregar("cv_leads") or {}
    inicio_base = _data((base_cv.get("periodo") or {}).get("inicio"))
    if fonte_vendas == "leads" and inicio_base and inicio - timedelta(days=180) < inicio_base:
        avisos.append(
            f"Vendas contam apenas leads cadastrados desde {inicio_base:%d/%m/%Y} (início da base). "
            "Vendas de leads mais antigos que isso não aparecem."
        )
    if emp_f and kpis["vendas_outro_empreendimento"]:
        avisos.append(
            f"{kpis['vendas_outro_empreendimento']} venda(s) contada(s) aqui pela regra do BI gerencial (empreendimento "
            "de interesse do lead) foram de unidades de outro empreendimento. \"Unidades vendidas\" mostra o que foi "
            "comprado neste empreendimento."
        )
    if (date.today() - fim).days < 90:
        avisos.append(
            "A conversão por coorte dos últimos 90 dias ainda está amadurecendo: leads recentes costumam "
            "virar venda meses depois do cadastro."
        )
    if not insights:
        avisos.append("Sem dados de investimento de Meta/Google no período — custo por lead indisponível.")
    distintos = len({l["id"] for l in leads})
    if distintos != len(leads):
        avisos.append(
            f"{len(leads) - distintos} interesse(s) a mais que leads: {distintos} pessoa(s) se cadastraram "
            "interessadas em mais de um empreendimento e contam em cada produto. A venda "
            "continua contando uma vez, no empreendimento de interesse do lead."
        )

    return {
        "periodo": {
            "inicio": inicio.isoformat(), "fim": fim.isoformat(),
            "anterior_inicio": ant_inicio.isoformat(), "anterior_fim": ant_fim.isoformat(),
            "granularidade": gran,
            "escopo": "online" if so_online else "tudo",
        },
        "kpis": kpis,
        "regra_leads": (
            "Leads online como no Power BI da gestão: o lead conta no período em que converteu (última conversão), no empreendimento "
            "da última conversão, com a origem da mídia daquela conversão. Origens offline (corretor, indicação) ficam de fora."
            if usa_regra_bi else REGRA_LEADS
        ),
        "regra_leads_bi": usa_regra_bi,
        "serie": serie,
        "por_grupo": por_grupo,
        "por_canal": por_canal,
        "por_empreendimento": por_empreendimento,
        "funil": {"todos": _funil(leads), "online": _funil([l for l in leads if l["online"]])},
        "funil_movimentacao": _funil(movimentacoes),
        "equivalencias_bi": equivalencias_bi,
        # Mesmo funil no período anterior de mesmo tamanho: base da comparação etapa a etapa
        "funil_anterior": _funil([l for l in leads_ant if l["online"]]),
        "campanhas": campanhas,
        "motivos_perda_online": [
            {"motivo": m, "leads": q, "pct": _pct(q, total_motivos)} for m, q in motivos.most_common(8)
        ],
        "qualidade": qualidade,
        "investimento": {
            "meta": round(sum(r["investimento"] for r in insights if r["plataforma"] == "meta"), 2),
            "google": round(sum(r["investimento"] for r in insights if r["plataforma"] == "google"), 2),
            "leads_segundo_meta": sum(r["leads_plataforma"] for r in insights if r["plataforma"] == "meta"),
            "leads_segundo_google": sum(r["leads_plataforma"] for r in insights if r["plataforma"] == "google"),
            "disponivel": bool(insights),
            # Conta a conta: é o que permite ver qual pedaço bate com o BI da agência, que só tem a
            # Meta das contas dela.
            "por_conta": _investimento_por_conta(insights),
        },
        "legenda": {
            "grupos": [{"grupo": g, "label": GRUPOS[g], "online": g in GRUPOS_ONLINE} for g in GRUPOS],
            "canais": [{"canal": c, "label": l, "grupo": g} for c, (l, g) in CANAIS.items()],
        },
        "opcoes": {
            "empreendimentos": sorted({e for l in todos for e in l["empreendimentos"]}, key=lambda n: (n == EMPREENDIMENTO_DESCONHECIDO, n)),
            "pracas": sorted({p for l in todos for p in l["pracas"]}),
            "canais": sorted({(l["canal"], l["canal_label"]) for l in todos}, key=lambda x: x[1]),
        },
        "bases": [bases.resumo(b) for b in ("cv_leads", "cv_reservas", "cv_empreendimentos", "meta_insights", "google_insights")],
        "avisos": avisos,
    }


def _investimento_por_conta(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Investimento de cada conta de anúncio no período, da maior para a menor."""
    contas: Dict[tuple, Dict[str, Any]] = {}
    for r in insights:
        chave = (r["plataforma"], r.get("conta_nome") or r.get("conta_id"))
        item = contas.setdefault(chave, {
            "plataforma": r["plataforma"], "conta": chave[1], "empreendimento": r["empreendimento"],
            "praca": praca_do_empreendimento(r["empreendimento"]) or "Não identificada",
            "investimento": 0.0, "leads_plataforma": 0,
        })
        item["investimento"] += r["investimento"] or 0
        item["leads_plataforma"] += r["leads_plataforma"] or 0
    for item in contas.values():
        item["investimento"] = round(item["investimento"], 2)
    return sorted(contas.values(), key=lambda c: -c["investimento"])


def opcoes() -> Dict[str, Any]:
    """Valores disponíveis para os filtros (independem do período)."""
    todos = leads_preparados()
    return {
        "empreendimentos": sorted({e for l in todos for e in l["empreendimentos"]}, key=lambda n: (n == EMPREENDIMENTO_DESCONHECIDO, n)),
        "pracas": sorted({p for l in todos for p in l["pracas"]}),
        "canais": [{"canal": c, "label": l} for c, l in sorted({(l["canal"], l["canal_label"]) for l in todos}, key=lambda x: x[1])],
    }


def leads_detalhe(
    inicio: date,
    fim: date,
    empreendimento: Optional[str] = None,
    canal: Optional[str] = None,
    grupo: Optional[str] = None,
    etapa_minima: Optional[int] = None,
    vendidos: bool = False,
    limite: int = 500,
    escopo: str = "tudo",
    criterio: str = "interesse",
    so_outro_empreendimento: bool = False,
) -> Dict[str, Any]:
    """
    Lista auditável por trás de qualquer número do BI: cada lead com a evidência da
    classificação e o link para abrir no CV. Sem nome, e-mail ou telefone.

    Vendas: criterio="interesse" filtra pelo empreendimento de interesse do lead (regra do BI gerencial);
    criterio="comprado" filtra pelo empreendimento da unidade vendida. O escopo online vale nos dois critérios.
    """
    if vendidos:
        return _vendas_detalhe(inicio, fim, empreendimento, canal, grupo, limite, escopo, criterio, so_outro_empreendimento)
    itens = []
    for l in leads_preparados():
        data_ref = l["data_venda"] if vendidos else l["data"]
        if not data_ref or not (inicio <= data_ref <= fim):
            continue
        if vendidos and not l["vendido"]:
            continue
        if escopo == "online" and not l["online"]:
            continue
        if empreendimento and empreendimento != (l["empreendimento"] if vendidos else l["empreendimento_lead"]):
            continue
        if canal and l["canal"] != canal:
            continue
        if grupo and l["grupo"] != grupo:
            continue
        if etapa_minima is not None and l["etapa"] < etapa_minima:
            continue
        itens.append({
            **l,
            "data": l["data"].isoformat() if l["data"] else None,
            "data_venda": l["data_venda"].isoformat() if l["data_venda"] else None,
            "etapa_label": ETAPAS[l["etapa"]][1],
        })
    itens.sort(key=lambda x: (x["data_venda"] or x["data"] or ""), reverse=True)
    return {"total": len(itens), "itens": itens[:limite], "truncado": len(itens) > limite}


def _vendas_detalhe(
    inicio: date, fim: date, empreendimento: Optional[str], canal: Optional[str], grupo: Optional[str],
    limite: int, escopo: str, criterio: str, so_outro_empreendimento: bool,
) -> Dict[str, Any]:
    """Cada venda com a unidade, os dois empreendimentos (comprado e de interesse), a origem do lead e como foi ligada."""
    reservas = vendas_preparadas()
    fonte = reservas if reservas is not None else [l for l in leads_preparados() if l["vendido"]]
    comprado = criterio == "comprado"
    itens = []
    for v in fonte:
        if not (inicio <= v["data_venda"] <= fim):
            continue
        if escopo == "online" and not v["online"]:
            continue
        if empreendimento and empreendimento != (v["empreendimento_comprado"] if comprado else v["empreendimento"]):
            continue
        if (canal and v["canal"] != canal) or (grupo and v["grupo"] != grupo):
            continue
        if so_outro_empreendimento and not v.get("outro_empreendimento"):
            continue
        itens.append({
            **{k: (x.isoformat() if isinstance(x, date) else x) for k, x in v.items()},
            "etapa_label": ETAPAS[v["etapa"]][1],
        })
    itens.sort(key=lambda x: x["data_venda"] or "", reverse=True)
    return {"total": len(itens), "itens": itens[:limite], "truncado": len(itens) > limite}
