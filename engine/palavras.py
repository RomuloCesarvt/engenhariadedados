"""
As palavras que trazem gente: as palavras-chave dos anúncios do Google em cada empreendimento e as
palavras buscadas que viraram sessão no site, por praça (Google Analytics).

Cada linha da base do GA4 é uma palavra num mês, com a campanha e a página de entrada. A praça
sai do empreendimento, e o empreendimento é achado na página de entrada, na campanha ou na própria
palavra (quem procura "terreno em itatinga" diz a cidade). O que não dá para ligar fica junto, em
"Não identificado", em vez de sumir.

O GA4 só tem a palavra quando ela veio do Google Ads (palavra-chave paga) ou de uma UTM com
utm_term. A busca orgânica do Google não traz palavra: isso só existe no Search Console.
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from engine import bases
from engine.bi import praca_do_empreendimento
from engine.normalizer import (EMPREENDIMENTO_DESCONHECIDO, cidade_no_texto, cidades_do_catalogo,
                               match_empreendimento, normalize_empreendimento)

PRACA_DESCONHECIDA = "Não identificada"
LIMITE_PADRAO = 12


def _mes(valor: Any) -> Optional[str]:
    texto = str(valor or "")
    return texto[:7] if re.fullmatch(r"\d{4}-\d{2}", texto[:7]) else None


def _dia(valor: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _meses(inicio: date, fim: date) -> Set[str]:
    """Meses que o período toca. O GA4 vem por mês: um filtro de dias cai no mês inteiro."""
    meses, ano, mes = set(), inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.add(f"{ano:04d}-{mes:02d}")
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def _texto(valor: Any) -> str:
    return re.sub(r"[-_/?=&+]", " ", str(valor or ""))


# De onde sai o empreendimento em cada base, na ordem da evidência mais forte para a mais fraca.
# No Google Ads a palavra NÃO entra: ela é o que a pessoa digitou, não onde o anúncio rodou —
# "central parque avare" buscado numa campanha da cidade não faz a verba ser do Central Parque.
CAMPOS_GA4 = ("pagina_entrada", "campanha_nome", "palavra")
CAMPOS_GOOGLE = ("conta_nome", "campanha_nome", "grupo_nome")


def local_da_linha(row: Dict[str, Any], catalogo: List[str], cidades: List[Tuple[str, str]],
                   cache: Dict[Any, Tuple[str, str]], campos: Tuple[str, ...] = CAMPOS_GA4) -> Tuple[str, str]:
    """
    O empreendimento e a praça de uma linha.

    Os campos são lidos na ordem dada — no Google Ads a conta costuma ser o empreendimento; no GA4,
    a página de entrada. A primeira que bate com o catálogo vale. Se nenhuma bate, fica só a cidade
    citada no texto: a campanha "avare_google-pmax_lancamento" roda nas contas dos dois produtos de
    Avaré, então o número é da praça, não de um produto escolhido a dedo.
    """
    chave = tuple(row.get(c) for c in campos)
    if chave not in cache:
        textos = [_texto(row.get(c)) for c in campos]
        empreendimento = next((m for t in textos if (m := match_empreendimento(t, catalogo))), None)
        cidade = cidade_no_texto(" ".join(textos), cidades)
        # O texto cita uma cidade, e o produto que casou é de outra: a página
        # "/empreendimento/central-parque-botucatu" não é o Central Parque de Avaré. Sem catálogo
        # para o produto de Botucatu, fica na praça — atribuir ao produto errado é pior.
        if empreendimento and cidade and not _mesma_cidade(empreendimento, cidade):
            empreendimento = None
        if empreendimento:
            cache[chave] = (empreendimento, praca_do_empreendimento(empreendimento) or PRACA_DESCONHECIDA)
        else:
            cache[chave] = (EMPREENDIMENTO_DESCONHECIDO, cidade or PRACA_DESCONHECIDA)
    return cache[chave]


def _mesma_cidade(empreendimento: str, cidade: str) -> bool:
    """O empreendimento do catálogo ("Avaré - Central Parque - 13700") é dessa cidade?"""
    return normalize_empreendimento(str(empreendimento).split(" - ")[0]) == normalize_empreendimento(cidade)


def _div(a: float, b: float, casas: int = 2) -> Optional[float]:
    return round(a / b, casas) if b else None


# De onde sai o empreendimento na base de termos de pesquisa (o termo, pelo mesmo motivo, fica fora)
CAMPOS_TERMOS = ("conta_nome", "campanha_nome")


def _termos_por_local(meses, catalogo, cidades, cache, emp_f, praca_f, limite, inicio=None, fim=None) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    O que as pessoas digitaram, por empreendimento.

    É o que existe no Performance Max, que não tem palavra-chave. O Google agrupa os termos em
    categorias e não informa o custo de cada uma — por isso aqui só há impressões, cliques e
    conversões.
    """
    agrupado: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
    for row in bases.registros("google_termos"):
        dia = _dia(row.get("data"))
        if dia is not None and inicio and fim:  # base nova: termo por dia, o período vale exatamente
            if not (inicio <= dia <= fim):
                continue
        elif _mes(row.get("mes")) not in meses:
            continue
        empreendimento, praca = local_da_linha(row, catalogo, cidades, cache, CAMPOS_TERMOS)
        if (emp_f and empreendimento not in emp_f) or (praca_f and praca not in praca_f):
            continue
        termo = str(row.get("termo") or "").strip()
        if not termo:
            continue
        item = agrupado.setdefault((empreendimento, praca), {}).setdefault(
            termo, {"termo": termo, "impressoes": 0, "cliques": 0, "conversoes": 0.0, "canais": set()})
        for campo in ("impressoes", "cliques", "conversoes"):
            item[campo] += row.get(campo) or 0
        if row.get("canal"):
            item["canais"].add(row["canal"])

    saida: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for chave, termos in agrupado.items():
        lista = sorted(({**t, "conversoes": round(t["conversoes"], 2), "canais": sorted(t["canais"])}
                        for t in termos.values()), key=lambda t: -t["cliques"])
        saida[chave] = {
            "termos": lista[:limite],
            "distintos": len(lista),
            "cliques": sum(t["cliques"] for t in lista),
            "conversoes": round(sum(t["conversoes"] for t in lista), 2),
            "canais": sorted({c for t in lista for c in t["canais"]}),
        }
    return saida


def por_empreendimento(
    inicio: date,
    fim: date,
    empreendimentos: Optional[List[str]] = None,
    pracas: Optional[List[str]] = None,
    limite: int = LIMITE_PADRAO,
) -> Dict[str, Any]:
    """
    As melhores palavras-chave dos anúncios do Google em cada empreendimento.

    Melhor é a que traz conversão: primeiro as que converteram, da mais barata por conversão para a
    mais cara; depois as que só trouxeram clique, das mais clicadas para as menos. Assim a lista
    começa pelo que vale a pena manter e termina no que só gasta.
    """
    base = bases.resumo("google_palavras")
    catalogo = bases.registros("cv_empreendimentos")
    meses = _meses(inicio, fim)
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    cidades = cidades_do_catalogo(catalogo)
    cache: Dict[Any, Tuple[str, str]] = {}

    agrupado: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
    for row in bases.registros("google_palavras"):
        # A palavra-chave vem por dia: o período escolhido na tela vale exatamente
        dia = _dia(row.get("data"))
        if dia is None:
            if _mes(row.get("mes")) not in meses:  # base antiga, ainda por mês
                continue
        elif not (inicio <= dia <= fim):
            continue
        empreendimento, praca = local_da_linha(row, catalogo, cidades, cache, CAMPOS_GOOGLE)
        if (emp_f and empreendimento not in emp_f) or (praca_f and praca not in praca_f):
            continue
        palavra = str(row.get("palavra") or "").strip().lower()
        if not palavra:
            continue
        item = agrupado.setdefault((empreendimento, praca), {}).setdefault(
            palavra, {"palavra": palavra, "correspondencia": row.get("correspondencia"), "investimento": 0.0,
                      "impressoes": 0, "cliques": 0, "conversoes": 0.0, "campanhas": set()})
        for campo in ("investimento", "impressoes", "cliques", "conversoes"):
            item[campo] += row.get(campo) or 0
        if row.get("campanha_nome"):
            item["campanhas"].add(row["campanha_nome"])

    termos = _termos_por_local(meses, catalogo, cidades, cache, emp_f, praca_f, limite, inicio, fim)
    saida = []
    for chave in termos:  # produto que só tem termo (Performance Max) também aparece
        agrupado.setdefault(chave, {})
    for (empreendimento, praca), palavras in agrupado.items():
        lista = [
            {**p, "investimento": round(p["investimento"], 2), "conversoes": round(p["conversoes"], 2),
             "ctr": _div(p["cliques"] * 100, p["impressoes"], 1), "cpc": _div(p["investimento"], p["cliques"]),
             "custo_por_conversao": _div(p["investimento"], p["conversoes"]),
             "campanhas": sorted(p["campanhas"])[:3]}
            for p in palavras.values()
        ]
        # Quem converteu vem primeiro, da conversão mais barata para a mais cara
        lista.sort(key=lambda p: (p["conversoes"] <= 0, p["custo_por_conversao"] if p["conversoes"] else -p["cliques"]))
        investimento = round(sum(p["investimento"] for p in lista), 2)
        conversoes = round(sum(p["conversoes"] for p in lista), 2)
        saida.append({
            "empreendimento": empreendimento,
            "praca": praca,
            "investimento": investimento,
            "impressoes": sum(p["impressoes"] for p in lista),
            "cliques": sum(p["cliques"] for p in lista),
            "conversoes": conversoes,
            "custo_por_conversao": _div(investimento, conversoes),
            "palavras_distintas": len(lista),
            "palavras_com_conversao": sum(1 for p in lista if p["conversoes"] > 0),
            "palavras": lista[:limite],
            "sem_conversao": sorted((p for p in lista if not p["conversoes"] and p["investimento"] > 0),
                                    key=lambda p: -p["investimento"])[:5],
            **{("termos" if k == "termos" else f"termos_{k}"): v
               for k, v in (termos.get((empreendimento, praca)) or
                            {"termos": [], "distintos": 0, "cliques": 0, "conversoes": 0.0, "canais": []}).items()},
        })
    saida.sort(key=lambda e: (e["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO, -e["investimento"]))
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "por_mes": sorted(meses)},
        "empreendimentos": saida,
        "base": base,
        "base_termos": bases.resumo("google_termos"),
        # As palavras-chave seguem o dia; os termos, só o mês — é o que o Google entrega de cada um
        "granularidade": {"palavras": "dia", "termos": "dia", "meses_dos_termos": sorted(meses)},
        "observacao": ("Palavras-chave dos anúncios de pesquisa do Google, no período exato escolhido. Conversão é o "
                       "que a conta do Google marca como ação principal — não é a venda do CV."),
        "observacao_termos": ("Termos de pesquisa: o que as pessoas digitaram, no período exato, para campanhas de pesquisa e "
                              "Performance Max. O Google omite os termos com pouquíssimo volume."),
    }


def por_praca(
    inicio: date,
    fim: date,
    empreendimentos: Optional[List[str]] = None,
    pracas: Optional[List[str]] = None,
    limite: int = LIMITE_PADRAO,
) -> Dict[str, Any]:
    """As palavras mais buscadas de cada praça no período, com sessões, usuários e conversões."""
    base = bases.resumo("ga4_palavras")
    catalogo = bases.registros("cv_empreendimentos")
    meses = _meses(inicio, fim)
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    cidades = cidades_do_catalogo(catalogo)
    cache: Dict[Any, Tuple[str, str]] = {}

    agrupado: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in bases.registros("ga4_palavras"):
        if _mes(row.get("mes")) not in meses:
            continue
        empreendimento, praca = local_da_linha(row, catalogo, cidades, cache)
        if (emp_f and empreendimento not in emp_f) or (praca_f and praca not in praca_f):
            continue
        palavra = str(row.get("palavra") or "").strip().lower()
        if not palavra:
            continue
        item = agrupado.setdefault(praca, {}).setdefault(
            palavra, {"palavra": palavra, "tipo": row.get("tipo"), "sessoes": 0, "usuarios": 0, "conversoes": 0,
                      "empreendimentos": set(), "campanhas": set()})
        item["sessoes"] += row.get("sessoes") or 0
        item["usuarios"] += row.get("usuarios") or 0
        item["conversoes"] += row.get("conversoes") or 0
        if empreendimento != EMPREENDIMENTO_DESCONHECIDO:
            item["empreendimentos"].add(empreendimento)
        if row.get("campanha_nome"):
            item["campanhas"].add(row["campanha_nome"])

    pracas_saida = []
    for praca, palavras in agrupado.items():
        lista = sorted(palavras.values(), key=lambda p: (-p["sessoes"], p["palavra"]))
        pracas_saida.append({
            "praca": praca,
            "sessoes": sum(p["sessoes"] for p in lista),
            "conversoes": sum(p["conversoes"] for p in lista),
            "palavras_distintas": len(lista),
            "palavras": [{**p, "empreendimentos": sorted(p["empreendimentos"]), "campanhas": sorted(p["campanhas"])[:3]}
                         for p in lista[:limite]],
        })
    pracas_saida.sort(key=lambda p: (p["praca"] == PRACA_DESCONHECIDA, -p["sessoes"]))
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "por_mes": sorted(meses)},
        "pracas": pracas_saida,
        "base": base,
        "observacao": ("O Google Analytics traz a palavra da busca paga (Google Ads) e o utm_term das campanhas; "
                       "a busca orgânica do Google não tem palavra no GA4. Os números são por mês: um período "
                       "no meio do mês mostra o mês inteiro."),
    }
