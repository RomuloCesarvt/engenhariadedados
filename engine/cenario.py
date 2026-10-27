"""
Cenário: por que o custo por lead mudou.

Quebra o CPL em três pedaços que têm causas diferentes:
  - preço do leilão (CPM): o que a plataforma cobra por mil exibições — onde entram eleição e concorrência;
  - clique (CTR): o quanto o criativo atrai;
  - conversão do clique em lead: o quanto a página/formulário/oferta convence.
CPL = CPM ÷ (1000 × CTR × conversão), então a variação do CPL é a soma (em logaritmo) das variações dos três.

Para a eleição não existe medidor direto: o que há é um teste indicativo. Compara-se o CPM de antes da campanha
eleitoral com o das últimas semanas, e olha-se se ele subiu também nas contas em que o NOSSO investimento não
subiu (se só subisse onde investimos mais, a causa seria a nossa pressão no leilão, não o mercado).

A concorrência vem de uma coleta da Biblioteca de Anúncios da Meta (anúncios ativos que citam a praça),
guardada em output/bases/concorrencia.json — a Biblioteca não tem API para anúncios comerciais no Brasil.
"""

import json
import math
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from engine import bases, bi
from engine.apresentacao import insights_resolvidos, periodo_de_comparacao, _insights_do_periodo

# Calendário eleitoral de 2026 (eleição geral). A Meta pausou novos anúncios políticos de 2 a 5/10 e de 23 a 26/10.
INICIO_CAMPANHA = date(2026, 8, 16)
PRIMEIRO_TURNO = date(2026, 10, 4)
SEGUNDO_TURNO = date(2026, 10, 25)
PAUSAS_META = [(date(2026, 10, 2), date(2026, 10, 5)), (date(2026, 10, 23), date(2026, 10, 26))]
DIAS_BASE = 35

ARQUIVO_CONCORRENCIA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output", "bases", "concorrencia.json"))
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _div(a: float, b: float, casas: int = 2) -> Optional[float]:
    return round(a / b, casas) if b else None


def _var(novo: Optional[float], antigo: Optional[float]) -> Optional[float]:
    return round((novo - antigo) / antigo * 100, 1) if novo is not None and antigo else None


def _metricas(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    imp = sum(r.get("impressoes") or 0 for r in rows)
    cli = sum(r.get("cliques") or 0 for r in rows)
    leads = sum(r.get("leads_plataforma") or 0 for r in rows)
    inv = sum(r.get("investimento") or 0 for r in rows)
    return {
        "investimento": round(inv, 2), "impressoes": imp, "cliques": cli, "leads": leads,
        "cpm": _div(inv * 1000, imp), "ctr": _div(cli * 100, imp, 3), "cpc": _div(inv, cli),
        "conversao": _div(leads * 100, cli, 2), "cpl": _div(inv, leads),
    }


def _atribuicao(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Quanto da variação do CPL veio de cada pedaço. Em logaritmo a conta fecha:
    ln(CPL) = ln(CPM) - ln(CTR) - ln(conversão) - constante.
    """
    chaves = ("cpm", "ctr", "conversao", "cpl")
    if not all(a.get(k) and b.get(k) for k in chaves):
        return None
    total = math.log(b["cpl"] / a["cpl"])
    partes = {
        "preco": math.log(b["cpm"] / a["cpm"]),
        "clique": -math.log(b["ctr"] / a["ctr"]),
        "conversao": -math.log(b["conversao"] / a["conversao"]),
    }
    if abs(total) < 0.02:
        return {"sentido": "estavel", **{k: None for k in partes}}
    return {"sentido": "alta" if total > 0 else "queda", **{k: round(v / total * 100) for k, v in partes.items()}}


def _filtrar(plataforma: str, ini: date, fim: date, insights, emp_f: Set[str], praca_f: Set[str]) -> List[Dict[str, Any]]:
    return [r for r in _insights_do_periodo(insights, ini, fim, emp_f, praca_f) if r["plataforma"] == plataforma]


def _dias(janela: Tuple[date, date]) -> int:
    return (janela[1] - janela[0]).days + 1


def _bloco(plataforma: str, atual: List[Dict[str, Any]], antes: List[Dict[str, Any]], dias_atual: int = 1, dias_antes: int = 1) -> Dict[str, Any]:
    """
    Antes × agora de uma plataforma. As janelas podem ter tamanhos diferentes (5 semanas × 4), então a variação do
    investimento compara a média POR DIA; comparar os totais faria o gasto parecer menor do que é.
    """
    a, b = _metricas(antes), _metricas(atual)
    variacao = {k: _var(b[k], a[k]) for k in ("investimento", "cpm", "ctr", "cpc", "conversao", "cpl")}
    variacao["investimento"] = _var(b["investimento"] / dias_atual, a["investimento"] / dias_antes) if a["investimento"] else None
    return {
        "plataforma": plataforma, "antes": a, "agora": b, "dias_antes": dias_antes, "dias_agora": dias_atual,
        "variacao": variacao,
        "atribuicao": _atribuicao(a, b),
    }


def _janelas(fim: date) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    """Base: as 5 semanas antes da campanha eleitoral. Recente: as últimas 4 semanas fechadas (segunda a domingo)."""
    base = (INICIO_CAMPANHA - timedelta(days=DIAS_BASE), INICIO_CAMPANHA - timedelta(days=1))
    fim_recente = fim - timedelta(days=(fim.weekday() + 1) % 7)
    return base, (fim_recente - timedelta(days=27), fim_recente)


def _segunda(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _serie_semanal(insights, plataforma: str, emp_f, praca_f, ate: date) -> List[Dict[str, Any]]:
    semanas: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    for r in insights:
        if r["plataforma"] != plataforma or not r["data_d"]:
            continue
        if emp_f and r["empreendimento"] not in emp_f:
            continue
        if praca_f and (bi.praca_do_empreendimento(r["empreendimento"]) or "Não identificada") not in praca_f:
            continue
        semanas[_segunda(r["data_d"])].append(r)
    saida = []
    for seg in sorted(semanas):
        # só semanas completas: a que está em andamento distorce a média
        if seg + timedelta(days=6) > ate or seg < date(2026, 5, 25):
            continue
        m = _metricas(semanas[seg])
        saida.append({"semana": seg.isoformat(), **{k: m[k] for k in ("investimento", "cpm", "cpc", "conversao", "cpl")}})
    return saida


def _serie_2025(insights, plataforma: str) -> List[Dict[str, Any]]:
    """As mesmas semanas de 2025 (sem eleição geral), como referência de sazonalidade."""
    semanas: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    for r in insights:
        if r["plataforma"] == plataforma and r["data_d"] and date(2025, 8, 25) <= r["data_d"] <= date(2025, 11, 2):
            semanas[_segunda(r["data_d"])].append(r)
    return [{"semana": s.isoformat(), "cpm": _metricas(rows)["cpm"]} for s, rows in sorted(semanas.items()) if _metricas(rows)["impressoes"] > 20000]


def _por_conta(insights, base, recente, plataforma: str, emp_f, praca_f) -> List[Dict[str, Any]]:
    """Cada conta (= empreendimento) antes e agora, para separar o efeito do mercado do efeito do nosso investimento."""
    def agrupar(janela):
        d: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in _filtrar(plataforma, janela[0], janela[1], insights, emp_f, praca_f):
            d[r.get("conta_nome") or r["empreendimento"]].append(r)
        return d

    a, b = agrupar(base), agrupar(recente)
    saida = []
    for conta, rows_b in b.items():
        rows_a = a.get(conta) or []
        ma, mb = _metricas(rows_a), _metricas(rows_b)
        if ma["impressoes"] < 20000 or mb["impressoes"] < 20000:
            continue
        emp = rows_b[0]["empreendimento"]
        var_inv = _var(mb["investimento"] / _dias(recente), ma["investimento"] / _dias(base)) if ma["investimento"] else None
        saida.append({
            "conta": conta, "empreendimento": emp, "praca": bi.praca_do_empreendimento(emp) or "Não identificada",
            "investimento_antes": ma["investimento"], "investimento_agora": mb["investimento"], "var_investimento": var_inv,
            "dias_antes": _dias(base), "dias_agora": _dias(recente),
            "investimento_estavel": var_inv is not None and var_inv <= 15,
            "var_cpm": _var(mb["cpm"], ma["cpm"]), "var_cpc": _var(mb["cpc"], ma["cpc"]),
            "var_conversao": _var(mb["conversao"], ma["conversao"]),
            "cpl_antes": ma["cpl"], "cpl_agora": mb["cpl"], "var_cpl": _var(mb["cpl"], ma["cpl"]),
            "atribuicao": _atribuicao(ma, mb),
        })
    saida.sort(key=lambda c: -c["investimento_agora"])
    return saida


def _teste_eleicao(contas: List[Dict[str, Any]], geral: Dict[str, Any]) -> Dict[str, Any]:
    estaveis = [c for c in contas if c["investimento_estavel"] and c["var_cpm"] is not None]
    medianas = sorted(c["var_cpm"] for c in estaveis)
    mediana = medianas[len(medianas) // 2] if medianas else None
    return {
        "inicio_campanha": INICIO_CAMPANHA.isoformat(), "primeiro_turno": PRIMEIRO_TURNO.isoformat(), "segundo_turno": SEGUNDO_TURNO.isoformat(),
        "pausas_meta": [{"de": a.isoformat(), "ate": b.isoformat()} for a, b in PAUSAS_META],
        "var_cpm_geral": geral["variacao"]["cpm"],
        "contas_estaveis": len(estaveis),
        "contas_estaveis_cpm_subiu": sum(1 for c in estaveis if (c["var_cpm"] or 0) > 5),
        "mediana_cpm_contas_estaveis": mediana,
    }


# ---------------------------------------------------------------------------
# Concorrência
# ---------------------------------------------------------------------------

_NAO_IMOVEL = re.compile(r"academia|viajando|collab|clinika|raices|arquitet|remax ve|win leil|cons[oó]rcio|magalu", re.I)
_CORRETOR = re.compile(r"im[oó]ve|imobili|corretor|broker|cushman|emaxim", re.I)
_LOTEADORA = re.compile(r"loteament|urbanismo|empreendiment|terrenos|campos de|costa verde|residencial|represa", re.I)


def _data_br(texto: str) -> Optional[date]:
    try:
        d, m, a = texto.split("/")
        return date(int(a), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def _tipo(nome: str) -> str:
    if _LOTEADORA.search(nome):
        return "Loteadora / empreendimento"
    if _CORRETOR.search(nome):
        return "Corretor / imobiliária"
    return "Outro"


def _concorrencia() -> Dict[str, Any]:
    if not os.path.exists(ARQUIVO_CONCORRENCIA):
        return {"disponivel": False, "pracas": []}
    dados = json.load(open(ARQUIVO_CONCORRENCIA, encoding="utf-8"))
    pracas = []
    for praca, buscas in dados["pracas"].items():
        anunciantes: Dict[str, Dict[str, Any]] = {}
        for busca in buscas.values():
            for a in busca["anunciantes"]:
                if _NAO_IMOVEL.search(a["nome"]):
                    continue
                it = anunciantes.setdefault(a["nome"], {"nome": a["nome"], "anuncios": 0, "desde": a["desde"], "tipo": _tipo(a["nome"])})
                it["anuncios"] = max(it["anuncios"], a["anuncios"])
                d_novo, d_atual = _data_br(a["desde"]), _data_br(it["desde"])
                if d_novo and d_atual and d_novo < d_atual:
                    it["desde"] = a["desde"]
        lista = sorted(anunciantes.values(), key=lambda x: (-x["anuncios"], x["nome"]))
        novos = [x for x in lista if (_data_br(x["desde"]) or date.min) >= INICIO_CAMPANHA]
        pracas.append({
            "praca": praca,
            "resultados": {q: b["total_resultados"] for q, b in buscas.items()},
            "maior_busca": max(b["total_resultados"] for b in buscas.values()),
            "anunciantes": len(lista),
            "loteadoras": sum(1 for x in lista if x["tipo"] == "Loteadora / empreendimento"),
            "novos_na_campanha": len(novos),
            "principais": lista[:5],
            "lista": lista,
            "corretores": sum(1 for x in lista if x["tipo"] == "Corretor / imobiliária"),
        })
    return {"disponivel": True, "coletado_em": dados.get("coletado_em"), "fonte": dados.get("fonte"), "limites": dados.get("limites"), "pracas": pracas}


def _por_praca(contas: List[Dict[str, Any]], concorrencia: Dict[str, Any]) -> List[Dict[str, Any]]:
    """CPL de cada praça ao lado da concorrência dela: é aqui que a pergunta 'foi a concorrência?' se testa."""
    grupos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in contas:
        grupos[c["praca"]].append(c)
    conc = {bi._limpo(p["praca"]): p for p in concorrencia.get("pracas", [])}
    saida = []
    for praca, cs in grupos.items():
        inv_a, inv_b = sum(c["investimento_antes"] for c in cs), sum(c["investimento_agora"] for c in cs)
        dias_a, dias_b = (cs[0].get("dias_antes") or 1), (cs[0].get("dias_agora") or 1)
        c = conc.get(bi._limpo(praca))
        pesos = [(x["var_cpm"], x["investimento_agora"]) for x in cs if x["var_cpm"] is not None]
        cpm = sum(v * p for v, p in pesos) / sum(p for _, p in pesos) if pesos else None
        pesos_cpl = [(x["var_cpl"], x["investimento_agora"]) for x in cs if x["var_cpl"] is not None]
        cpl = sum(v * p for v, p in pesos_cpl) / sum(p for _, p in pesos_cpl) if pesos_cpl else None
        pesos_conv = [(x["var_conversao"], x["investimento_agora"]) for x in cs if x["var_conversao"] is not None]
        conv = sum(v * p for v, p in pesos_conv) / sum(p for _, p in pesos_conv) if pesos_conv else None
        saida.append({
            "praca": praca, "investimento_agora": round(inv_b, 2), "var_investimento": _var(inv_b / dias_b, inv_a / dias_a) if inv_a else None,
            "var_cpm": round(cpm, 1) if cpm is not None else None, "var_conversao": round(conv, 1) if conv is not None else None,
            "var_cpl": round(cpl, 1) if cpl is not None else None,
            "concorrencia": ({"maior_busca": c["maior_busca"], "novos_na_campanha": c["novos_na_campanha"],
                              "loteadoras": c["loteadoras"], "anunciantes": c["anunciantes"]} if c else None),
        })
    saida.sort(key=lambda p: -p["investimento_agora"])
    return saida


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _leitura(meta: Dict[str, Any], teste: Dict[str, Any], pracas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Frases que o slide mostra. Cada uma diz o que os números sustentam — e o que eles não provam."""
    achados: List[Dict[str, str]] = []
    at, v = meta.get("atribuicao"), meta["variacao"]
    if at and at["sentido"] == "alta" and v["cpl"] is not None:
        achados.append({"tipo": "fato", "texto": (
            f"O CPL do Meta subiu {v['cpl']:.0f}% em relação ao período antes da campanha eleitoral. "
            f"Do aumento, cerca de {at['preco']}% veio do preço do leilão (CPM {v['cpm']:+.0f}%), "
            f"{at['clique']}% do clique (CTR {v['ctr']:+.0f}%) e {at['conversao']}% da conversão do clique em lead ({v['conversao']:+.0f}%).")})
    if teste["contas_estaveis"]:
        achados.append({"tipo": "indicio", "texto": (
            f"Em {teste['contas_estaveis_cpm_subiu']} de {teste['contas_estaveis']} contas em que o nosso investimento não subiu, o CPM subiu "
            f"(mediana {teste['mediana_cpm_contas_estaveis']:+.0f}%). Isso aponta para pressão de mercado, e não só para o nosso gasto — "
            "compatível com a eleição (campanha desde 16/08, 1º turno em 04/10, 2º turno em 25/10), mas não a prova.")})
    com_conc = [p for p in pracas if p.get("concorrencia") and p["var_cpl"] is not None]
    if com_conc:
        mais = max(com_conc, key=lambda p: p["concorrencia"]["maior_busca"])
        menos = [p for p in com_conc if p["concorrencia"]["maior_busca"] < 20 and p["var_cpl"] is not None]
        texto = f"{mais['praca']} é a praça mais disputada ({mais['concorrencia']['maior_busca']} anúncios ativos citando a cidade, {mais['concorrencia']['novos_na_campanha']} anunciantes novos desde 16/08) e o CPL variou {mais['var_cpl']:+.0f}%."
        if menos:
            m = max(menos, key=lambda p: abs(p["var_cpl"]))
            texto += f" Já {m['praca']} quase não tem concorrente visível e o CPL variou {m['var_cpl']:+.0f}% — onde a concorrência não explica, a causa está no preço geral do leilão ou no nosso lado."
        achados.append({"tipo": "indicio", "texto": texto})
    if at and at["sentido"] == "alta" and at["conversao"] and at["conversao"] >= 35:
        achados.append({"tipo": "atencao", "texto": (
            "A conversão do clique em lead caiu bastante. Isso não é preço de leilão: pode ser fadiga do criativo, mudança na página ou no formulário, "
            "ou menos intenção de compra no período eleitoral. Vale revisar os anúncios com mais impressões e o funil do formulário.")})
    achados.append({"tipo": "limite", "texto": (
        "Os dados não separam eleição, concorrência e o nosso próprio aumento de investimento: os três mexem no leilão ao mesmo tempo. "
        "Por isso o cenário aponta onde olhar, e não afirma uma causa única.")})
    return achados



# ---------------------------------------------------------------------------
# Cenário de cada praça
# ---------------------------------------------------------------------------


def _r(valor: float) -> str:
    """R$ 29,38 (vírgula decimal, como o resto do sistema)."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _intensidade(maior_busca: int) -> str:
    return "alta" if maior_busca >= 100 else "média" if maior_busca >= 30 else "baixa"


def _leitura_praca(praca: str, meta: Dict[str, Any], google: Dict[str, Any], contas: List[Dict[str, Any]], conc: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    achados: List[Dict[str, str]] = []
    v, at = meta["variacao"], meta["atribuicao"]
    a, g = meta["antes"], meta["agora"]

    if g["cpl"] and a["cpl"] and v["cpl"] is not None:
        texto = f"O CPL do Meta em {praca} {'subiu' if v['cpl'] > 0 else 'caiu'} {abs(v['cpl']):.0f}% (de {_r(a['cpl'])} para {_r(g['cpl'])})."
        if abs(v["cpl"]) < 15:
            texto += " Variação pequena: não há o que decompor."
        elif at and at["sentido"] == "alta":
            texto += (f" Do aumento: {at['preco']}% veio do preço do leilão (CPM {v['cpm']:+.0f}%), {at['clique']}% do clique "
                      f"e {at['conversao']}% da conversão do clique em lead ({v['conversao']:+.0f}%).")
        achados.append({"tipo": "fato", "texto": texto})
    else:
        achados.append({"tipo": "limite", "texto": f"{praca} não tem investimento no Meta nas duas janelas: não dá para comparar o CPL."})

    cpm, inv = v["cpm"], v["investimento"]
    if cpm is not None:
        if cpm > 10 and (inv is None or inv <= 15):
            achados.append({"tipo": "indicio", "texto": (
                f"O CPM subiu {cpm:.0f}% sem aumento relevante do nosso investimento (ritmo diário {inv:+.0f}%): o leilão encareceu por fora da nossa pressão. "
                "Compatível com a eleição (campanha desde 16/08, 2º turno em 25/10), mas não é prova.")})
        elif cpm > 10:
            achados.append({"tipo": "indicio", "texto": (
                f"O CPM subiu {cpm:.0f}%, mas o nosso investimento também subiu {inv:+.0f}% por dia: parte da alta pode ser o nosso próprio aumento no leilão, "
                "então a eleição não é a única hipótese.")})
        elif abs(cpm) <= 10:
            achados.append({"tipo": "fato", "texto": f"O preço do leilão ficou estável aqui (CPM {cpm:+.0f}%): nesta praça a eleição não aparece no preço."})

    if conc:
        itens = [x for x in conc.get("lista", [])]
        loteadoras = [x["nome"] for x in itens if x["tipo"] == "Loteadora / empreendimento"][:3]
        texto = (f"Concorrência {_intensidade(conc['maior_busca'])}: {conc['maior_busca']} anúncios ativos citam {praca}, "
                 f"{conc['novos_na_campanha']} anunciante(s) entraram desde 16/08; corretores/imobiliárias entre os maiores anunciantes: {conc.get('corretores', 0)}.")
        if loteadoras:
            texto += " Loteadoras/empreendimentos: " + ", ".join(loteadoras) + "."
        achados.append({"tipo": "indicio", "texto": texto})
        if conc["maior_busca"] < 30 and v["cpl"] is not None and v["cpl"] > 30:
            achados.append({"tipo": "atencao", "texto": "O CPL subiu com pouca concorrência visível: a concorrência não explica. A causa está no leilão geral ou no nosso lado (criativo, página, formulário)."})
    else:
        achados.append({"tipo": "limite", "texto": f"Sem coleta de concorrência para {praca}."})

    if v["conversao"] is not None and v["conversao"] <= -30:
        piores = sorted((c for c in contas if c["var_conversao"] is not None), key=lambda c: c["var_conversao"])[:2]
        nomes = ", ".join(f"{c['conta']} ({c['var_conversao']:+.0f}%)" for c in piores)
        achados.append({"tipo": "atencao", "texto": f"A conversão do clique em lead caiu {abs(v['conversao']):.0f}%. Isso não é preço de leilão — revise criativos, página e formulário. Onde mais caiu: {nomes}."})

    gg, ga, vg = google["agora"], google["antes"], google["variacao"]
    if gg["investimento"] > 0:
        texto = f"No Google, {praca} gastou {_r(gg['investimento'])} nas últimas 4 semanas"
        if vg["investimento"] is not None:
            texto += f" (ritmo diário {vg['investimento']:+.0f}% contra antes da campanha)"
        if gg["cpl"] and ga["cpl"] and vg["cpl"] is not None:
            texto += f"; o CPL da plataforma foi de {_r(ga['cpl'])} para {_r(gg['cpl'])} ({vg['cpl']:+.0f}%)"
        elif gg["cpl"]:
            texto += f"; CPL da plataforma {_r(gg['cpl'])} (sem gasto antes da campanha para comparar)"
        achados.append({"tipo": "fato", "texto": texto + "."})
    return achados


def _cenario_praca(praca: str, insights, base, recente, fim: date, concorrencia: Dict[str, Any], emp_f: Set[str]) -> Dict[str, Any]:
    praca_f = {praca}
    meta = _bloco("meta", _filtrar("meta", recente[0], recente[1], insights, emp_f, praca_f), _filtrar("meta", base[0], base[1], insights, emp_f, praca_f), _dias(recente), _dias(base))
    google = _bloco("google", _filtrar("google", recente[0], recente[1], insights, emp_f, praca_f), _filtrar("google", base[0], base[1], insights, emp_f, praca_f), _dias(recente), _dias(base))
    contas = _por_conta(insights, base, recente, "meta", emp_f, praca_f)
    conc = next((c for c in concorrencia.get("pracas", []) if bi._limpo(c["praca"]) == bi._limpo(praca)), None)
    return {
        "praca": praca,
        "meta": meta, "google": google,
        "serie": {"meta": _serie_semanal(insights, "meta", emp_f, praca_f, fim), "meta_2025": []},
        "contas": contas,
        "concorrencia": ({k: conc[k] for k in ("maior_busca", "resultados", "anunciantes", "loteadoras", "corretores", "novos_na_campanha")} | {"lista": conc["lista"][:8]}) if conc else None,
        "leitura": _leitura_praca(praca, meta, google, contas, conc),
    }

def _ratear_sem_produto(insights: List[Dict[str, Any]], ini: date, fim: date) -> List[Dict[str, Any]]:
    """
    A verba de campanha que atende mais de um produto da praça (comum no Google) fica numa linha "sem produto definido"; com um
    produto selecionado ela sumia e o gasto aparecia zerado. Aqui ela é repartida como na Apresentação (custo do grupo de recursos,
    quando o Google informa, ou pelos leads de cada produto), dentro do intervalo que o cenário usa.
    """
    from engine.apresentacao import ratear_sem_produto, _grupos_de_recursos
    from engine.leads_bi import leads_do_bi
    if not bases.registros("cv_conversoes"):
        return insights
    dentro = [r for r in insights if r["data_d"] and ini <= r["data_d"] <= fim]
    fora = [r for r in insights if not (r["data_d"] and ini <= r["data_d"] <= fim)]
    rateados, _ = ratear_sem_produto(dentro, leads_do_bi(ini, fim, set(), set()), _grupos_de_recursos())
    return fora + rateados


def compilar(inicio: date, fim: date, empreendimentos: Optional[List[str]] = None, pracas: Optional[List[str]] = None) -> Dict[str, Any]:
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    insights = insights_resolvidos(bi._insights_com_empreendimento(bases.registros("cv_empreendimentos")))
    comp = periodo_de_comparacao(inicio, fim)
    base, recente = _janelas(fim)
    insights = _ratear_sem_produto(insights, min(base[0], comp[0], inicio), fim)

    mes = {p: _bloco(p, _filtrar(p, inicio, fim, insights, emp_f, praca_f), _filtrar(p, comp[0], comp[1], insights, emp_f, praca_f)) for p in ("meta", "google")}
    desde_a_eleicao = {p: _bloco(p, _filtrar(p, recente[0], recente[1], insights, emp_f, praca_f), _filtrar(p, base[0], base[1], insights, emp_f, praca_f), _dias(recente), _dias(base)) for p in ("meta", "google")}
    contas = _por_conta(insights, base, recente, "meta", emp_f, praca_f)
    concorrencia = _concorrencia()
    por_praca = _por_praca(contas, concorrencia)
    teste = _teste_eleicao(contas, desde_a_eleicao["meta"])

    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "comparacao": {"inicio": comp[0].isoformat(), "fim": comp[1].isoformat()},
        "janelas": {"base": [base[0].isoformat(), base[1].isoformat()], "recente": [recente[0].isoformat(), recente[1].isoformat()]},
        "mes_contra_mes": mes,
        "antes_da_eleicao_contra_agora": desde_a_eleicao,
        "serie": {"meta": _serie_semanal(insights, "meta", emp_f, praca_f, fim), "google": _serie_semanal(insights, "google", emp_f, praca_f, fim),
                  "meta_2025": _serie_2025(insights, "meta")},
        "contas": contas,
        "eleicao": teste,
        "por_praca": por_praca,
        "concorrencia": concorrencia,
        "cenarios_por_praca": [
            _cenario_praca(p["praca"], insights, base, recente, fim, concorrencia, emp_f)
            for p in por_praca
            if not p["praca"].startswith("Não") and p["investimento_agora"] > 0
        ],
        "leitura": _leitura(desde_a_eleicao["meta"], teste, por_praca),
        "avisos": ["CPL aqui é o da plataforma (investimento ÷ leads que a Meta/Google registram), porque só ele se decompõe em cliques e impressões."],
    }
