"""
Apresentação semanal: tudo o que a reunião de segunda precisa, compilado numa resposta só.

O período é o do mês em andamento (do dia 1 até a data de corte) e a comparação é o MESMO intervalo
do mês anterior (01 a 23 contra 01 a 23): é a única comparação justa para um mês que ainda não fechou.

Nada aqui recalcula regra de negócio: leads, origem e etapa vêm do BI (`bi`), os anúncios da
auditoria (`anuncios`), as palavras do Google de `palavras` e o site de `audiencia`. Este módulo só
junta, compara e escolhe o que mostrar — para o número da apresentação ser o mesmo da tela de origem.
"""

import calendar
import json
import math
import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from collections import Counter
from engine import anuncios, audiencia, bases, bi, criativo_info, origem_rd, palavras
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO, cidades_do_catalogo, match_empreendimento
from engine.taxonomy import utms_do_lead

FONTES = (
    ("meta", "Meta Ads"),
    ("google", "Google Ads"),
    ("organico", "Orgânico"),
    ("indicacao", "Indicação (Indique e Ganhe)"),
    ("pago_outro", "Outras mídias pagas"),
)
ROTULO_FONTE = dict(FONTES)

TERMO_AGRUPADO = "outros termos"
SEM_UTM = "Sem UTM no CV"


# ---------------------------------------------------------------------------
# Período
# ---------------------------------------------------------------------------


def mes_anterior(d: date) -> date:
    """O mesmo dia no mês anterior; num mês mais curto, o último dia dele."""
    ano, mes = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def periodo_de_comparacao(inicio: date, fim: date) -> Tuple[date, date]:
    return mes_anterior(inicio), mes_anterior(fim)


def minimos(dias: int) -> Dict[str, float]:
    """
    Amostra mínima para ranquear anúncio. A tela de Anúncios usa 5 leads / R$ 100 / 10 leads para 30
    dias; no começo do mês, exigir isso deixaria todos os rankings vazios, então a régua acompanha os dias.
    """
    fator = min(max(dias, 1), 30) / 30
    return {
        "leads_cpl": max(3, math.ceil(anuncios.MIN_LEADS_CPL * fator)),
        "investimento_cpl": max(50.0, round(anuncios.MIN_INVESTIMENTO_CPL * fator)),
        "leads_conversao": max(3, math.ceil(anuncios.MIN_LEADS_CONVERSAO * fator * 0.5)),
    }


def _div(a: float, b: float, casas: int = 2) -> Optional[float]:
    return round(a / b, casas) if b else None


def _pct(parte: float, total: float) -> Optional[float]:
    return round(parte / total * 100, 1) if total else None


def _variacao(atual: Optional[float], anterior: Optional[float]) -> Optional[float]:
    if atual is None or not anterior:
        return None
    return round((atual - anterior) / anterior * 100, 1)


# ---------------------------------------------------------------------------
# Leads e investimento (as mesmas regras do BI)
# ---------------------------------------------------------------------------


def fonte_do_lead(lead: Dict[str, Any]) -> str:
    if lead["canal"] in ("meta", "google"):
        return lead["canal"]
    return {"online_organico": "organico", "indicacao_digital": "indicacao"}.get(lead["grupo"], "pago_outro")


def _passa(emp: str, praca: str, emp_f: Set[str], praca_f: Set[str]) -> bool:
    return (not emp_f or emp in emp_f) and (not praca_f or praca in praca_f)


def _leads_do_periodo(expandidos: List[Dict[str, Any]], inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]):
    """Leads online cadastrados no período, um por empreendimento de interesse — como o BI da gestão conta."""
    return [
        l for l in expandidos
        if l["online"] and l["data"] and inicio <= l["data"] <= fim
        and _passa(l["empreendimento_lead"], l["praca_lead"], emp_f, praca_f)
    ]


def insights_resolvidos(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Investimento sem empreendimento ganha a praça pelo nome da campanha ou da conta.

    A campanha "avare_google-pmax_lancamento" roda numa conta que atende dois produtos de Avaré: não dá para
    escolher um deles, mas é de Avaré. Sem isso, esse gasto some ao filtrar por praça e cai em "Não identificado".
    Fica como "Avaré - Campanha sem produto definido": a praça vale, o produto não é chutado.
    """
    catalogo = bases.registros("cv_empreendimentos")
    cidades = cidades_do_catalogo(catalogo)
    cache: Dict[Any, Tuple[str, str]] = {}
    saida = []
    for r in insights:
        if r["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO:
            emp, praca = palavras.local_da_linha(r, catalogo, cidades, cache, palavras.CAMPOS_GOOGLE)
            if emp != EMPREENDIMENTO_DESCONHECIDO:
                r = {**r, "empreendimento": emp}
            elif praca and praca != palavras.PRACA_DESCONHECIDA:
                r = {**r, "empreendimento": f"{praca} - Campanha sem produto definido"}
        saida.append(r)
    return saida


SEM_PRODUTO = "Campanha sem produto definido"


def empreendimento_curto_py(nome: str) -> str:
    """"Avaré - Reserva Central Parque II - 14000" -> "Reserva Central Parque II"."""
    partes = re.split(r"\s+-\s+", nome)
    return " - ".join(partes[1:-1]) if len(partes) >= 3 else nome



def _palavras_do_nome(texto: Any) -> Set[str]:
    return set(bi._limpo(re.sub(r"[_\-/]+", " ", str(texto or ""))).split())


def produto_do_grupo(nome_grupo: str, candidatos: List[str]) -> Optional[str]:
    """
    A que produto pertence o grupo de recursos "reserva_google-pmax_..." ou "central_google-pmax_...".
    "reserva" no nome manda para os produtos "Reserva ..."; sem ela, para os que não são "Reserva ...". Se ainda restar mais
    de um, vale o que tem mais palavras do nome do produto no grupo; empate não é decidido (devolve None).
    """
    palavras_grupo = _palavras_do_nome(nome_grupo)
    tem_reserva = "reserva" in palavras_grupo
    cand = [c for c in candidatos if ("reserva" in bi._limpo(c)) == tem_reserva] or []
    if len(cand) == 1:
        return cand[0]
    pontos = {c: len(_palavras_do_nome(empreendimento_curto_py(c)) & palavras_grupo) for c in cand}
    melhor = max(pontos.values(), default=0)
    escolhidos = [c for c, pt in pontos.items() if pt == melhor and melhor > 0]
    return escolhidos[0] if len(escolhidos) == 1 else None


def _grupos_de_recursos() -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    """Custo de cada grupo de recursos do Performance Max por conta, campanha e dia (o Google informa de cada um)."""
    indice: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for g in bases.registros("google_anuncios"):
        if g.get("canal") == "Performance Max":
            indice.setdefault((g.get("conta_nome") or "", g.get("campanha_nome") or "", str(g.get("data"))[:10]), []).append(g)
    return indice


def ratear_sem_produto(
    insights: List[Dict[str, Any]], leads: List[Dict[str, Any]], grupos: Optional[Dict[Tuple[str, str, str], List[Dict[str, Any]]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Reparte o custo de campanha que atende mais de um produto da praça.

    1) Pelo custo de cada grupo de recursos, quando o Google o informa e o nome do grupo diz o produto
       (`central_...`, `reserva_...`): é custo MEDIDO, não estimado.
    2) Sem isso, pelos leads que cada produto recebeu da plataforma: aí é ESTIMATIVA.
    Sem nenhum dos dois, o custo fica em "sem produto definido".
    Devolve (linhas com o custo repartido, o resumo do que foi repartido e por qual método).
    """
    produtos_da_praca: Dict[str, Set[str]] = {}
    for r in insights:
        if not r["empreendimento"].endswith(SEM_PRODUTO) and r["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO:
            produtos_da_praca.setdefault(bi.praca_do_empreendimento(r["empreendimento"]) or "", set()).add(r["empreendimento"])

    saida: List[Dict[str, Any]] = []
    resumo: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def somar(praca: str, plataforma: str, metodo: str, produto: str, valor: float) -> None:
        item = resumo.setdefault((praca, plataforma, metodo), {"praca": praca, "plataforma": plataforma, "metodo": metodo, "valor": 0.0, "produtos": {}})
        item["valor"] += valor
        item["produtos"][produto] = item["produtos"].get(produto, 0) + valor

    for r in insights:
        if not r["empreendimento"].endswith(SEM_PRODUTO) or r["plataforma"] not in ("google", "meta"):
            saida.append(r)
            continue
        praca = bi.praca_do_empreendimento(r["empreendimento"]) or ""
        pesos: Dict[str, int] = {}
        for l in leads:
            if l["canal"] == r["plataforma"] and l["praca_lead"] == praca:
                pesos[l["empreendimento_lead"]] = pesos.get(l["empreendimento_lead"], 0) + 1
        candidatos = sorted(produtos_da_praca.get(praca, set()) | set(pesos))

        # 1) custo medido por grupo de recursos
        partes: Dict[str, Dict[str, float]] = {}
        for g in (grupos or {}).get((r.get("conta_nome") or "", r.get("campanha_nome") or "", str(r.get("data"))[:10]), []):
            produto = produto_do_grupo(g.get("anuncio_nome") or "", candidatos)
            if produto:
                x = partes.setdefault(produto, {"investimento": 0.0, "impressoes": 0, "cliques": 0, "leads_plataforma": 0})
                x["investimento"] += g.get("investimento") or 0
                x["impressoes"] += g.get("impressoes") or 0
                x["cliques"] += g.get("cliques") or 0
                x["leads_plataforma"] += int(round(g.get("conversoes") or 0))
        if partes and sum(x["investimento"] for x in partes.values()) >= 0.5 * (r.get("investimento") or 0):
            for produto, x in partes.items():
                saida.append({**r, "empreendimento": produto, "rateado": "grupo", **x})
                somar(praca, r["plataforma"], "grupo", produto, x["investimento"])
            continue

        # 2) estimativa pelos leads de cada produto
        total = sum(pesos.values())
        if not total:
            saida.append(r)
            continue
        for produto, n in pesos.items():
            fator = n / total
            saida.append({**r, "empreendimento": produto, "rateado": "leads",
                          **{c: (r.get(c) or 0) * fator for c in ("investimento", "impressoes", "cliques", "leads_plataforma")}})
            somar(praca, r["plataforma"], "leads", produto, (r.get("investimento") or 0) * fator)
    return saida, [
        {"praca": i["praca"], "plataforma": i["plataforma"], "metodo": i["metodo"], "valor": round(i["valor"], 2),
         "produtos": [{"empreendimento": e, "valor": round(v, 2)} for e, v in sorted(i["produtos"].items(), key=lambda x: -x[1])]}
        for i in resumo.values()
    ]


def _insights_do_periodo(insights: List[Dict[str, Any]], inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]):
    return [
        r for r in insights
        if r["data_d"] and inicio <= r["data_d"] <= fim
        and _passa(r["empreendimento"], bi.praca_do_empreendimento(r["empreendimento"]) or "Não identificada", emp_f, praca_f)
    ]


def _bloco(leads: List[Dict[str, Any]], investimento: float = 0.0) -> Dict[str, Any]:
    sql = sum(1 for l in leads if l["etapa"] >= 2)
    vendas = sum(1 for l in leads if l["vendido"])
    return {
        "leads": len(leads),
        "sql": sql,
        "pct_sql": _pct(sql, len(leads)),
        "vendas": vendas,
        "investimento": round(investimento, 2),
        "cpl": _div(investimento, len(leads)) if investimento else None,
        "custo_sql": _div(investimento, sql) if investimento else None,
    }


def _resumo(leads: List[Dict[str, Any]], insights: List[Dict[str, Any]], sqls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    invest = {"meta": 0.0, "google": 0.0}
    leads_plataforma = {"meta": 0, "google": 0}
    invest_whatsapp = 0.0
    for r in insights:
        if r["plataforma"] in invest:
            invest[r["plataforma"]] += r["investimento"] or 0
            leads_plataforma[r["plataforma"]] += r["leads_plataforma"] or 0
            if r["plataforma"] == "meta" and "whatsapp" in bi._limpo(r.get("campanha_nome")):
                invest_whatsapp += r["investimento"] or 0

    por_fonte = {chave: [l for l in leads if fonte_do_lead(l) == chave] for chave, _ in FONTES}
    fontes = {chave: _bloco(por_fonte[chave], invest.get(chave, 0.0)) for chave, _ in FONTES}
    for chave in ("meta", "google"):
        fontes[chave]["leads_plataforma"] = leads_plataforma[chave]
        fontes[chave]["cpl_plataforma"] = _div(invest[chave], leads_plataforma[chave]) if invest[chave] else None

    pagos = por_fonte["meta"] + por_fonte["google"]
    investimento = invest["meta"] + invest["google"]
    total = _bloco(leads, investimento)
    # CPL pago: investimento ÷ leads das fontes que TÊM custo. Lead de uma fonte sem custo atribuído (ex.: Google sem
    # investimento no recorte) não entra: senão o CPL pago ficaria abaixo do CPL de cada fonte, o que não existe.
    com_custo = [l for l in pagos if invest.get(fonte_do_lead(l), 0) > 0]
    total["cpl"] = _div(investimento, len(com_custo)) if investimento else None
    total["leads_pagos"] = len(pagos)
    total["leads_pagos_com_custo"] = len(com_custo)

    # Faixa do CPL: o clique no WhatsApp de anúncio já é Meta ("Click To WhatsApp | ..."). Mas uma parte do gasto vai para
    # campanha de conversa, e a conversa que chega sem rastreio entra no CV com origem "WhatsApp". O assistente marca como
    # orgânica ("mia-organico") a que veio sem anúncio; a SEM essa marca pode ser anúncio. Somar só estas dá o piso do CPL.
    leads_whatsapp = [l for l in leads if str(l.get("origem") or "").lower() == "whatsapp" and not l.get("mia_organico")]
    if invest_whatsapp > 0 and leads_whatsapp:
        fontes["meta"]["investimento_whatsapp"] = round(invest_whatsapp, 2)
        fontes["meta"]["leads_whatsapp"] = len(leads_whatsapp)
        fontes["meta"]["cpl_com_whatsapp"] = _div(invest["meta"], len(por_fonte["meta"]) + len(leads_whatsapp))
        total["leads_whatsapp"] = len(leads_whatsapp)
        total["cpl_com_whatsapp"] = _div(investimento, len(com_custo) + len(leads_whatsapp))
    total["pessoas_unicas"] = len({l["id"] for l in leads})
    if sqls is not None:
        # SQL do jeito do BI: não é subconjunto dos leads do período (inclui lead qualificado agora que converteu antes)
        por_fonte_sql = Counter(fonte_do_lead(l) for l in sqls)
        for chave, _ in FONTES:
            n = por_fonte_sql.get(chave, 0)
            leads_f = fontes[chave]["leads"]
            pct = _pct(n, leads_f)
            fontes[chave].update(sql=n, pct_sql=pct if pct is None or pct <= 100 else None,
                                 custo_sql=_div(invest.get(chave, 0.0), n) if invest.get(chave) else None)
        n = len(sqls)
        pct = _pct(n, total["leads"])
        total.update(sql=n, pct_sql=pct if pct is None or pct <= 100 else None, custo_sql=_div(investimento, n) if investimento else None)
    return {"total": total, "fontes": fontes}


def _comparar(atual: Dict[str, Any], anterior: Dict[str, Any]) -> Dict[str, Any]:
    campos = ("leads", "sql", "vendas", "investimento", "cpl", "custo_sql")
    return {
        "total": {c: _variacao(atual["total"].get(c), anterior["total"].get(c)) for c in campos},
        "fontes": {
            chave: {c: _variacao(atual["fontes"][chave].get(c), anterior["fontes"][chave].get(c)) for c in campos}
            for chave, _ in FONTES
        },
    }


def _por_empreendimento(leads: List[Dict[str, Any]], insights: List[Dict[str, Any]], limite: int, sqls: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    itens: Dict[str, Dict[str, Any]] = {}

    def item(nome: str) -> Dict[str, Any]:
        return itens.setdefault(nome, {
            "empreendimento": nome, "praca": bi.praca_do_empreendimento(nome) or "Não identificada",
            "leads": 0, "meta": 0, "google": 0, "organico": 0, "outros": 0, "sql": 0, "vendas": 0,
            "meta_ctw": 0, "meta_form": 0,
            "invest_meta": 0.0, "invest_google": 0.0,
        })

    formularios = anuncios._formularios_por_lead_cv()
    cobertas = _pracas_com_formulario_lido(formularios, leads)
    for l in leads:
        e = item(l["empreendimento_lead"])
        fonte = fonte_do_lead(l)
        e["leads"] += 1
        e[fonte if fonte in ("meta", "google", "organico") else "outros"] += 1
        if fonte == "meta":
            e["meta_form" if _tipo_do_lead_meta(l, formularios, cobertas) == "formulario" else "meta_ctw"] += 1
        e["sql"] += int(l["etapa"] >= 2)
        e["vendas"] += int(l["vendido"])
    for r in insights:
        if r["plataforma"] in ("meta", "google"):
            item(r["empreendimento"])[f"invest_{r['plataforma']}"] += r["investimento"] or 0

    if sqls is not None:
        por_emp = Counter(l["empreendimento_lead"] for l in sqls)
        for nome, e in itens.items():
            e["sql"] = por_emp.get(nome, 0)
        for nome, n in por_emp.items():
            if nome not in itens:
                item(nome)["sql"] = n
    saida = []
    for e in itens.values():
        investimento = e["invest_meta"] + e["invest_google"]
        pagos = e["meta"] + e["google"]
        saida.append({
            **e,
            "invest_meta": round(e["invest_meta"], 2), "invest_google": round(e["invest_google"], 2),
            "investimento": round(investimento, 2),
            "cpl": _div(investimento, pagos) if investimento else None,
            "pct_sql": _pct(e["sql"], e["leads"]),
            "custo_sql": _div(investimento, e["sql"]) if investimento and e["sql"] else None,
        })
    saida.sort(key=lambda e: (e["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO, -e["leads"], -e["investimento"]))
    return saida[:limite]


from engine.leads_bi import (  # noqa: E402 — regra única de leads do BI, compartilhada com as telas
    ORIGENS_META, ORIGENS_GOOGLE, ORIGENS_ONLINE_BI, _chave_origem, _ids_de_empreendimento, _lead_bruto, leads_do_bi, origem_do_bi,
)


def _origens_do_bi(leads: List[Dict[str, Any]], limite: int = 8, sqls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Origem de cada lead online com o nome que o BI usa (Facebook Ads, WhatsApp, Busca Orgânica...)."""
    total = len(leads)
    itens: Dict[str, Dict[str, Any]] = {}
    for l in leads:
        it = itens.setdefault(l["origem"], {"origem": l["origem"], "pago": l["grupo"] == "online_pago", "leads": 0, "sql": 0, "vendas": 0, "conversoes": Counter()})
        it["leads"] += 1
        it["sql"] += int(l["etapa"] >= 2) if sqls is None else 0
        it["vendas"] += int(l["vendido"])
        it["conversoes"][str(l.get("conversao") or "")[:40]] += 1
    for l in sqls or []:
        it = itens.setdefault(l["origem"], {"origem": l["origem"], "pago": l["grupo"] == "online_pago", "leads": 0, "sql": 0, "vendas": 0, "conversoes": Counter()})
        it["sql"] += 1
    lista = sorted(itens.values(), key=lambda i: -i["leads"])
    saida = [
        {"origem": i["origem"], "canal": (i["conversoes"].most_common(1) or [("", 0)])[0][0] or ("Mídia paga" if i["pago"] else "—"),
         "pago": i["pago"], "leads": i["leads"], "sql": i["sql"], "vendas": i["vendas"],
         "pct": _pct(i["leads"], total), "pct_sql": _pct(i["sql"], i["leads"])}
        for i in lista
    ]
    organicos = [i for i in saida if not i["pago"]]
    if len(organicos) > limite:
        resto = organicos[limite - 1:]
        organicos = organicos[: limite - 1] + [{
            "origem": f"Outras ({len(resto)} origens)", "canal": "—", "pago": False,
            "leads": sum(i["leads"] for i in resto), "sql": sum(i["sql"] for i in resto), "vendas": sum(i["vendas"] for i in resto),
            "pct": _pct(sum(i["leads"] for i in resto), total), "pct_sql": None,
        }]
    return {"total": total, "todas": saida, "por_origem": organicos}


# ---------------------------------------------------------------------------
# Leads orgânicos: de onde vieram
# ---------------------------------------------------------------------------


def _nome(valor: Any) -> Optional[str]:
    return bi._nome(valor)


def _rotulo_utm(utm: Dict[str, str]) -> Optional[str]:
    """Nome legível da UTM (utm_source / utm_medium / utm_campaign / utm_content), ou None sem UTM."""
    src, med = utm.get("cf_utm_source"), utm.get("cf_utm_medium")
    if not src and not med:
        return None
    texto = bi._limpo(" ".join(str(utm.get(c) or "") for c in ("cf_utm_source", "cf_utm_medium", "cf_utm_campaign", "cf_utm_content")))
    if "banner" in texto:
        return "Banner"
    if "instagram" in texto or "insta" in texto or re.search(r"\big\b", texto):
        return "Instagram"
    if "facebook" in texto or re.search(r"\bfb\b", texto):
        return "Facebook"
    if "linktr" in texto or re.search(r"\bbio\b", texto):
        return "Link da bio"
    if "youtube" in texto:
        return "YouTube"
    if "email" in texto or "rd station" in texto or "rd-station" in texto or "rdstation" in texto:
        return "E-mail / RD Station"
    if "chatgpt" in texto or "ai-assistant" in texto:
        return "Assistentes de IA (ChatGPT e outros)"
    if "whatsapp" in texto:
        return "WhatsApp"
    return f"UTM: {src or '—'} / {med or '—'}"


def _rotulo_formulario(identificador: Optional[str]) -> Optional[str]:
    """Formulário da RD que o lead preencheu: 'form-mobile-lp-reserva-dos-ramos' -> 'Landing page · Reserva dos Ramos'."""
    if not identificador:
        return None
    ident = str(identificador).strip()
    lp = re.search(r"-lp-(.+)$", ident)
    if lp:
        return f"Landing page · {lp.group(1).replace('-', ' ').replace('_', ' ').title()}"
    if ident.lower() in ("form_site", "form-site"):
        return "Formulário do site"
    if ident.startswith("/") or "fale-conosco" in ident:
        return "Fale conosco (site)"
    return f"Formulário: {ident}"


def origem_do_organico(lead: Dict[str, Any], raw: Dict[str, Any], rd: Dict[str, Any]) -> Tuple[str, bool]:
    """
    (origem legível, tem UTM no CV). Da evidência mais forte para a mais fraca: UTM, formulário da RD,
    mídia do CV, origem do CV. O que não tem nenhuma fica com o nome do canal — nunca é chutado.
    """
    utm = utms_do_lead(raw)
    rotulo_utm = _rotulo_utm(utm)
    if rotulo_utm:
        return rotulo_utm, True

    formulario = _rotulo_formulario((rd.get(str(lead["id"])) or {}).get("identificador"))
    if formulario:
        return formulario, False

    midia = _nome(raw.get("midia_principal")) or next((_nome(m) for m in raw.get("midias") or [] if _nome(m)), None)
    origem = _nome(raw.get("origem"))
    m, o = bi._limpo(midia), bi._limpo(origem)

    if m == "whatsapp" or lead["canal"] in ("whatsapp_organico", "whatsapp_nao_rastreado"):
        if o in ("facebook", "instagram"):
            return f"WhatsApp (origem no CV: {origem})", False
        return "WhatsApp (sem UTM)", False
    if m == "pesquisa":
        return "Busca no Google", False
    if "trafego direto" in (m, o):
        return "Acesso direto ao site", False
    if "linktr" in m:
        return "Link da bio (Linktree)", False
    if m.startswith("http") or re.search(r"\.(com|br|ee|co)\b", m):
        dominio = urlparse(m if m.startswith("http") else f"//{m}").netloc or m
        return f"Site: {dominio.replace('www.', '')}", False
    if "instagram" in m or "instagram" in o:
        return "Instagram", False
    if "facebook" in m or "facebook" in o:
        return "Facebook", False
    if "chat" in m or lead["canal"] == "chat":
        return "Chat do site", False
    if midia:
        return str(midia), False
    if origem and o not in ("outros", "nao definido"):
        return str(origem), False
    return lead["canal_label"], False


def _organicos(leads: List[Dict[str, Any]], brutos: Dict[str, Dict[str, Any]], limite: int = 8) -> Dict[str, Any]:
    organicos = [l for l in leads if l["grupo"] == "online_organico"]
    rd = origem_rd.por_lead()
    por_origem: Dict[str, Dict[str, Any]] = {}
    por_canal: Dict[str, Dict[str, Any]] = {}
    com_utm = 0
    for l in organicos:
        origem, tem_utm = origem_do_organico(l, brutos.get(str(l["id"])) or {}, rd)
        com_utm += int(tem_utm)
        for tabela, chave, extra in ((por_origem, origem, {"canal": l["canal_label"]}), (por_canal, l["canal_label"], {})):
            it = tabela.setdefault(chave, {"origem": chave, **extra, "leads": 0, "sql": 0, "vendas": 0})
            it["leads"] += 1
            it["sql"] += int(l["etapa"] >= 2)
            it["vendas"] += int(l["vendido"])
    total = len(organicos)

    def fechar(tabela: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        lista = sorted(tabela.values(), key=lambda i: -i["leads"])
        return [{**i, "pct": _pct(i["leads"], total), "pct_sql": _pct(i["sql"], i["leads"])} for i in lista]

    origens = fechar(por_origem)
    if len(origens) > limite:
        resto = origens[limite - 1:]
        leads_resto = sum(i["leads"] for i in resto)
        origens = origens[: limite - 1] + [{
            "origem": f"Outras ({len(resto)} origens)", "canal": "—", "leads": leads_resto,
            "sql": sum(i["sql"] for i in resto), "vendas": sum(i["vendas"] for i in resto),
            "pct": _pct(leads_resto, total), "pct_sql": _pct(sum(i["sql"] for i in resto), leads_resto),
        }]
    return {
        "total": total,
        "com_utm": com_utm,
        "pct_com_utm": _pct(com_utm, total),
        "por_origem": origens,
        "por_canal": fechar(por_canal),
    }


# ---------------------------------------------------------------------------
# Anúncios da Meta: campeões, formato e tema
# ---------------------------------------------------------------------------

CAMPOS_ANUNCIO = (
    "chave", "anuncio", "conjunto", "campanha", "empreendimento", "miniatura", "anuncio_ids", "status",
    "sem_dados_da_plataforma", "investimento", "impressoes", "cliques", "ctr", "leads_plataforma", "leads_cv",
    "cpl_real", "sql", "taxa_sql", "custo_por_sql", "vendas", "taxa_venda", "vgv", "leads_efetivos", "cpl_efetivo", "base_leads",
    "leads_est", "sql_est", "vendas_est", "sql_efetivo", "taxa_sql_efetiva", "leads_total", "primeiro_dia", "ctr", "cpc",
)

# Tema inferido do nome do anúncio. A primeira regra que bate vale; o nome é o que a agência escreve
# ao subir a peça, então é a única descrição do criativo que existe em todas as bases.
TEMAS = (
    ("Prova de vendas / escassez", r"sucesso-de-vendas|sucesso de vendas|vendido|ultimas-unidades|ultimas unidades|ainda-da-tempo|oportunidades"),
    ("Depoimento / autoridade", r"depoimento|prefeito|\bpref\b|gustavo|eduardo|fanton|cliente"),
    ("Atualização de obra", r"atualizacao|atualização|obra|entrega|timelapse|aerea|aérea|noturna"),
    ("Lançamento / apresentação", r"lancamento|lançamento|apresentando|humanizado"),
    ("Condições e preço", r"entrada|mensais|parcela|planos|\d+x\b|valor|preco|preço"),
    ("Investimento", r"invista|investimento|investir"),
    ("Oferta do mês", r"comercial"),
    ("Localização", r"localizacao|localização"),
)


def formato_e_tema(nome: Optional[str]) -> Tuple[str, str]:
    texto = bi._limpo(nome)
    if re.search(r"video|animado|reels|depoimento|timelapse", texto):
        formato = "Vídeo"
    elif re.search(r"imagem|img|foto|estatic", texto):
        formato = "Imagem"
    elif "carrossel" in texto or "carousel" in texto:
        formato = "Carrossel"
    else:
        formato = "Formato não informado no nome"
    tema = next((t for t, padrao in TEMAS if re.search(padrao, texto)), "Tema não informado no nome")
    return formato, tema


def _resumo_anuncio(a: Dict[str, Any]) -> Dict[str, Any]:
    return {c: a.get(c) for c in CAMPOS_ANUNCIO}


def _ranking(lista: List[Dict[str, Any]], elegiveis, ordem, n: int = 3) -> List[Dict[str, Any]]:
    return [_resumo_anuncio(a) for a in sorted((a for a in lista if elegiveis(a)), key=ordem)[:n]]


def _com_leads_efetivos(lista: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    O CV só liga o lead ao anúncio quando a UTM traz o nome dele (clique no WhatsApp e assistente não trazem), então muitos
    anúncios aparecem com poucos leads no CV. Para custo e volume vale o maior entre o CV e o que a Meta registra no anúncio;
    SQL e venda só existem nos leads do CV.
    """
    saida = []
    for a in lista:
        cv, plat = a["leads_cv"] or 0, int(round(a.get("leads_plataforma") or 0))
        total_cv = cv + (a.get("leads_est") or 0)  # CV: ligados por UTM mais os repartidos pelo título do anúncio
        usa_plat = plat > total_cv
        n = plat if usa_plat else total_cv
        sql_ef = (a.get("sql") or 0) + (a.get("sql_est") or 0)
        saida.append({**a, "leads_efetivos": round(n, 1), "cpl_efetivo": _div(a["investimento"], n) if n and a["investimento"] else None, "base_leads": "Meta" if usa_plat else "CV",
                      "leads_total": round(total_cv, 1), "sql_efetivo": round(sql_ef, 1), "taxa_sql_efetiva": _pct(sql_ef, total_cv)})
    return saida


def _cartao_menor_cpl(lista: List[Dict[str, Any]], m: Dict[str, float], custo_ok) -> Dict[str, Any]:
    """Menor custo por lead; sem anúncio na amostra mínima, usa uma amostra menor (2+ leads, R$ 30+) e diz isso no título, em vez de deixar o cartão vazio."""
    ordem = lambda a: a["cpl_efetivo"] or 10**9
    ranking = _ranking(lista, custo_ok, ordem)
    cartao = {
        "id": "menor_cpl", "titulo": "Menor custo por lead", "metrica": "cpl_real",
        "descricao": f"Menor investimento ÷ leads, com {m['leads_cpl']}+ leads e R$ {m['investimento_cpl']:.0f}+ investidos. Leads: o maior entre o CV e a Meta.",
        "ranking": ranking,
        "motivo_vazio": f"Nenhum anúncio com 2+ leads e R$ 30+ investidos no período.",
    }
    if not ranking:
        pequena = _ranking(lista, lambda a: a["leads_efetivos"] >= 2 and a["investimento"] >= 30 and a["cpl_efetivo"], ordem)
        if pequena:
            cartao.update(titulo="Menor custo por lead (amostra pequena)", ranking=pequena,
                          descricao="Nenhum anúncio chegou à amostra mínima do mês; ranking com 2+ leads e R$ 30+ investidos.")
    return cartao


def _campeoes_anuncios(lista: List[Dict[str, Any]], dias: int, contexto: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    m = minimos(dias)
    lista = _com_leads_efetivos(lista)
    com_leads = lambda a: a["leads_efetivos"] > 0
    custo_ok = lambda a: a["leads_efetivos"] >= m["leads_cpl"] and a["investimento"] >= m["investimento_cpl"]
    conv_ok = lambda a: a["leads_total"] >= m["leads_conversao"]
    ctx = contexto or {}
    identificados = sum(a["leads_cv"] for a in lista)
    nota = (f" Só {identificados} de {ctx['leads_meta']} leads de Meta deste filtro trazem o anúncio na UTM; SQL e venda por anúncio só são medidos nesses."
            if ctx.get("leads_meta") else "")

    venda = _ranking(lista, lambda a: conv_ok(a) and a["vendas"] > 0, lambda a: (-(a["taxa_venda"] or 0), -a["vendas"]))
    conversao = {
        "id": "maior_conversao", "titulo": "Maior conversão", "metrica": "taxa_venda",
        "descricao": f"Maior % de leads que viraram venda, com {m['leads_conversao']}+ leads no CV.",
        "ranking": venda,
    }
    if not venda:
        # Começo de mês: ainda não houve venda. Mostra quem mais converteu em SQL, dizendo que é isso.
        conversao.update(
            titulo="Maior conversão em SQL", metrica="taxa_sql",
            descricao=f"Ainda sem vendas dos leads do período. Maior % de leads que chegaram a SQL, com {m['leads_conversao']}+ leads no CV.",
            ranking=_ranking(lista, lambda a: a["leads_total"] >= 2 and a["sql_efetivo"] > 0, lambda a: (-(a["taxa_sql_efetiva"] or 0), -a["sql_efetivo"])),
        )
    conversao["motivo_vazio"] = f"Nenhum anúncio com 2+ leads chegou a SQL no período.{nota}"

    return {
        "minimos": m,
        "criterios": [
            _cartao_menor_cpl(lista, m, custo_ok),
            {
                "id": "mais_leads", "titulo": "Mais leads", "metrica": "leads_cv",
                "descricao": "Mais leads no período: o maior entre o CV e a Meta.",
                "ranking": _ranking(lista, com_leads, lambda a: (-a["leads_efetivos"], a["cpl_efetivo"] or 10**9)),
                "motivo_vazio": "Nenhum anúncio com lead no período.",
            },
            {
                "id": "mais_sql", "titulo": "Mais SQL", "metrica": "sql",
                "descricao": "Mais leads qualificados (SQL). Os que o CV liga ao anúncio por UTM são exatos; os de clique no WhatsApp são repartidos entre os anúncios que usam o mesmo título, pelas conversas de cada um (estimativa).",
                "ranking": _ranking(lista, lambda a: a["sql_efetivo"] > 0, lambda a: (-a["sql_efetivo"], -(a["taxa_sql_efetiva"] or 0))),
                "motivo_vazio": f"Nenhum lead ligado a anúncio chegou a SQL no período.{nota}",
            },
            conversao,
        ],
    }




def _mediana(valores: List[float]) -> Optional[float]:
    valores = sorted(v for v in valores if v is not None)
    if not valores:
        return None
    meio = len(valores) // 2
    return valores[meio] if len(valores) % 2 else (valores[meio - 1] + valores[meio]) / 2


def _anuncios_novos(itens: List[Dict[str, Any]], inicio: Optional[date], fim: Optional[date], criados: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Anúncios NOVOS = os que começaram a gastar dentro do período (o mês selecionado), com o que já entregaram, e a régua dos que já rodavam
    antes (mediana de custo por resultado e de leads por dia entre os anúncios mais antigos com investimento relevante).
    """
    if not fim or not inicio:
        return {"desde": None, "anuncios": [], "referencia": None}
    corte = inicio.isoformat()
    todos = _com_leads_efetivos(itens)
    # Anúncio só é novo se NENHUMA versão dele (mesmo nome) gastou antes do mês: copiar o criativo para uma campanha nova gera outro id,
    # mas o anúncio continua sendo o mesmo. A data vem da base inteira, não só do período.
    chave_nome = lambda n: re.sub(r"\s+", " ", str(n or "").strip().lower())
    primeiro_por_nome: Dict[str, str] = {}
    for r in bases.registros("meta_anuncios"):
        if (r.get("investimento") or 0) > 0:
            k = chave_nome(r.get("anuncio_nome"))
            if k not in primeiro_por_nome or r["data"] < primeiro_por_nome[k]:
                primeiro_por_nome[k] = r["data"]
    novos, velhos = [], []
    for a in todos:
        if not a["investimento"]:
            continue
        primeiro = min(a.get("primeiro_dia") or "9999", primeiro_por_nome.get(chave_nome(a.get("anuncio")), "9999"))
        (novos if primeiro >= corte else velhos).append({**a, "primeiro_dia": primeiro})
    resultados = lambda a: (a.get("leads_plataforma") or 0) + (a.get("conversas_whatsapp") or 0)   # o que a Meta registra: formulários + conversas de WhatsApp
    ref_cpl = _mediana([a["cpl_efetivo"] for a in velhos if a["leads_efetivos"] >= 3 and a["investimento"] >= 50])
    ref_ld = _mediana([a["leads_efetivos"] / max(a["dias_com_investimento"] or 1, 1) for a in velhos if a["investimento"] >= 50])
    ref_res = _mediana([a["investimento"] / resultados(a) for a in velhos if resultados(a) >= 3 and a["investimento"] >= 50])
    # O mesmo anúncio roda em mais de uma campanha/conjunto: fica só a melhor versão (menor custo por resultado; sem resultado, a que mais gastou).
    # Anúncio novo que ainda não converteu não entra: o slide é para mostrar o que há de novo e está funcionando.
    por_nome: Dict[str, Dict[str, Any]] = {}
    for a in novos:
        chave = re.sub(r"\s+", " ", str(a.get("anuncio") or "").strip().lower())
        res = resultados(a)
        pontuacao = (0, a["investimento"] / res, -res) if res else (1, 0.0, -a["investimento"])   # com resultado primeiro; entre eles o mais barato
        if chave not in por_nome or pontuacao < por_nome[chave]["_p"]:
            por_nome[chave] = {**a, "_p": pontuacao}
    unicos = list(por_nome.values())
    convertendo = [a for a in unicos if a["investimento"] >= 20 and (resultados(a) >= 1 or a["leads_efetivos"] >= 1)]
    saida = []
    for a in sorted(convertendo, key=lambda x: (-resultados(x), x["investimento"] / max(resultados(x), 1)))[:8]:
        dias_no_ar = max((fim - date.fromisoformat(a["primeiro_dia"])).days + 1, 1)
        leads_dia = a["leads_efetivos"] / dias_no_ar if a["leads_efetivos"] else 0
        res = resultados(a)
        custo_res = a["investimento"] / res if res else None
        saida.append({**_resumo_anuncio(a), "dias_no_ar": dias_no_ar, "leads_por_dia": round(leads_dia, 2),
                      "cpl_vs_referencia": round((a["cpl_efetivo"] / ref_cpl - 1) * 100, 0) if a["cpl_efetivo"] and ref_cpl else None,
                      "resultados_meta": round(res), "custo_resultado_meta": round(custo_res, 2) if custo_res else None,
                      "custo_resultado_vs_referencia": round((custo_res / ref_res - 1) * 100, 0) if custo_res and ref_res else None})
    # Os novos que ainda não deram resultado: só para mostrar que existem (mais recentes primeiro), sem métricas de custo
    ids_convertendo = {id(a) for a in convertendo}
    sem_resultado = []
    for a in sorted((a for a in unicos if id(a) not in ids_convertendo), key=lambda x: (x["primeiro_dia"], x["investimento"]), reverse=True):
        sem_resultado.append({**_resumo_anuncio(a), "dias_no_ar": max((fim - date.fromisoformat(a["primeiro_dia"])).days + 1, 1)})
    # Criados no mês e já no ar, mas que ainda não gastaram nada (não existem na base de gasto): entram na mesma faixa, uma vez por nome
    conhecidos = {chave_nome(a.get("anuncio")) for a in todos} | {k for k, d in primeiro_por_nome.items() if d < corte}
    for c in sorted(criados or [], key=lambda c: (c["criado"], c["nome"]), reverse=True):
        k = chave_nome(c["nome"])
        if k in conhecidos:
            continue
        conhecidos.add(k)
        sem_resultado.append({**{campo: None for campo in CAMPOS_ANUNCIO}, "chave": f"criado:{c['anuncio_id']}", "anuncio": c["nome"],
                              "empreendimento": c.get("empreendimento"), "anuncio_ids": [c["anuncio_id"]], "primeiro_dia": c["criado"],
                              "investimento": 0.0, "sem_dados_da_plataforma": False, "leads_cv": 0, "sql": 0,
                              "dias_no_ar": max((fim - date.fromisoformat(c["criado"])).days + 1, 1)})
    sem_resultado.sort(key=lambda x: (x["primeiro_dia"], x["investimento"]), reverse=True)
    total_sem_resultado = len(sem_resultado)
    sem_resultado = sem_resultado[:8]
    return {"desde": corte, "anuncios": saida, "sem_resultado": sem_resultado, "total_novos": len(unicos) + (total_sem_resultado - (len(unicos) - len(convertendo))),
            "sem_resultado_ainda": total_sem_resultado,
            "referencia": {"cpl": round(ref_cpl, 2) if ref_cpl else None, "leads_por_dia": round(ref_ld, 2) if ref_ld else None,
                          "custo_resultado_meta": round(ref_res, 2) if ref_res else None, "anuncios_veteranos": len(velhos)}}


def _anuncios_por_praca(lista: List[Dict[str, Any]], dias: int, insights_p: Optional[List[Dict[str, Any]]] = None, leads_meta: Optional[Dict[str, int]] = None, fim: Optional[date] = None, inicio: Optional[date] = None, emp_f: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Os campeões de anúncio de cada praça, com a amostra mínima calculada só entre os anúncios dela.

    Quando nenhum lead do CV foi ligado a anúncio da praça (acontece quando os anúncios têm nomes genéricos e a
    campanha não manda a UTM do anúncio), o ranking usa os leads que a própria Meta registra por anúncio, e o slide diz isso.
    """
    pracas: Dict[str, List[Dict[str, Any]]] = {}
    for a in lista:
        praca = bi.praca_do_empreendimento(a["empreendimento"]) if a["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO else None
        if praca:
            pracas.setdefault(praca, []).append(a)
    saida: Dict[str, Any] = {}
    # Anúncios criados no período e já no ar (inclusive os que ainda não gastaram), por praça da conta em que foram criados
    criados_por_praca: Dict[str, List[Dict[str, Any]]] = {}
    if inicio and fim:
        try:
            catalogo = bases.registros("cv_empreendimentos")
            for c in criativo_info.criados_desde(inicio):
                emp = match_empreendimento(c.get("conta_nome"), catalogo)
                praca_c = bi.praca_do_empreendimento(emp) if emp else None
                if praca_c and (not emp_f or emp in emp_f):      # com um empreendimento filtrado, só os anúncios dele (a Reserva não entra no Central)
                    criados_por_praca.setdefault(praca_c, []).append({**c, "empreendimento": emp})
        except Exception:      # sem rede ou sem token: segue só com o que tem gasto
            criados_por_praca = {}
    for praca, itens in pracas.items():
        if not any(a["investimento"] or a["leads_cv"] for a in itens):
            continue
        da_plataforma = not any(a["leads_cv"] for a in itens) and any(a["leads_plataforma"] for a in itens)
        base = itens
        if da_plataforma:
            base = [{**a, "leads_cv": a["leads_plataforma"], "cpl_real": a.get("cpl_plataforma"), "sql": 0, "taxa_sql": None, "vendas": 0, "taxa_venda": None}
                    for a in itens]
        quadro = sorted((a for a in _com_leads_efetivos(base) if a["investimento"] or a["leads_cv"] or a["leads_efetivos"]), key=lambda a: (-(a["leads_efetivos"] or 0), -(a["investimento"] or 0)))[:10]
        por_nome: Dict[str, Dict[str, Any]] = {}
        # O custo de uma campanha que atende mais de um produto vem dividido por produto; no quadro da praça volta a ser uma linha só
        for c in _campanhas_google([r for r in (insights_p or []) if bi.praca_do_empreendimento(r["empreendimento"]) == praca], 40):
            g = por_nome.setdefault(c["campanha"], {"campanha": c["campanha"], "tipo": c["tipo"], "investimento": 0.0, "impressoes": 0, "cliques": 0, "leads_plataforma": 0})
            for campo in ("investimento", "impressoes", "cliques", "leads_plataforma"):
                g[campo] += c.get(campo) or 0
        google = sorted((
            {**g, "investimento": round(g["investimento"], 2), "cpl": _div(g["investimento"], g["leads_plataforma"]), "ctr": _pct(g["cliques"], g["impressoes"]), "cpc": _div(g["investimento"], g["cliques"])}
            for g in por_nome.values()), key=lambda g: -g["investimento"])[:8]
        saida[praca] = {
            "total": len(itens), "leads_da_plataforma": da_plataforma, **_campeoes_anuncios(base, dias, {"leads_meta": (leads_meta or {}).get(praca)}),
            "quadro": [{**_resumo_anuncio(a), "custo_por_sql": _div(a["investimento"], a["sql_efetivo"]) if a.get("sql_efetivo") and a["investimento"] else None} for a in quadro],
            "google": google,
            "novos": _anuncios_novos(base, inicio, fim, criados_por_praca.get(praca)),
        }
        # Praça com mais de um produto (ex.: Central Parque II e Reserva, em Avaré): cada um com os seus anúncios novos e a sua própria régua
        criados_praca = criados_por_praca.get(praca) or []
        emps = sorted({a["empreendimento"] for a in base} | {c["empreendimento"] for c in criados_praca})
        if len(emps) > 1:
            saida[praca]["novos_por_produto"] = {
                e: _anuncios_novos([a for a in base if a["empreendimento"] == e], inicio, fim, [c for c in criados_praca if c["empreendimento"] == e])
                for e in emps
            }
    return saida


AJUSTES_LEADS = os.path.join(bases.BASES_DIR, "ajustes_leads_anuncio.json")


def _aplicar_ajustes_manuais(itens: List[Dict[str, Any]], leads: List[float], leads_total: Optional[int]) -> List[float]:
    """
    Ajuste manual de leads por nome de anúncio (arquivo `ajustes_leads_anuncio.json`: {"<nome do anúncio>": <leads>}), decidido pela gestão onde o CV
    não permite medir. O anúncio passa a ter esse total (dividido entre os anúncios de mesmo nome na proporção atual) e o que sobra é tirado dos
    outros na proporção, para a soma continuar igual ao Resumo.
    """
    try:
        with open(AJUSTES_LEADS, encoding="utf-8") as f:
            ajustes = json.load(f)
    except (OSError, ValueError):
        return leads
    leads = list(leads)
    fixos: Set[int] = set()
    for nome, alvo in ajustes.items():
        idx = [k for k, a in enumerate(itens) if a.get("anuncio") == nome]
        atual = sum(leads[k] for k in idx)
        if not idx or not atual:
            continue
        for k in idx:
            leads[k] = leads[k] * alvo / atual
        fixos |= set(idx)
    total = leads_total if leads_total else None
    if total:
        livres = [k for k in range(len(leads)) if k not in fixos]
        soma_livre = sum(leads[k] for k in livres)
        restante = total - sum(leads[k] for k in fixos)
        if soma_livre and restante > 0:
            for k in livres:
                leads[k] = leads[k] * restante / soma_livre
    return leads


def _distribuir_pelos_anuncios(itens: List[Dict[str, Any]], leads_total: Optional[int], sql_total: Optional[int]) -> List[Dict[str, Any]]:
    """
    Leads e SQL de Meta por anúncio, somando EXATAMENTE os totais do Resumo.

    Parte do que o CV liga ao anúncio (UTM, formulário, título do anúncio) e reparte o que sobra (clique no WhatsApp sem UTM nem título) pelo
    volume que a Meta registra em cada anúncio (formulários + conversas de WhatsApp). Os valores por anúncio são estimativa; a soma não é.
    """
    saida = [dict(a) for a in itens]
    base = [a["leads_total"] for a in saida]
    volume = [(a.get("leads_plataforma") or 0) + (a.get("conversas_whatsapp") or 0) for a in saida]
    if leads_total:
        soma = sum(base)
        if soma > leads_total:
            base = [b * leads_total / soma for b in base]
            sobra = 0.0
        else:
            sobra = leads_total - soma
        vsoma = sum(volume) or 0
        leads = [b + (sobra * v / vsoma if vsoma else 0) for b, v in zip(base, volume)]
    else:
        leads = base
    leads = _aplicar_ajustes_manuais(saida, leads, leads_total)
    sqls = [a["sql_efetivo"] for a in saida]
    if sql_total is not None:
        soma = sum(sqls)
        if soma > sql_total:
            sqls = [x * sql_total / soma for x in sqls]
            sobra = 0.0
        else:
            sobra = sql_total - soma
        lsoma = sum(leads) or 0
        sqls = [x + (sobra * l / lsoma if lsoma else 0) for x, l in zip(sqls, leads)]
    for a, l, q in zip(saida, leads, sqls):
        a["leads_distribuidos"], a["sql_distribuido"] = l, min(q, l) if l else q
    return saida


def _arredondar_somando(valores: List[float], total: Optional[int]) -> List[int]:
    """Arredonda para inteiros sem perder a soma (maior resto)."""
    pisos = [int(v) for v in valores]
    alvo = total if total is not None else round(sum(valores))
    faltam = max(0, alvo - sum(pisos))
    for k in sorted(range(len(valores)), key=lambda k: -(valores[k] - pisos[k]))[:faltam]:
        pisos[k] += 1
    return pisos


TEMAS_EXTRA = (("Lazer, natureza e privacidade", r"lazer|natureza|privacidade|seguranca|segurança|qualidade de vida|area verde|área verde"),)


def _formato_do_anuncio(nome: str, info: Dict[str, Any], rotulo: Dict[str, str]) -> str:
    """Formato pelo criativo na Meta; só na falta dele (anúncio de publicação) vale o nome."""
    if rotulo.get("formato"):
        return rotulo["formato"]
    if info.get("formato"):
        return info["formato"]
    texto = bi._limpo(nome)
    if "carrossel" in texto or "carousel" in texto:
        return "Carrossel"
    if re.search(r"video|animado|reels|motion|depoimento|timelapse", texto):
        return "Vídeo"
    if re.search(r"imagem|img|foto|estatic|post", texto):
        return "Imagem"
    return "Formato não identificado"


def _tema_do_anuncio(nome: str, info: Dict[str, Any], rotulo: Dict[str, str]) -> str:
    """Tema pelo que o criativo diz: primeiro o nome, depois os títulos e por último a legenda (a legenda cita de tudo, então é o último recurso)."""
    if rotulo.get("tema"):
        return rotulo["tema"]
    for texto in (nome, " ".join(info.get("titulos") or []), " ".join(info.get("corpos") or [])):
        texto = bi._limpo(texto)
        achou = next((t for t, padrao in TEMAS + TEMAS_EXTRA if re.search(padrao, texto)), None)
        if achou:
            return achou
    return "Outros"


def _criativos_reais(lista: List[Dict[str, Any]], leads_meta_cv: Optional[int], sql_meta: Optional[int]) -> Dict[str, Any]:
    """
    Criativos de verdade: cópias do mesmo vídeo/imagem em campanhas diferentes viram UM criativo (é como se conta no Meta).
    Formato e tema vêm do criativo; leads e SQL continuam somando os do Resumo. Criativos com CPL muito alto (mais que o dobro da mediana)
    ou sem lead depois de gastar bastante ficam fora da lista dos que funcionam, mas entram nos totais.
    """
    try:
        criativo_info.atualizar(limite=60)       # só os anúncios que ainda não foram lidos na Meta
    except Exception:                            # sem rede ou sem token: segue com o que já está guardado
        pass
    info_todos, rotulos = criativo_info.lido(), criativo_info.rotulos()
    itens = _distribuir_pelos_anuncios(_com_leads_efetivos(lista), leads_meta_cv, sql_meta)
    pecas: Dict[str, Dict[str, Any]] = {}
    for a in itens:
        if not (a["investimento"] or a["leads_distribuidos"]):
            continue
        info = next((info_todos[str(i)] for i in reversed(a.get("anuncio_ids") or []) if str(i) in info_todos), {})
        rotulo = rotulos.get(str(info.get("chave_peca") or "").lower()) or rotulos.get(str(a["anuncio"] or "").strip().lower()) or {}
        chave = info.get("chave_peca") or f"n:{str(a['anuncio'] or '').strip().lower()}"
        p = pecas.setdefault(chave, {"melhor": a, "copias": 0, "investimento": 0.0, "leads": 0.0, "sql": 0.0, "vendas": 0.0,
                                     "formato": _formato_do_anuncio(a["anuncio"], info, rotulo), "tema": _tema_do_anuncio(a["anuncio"], info, rotulo),
                                     "empreendimentos": set()})
        p["copias"] += 1
        p["investimento"] += a["investimento"]
        p["leads"] += a["leads_distribuidos"]
        p["sql"] += a["sql_distribuido"]
        p["vendas"] += (a["vendas"] or 0) + (a.get("vendas_est") or 0)
        p["empreendimentos"].add(a["empreendimento"])
        if a["investimento"] > p["melhor"]["investimento"]:
            p["melhor"] = a      # a cópia que mais gastou dá o nome e a imagem
    lista_p = list(pecas.values())

    def grupo(campo: str) -> List[Dict[str, Any]]:
        g: Dict[str, Dict[str, Any]] = {}
        for p in lista_p:
            x = g.setdefault(p[campo], {"nome": p[campo], "criativos": 0, "anuncios": 0, "investimento": 0.0, "leads": 0.0, "sql": 0.0, "vendas": 0.0, "exemplo": None})
            x["criativos"] += 1
            x["anuncios"] += p["copias"]
            x["investimento"] += p["investimento"]
            x["leads"] += p["leads"]
            x["sql"] += p["sql"]
            x["vendas"] += p["vendas"]
            if x["exemplo"] is None or p["leads"] > x["exemplo"]["_l"]:
                x["exemplo"] = {"anuncio": p["melhor"]["anuncio"], "_l": p["leads"]}
        ordem = sorted(g.values(), key=lambda x: (x["nome"] in ("Outros", "Formato não identificado"), -x["leads"], -x["investimento"]))
        leads_i = _arredondar_somando([x["leads"] for x in ordem], leads_meta_cv)
        sql_i = _arredondar_somando([x["sql"] for x in ordem], sql_meta)
        saida = []
        for x, l, q in zip(ordem, leads_i, sql_i):
            q = min(q, l)
            saida.append({"nome": x["nome"], "criativos": x["criativos"], "anuncios": x["anuncios"], "investimento": round(x["investimento"], 2), "leads_cv": l, "sql": q,
                          "vendas": round(x["vendas"]), "cpl": _div(x["investimento"], l), "pct_sql": _pct(q, l),
                          "exemplo": {"anuncio": x["exemplo"]["anuncio"], "leads_cv": round(x["exemplo"]["_l"])} if x["exemplo"] else None})
        return saida

    # Quem funciona: CPL até 1,5x a mediana dos criativos com amostra; quem passa de 2x a mediana (ou gastou 100+ sem lead) não é mostrado
    # A régua é a mediana de CPL dos criativos da própria praça (ou do filtro): com poucos criativos na amostra, vale a de todos que tiveram lead.
    com_amostra = [p for p in lista_p if p["leads"] >= 2 and p["investimento"] >= 50]
    base_mediana = com_amostra if len(com_amostra) >= 3 else [p for p in lista_p if p["leads"] >= 0.5]
    mediana = _mediana([p["investimento"] / p["leads"] for p in base_mediana]) or 0
    funcionam, ocultos = [], []
    for p in sorted(lista_p, key=lambda p: (-p["leads"], p["investimento"])):
        cpl = p["investimento"] / p["leads"] if p["leads"] >= 0.5 else None
        if cpl and p["investimento"] >= 20 and (not mediana or cpl <= mediana * 2):
            funcionam.append((p, cpl))
        elif p["investimento"] >= 100 and (cpl is None or (mediana and cpl > mediana * 2)):
            ocultos.append(p)
    # Peças do mesmo formato e assunto são variações do mesmo criativo (mesma arte, outro texto): viram um cartão só, com os resultados somados.
    # A imagem e o nome são os da variação que mais trouxe lead.
    combinados: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for p, _cpl in funcionam:
        c = combinados.setdefault((p["formato"], p["tema"]), {"lider": p, "variacoes": 0, "copias": 0, "investimento": 0.0, "leads": 0.0, "sql": 0.0,
                                                               "vendas": 0.0, "empreendimentos": set()})
        c["variacoes"] += 1
        c["copias"] += p["copias"]
        c["investimento"] += p["investimento"]
        c["leads"] += p["leads"]
        c["sql"] += p["sql"]
        c["vendas"] += p["vendas"]
        c["empreendimentos"] |= p["empreendimentos"]
    melhores = []
    for c in sorted(combinados.values(), key=lambda c: (-c["leads"], c["investimento"]))[:6]:
        m = c["lider"]["melhor"]
        melhores.append({**_resumo_anuncio(m), "formato": c["lider"]["formato"], "tema": c["lider"]["tema"], "copias": c["copias"], "variacoes": c["variacoes"],
                         "investimento": round(c["investimento"], 2), "leads_cv": round(c["leads"], 1), "sql": round(c["sql"], 1),
                         "cpl": round(c["investimento"] / c["leads"], 2), "vendas": round(c["vendas"]),
                         "pracas": sorted({bi.praca_do_empreendimento(e) for e in c["empreendimentos"] if e and e != EMPREENDIMENTO_DESCONHECIDO} - {None})})
    return {
        "por_formato": grupo("formato"), "por_tema": grupo("tema"), "melhores": melhores,
        "criativos_total": len(lista_p), "anuncios_total": sum(p["copias"] for p in lista_p),
        "cpl_mediana": round(mediana, 2) if mediana else None,
        "ocultos": {"criativos": len(ocultos), "investimento": round(sum(p["investimento"] for p in ocultos), 2)},
    }


def _agrupar_criativos(lista: List[Dict[str, Any]], indice: int, leads_meta_cv: Optional[int] = None, sql_meta: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Formato (índice 0) ou tema (índice 1) dos anúncios, com investimento, leads e SQL de Meta. Leads e SQL somam os do Resumo (ver `_distribuir_pelos_anuncios`).
    """
    itens = _distribuir_pelos_anuncios(_com_leads_efetivos(lista), leads_meta_cv, sql_meta)
    grupos: Dict[str, Dict[str, Any]] = {}
    for a in itens:
        if not (a["investimento"] or a["leads_distribuidos"]):
            continue
        nome = formato_e_tema(a["anuncio"])[indice]
        g = grupos.setdefault(nome, {"nome": nome, "anuncios": 0, "investimento": 0.0, "leads": 0.0, "sql": 0.0, "vendas": 0.0, "exemplo": None})
        g["anuncios"] += 1
        g["investimento"] += a["investimento"]
        g["leads"] += a["leads_distribuidos"]
        g["sql"] += a["sql_distribuido"]
        g["vendas"] += (a["vendas"] or 0) + (a.get("vendas_est") or 0)
        if g["exemplo"] is None or a["leads_distribuidos"] > g["exemplo"]["_l"]:
            g["exemplo"] = {"anuncio": a["anuncio"], "_l": a["leads_distribuidos"]}
    ordem = sorted(grupos.values(), key=lambda g: (g["nome"].startswith(("Tema não", "Formato não")), -g["leads"], -g["investimento"]))
    leads_i = _arredondar_somando([g["leads"] for g in ordem], leads_meta_cv)
    sql_i = _arredondar_somando([g["sql"] for g in ordem], sql_meta)
    saida = []
    for g, l, q in zip(ordem, leads_i, sql_i):
        q = min(q, l)
        saida.append({"nome": g["nome"], "anuncios": g["anuncios"], "investimento": round(g["investimento"], 2), "leads_cv": l, "sql": q,
                      "vendas": round(g["vendas"]), "cpl": _div(g["investimento"], l), "pct_sql": _pct(q, l),
                      "exemplo": {"anuncio": g["exemplo"]["anuncio"], "leads_cv": round(g["exemplo"]["_l"])} if g["exemplo"] else None})
    return saida


# ---------------------------------------------------------------------------
# Google Ads: campanhas, termos do Performance Max e palavras-chave
# ---------------------------------------------------------------------------


def _tipo_campanha(nome: Optional[str]) -> str:
    texto = bi._limpo(nome)
    if "pmax" in texto or "performance max" in texto:
        return "Performance Max"
    if "search" in texto or "pesquisa" in texto or "keywords" in texto or texto.startswith("rp "):
        return "Pesquisa"
    return "Outras"


def _campanhas_google(insights: List[Dict[str, Any]], limite: int) -> List[Dict[str, Any]]:
    campanhas: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in insights:
        if r["plataforma"] != "google":
            continue
        c = campanhas.setdefault((r["empreendimento"], r.get("campanha_nome") or "—"), {
            "campanha": r.get("campanha_nome") or "—", "empreendimento": r["empreendimento"],
            "tipo": _tipo_campanha(r.get("campanha_nome")),
            "investimento": 0.0, "impressoes": 0, "cliques": 0, "leads_plataforma": 0,
        })
        for campo in ("investimento", "impressoes", "cliques", "leads_plataforma"):
            c[campo] += r.get(campo) or 0
    saida = [
        {**c, "investimento": round(c["investimento"], 2), "cpl": _div(c["investimento"], c["leads_plataforma"]),
         "ctr": _pct(c["cliques"], c["impressoes"]), "cpc": _div(c["investimento"], c["cliques"])}
        for c in campanhas.values()
    ]
    saida.sort(key=lambda c: -c["investimento"])
    return saida[:limite]


def _no_periodo(row: Dict[str, Any], inicio: date, fim: date, meses: Set[str]) -> bool:
    """Linha por dia vale pelo dia exato; base antiga, que só tem o mês, vale pelo mês."""
    dia = palavras._dia(row.get("data"))
    if dia is not None:
        return inicio <= dia <= fim
    return palavras._mes(row.get("mes")) in meses


def _filtro_local(emp_f: Set[str], praca_f: Set[str]):
    catalogo = bases.registros("cv_empreendimentos")
    cidades = cidades_do_catalogo(catalogo)
    cache: Dict[Any, Tuple[str, str]] = {}

    def passa(row: Dict[str, Any]) -> Tuple[bool, str]:
        emp, praca = palavras.local_da_linha(row, catalogo, cidades, cache, palavras.CAMPOS_GOOGLE)
        return ((not emp_f or emp in emp_f) and (not praca_f or praca in praca_f)), emp

    return passa


def _termos(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], limite: int) -> Dict[str, Any]:
    """
    O que as pessoas digitaram nas campanhas do Google, termo por termo, com custo e conversões. Vem do
    `search_term_view` (pesquisa) e do `campaign_search_term_view` (Performance Max). O Google omite os termos
    com pouquíssimo volume, então a soma dos termos pode ficar abaixo do total da campanha.
    """
    passa = _filtro_local(emp_f, praca_f)
    meses = palavras._meses(inicio, fim)
    tabelas: Dict[str, Dict[str, Dict[str, Any]]] = {"Performance Max": {}, "Pesquisa": {}}

    for row in bases.registros("google_termos"):
        if not _no_periodo(row, inicio, fim, meses):
            continue
        ok, emp = passa(row)
        termo = str(row.get("termo") or "").strip().lower()
        if not ok or not termo:
            continue
        tipo = "Performance Max" if "performance max" in bi._limpo(row.get("canal")) or "pmax" in bi._limpo(row.get("campanha_nome")) else "Pesquisa"
        it = tabelas[tipo].setdefault(termo, {
            "termo": termo, "impressoes": 0, "cliques": 0, "investimento": 0.0, "conversoes": 0.0,
            "campanhas": set(), "empreendimentos": set(),
        })
        for campo in ("impressoes", "cliques", "investimento", "conversoes"):
            it[campo] += row.get(campo) or 0
        if row.get("campanha_nome"):
            it["campanhas"].add(row["campanha_nome"])
        if emp != EMPREENDIMENTO_DESCONHECIDO:
            it["empreendimentos"].add(emp)

    def formatar(t: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "termo": t["termo"], "impressoes": t["impressoes"], "cliques": t["cliques"],
            "investimento": round(t["investimento"], 2), "conversoes": round(t["conversoes"], 2),
            "ctr": _pct(t["cliques"], t["impressoes"]), "cpc": _div(t["investimento"], t["cliques"]),
            "custo_por_conversao": _div(t["investimento"], t["conversoes"]),
            "campanhas": sorted(t["campanhas"])[:2], "empreendimentos": sorted(t["empreendimentos"])[:2],
        }

    def fechar(tabela: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        todos = list(tabela.values())
        return {
            "cliques": sum(t["cliques"] for t in todos),
            "investimento": round(sum(t["investimento"] for t in todos), 2),
            "conversoes": round(sum(t["conversoes"] for t in todos), 2),
            "termos_distintos": len(todos),
            "mais_cliques": [formatar(t) for t in sorted(todos, key=lambda t: (-t["cliques"], -t["conversoes"]))[:limite]],
            "mais_conversoes": [
                formatar(t) for t in sorted((t for t in todos if t["conversoes"] > 0),
                                            key=lambda t: (-t["conversoes"], _div(t["investimento"], t["conversoes"]) or 0))[:limite]
            ],
        }

    return {
        "pmax": fechar(tabelas["Performance Max"]),
        "pesquisa": fechar(tabelas["Pesquisa"]),
        "base": bases.resumo("google_termos"),
        "exato": any(palavras._dia(r.get("data")) for r in bases.registros("google_termos")[:50]),
    }


def _anuncios_google(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], dias: int) -> Dict[str, Any]:
    """Os anúncios do Google (pesquisa e grupos de recursos do Performance Max) e quem foi melhor em cada critério."""
    passa = _filtro_local(emp_f, praca_f)
    meses = palavras._meses(inicio, fim)
    itens: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in bases.registros("google_anuncios"):
        if not _no_periodo(row, inicio, fim, meses):
            continue
        ok, emp = passa(row)
        if not ok:
            continue
        a = itens.setdefault((row.get("campanha_id") or "", row.get("anuncio_id") or ""), {
            "anuncio": row.get("anuncio_nome") or "(anúncio sem nome)", "tipo": row.get("canal"),
            "campanha": row.get("campanha_nome"), "grupo": row.get("grupo_nome"), "forca": row.get("forca"),
            "empreendimento": emp, "investimento": 0.0, "impressoes": 0, "cliques": 0, "conversoes": 0.0,
        })
        for campo in ("investimento", "impressoes", "cliques", "conversoes"):
            a[campo] += row.get(campo) or 0
    lista = [
        {**a, "investimento": round(a["investimento"], 2), "conversoes": round(a["conversoes"], 2),
         "ctr": _pct(a["cliques"], a["impressoes"]), "cpc": _div(a["investimento"], a["cliques"]),
         "custo_por_conversao": _div(a["investimento"], a["conversoes"])}
        for a in itens.values() if a["impressoes"]
    ]
    m = minimos(dias)
    custo_ok = lambda a: a["conversoes"] >= m["leads_cpl"] and a["investimento"] >= m["investimento_cpl"]
    top = lambda filtro, ordem: sorted((a for a in lista if filtro(a)), key=ordem)[:3]
    return {
        "total": len(lista),
        "criterios": [
            {"id": "mais_conversoes", "titulo": "Mais conversões", "metrica": "conversoes",
             "descricao": "Mais conversões (ação principal da conta do Google) no período.",
             "motivo_vazio": "Nenhum anúncio do Google com conversão no período.",
             "ranking": top(lambda a: a["conversoes"] > 0, lambda a: (-a["conversoes"], a["custo_por_conversao"] or 10**9))},
            {"id": "menor_custo", "titulo": "Menor custo por conversão", "metrica": "custo_por_conversao",
             "descricao": f"Menor custo por conversão, com {m['leads_cpl']}+ conversões e R$ {m['investimento_cpl']:.0f}+ investidos.",
             "motivo_vazio": f"Nenhum anúncio com {m['leads_cpl']}+ conversões e R$ {m['investimento_cpl']:.0f}+ investidos no período.",
             "ranking": top(custo_ok, lambda a: a["custo_por_conversao"] or 10**9)},
            {"id": "maior_ctr", "titulo": "Maior taxa de clique", "metrica": "ctr",
             "descricao": "Maior CTR, com 500+ impressões.",
             "motivo_vazio": "Nenhum anúncio com 500+ impressões no período.",
             "ranking": top(lambda a: a["impressoes"] >= 500, lambda a: -(a["ctr"] or 0))},
        ],
        "base": bases.resumo("google_anuncios"),
    }


def _detalhes_google(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]) -> Dict[str, Any]:
    """Como as conversões do Google acontecem (formulário, WhatsApp...), em que aparelho e quanta impressão se perdeu."""
    passa = _filtro_local(emp_f, praca_f)
    meses = palavras._meses(inicio, fim)
    acoes: Dict[str, Dict[str, Any]] = {}
    aparelhos: Dict[str, Dict[str, Any]] = {}
    campanhas: Dict[str, Dict[str, Any]] = {}
    for row in bases.registros("google_detalhes"):
        if not _no_periodo(row, inicio, fim, meses) or not passa(row)[0]:
            continue
        tipo = row.get("tipo")
        if tipo == "conversao":
            a = acoes.setdefault(row.get("acao") or "(sem nome)", {"acao": row.get("acao") or "(sem nome)", "categoria": row.get("categoria"), "conversoes": 0.0, "todas": 0.0})
            a["conversoes"] += row.get("conversoes") or 0
            a["todas"] += row.get("todas_conversoes") or 0
        elif tipo == "dispositivo":
            a = aparelhos.setdefault(row.get("dispositivo") or "Outro", {"dispositivo": row.get("dispositivo") or "Outro", "impressoes": 0, "cliques": 0, "investimento": 0.0, "conversoes": 0.0})
            for campo in ("impressoes", "cliques", "investimento", "conversoes"):
                a[campo] += row.get(campo) or 0
        elif tipo == "participacao" and row.get("participacao") is not None:
            c = campanhas.setdefault(row.get("campanha_nome") or "—", {"campanha": row.get("campanha_nome") or "—", "impressoes": 0, "p": 0.0, "o": 0.0, "r": 0.0})
            peso = row.get("impressoes") or 0
            c["impressoes"] += peso
            c["p"] += (row.get("participacao") or 0) * peso
            c["o"] += (row.get("perdida_orcamento") or 0) * peso
            c["r"] += (row.get("perdida_ranking") or 0) * peso

    total_acoes = sum(a["todas"] for a in acoes.values())
    total_cliques = sum(a["cliques"] for a in aparelhos.values())
    return {
        "acoes": sorted(
            ({**a, "conversoes": round(a["conversoes"], 1), "todas": round(a["todas"], 1), "pct": _pct(a["todas"], total_acoes)}
             for a in acoes.values()), key=lambda a: -a["todas"])[:6],
        "aparelhos": sorted(
            ({**a, "investimento": round(a["investimento"], 2), "conversoes": round(a["conversoes"], 1),
              "pct_cliques": _pct(a["cliques"], total_cliques), "taxa_conversao": _pct(a["conversoes"], a["cliques"]),
              "custo_por_conversao": _div(a["investimento"], a["conversoes"])} for a in aparelhos.values()),
            key=lambda a: -a["cliques"]),
        "participacao": sorted(
            ({"campanha": c["campanha"], "impressoes": c["impressoes"],
              "participacao": round(c["p"] / c["impressoes"] * 100, 1) if c["impressoes"] else None,
              "perdida_orcamento": round(c["o"] / c["impressoes"] * 100, 1) if c["impressoes"] else None,
              "perdida_ranking": round(c["r"] / c["impressoes"] * 100, 1) if c["impressoes"] else None}
             for c in campanhas.values()), key=lambda c: -c["impressoes"])[:6],
        "base": bases.resumo("google_detalhes"),
    }


def _palavras_chave(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], limite: int) -> List[Dict[str, Any]]:
    """As palavras-chave dos anúncios de pesquisa que mais converteram, de todos os empreendimentos do filtro."""
    dados = palavras.por_empreendimento(inicio, fim, sorted(emp_f) or None, sorted(praca_f) or None, 20)
    todas = []
    for e in dados["empreendimentos"]:
        for p in e["palavras"]:
            if p["conversoes"] > 0 or p["cliques"] > 0:
                todas.append({**{k: p[k] for k in ("palavra", "correspondencia", "investimento", "cliques", "conversoes", "custo_por_conversao", "ctr")},
                              "empreendimento": e["empreendimento"]})
    todas.sort(key=lambda p: (p["conversoes"] <= 0, p["custo_por_conversao"] if p["conversoes"] else -p["cliques"]))
    return todas[:limite]


# ---------------------------------------------------------------------------
# Site (Google Analytics)
# ---------------------------------------------------------------------------


def _site(inicio: date, fim: date, comp: Tuple[date, date], emp: List[str], pracas: List[str], limite: int) -> Dict[str, Any]:
    # Reaproveita as peças da tela do Site; só a janela de comparação muda (mês anterior, não "período anterior")
    atrib = audiencia._Atribuicao()
    atual = audiencia._linhas("ga4_trafego", inicio, fim, atrib, emp, pracas)
    antes = audiencia._linhas("ga4_trafego", comp[0], comp[1], atrib, emp, pracas)
    t, ta = audiencia._totais(atual), audiencia._totais(antes)
    ate = max((l["data"] for l in bases.registros("ga4_trafego") if l.get("data")), default=None)
    return {
        "totais": {**t, "anterior": ta, "variacao": {c: _variacao(t[c], ta[c]) for c in ("sessoes", "usuarios", "conversoes")}},
        "origens": audiencia._quadro(atual, antes, "origem_midia", "origem", limite),
        "canais": audiencia._quadro(atual, antes, "canal", "canal"),
        "paginas": audiencia._quadro(atual, antes, "pagina_entrada", "pagina", limite),
        "base": bases.resumo("ga4_trafego"),
        "dados_ate": ate,
    }


# ---------------------------------------------------------------------------


def _rastro_do_lead(lead_id: str, raw: Dict[str, Any], convs_do_lead: List[Dict[str, Any]]) -> Optional[Tuple[str, Optional[str]]]:
    """Rastro de anúncio pago de um lead que o BI classificou como orgânico: (plataforma, nome do anúncio) ou None.
    Evidências: UTM de anúncio ou clique pago, conversão dele com origem "Busca Compartilhada"/"Click To WhatsApp",
    origem de cadastro ou histórico de mídias com anúncio."""
    utm = utms_do_lead(raw)
    texto_utm = bi._limpo(" ".join(str(utm.get(c) or "") for c in ("cf_utm_source", "cf_utm_medium", "cf_utm_campaign", "cf_utm_content")))
    rastro = None
    if "gclid" in texto_utm or "cpc" in texto_utm or "google" in texto_utm and "pmax" in texto_utm:
        rastro = "Google Ads"
    elif "meta ads" in texto_utm or re.search(r"\bfb\b", texto_utm) or "ad name" in texto_utm or "fbclid" in texto_utm:
        rastro = "Meta Ads"
    if not rastro:
        for c in convs_do_lead:
            tipo, _, resto = str(c.get("conversao") or "").partition("|")
            if bi._limpo(tipo) in ("busca compartilhada", "click to whatsapp"):
                midia = bi._limpo(c.get("midia_conversao") or resto)
                rastro = "Google Ads" if "google" in midia else "Meta Ads"
                break
        if not rastro and bi._limpo(raw.get("origem")) == "busca compartilhada":
            rastro = "Google Ads" if "google" in bi._limpo(raw.get("midia_principal")) else "Meta Ads"
        if not rastro:
            hist = bi._limpo(" ".join(str(m) for m in (raw.get("midias") or []))) + " " + bi._limpo(raw.get("origem"))
            if "google ads" in hist or "busca compartilhada" in hist:
                rastro = "Google Ads"
            elif any(k in hist for k in ("meta_ads", "facebook", "instagram ads", "midia paga")):
                rastro = "Meta Ads"
    if not rastro:
        return None
    anuncio = re.search(r"Ad Name:\s*([^|]+)", str(utm.get("cf_utm_content") or ""))
    return rastro, (anuncio.group(1).strip() if anuncio else None)


def reclassificar_pagos(listas: List[Optional[List[Dict[str, Any]]]]) -> Dict[str, Any]:
    """Lead que o BI conta como orgânico (última conversão = WhatsApp) mas que tem rastro de anúncio pago passa a contar como
    mídia paga na Apresentação. Os totais de leads não mudam; só a divisão entre pago e orgânico. Devolve o resumo do que mudou."""
    candidatos = {str(l["id"]) for lista in listas for l in (lista or []) if fonte_do_lead(l) == "organico"}
    if not candidatos:
        return {"total": 0, "meta": 0, "google": 0, "sql": 0, "anuncios": []}
    brutos = {str(r.get("idlead")): r for r in bases.registros("cv_leads") if str(r.get("idlead")) in candidatos}
    convs: Dict[str, List[Dict[str, Any]]] = {}
    for c in bases.registros("cv_conversoes"):
        if str(c.get("idlead")) in candidatos:
            convs.setdefault(str(c["idlead"]), []).append(c)
    achados = {i: _rastro_do_lead(i, brutos.get(i) or {}, convs.get(i, [])) for i in candidatos}
    resumo = {"meta": 0, "google": 0, "sql": 0, "total": 0}
    anuncios_c: Counter = Counter()
    for k, lista in enumerate(listas):
        for l in lista or []:
            r = achados.get(str(l["id"])) if fonte_do_lead(l) == "organico" else None
            if not r:
                continue
            plataforma = "google" if r[0] == "Google Ads" else "meta"
            l["canal"], l["grupo"], l["reclassificado"] = plataforma, "online_pago", True
            if k == 0:
                resumo["total"] += 1
                resumo[plataforma] += 1
                resumo["sql"] += int(l.get("etapa", 0) >= 2)
                anuncios_c[r[1] or r[0]] += 1
    resumo["anuncios"] = [{"nome": n, "leads": q} for n, q in anuncios_c.most_common(5)]
    return resumo


def _organicos_origem(leads: List[Dict[str, Any]], sqls: Optional[List[Dict[str, Any]]], inicio: Optional[date] = None) -> Dict[str, Any]:
    """
    De onde vieram de verdade os leads que o BI chama de orgânicos (e a indicação).

    O BI classifica pela ÚLTIMA conversão: o lead que veio de um anúncio e depois conversou com a assistente no WhatsApp vira "WhatsApp".
    Aqui cada um é aberto, da evidência mais forte para a mais fraca:
      1. Indique e Ganhe: o lead está na base do BeeViral (campanha, quem indicou);
      2. rastro de anúncio no CV: UTM de anúncio/clique pago, ou uma conversão dele com origem "Busca Compartilhada" ou "Click To WhatsApp";
      3. busca orgânica do Google ("Busca Orgânica");
      4. UTM de outra origem (Instagram, link da bio, site...), formulário ou mídia do CV;
      5. WhatsApp direto, sem nenhum rastro.
    Não muda a conta do BI (o lead continua orgânico); só mostra o que há por trás.
    """
    alvo = [l for l in leads if fonte_do_lead(l) in ("organico", "indicacao")]
    if not alvo:
        return {"total": 0, "categorias": [], "indique_e_ganhe": [], "com_rastro_de_anuncio": 0}
    ids = {str(l["id"]) for l in alvo}
    brutos = {str(r.get("idlead")): r for r in bases.registros("cv_leads") if str(r.get("idlead")) in ids}
    convs: Dict[str, List[Dict[str, Any]]] = {}
    for c in bases.registros("cv_conversoes"):
        if str(c.get("idlead")) in ids:
            convs.setdefault(str(c["idlead"]), []).append(c)
    rd = origem_rd.por_lead()

    def digitos(t: Any) -> str:
        return re.sub(r"\D", "", str(t or ""))[-9:]

    bee_email, bee_fone = {}, {}
    for b in bases.registros("beeviral"):
        if b.get("EMAIL"):
            bee_email[str(b["EMAIL"]).strip().lower()] = b
        if digitos(b.get("PHONE")):
            bee_fone[digitos(b.get("PHONE"))] = b

    sql_ids = {str(l["id"]) for l in (sqls or [])}
    categorias: Dict[str, Dict[str, Any]] = {}
    indique: Dict[str, int] = Counter()
    exemplos: Dict[str, Counter] = {}

    def somar(cat: str, detalhe: str, lead: Dict[str, Any]) -> None:
        c = categorias.setdefault(cat, {"categoria": cat, "leads": 0, "sql": 0, "vendas": 0})
        c["leads"] += 1
        c["sql"] += int(str(lead["id"]) in sql_ids or lead["etapa"] >= 2)
        c["vendas"] += int(lead["vendido"])
        exemplos.setdefault(cat, Counter())[detalhe] += 1

    com_rastro = 0
    antigos = 0
    for l in alvo:
        raw = brutos.get(str(l["id"])) or {}
        if inicio and str(raw.get("data_cad") or "9999")[:10] < inicio.isoformat():
            antigos += 1
        email = str(raw.get("email") or "").strip().lower()
        # 1) Indique e Ganhe
        b = bee_email.get(email) or bee_fone.get(digitos(raw.get("telefone")))
        if l["grupo"] == "indicacao_digital" or b:
            campanha = ((b or {}).get("CAMPAIGN") or {}).get("NAME") or "sem registro no BeeViral"
            indique[campanha] += 1
            somar("Indique e Ganhe", campanha, l)
            continue
        # 2) rastro de anúncio (ficou como orgânico só se não achou nada)
        rastro = _rastro_do_lead(str(l["id"]), raw, convs.get(str(l["id"]), []))
        if rastro:
            com_rastro += 1
            somar(f"Veio de anúncio ({rastro[0]}) e depois falou com a assistente", rastro[1] or rastro[0], l)
            continue
        # 3) busca orgânica do Google
        if any("busca organica" in bi._limpo(c.get("conversao")) for c in convs.get(str(l["id"]), [])):
            somar("Busca orgânica do Google", "Busca Orgânica", l)
            continue
        # 4/5) o que sobrar
        origem, _ = origem_do_organico(l, raw, rd)
        if origem.startswith("WhatsApp"):
            somar("WhatsApp direto, sem nenhum rastro de anúncio", origem, l)
        else:
            somar(origem, origem, l)

    total = len(alvo)
    saida = []
    for c in sorted(categorias.values(), key=lambda x: -x["leads"]):
        saida.append({**c, "pct": _pct(c["leads"], total), "pct_sql": _pct(c["sql"], c["leads"]),
                      "detalhes": [{"nome": n, "leads": q} for n, q in exemplos[c["categoria"]].most_common(4)]})
    return {
        "total": total, "categorias": saida, "com_rastro_de_anuncio": com_rastro, "cadastrados_antes_do_periodo": antigos,
        "indique_e_ganhe": [{"campanha": n, "leads": q} for n, q in indique.most_common()],
    }


def _tipo_da_campanha_meta(nome: Optional[str]) -> Optional[str]:
    """'ctw' (clique no WhatsApp), 'formulario' (cadastro/formulário da Meta) ou None (alcance, vídeo, engajamento...). Pelo nome da campanha."""
    n = bi._limpo(nome)
    if "whatsapp" in n or "ctw" in n:
        return "ctw"
    if "leads cadastro" in n or "leads_cadastro" in n or "gdc" in n or "formulario" in n or "cadastro" in n:
        return "formulario"
    return None


def _pracas_com_formulario_lido(formularios: Dict[str, List[Dict[str, Any]]], leads: List[Dict[str, Any]]) -> Set[str]:
    """Praças em que os formulários da Meta são lidos pelo sistema (há lead de formulário casado nos últimos 90 dias): ali, não casar = não é formulário."""
    ids = {str(l["id"]): l for l in leads if l.get("canal") == "meta"}
    cobertas: Set[str] = set()
    for id_lead, lista in formularios.items():
        l = ids.get(id_lead)
        if l and any(f.get("data") and l.get("data") and abs((f["data"] - l["data"]).days) <= 90 for f in lista):
            cobertas.add(l["praca_lead"])
    return cobertas


def _tipo_do_lead_meta(lead: Dict[str, Any], formularios: Optional[Dict[str, List[Dict[str, Any]]]] = None, pracas_cobertas: Optional[Set[str]] = None) -> str:
    """
    'formulario' ou 'ctw' (clique no WhatsApp) de um lead de Meta, com o critério mais forte que existir:
      1. o lead preencheu um formulário da Meta (achado no CV por e-mail ou telefone, até 30 dias do lead): é formulário;
      2. praça em que os formulários da Meta são lidos e o lead não casou com nenhum: é clique no WhatsApp (o padrão da conversão não vale,
         porque "meta_ads" também aparece em lead de clique: em Central Parque II dava 20 formulários contra 5 que a Meta registra);
      3. praça sem leitura dos formulários (Itu/Altavista): vale o marcador do CV: RD Station, Campanha Meta, Busca Compartilhada ou
         "Facebook | meta_ads | meta_ads" = formulário; "Click To WhatsApp" ou conversa com o título do anúncio = clique no WhatsApp.
    """
    for f in (formularios or {}).get(str(lead["id"]), []):
        if f.get("data") and lead.get("data") and abs((f["data"] - lead["data"]).days) <= 30:  # 30 dias: a janela que mais se aproxima do que a Meta registra
            return "formulario"
    if lead.get("reclassificado"):
        return "ctw"  # voltou pelo WhatsApp depois do anúncio
    if pracas_cobertas and lead.get("praca_lead") in pracas_cobertas:
        return "ctw"
    texto = bi._limpo(lead.get("conversao"))
    primeiro = texto.split("|")[0].strip()
    if primeiro in ("rdstation", "campanha meta", "busca compartilhada") or "meta_ads" in texto:
        return "formulario"
    return "ctw"


def _ctw_x_formulario(leads: List[Dict[str, Any]], sqls: Optional[List[Dict[str, Any]]], opps: Optional[List[Dict[str, Any]]], insights: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Clique no WhatsApp (CTW) contra formulário da Meta, por praça: investimento, leads, SQL, OPPS, vendas e custos de cada um."""
    formularios = anuncios._formularios_por_lead_cv()
    cobertas = _pracas_com_formulario_lido(formularios, leads)
    tipo_de_lead: Dict[Any, str] = {l["id"]: _tipo_do_lead_meta(l, formularios, cobertas) for l in leads if l["canal"] == "meta"}

    def vazio() -> Dict[str, Any]:
        return {"investimento": 0.0, "leads": 0, "sql": 0, "opps": 0, "vendas": 0, "leads_plataforma": 0.0, "conversas": 0.0, "formularios": 0.0}

    por_praca: Dict[str, Dict[str, Dict[str, Any]]] = {}
    outras: Dict[str, float] = {}

    def bloco(praca: str, tipo: str) -> Dict[str, Any]:
        return por_praca.setdefault(praca, {"ctw": vazio(), "formulario": vazio()})[tipo]

    for r in insights:
        if r["plataforma"] != "meta":
            continue
        praca = bi.praca_do_empreendimento(r["empreendimento"]) or "Não identificada"
        tipo = _tipo_da_campanha_meta(r.get("campanha_nome"))
        if tipo is None:
            outras[praca] = outras.get(praca, 0.0) + (r["investimento"] or 0)
            continue
        b = bloco(praca, tipo)
        b["investimento"] += r["investimento"] or 0
        b["leads_plataforma"] += r.get("leads_plataforma") or 0
        b["conversas"] += r.get("conversas_whatsapp") or 0
        b["formularios"] += r.get("leads_formulario") or 0

    for l in leads:
        if l["canal"] != "meta":
            continue
        b = bloco(l["praca_lead"], tipo_de_lead[l["id"]])
        b["leads"] += 1
        b["vendas"] += int(l["vendido"])
    meta_ids = set(tipo_de_lead)
    for lista, campo in ((sqls, "sql"), (opps, "opps")):
        for l in lista or []:
            if l["id"] in meta_ids or l["canal"] == "meta":
                tipo = tipo_de_lead.get(l["id"]) or _tipo_do_lead_meta(l, formularios, cobertas)
                bloco(l["praca_lead"], tipo)[campo] += 1

    def final(b: Dict[str, Any]) -> Dict[str, Any]:
        return {**b, "investimento": round(b["investimento"], 2), "leads_plataforma": round(b["leads_plataforma"]), "conversas": round(b["conversas"]), "formularios": round(b["formularios"]),
                "cpl": _div(b["investimento"], b["leads"]) if b["investimento"] else None,
                "pct_sql": _pct(b["sql"], b["leads"]), "pct_opps": _pct(b["opps"], b["leads"]),
                "custo_sql": _div(b["investimento"], b["sql"]) if b["investimento"] else None,
                "custo_opps": _div(b["investimento"], b["opps"]) if b["investimento"] else None,
                "custo_venda": _div(b["investimento"], b["vendas"]) if b["investimento"] else None}

    total = {"ctw": vazio(), "formulario": vazio()}
    for blocos in por_praca.values():
        for tipo in ("ctw", "formulario"):
            for k, v in blocos[tipo].items():
                total[tipo][k] += v
    pracas = [{"praca": praca, "ctw": final(b["ctw"]), "formulario": final(b["formulario"])}
              for praca, b in sorted(por_praca.items(), key=lambda x: -(x[1]["ctw"]["investimento"] + x[1]["formulario"]["investimento"]))
              if any(b[t]["investimento"] for t in ("ctw", "formulario"))]
    return {"total": {t: final(total[t]) for t in ("ctw", "formulario")}, "pracas": pracas, "outras_campanhas": round(sum(outras.values()), 2)}


def _metas_do_mes(fim: date, emp_f: Set[str], praca_f: Set[str], leads: Optional[List[Dict[str, Any]]] = None, insights: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """
    Meta de leads do mês por praça e empreendimento (planilha de metas), com o saldo do que faltou nos meses anteriores, e quanto investir:
    investimento a mais para fechar a meta do mês (leads que faltam × custo por lead pago do produto) e o que novembro pede, somando o saldo que
    passa adiante (projeção de fim de mês).
    """
    try:
        from engine import metas
        m = metas.calcular(fim, emp_f, praca_f)
    except Exception:  # noqa: BLE001 — a meta é um complemento: sem a planilha importada, o resto da Apresentação segue
        return None
    if not m:
        return None
    invest: Dict[str, float] = {}
    for r in insights or []:
        if r["plataforma"] in ("meta", "google"):
            invest[r["empreendimento"]] = invest.get(r["empreendimento"], 0.0) + (r["investimento"] or 0)
    pagos: Dict[str, int] = {}
    for l in leads or []:
        if fonte_do_lead(l) in ("meta", "google"):
            pagos[l["empreendimento_lead"]] = pagos.get(l["empreendimento_lead"], 0) + 1
    dias_mes, dias = m["dias_no_mes"], max(m["dias_decorridos"], 1)
    peso_mes = min(dias / dias_mes, 1.0)
    m["peso_cpl_mes"] = round(peso_mes, 3)
    for g in m["pracas"]:
        for p in g["produtos"]:
            inv, n = invest.get(p["produto"], 0.0), pagos.get(p["produto"], 0)
            cpl_mes = inv / n if inv and n else None
            # CPL de referência do investimento necessário: o CPL pago do mês e o histórico do empreendimento (planilha de metas), com o peso do mês
            # crescendo com os dias que já passaram (peso = dias decorridos ÷ dias do mês). No começo do mês vale o histórico; no fim, o que o mês
            # entregou. É o CPL esperado no fim do mês se os dias que faltam renderem o histórico. Se faltar um dos dois, vale o outro.
            hist = p.get("cpl_historico")
            cpl = peso_mes * cpl_mes + (1 - peso_mes) * hist if hist and cpl_mes else (hist or cpl_mes)
            falta_fim = max(0, p["meta_efetiva"] - (p["projecao"] or 0)) if p["projecao"] is not None else None
            meta_prox = p["prox_meta_base"] + (falta_fim or 0)
            p.update({
                "investimento_mes": round(inv, 2), "leads_pagos": n, "cpl_pago": round(cpl_mes, 2) if cpl_mes else None, "cpl_usado": round(cpl, 2) if cpl else None,
                "cpl_base": "mês e histórico, ponderados pelos dias" if (p.get("cpl_historico") and cpl_mes) else ("histórico" if p.get("cpl_historico") else "do mês"),
                "investir_a_mais": round(p["falta"] * cpl, 2) if cpl and p["atingido"] is not None else None,
                "falta_fim_projetada": falta_fim, "prox_meta_efetiva": meta_prox,
                "prox_investimento": round(meta_prox * cpl, 2) if cpl else None,
                "investimento_ritmo_mes": round(inv / dias * dias_mes, 2) if inv else None,
            })
        com = [p for p in g["produtos"] if p.get("cpl_usado") and not p.get("sem_dados")]
        g["investimento_mes"] = round(sum(p["investimento_mes"] for p in com), 2)
        g["investir_a_mais"] = round(sum(p["investir_a_mais"] or 0 for p in com), 2)
        g["prox_meta_base"] = sum(p["prox_meta_base"] for p in g["produtos"] if not p.get("sem_dados"))
        g["prox_meta_efetiva"] = sum(p["prox_meta_efetiva"] for p in com)
        g["prox_investimento"] = round(sum(p["prox_investimento"] or 0 for p in com), 2)
        g["investimento_ritmo_mes"] = round(sum(p["investimento_ritmo_mes"] or 0 for p in com), 2)
        g["falta_fim_projetada"] = sum(p["falta_fim_projetada"] or 0 for p in com)
    validas = [g for g in m["pracas"] if g["meta_efetiva"] and not g.get("sem_dados")]
    for k in ("investimento_mes", "investir_a_mais", "prox_meta_base", "prox_meta_efetiva", "prox_investimento", "investimento_ritmo_mes", "falta_fim_projetada"):
        m["total"][k] = round(sum(g.get(k, 0) for g in validas), 2)
    m["prox_mes"] = m["pracas"][0]["produtos"][0]["prox_mes"] if m["pracas"] and m["pracas"][0]["produtos"] else None
    return m


def _completude(anuncios_pp: Dict[str, Any], metas: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    O que está incompleto ou desatualizado para esta Apresentação: base atrasada ou com erro, conta da Meta não lida, anúncio sem imagem,
    cartão de campeão vazio, meta de leads não importada. Aparece no topo da página, para ninguém apresentar com dado faltando sem saber.
    """
    itens: List[Dict[str, str]] = []
    limites = {"cv_conversoes": 24, "cv_leads": 24, "cv_leads_historico": 24, "cv_leads_dw": 24, "meta_insights": 24, "meta_anuncios": 24,
               "google_insights": 36, "google_anuncios": 36, "ga4_trafego": 48, "rd_leads": 48}
    for chave, limite in limites.items():
        try:
            r = bases.resumo(chave)
        except Exception:  # noqa: BLE001
            continue
        st, idade = r.get("status") or {}, r.get("idade_horas")
        nome = (r.get("label") or chave)
        if st.get("mode") != "real":
            itens.append({"nivel": "erro", "texto": f"{nome}: {str(st.get('message') or 'base não baixada')[:140]}"})
            continue
        if "não lidas" in str(st.get("message")) or "Contas não lidas" in str(st.get("message")):
            trecho = str(st.get("message")).split("Contas não lidas:")[-1].strip()[:200]
            itens.append({"nivel": "aviso", "texto": f"{nome}: conta(s) da Meta lida(s) só em parte ou não lida(s): {trecho}"})
        if idade is None or idade > limite:
            itens.append({"nivel": "aviso", "texto": f"{nome}: dados de {'?' if idade is None else round(idade)}h atrás (limite {limite}h). Clique em Atualizar dados."})
    for praca, b in anuncios_pp.items():
        quadro = b.get("quadro") or []
        sem = [a for a in quadro if not a.get("miniatura")]
        if quadro and sem:
            itens.append({"nivel": "aviso", "texto": f"{praca}: {len(sem)} de {len(quadro)} anúncios sem imagem (a Meta não devolveu a miniatura)."})
        vazios = [c["titulo"] for c in b.get("criterios", []) if not c.get("ranking")]
        if vazios:
            itens.append({"nivel": "aviso", "texto": f"{praca}: cartão(ões) de campeões sem anúncio: {', '.join(vazios)}."})
    if metas is None:
        itens.append({"nivel": "aviso", "texto": "Meta de leads por praça não importada (rode: python -m engine.metas importar <planilha>)."})
    return {"ok": not itens, "itens": itens}


def _participacao_praca(inicio: date, fim: date, praca: str) -> Optional[Dict[str, Any]]:
    """Das buscas em que os anúncios do Google da praça podiam aparecer: quanto apareceram e quanto perderam por ranking e por verba."""
    passa = _filtro_local(set(), {praca})
    meses = palavras._meses(inicio, fim)
    peso_total = p = o = r = 0.0
    campanhas: Dict[str, Dict[str, float]] = {}
    for row in bases.registros("google_detalhes"):
        if row.get("tipo") != "participacao" or row.get("participacao") is None:
            continue
        if not _no_periodo(row, inicio, fim, meses) or not passa(row)[0]:
            continue
        peso = row.get("impressoes") or 0
        peso_total += peso
        p += (row.get("participacao") or 0) * peso
        o += (row.get("perdida_orcamento") or 0) * peso
        r += (row.get("perdida_ranking") or 0) * peso
        c = campanhas.setdefault(row.get("campanha_nome") or "—", {"imp": 0.0, "p": 0.0, "o": 0.0, "r": 0.0})
        c["imp"] += peso
        c["p"] += (row.get("participacao") or 0) * peso
        c["o"] += (row.get("perdida_orcamento") or 0) * peso
        c["r"] += (row.get("perdida_ranking") or 0) * peso
    if not peso_total:
        return None
    return {
        "impressoes": int(peso_total), "apareceu": round(p / peso_total * 100, 1), "perdida_orcamento": round(o / peso_total * 100, 1),
        "perdida_ranking": round(r / peso_total * 100, 1),
        "campanhas": [{"campanha": n, "impressoes": int(c["imp"]), "apareceu": round(c["p"] / c["imp"] * 100, 1), "perdida_ranking": round(c["r"] / c["imp"] * 100, 1),
                       "perdida_orcamento": round(c["o"] / c["imp"] * 100, 1)} for n, c in sorted(campanhas.items(), key=lambda kv: -kv[1]["imp"])[:4] if c["imp"]],
    }


def _cpc_praca(insights: List[Dict[str, Any]], praca: str, plataforma: str = "google") -> Optional[Dict[str, Any]]:
    inv = cliques = imp = 0.0
    for x in insights:
        if x["plataforma"] == plataforma and bi.praca_do_empreendimento(x["empreendimento"]) == praca:
            inv += x.get("investimento") or 0
            cliques += x.get("cliques") or 0
            imp += x.get("impressoes") or 0
    if not cliques:
        return None
    return {"investimento": round(inv, 2), "cliques": int(cliques), "cpc": round(inv / cliques, 2), "cpm": round(inv / imp * 1000, 2) if imp else None}


def _concorrencia_do_periodo(inicio: date, fim: date, comp: Tuple[date, date], insights_p: List[Dict[str, Any]], insights_ant: List[Dict[str, Any]], pracas: List[str]) -> Dict[str, Any]:
    """Concorrência de cada praça: pressão no leilão (nossos dados do Google e da Meta) e quem anuncia (Biblioteca de Anúncios da Meta)."""
    from engine import concorrencia

    base = concorrencia.compilar()
    saida: Dict[str, Any] = {}
    for praca in pracas:
        agora, antes = _participacao_praca(inicio, fim, praca), _participacao_praca(comp[0], comp[1], praca)
        cpc_a, cpc_b = _cpc_praca(insights_p, praca), _cpc_praca(insights_ant, praca)
        cpm_a, cpm_b = _cpc_praca(insights_p, praca, "meta"), _cpc_praca(insights_ant, praca, "meta")
        saida[praca] = {
            "google": {"agora": agora, "antes": antes, "cpc": cpc_a, "cpc_antes": cpc_b, "var_cpc": _variacao(cpc_a["cpc"] if cpc_a else None, cpc_b["cpc"] if cpc_b else None)},
            "meta": {"cpm": cpm_a["cpm"] if cpm_a else None, "cpm_antes": cpm_b["cpm"] if cpm_b else None,
                     "var_cpm": _variacao(cpm_a["cpm"] if cpm_a else None, cpm_b["cpm"] if cpm_b else None)},
            "anunciantes": base["pracas"].get(praca),
        }
    return {"disponivel": base["disponivel"], "coletado_em": base["coletado_em"], "consultas": base["consultas"], "inicio_campanha": base["inicio_campanha"], "pracas": saida,
            "auction_insights": "Os dados de leilão do Google (Auction Insights: quem concorre, sobreposição, quem aparece acima) não saem pela API sem aprovação do Google; a pressão do Google aqui é a que a própria conta informa (participação de impressões perdida por ranking e por verba)."}


def compilar(inicio: date, fim: date, empreendimentos: Optional[List[str]] = None, pracas: Optional[List[str]] = None) -> Dict[str, Any]:
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    comp = periodo_de_comparacao(inicio, fim)
    dias = (fim - inicio).days + 1

    expandidos = bi._expandir_por_interesse(bi.leads_preparados())
    insights = insights_resolvidos(bi._insights_com_empreendimento(bases.registros("cv_empreendimentos")))
    usa_bi = bool(bases.registros("cv_conversoes"))
    fora_do_online: Counter = Counter()
    if usa_bi:
        leads = leads_do_bi(inicio, fim, emp_f, praca_f, fora_do_online)
        leads_ant = leads_do_bi(comp[0], comp[1], emp_f, praca_f)
    else:
        leads = _leads_do_periodo(expandidos, inicio, fim, emp_f, praca_f)
        leads_ant = _leads_do_periodo(expandidos, comp[0], comp[1], emp_f, praca_f)
    # O custo de campanha que atende mais de um produto é dividido pelos leads de cada um (estimativa), para o produto
    # não aparecer com lead e sem custo. Os pesos usam os leads de TODOS os produtos da praça, não só os do filtro.
    def _leads_sem_filtro(ini: date, fi: date) -> List[Dict[str, Any]]:
        return leads_do_bi(ini, fi, set(), set()) if usa_bi else _leads_do_periodo(expandidos, ini, fi, set(), set())

    grupos = _grupos_de_recursos()
    todos_p, rateio = ratear_sem_produto(_insights_do_periodo(insights, inicio, fim, set(), set()), _leads_sem_filtro(inicio, fim), grupos)
    todos_ant, _ = ratear_sem_produto(_insights_do_periodo(insights, comp[0], comp[1], set(), set()), _leads_sem_filtro(comp[0], comp[1]), grupos)
    insights_p = _insights_do_periodo(todos_p, inicio, fim, emp_f, praca_f)
    insights_ant = _insights_do_periodo(todos_ant, comp[0], comp[1], emp_f, praca_f)

    sql_p = sql_ant = opps_p = None
    if usa_bi:
        from engine import leads_bi as _lb
        sql_p = _lb.sql_do_bi(inicio, fim, emp_f, praca_f)
        sql_ant = _lb.sql_do_bi(comp[0], comp[1], emp_f, praca_f)
    reclass = reclassificar_pagos([leads, leads_ant, sql_p, sql_ant]) if usa_bi else None
    atual, anterior = _resumo(leads, insights_p, sql_p), _resumo(leads_ant, insights_ant, sql_ant)
    if usa_bi:
        opps_p = _lb.opps_do_bi(inicio, fim, emp_f, praca_f)
        reclassificar_pagos([opps_p])
        atual['total']['opps'] = len(opps_p)
        anterior['total']['opps'] = len(_lb.opps_do_bi(comp[0], comp[1], emp_f, praca_f))
    brutos = {str(r.get("idlead")): r for r in bases.registros("cv_leads")}

    auditoria = anuncios.auditoria(inicio, fim, empreendimentos, pracas)
    lista = auditoria["anuncios"]

    avisos: List[str] = []
    if not usa_bi:
        avisos.append("A base de conversões do CV ainda não foi baixada: os leads estão contados pela regra antiga e podem não bater com o Power BI. Atualize as bases.")
    else:
        avisos.append("Leads e origem seguem a regra do Power BI da gestão (conversão do mês, origem da mídia da conversão). SQL e OPPS contam quem entrou nessa situação no período, pelo histórico de situações do CV, como o BI; pode diferir em poucas unidades.")
    relevantes = [f"{o['origem']} ({o['leads']})" for o in [{"origem": o, "leads": n} for o, n in fora_do_online.most_common(4)] if o["origem"] != "(sem mídia)"]
    if usa_bi and relevantes:
        avisos.append("Fora do online, como no BI: " + ", ".join(relevantes) + ".")
    for item in rateio:
        valor = "R$ " + f"{item['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        partes = ", ".join(f"{empreendimento_curto_py(p['empreendimento'])} (R$ {format(p['valor'], ',.0f').replace(',', '.')})" for p in item["produtos"][:4])
        nome = "Google" if item["plataforma"] == "google" else "Meta"
        if item["metodo"] == "grupo":
            avisos.append(f"{valor} de {nome} em {item['praca']} vêm de uma campanha que atende mais de um produto; o custo foi dividido pelo custo de cada grupo de recursos, que o Google informa: {partes}.")
        else:
            avisos.append(f"Estimativa: {valor} de {nome} em {item['praca']} vêm de campanha que atende mais de um produto; o custo foi dividido pelos leads de cada um: {partes}.")
    if emp_f:
        # Campanha que atende mais de um produto da praça não entra no filtro de um produto: diz quanto ficou de fora
        pracas_filtro = {bi.praca_do_empreendimento(e) for e in emp_f}
        fora = {}
        for r in todos_p:
            if r["empreendimento"].endswith(SEM_PRODUTO) and bi.praca_do_empreendimento(r["empreendimento"]) in pracas_filtro:
                fora[r["plataforma"]] = fora.get(r["plataforma"], 0) + (r["investimento"] or 0)
        for plataforma, valor in fora.items():
            if valor >= 1:
                reais = "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                avisos.append(
                    f"{reais} de {'Google' if plataforma == 'google' else 'Meta'} da mesma praça ficam fora deste filtro: a campanha atende mais de um produto "
                    "e não dá para atribuí-la a um só. Filtre pela praça para incluir esse gasto."
                )
    meta_f = atual["fontes"]["meta"]
    if meta_f.get("cpl_com_whatsapp") and meta_f.get("cpl"):
        brl = lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        avisos.append(
            f"O CPL do Meta tem uma faixa: {brl(meta_f['cpl_com_whatsapp'])} a {brl(meta_f['cpl'])}. O clique no WhatsApp de anúncio já conta como Meta; o piso soma também "
            f"os {meta_f['leads_whatsapp']} lead(s) de WhatsApp que o assistente não marcou como orgânicos (podem ser anúncio sem rastreio), porque {brl(meta_f['investimento_whatsapp'])} "
            "do gasto foi em campanha de conversa por WhatsApp. O valor real fica entre os dois."
        )
    sem_custo = atual["total"].get("leads_pagos", 0) - atual["total"].get("leads_pagos_com_custo", 0)
    if sem_custo > 0:
        avisos.append(f"{sem_custo} lead(s) pago(s) de uma fonte sem custo atribuído neste recorte ficaram fora do CPL pago, para ele não sair menor que o CPL de cada fonte.")
    if not insights_p:
        avisos.append("Sem investimento de Meta/Google no período: custo por lead indisponível.")
    if not auditoria["disponivel"]:
        avisos.append("A base de anúncios da Meta ainda não foi baixada: os campeões de anúncio ficam vazios.")
    avisos += [a for a in auditoria["avisos"] if a.startswith("Só ")]
    g = atual["fontes"]["google"]
    if g["leads_plataforma"] >= 5 and g["leads"] < g["leads_plataforma"] * 0.5:
        avisos.append(
            f"O Google registra {g['leads_plataforma']} conversões, mas só {g['leads']} lead(s) chegaram ao CV com origem Google: "
            "o CPL do CV do Google fica alto demais. Use o CPL da plataforma como referência."
        )
    site = _site(inicio, fim, comp, empreendimentos or [], pracas or [], 10)
    if site["dados_ate"] and site["dados_ate"] < fim.isoformat():
        d = site["dados_ate"]
        avisos.append(f"O Google Analytics foi baixado só até {d[8:10]}/{d[5:7]}: atualize os dados para o site cobrir o período inteiro.")
    termos = _termos(inicio, fim, emp_f, praca_f, 10)
    # Quanto dos cliques das campanhas os termos explicam: o Google omite os termos de pouquíssimo volume
    cliques_campanha = {"Performance Max": 0, "Pesquisa": 0}
    for r in insights_p:
        if r["plataforma"] == "google":
            cliques_campanha["Performance Max" if _tipo_campanha(r.get("campanha_nome")) == "Performance Max" else "Pesquisa"] += r.get("cliques") or 0
    for chave, tipo in (("pmax", "Performance Max"), ("pesquisa", "Pesquisa")):
        termos[chave]["cobertura"] = _pct(termos[chave]["cliques"], cliques_campanha[tipo])
    if not termos["exato"]:
        avisos.append("A base de termos do Google ainda está no formato antigo (por mês, só categorias): atualize os dados para ver os termos reais.")

    leads_meta_praca: Counter = Counter()
    if usa_bi:
        for l in leads:
            if l["canal"] == "meta" and l.get("praca_lead"):
                leads_meta_praca[l["praca_lead"]] += 1
    anuncios_pp = _anuncios_por_praca(lista, dias, insights_p, dict(leads_meta_praca), fim, inicio, emp_f)
    metas_mes = _metas_do_mes(fim, emp_f, praca_f, leads, insights_p) if usa_bi else None
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "dias": dias},
        "comparacao": {"inicio": comp[0].isoformat(), "fim": comp[1].isoformat()},
        "filtro": {"empreendimentos": sorted(emp_f), "pracas": sorted(praca_f)},
        "resumo": {**atual, "anterior": anterior, "variacao": _comparar(atual, anterior)},
        "fontes": [{"chave": c, "label": l} for c, l in FONTES],
        "por_empreendimento": _por_empreendimento(leads, insights_p, 10, sql_p),
        "organicos": _origens_do_bi(leads, 8, sql_p) if usa_bi else _organicos(leads, brutos),
        "metas_leads": metas_mes,
        "completude": _completude(anuncios_pp, metas_mes),
        "ctw_x_formulario": _ctw_x_formulario(leads, sql_p, opps_p, insights_p) if usa_bi else None,
        "organicos_origem": ({**_organicos_origem(leads, sql_p, inicio), "reclassificados": reclass} if usa_bi else None),
        "regra_leads": "bi" if usa_bi else "cv",
        "custo_rateado": rateio,
        "origens_fora_do_online": [{"origem": o, "leads": n} for o, n in fora_do_online.most_common(8)],
        "anuncios": {
            "disponivel": auditoria["disponivel"],
            "total": len(lista),
            "cobertura": auditoria["resumo"]["cobertura"],
            **_campeoes_anuncios(lista, dias),
        },
        "anuncios_por_praca": anuncios_pp,
        "concorrencia": _concorrencia_do_periodo(inicio, fim, comp, insights_p, insights_ant, list(anuncios_pp.keys())),
        "criativos": {
            **_criativos_reais(lista, sum(1 for l in leads if l["canal"] == "meta"), sum(1 for l in (sql_p or []) if l["canal"] == "meta")),
            "observacao": "Criativo = a peça lida na Meta (cópias em outras campanhas contam uma vez); formato vem do criativo e o assunto, do que ele diz. Investimento é medido; leads e SQL somam os do Resumo, e a divisão por anúncio é estimada (o CV não diz de qual anúncio veio cada clique no WhatsApp).",
        },
        "google": {
            "campanhas": _campanhas_google(insights_p, 8),
            "termos": termos,
            "anuncios": _anuncios_google(inicio, fim, emp_f, praca_f, dias),
            "detalhes": _detalhes_google(inicio, fim, emp_f, praca_f),
            "palavras_chave": _palavras_chave(inicio, fim, emp_f, praca_f, 8),
        },
        "site": site,
        "bases": [bases.resumo(b) for b in ("cv_leads", "cv_conversoes", "meta_anuncios", "google_insights", "google_termos", "google_anuncios", "google_detalhes", "ga4_trafego")],
        "avisos": avisos,
    }
