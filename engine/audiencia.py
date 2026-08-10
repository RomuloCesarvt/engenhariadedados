"""
A audiência do site (Google Analytics), compilada: de onde vêm as sessões, em que aparelho, de que
cidade e para qual empreendimento — sempre comparado com o período anterior de mesmo tamanho.

O que muda em relação a olhar o GA4 direto:
  - a página de entrada vira empreendimento e praça (as mesmas do CV), então dá para cruzar com
    leads e vendas em vez de ler URL;
  - quem entra pela home ou pelo blog não diz qual produto procurava: isso fica num grupo à parte,
    dito na tela, em vez de ser rateado entre os produtos;
  - cada quadro traz o número do período anterior do lado, e o módulo escreve o que a comparação
    mostra (`analises`) — é o que o Rômulo pede: não só número, leitura.

As bases (`ga4_trafego` e `ga4_cidades`) vêm por dia, então o período escolhido na tela vale
exatamente, e o período anterior é o mesmo número de dias imediatamente antes.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from engine import bases, palavras
from engine.bi import praca_do_empreendimento
from engine.normalizer import (EMPREENDIMENTO_DESCONHECIDO, cidade_no_texto, cidades_do_catalogo,
                               normalize_empreendimento)

PRACA_DESCONHECIDA = palavras.PRACA_DESCONHECIDA
LIMITE_PADRAO = 12
CAMPOS_PAGINA = ("pagina_entrada",)

# Tipos de página de entrada: só a página do empreendimento diz qual produto a pessoa procurava
HOME, BLOG, PRODUTO, OUTRAS = "Home", "Blog", "Página de empreendimento", "Outras páginas"
ORDEM_ENTRADAS = (PRODUTO, HOME, BLOG, OUTRAS)

# Amostras mínimas antes de comentar qualquer variação (sem alarme porque 3 sessões viraram 1)
MIN_SESSOES_TOTAL = 200
MIN_SESSOES_CANAL = 100
MIN_SESSOES_PRODUTO = 80
MIN_SESSOES_CIDADE = 50
MIN_SESSOES_APARELHO = 300
MIN_CONVERSOES = 20         # conversões no período anterior para comentar a variação
VAR_RELEVANTE = 15.0        # % de variação que vale comentar
VAR_FORTE = 30.0            # % de variação de um item isolado
FATOR_CONVERSAO = 1.5       # quanto um aparelho precisa converter mais que o outro para virar achado


def _div(a: float, b: float, casas: int = 1) -> Optional[float]:
    return round(a / b, casas) if b else None


def _pct(parte: float, total: float) -> Optional[float]:
    return round(parte / total * 100, 1) if total else None


def _variacao(atual: float, anterior: float) -> Optional[float]:
    return round((atual - anterior) / anterior * 100, 1) if anterior else None


def _periodo_anterior(inicio: date, fim: date) -> Tuple[date, date]:
    dias = (fim - inicio).days + 1
    return inicio - timedelta(days=dias), inicio - timedelta(days=1)


def _dia(valor: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def tipo_da_pagina(pagina: Optional[str]) -> str:
    """Home, blog, página de empreendimento ou o resto do site."""
    caminho = (pagina or "").split("?")[0].strip().rstrip("/").lower()
    if not caminho:
        return HOME
    if caminho.startswith("/blog"):
        return BLOG
    if caminho.startswith("/empreendimento"):
        return PRODUTO
    return OUTRAS


class _Atribuicao:
    """Liga a página de entrada ao empreendimento e à praça, uma vez por página."""

    def __init__(self):
        self.catalogo = bases.registros("cv_empreendimentos")
        self.cidades = cidades_do_catalogo(self.catalogo)
        self._cache: Dict[Any, Tuple[str, str]] = {}
        self._cidades_norm = {normalize_empreendimento(sem_acento): nome for sem_acento, nome in self.cidades}

    def pagina(self, pagina: Optional[str]) -> Tuple[str, str]:
        return palavras.local_da_linha({"pagina_entrada": pagina}, self.catalogo, self.cidades,
                                       self._cache, CAMPOS_PAGINA)

    def praca_da_cidade(self, cidade: str) -> Optional[str]:
        """A cidade que o GA4 informou é uma praça nossa? ("Avare" no GA4, "Avaré" no CV)"""
        return self._cidades_norm.get(normalize_empreendimento(cidade) or "") or cidade_no_texto(cidade, self.cidades)


def _linhas(chave: str, inicio: date, fim: date, atrib: _Atribuicao,
            empreendimentos: Optional[List[str]], pracas: Optional[List[str]]) -> List[Dict[str, Any]]:
    """As linhas da base no período, já com empreendimento e praça, e já filtradas."""
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    saida = []
    for row in bases.registros(chave):
        dia = _dia(row.get("data"))
        if dia is None or not (inicio <= dia <= fim):
            continue
        empreendimento, praca = atrib.pagina(row.get("pagina_entrada"))
        if (emp_f and empreendimento not in emp_f) or (praca_f and praca not in praca_f):
            continue
        saida.append({**row, "empreendimento": empreendimento, "praca": praca})
    return saida


def _somar(linhas: List[Dict[str, Any]], campos: Tuple[str, ...]) -> Dict[str, int]:
    return {c: sum(l.get(c) or 0 for l in linhas) for c in campos}


CAMPOS_TRAFEGO = ("sessoes", "usuarios", "novos_usuarios", "sessoes_engajadas", "conversoes", "tempo_engajamento")


def _totais(linhas: List[Dict[str, Any]]) -> Dict[str, Any]:
    t = _somar(linhas, CAMPOS_TRAFEGO)
    return {
        **t,
        "pct_novos": _pct(t["novos_usuarios"], t["usuarios"]),
        "engajamento": _pct(t["sessoes_engajadas"], t["sessoes"]),
        "taxa_conversao": _pct(t["conversoes"], t["sessoes"]),
        "tempo_medio": _div(t["tempo_engajamento"], t["sessoes"], 0),
    }


def _quadro(linhas: List[Dict[str, Any]], anteriores: List[Dict[str, Any]], campo: str, rotulo: str,
            limite: Optional[int] = None, extra: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Um quadro comparado: agrupa por um campo (canal, aparelho, cidade, produto) e põe ao lado o
    mesmo grupo no período anterior.
    """
    def agrupar(lista):
        grupos: Dict[str, Dict[str, Any]] = {}
        for l in lista:
            g = grupos.setdefault(str(l.get(campo)), {"sessoes": 0, "usuarios": 0, "sessoes_engajadas": 0,
                                                      "conversoes": 0, "extra": set()})
            for c in ("sessoes", "usuarios", "sessoes_engajadas", "conversoes"):
                g[c] += l.get(c) or 0
            if extra and l.get(extra):
                g["extra"].add(str(l[extra]))
        return grupos

    atual, antes = agrupar(linhas), agrupar(anteriores)
    total = sum(g["sessoes"] for g in atual.values())
    saida = []
    for nome, g in atual.items():
        a = antes.get(nome) or {}
        saida.append({
            rotulo: nome,
            "sessoes": g["sessoes"],
            "pct": _pct(g["sessoes"], total),
            "usuarios": g["usuarios"],
            "engajamento": _pct(g["sessoes_engajadas"], g["sessoes"]),
            "conversoes": g["conversoes"],
            "taxa_conversao": _pct(g["conversoes"], g["sessoes"]),
            "sessoes_antes": a.get("sessoes", 0),
            "variacao": _variacao(g["sessoes"], a.get("sessoes", 0)),
            **({extra: sorted(g["extra"])[:3]} if extra else {}),
        })
    saida.sort(key=lambda x: -x["sessoes"])
    return saida[:limite] if limite else saida


def _produtos(linhas, anteriores, limite) -> List[Dict[str, Any]]:
    """Por empreendimento, com a praça junto. O que não é página de produto fica fora."""
    so_produto = [l for l in linhas if l["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO]
    so_antes = [l for l in anteriores if l["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO]
    quadro = _quadro(so_produto, so_antes, "empreendimento", "empreendimento", limite)
    for item in quadro:
        item["praca"] = praca_do_empreendimento(item["empreendimento"]) or PRACA_DESCONHECIDA
    return quadro


def _entradas(linhas, anteriores) -> List[Dict[str, Any]]:
    """Por tipo de página de entrada, para ficar claro quanto do site não diz qual produto."""
    marcar = lambda lista: [{**l, "tipo_pagina": tipo_da_pagina(l.get("pagina_entrada"))} for l in lista]
    quadro = _quadro(marcar(linhas), marcar(anteriores), "tipo_pagina", "tipo")
    ordem = {t: i for i, t in enumerate(ORDEM_ENTRADAS)}
    quadro.sort(key=lambda x: ordem.get(x["tipo"], 99))
    return quadro


def _cidades(inicio, fim, anterior, atrib, empreendimentos, pracas, limite) -> Dict[str, Any]:
    """De que cidade vem quem acessa, e quanto disso é das nossas praças."""
    atual = _linhas("ga4_cidades", inicio, fim, atrib, empreendimentos, pracas)
    antes = _linhas("ga4_cidades", anterior[0], anterior[1], atrib, empreendimentos, pracas)
    quadro = _quadro(atual, antes, "cidade", "cidade", limite, extra="estado")
    for item in quadro:
        item["praca"] = atrib.praca_da_cidade(item["cidade"])
    sessoes = sum(l["sessoes"] for l in atual)
    das_pracas = sum(l["sessoes"] for l in atual if atrib.praca_da_cidade(l["cidade"]))
    return {
        "cidades": quadro,
        "sessoes": sessoes,
        "distintas": len({l["cidade"] for l in atual}),
        "das_nossas_pracas": das_pracas,
        "pct_das_nossas_pracas": _pct(das_pracas, sessoes),
        "base": bases.resumo("ga4_cidades"),
    }


# ---------------------------------------------------------------------------
# A leitura: o que a comparação mostra
# ---------------------------------------------------------------------------


def _n(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def _p(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.1f}".replace(".", ",") + "%"


def _var(valor: Optional[float]) -> str:
    return "—" if valor is None else ("+" if valor > 0 else "") + _p(valor)


def _achado(chave, tipo, titulo, texto) -> Dict[str, Any]:
    return {"chave": chave, "tipo": tipo, "titulo": titulo, "texto": texto}


def _analise_total(t, ta) -> List[Dict[str, Any]]:
    var = _variacao(t["sessoes"], ta["sessoes"])
    if ta["sessoes"] < MIN_SESSOES_TOTAL or var is None or abs(var) < VAR_RELEVANTE:
        return []
    caiu = var < 0
    return [_achado(
        "sessoes_variacao", "alerta" if caiu else "destaque",
        f"Acessos ao site {'caíram' if caiu else 'subiram'} {_var(var)}",
        f"{_n(t['sessoes'])} sessões no período, contra {_n(ta['sessoes'])} no período anterior de mesmo tamanho.",
    )]


def _analise_conversoes(t, ta) -> List[Dict[str, Any]]:
    """A conversão do site é o que mais interessa: ela pode cair mesmo com o acesso subindo."""
    var = _variacao(t["conversoes"], ta["conversoes"])
    if ta["conversoes"] < MIN_CONVERSOES or var is None or abs(var) < VAR_RELEVANTE:
        return []
    caiu = var < 0
    # Conversão caindo com acesso subindo é o caso que mais importa: o problema está no site, não na mídia
    var_sessoes = _variacao(t["sessoes"], ta["sessoes"])
    contraste = (f" E as sessões foram para o outro lado ({_var(var_sessoes)}): entrou mais gente e converteu menos."
                 if caiu and var_sessoes is not None and var_sessoes > 0 else "")
    return [_achado(
        "conversoes_variacao", "alerta" if caiu else "destaque",
        f"As conversões do site {'caíram' if caiu else 'subiram'} {_var(var)}",
        f"{_n(t['conversoes'])} conversões contra {_n(ta['conversoes'])} no período anterior. "
        f"Taxa: {_p(t['taxa_conversao'])} das sessões, contra {_p(ta['taxa_conversao'])}.{contraste}",
    )]


def _analise_canais(canais) -> List[Dict[str, Any]]:
    """Qual canal explica a mudança: o que mais ganhou ou perdeu sessão em número absoluto."""
    com_base = [c for c in canais if c["sessoes_antes"] >= MIN_SESSOES_CANAL and c["variacao"] is not None]
    if not com_base:
        return []
    achados = []
    pior = min(com_base, key=lambda c: c["sessoes"] - c["sessoes_antes"])
    if pior["sessoes"] - pior["sessoes_antes"] < 0 and abs(pior["variacao"]) >= VAR_RELEVANTE:
        achados.append(_achado(
            "canal_queda", "alerta", f"A queda veio de {pior['canal']}",
            f"{_n(pior['sessoes'])} sessões contra {_n(pior['sessoes_antes'])} ({_var(pior['variacao'])}), "
            f"{_n(pior['sessoes_antes'] - pior['sessoes'])} sessões a menos. É {_p(pior['pct'])} do site.",
        ))
    melhor = max(com_base, key=lambda c: c["sessoes"] - c["sessoes_antes"])
    if melhor["sessoes"] - melhor["sessoes_antes"] > 0 and melhor["variacao"] >= VAR_RELEVANTE:
        achados.append(_achado(
            "canal_alta", "destaque", f"{melhor['canal']} cresceu {_var(melhor['variacao'])}",
            f"{_n(melhor['sessoes'])} sessões contra {_n(melhor['sessoes_antes'])}, "
            f"{_n(melhor['sessoes'] - melhor['sessoes_antes'])} a mais. É {_p(melhor['pct'])} do site.",
        ))
    return achados


def _analise_aparelhos(dispositivos) -> List[Dict[str, Any]]:
    """Celular × computador: quem traz gente e quem converte."""
    por_nome = {d["dispositivo"]: d for d in dispositivos}
    celular, computador = por_nome.get("Celular"), por_nome.get("Computador")
    if not celular or not computador or celular["sessoes"] < MIN_SESSOES_APARELHO:
        return []
    achados = [_achado(
        "aparelho_divisao", "contexto", f"{_p(celular['pct'])} dos acessos são pelo celular",
        f"Celular: {_n(celular['sessoes'])} sessões, {_p(celular['taxa_conversao'])} de conversão. "
        f"Computador: {_n(computador['sessoes'])} sessões, {_p(computador['taxa_conversao'])} de conversão.",
    )]
    tc, tp = celular["taxa_conversao"] or 0, computador["taxa_conversao"] or 0
    if tp and tc and tp >= tc * FATOR_CONVERSAO and celular["pct"] and celular["pct"] >= 50:
        achados.append(_achado(
            "aparelho_conversao", "alerta", "Quem entra pelo celular converte bem menos",
            f"O celular traz {_p(celular['pct'])} das sessões, mas converte {_p(tc)} contra {_p(tp)} do computador. "
            "Vale olhar o formulário e a velocidade da página no celular.",
        ))
    return achados


def _analise_entradas(entradas) -> List[Dict[str, Any]]:
    sem_produto = [e for e in entradas if e["tipo"] in (HOME, BLOG, OUTRAS)]
    pct = sum(e["pct"] or 0 for e in sem_produto)
    if pct < 40:
        return []
    return [_achado(
        "entrada_sem_produto", "contexto", f"{_p(pct)} das sessões não dizem qual produto a pessoa procurava",
        "Entraram pela home, pelo blog ou por outra página institucional. Esse tráfego não é rateado entre os "
        "empreendimentos: aparece separado, para o número de cada produto continuar confiável.",
    )]


def _analise_produtos(produtos) -> List[Dict[str, Any]]:
    if not produtos:
        return []
    achados = []
    topo = produtos[0]
    achados.append(_achado(
        "produto_topo", "contexto", f"{topo['empreendimento']} é o produto mais procurado no site",
        f"{_n(topo['sessoes'])} sessões ({_p(topo['pct'])} das que chegam numa página de empreendimento), "
        f"{_n(topo['conversoes'])} conversão(ões). Variação: {_var(topo['variacao'])}.",
    ))
    caindo = [p for p in produtos if p["sessoes_antes"] >= MIN_SESSOES_PRODUTO
              and p["variacao"] is not None and p["variacao"] <= -VAR_FORTE]
    for p in caindo[:2]:
        achados.append(_achado(
            f"produto_queda_{p['empreendimento']}", "alerta",
            f"{p['empreendimento']}: acessos caíram {_var(p['variacao'])}",
            f"{_n(p['sessoes'])} sessões contra {_n(p['sessoes_antes'])} no período anterior. "
            "Confira em Anúncios se as campanhas desse produto mudaram.",
        ))
    subindo = [p for p in produtos if p["sessoes_antes"] >= MIN_SESSOES_PRODUTO
               and p["variacao"] is not None and p["variacao"] >= VAR_FORTE]
    for p in subindo[:1]:
        achados.append(_achado(
            f"produto_alta_{p['empreendimento']}", "destaque",
            f"{p['empreendimento']}: acessos subiram {_var(p['variacao'])}",
            f"{_n(p['sessoes'])} sessões contra {_n(p['sessoes_antes'])} no período anterior.",
        ))
    return achados


def _analise_cidades(dados) -> List[Dict[str, Any]]:
    cidades = dados["cidades"]
    if not cidades:
        return []
    achados = []
    if dados["pct_das_nossas_pracas"] is not None:
        achados.append(_achado(
            "cidades_pracas", "contexto",
            f"{_p(dados['pct_das_nossas_pracas'])} dos acessos vêm das cidades onde temos empreendimento",
            f"{_n(dados['das_nossas_pracas'])} de {_n(dados['sessoes'])} sessões, vindas de {dados['distintas']} "
            "cidades diferentes no total. O resto é gente de fora da praça — normalmente quem compra para investir.",
        ))
    crescendo = [c for c in cidades if c["sessoes_antes"] >= MIN_SESSOES_CIDADE
                 and c["variacao"] is not None and c["variacao"] >= VAR_FORTE]
    if crescendo:
        c = crescendo[0]
        achados.append(_achado(
            "cidade_alta", "destaque", f"{c['cidade']} cresceu {_var(c['variacao'])}",
            f"{_n(c['sessoes'])} sessões contra {_n(c['sessoes_antes'])} no período anterior"
            + (f" — é praça nossa ({c['praca']})." if c["praca"] else ", e não é uma cidade onde temos produto."),
        ))
    return achados


def _analise_engajamento(t, ta) -> List[Dict[str, Any]]:
    if ta["sessoes"] < MIN_SESSOES_TOTAL or t["engajamento"] is None or ta["engajamento"] is None:
        return []
    pp = round(t["engajamento"] - ta["engajamento"], 1)
    if abs(pp) < 5:
        return []
    caiu = pp < 0
    return [_achado(
        "engajamento", "alerta" if caiu else "destaque",
        f"O engajamento {'caiu' if caiu else 'subiu'} {abs(pp):.1f} ponto(s) percentual(is)".replace(".", ","),
        f"{_p(t['engajamento'])} das sessões foram engajadas, contra {_p(ta['engajamento'])} antes. "
        f"Tempo médio por sessão: {_n(t['tempo_medio'] or 0)}s, contra {_n(ta['tempo_medio'] or 0)}s.",
    )]


def _analises(t, ta, canais, dispositivos, entradas, produtos, cidades) -> List[Dict[str, Any]]:
    return (_analise_total(t, ta) + _analise_conversoes(t, ta) + _analise_canais(canais) + _analise_engajamento(t, ta)
            + _analise_aparelhos(dispositivos) + _analise_produtos(produtos)
            + _analise_cidades(cidades) + _analise_entradas(entradas))


# ---------------------------------------------------------------------------


def compilar(
    inicio: date,
    fim: date,
    empreendimentos: Optional[List[str]] = None,
    pracas: Optional[List[str]] = None,
    limite: int = LIMITE_PADRAO,
) -> Dict[str, Any]:
    """Tudo o que o Google Analytics mostra do site no período, comparado com o período anterior."""
    anterior = _periodo_anterior(inicio, fim)
    atrib = _Atribuicao()
    atual = _linhas("ga4_trafego", inicio, fim, atrib, empreendimentos, pracas)
    antes = _linhas("ga4_trafego", anterior[0], anterior[1], atrib, empreendimentos, pracas)

    t, ta = _totais(atual), _totais(antes)
    canais = _quadro(atual, antes, "canal", "canal")
    origens = _quadro(atual, antes, "origem_midia", "origem", limite)
    dispositivos = _quadro(atual, antes, "dispositivo", "dispositivo")
    entradas = _entradas(atual, antes)
    produtos = _produtos(atual, antes, limite)
    paginas = _quadro(atual, antes, "pagina_entrada", "pagina", limite)
    cidades = _cidades(inicio, fim, anterior, atrib, empreendimentos, pracas, limite)

    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "dias": (fim - inicio).days + 1},
        "anterior": {"inicio": anterior[0].isoformat(), "fim": anterior[1].isoformat()},
        "totais": {**t, "anterior": ta, "variacao": {
            c: _variacao(t[c], ta[c]) for c in ("sessoes", "usuarios", "novos_usuarios", "conversoes")}},
        "canais": canais,
        "origens": origens,
        "dispositivos": dispositivos,
        "entradas": entradas,
        "produtos": produtos,
        "paginas": paginas,
        "cidades": cidades,
        "analises": _analises(t, ta, canais, dispositivos, entradas, produtos, cidades),
        "base": bases.resumo("ga4_trafego"),
        "observacao": ("Números do Google Analytics, por dia. Conversão aqui é o evento principal marcado na "
                       "propriedade (formulário, WhatsApp) — não é o lead no CV nem a venda. O empreendimento sai "
                       "da página de entrada; quem entra pela home ou pelo blog fica em 'não diz qual produto'."),
    }
