"""
Analista digital: lê todos os números do período e diz o que importa, por que e o que fazer.

Regras que valem para todo achado:
  - cada número vem das mesmas funções das telas (BI, anúncios, vendas × leads, diagnósticos), então o que o
    analista afirma é o que a tela mostra ao clicar no link;
  - toda variação compara com o período anterior de mesmo tamanho e exige amostra mínima (sem alarme porque
    3 leads viraram 1);
  - cada achado responde: o que aconteceu (com números), o que fazer e onde conferir.
"""

import re
import statistics
import time
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from engine import anuncios, auditoria_vendas, bases, bi, diagnosticos
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO

TIPOS = {"alerta": "Alerta", "oportunidade": "Oportunidade", "destaque": "Destaque", "contexto": "Contexto"}
AREAS = {
    "leads": "Leads",
    "investimento": "Investimento e custo por lead",
    "anuncios": "Anúncios",
    "funil": "Funil",
    "vendas": "Vendas",
    "dados": "Qualidade dos dados",
}
PESO_TIPO = {"alerta": 60, "oportunidade": 45, "destaque": 30, "contexto": 10}

# Amostras mínimas e limites de variação
MIN_LEADS_VARIACAO = 30        # leads no período anterior para comentar a variação total
VAR_LEADS = 20.0               # % de variação dos leads totais
MIN_LEADS_EMP = 20             # leads do empreendimento no período anterior
VAR_LEADS_EMP = 30.0           # % de variação dos leads do empreendimento
MIN_INVEST_CPL = 500.0         # R$ investidos (nos dois períodos) para comparar custo por lead
VAR_CPL = 30.0                 # % de variação do custo por lead
MIN_LEADS_SEM_INVEST = 20      # leads Meta no CV sem investimento ligado
MIN_ANUNCIO_SEM_LEAD = 300.0   # R$ gastos num anúncio sem nenhum lead no CV
MIN_ANUNCIO_CARO = 300.0       # R$ gastos para apontar anúncio caro ou piorando
FATOR_BARATO = 0.6             # CPL até 60% da mediana: candidato a mais verba
FATOR_CARO = 2.0               # CPL de 2× a mediana ou mais: revisar
PIORA_CPL = 50.0               # % de alta do CPL do mesmo anúncio
MIN_BASE_ETAPA = 30            # leads na etapa para comparar a passagem do funil
VAR_PASSAGEM_PP = 10.0         # pontos percentuais de mudança na passagem entre etapas
MIN_VENDAS_VARIACAO = 5
VAR_VENDAS = 30.0


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------


def _n(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def _r(valor: float) -> str:
    return "R$ " + _n(valor)


def _rc(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _p(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.1f}".replace(".", ",") + "%"


def _var(valor: float) -> str:
    return ("+" if valor > 0 else "") + _p(valor)


def _variacao(atual: float, anterior: float) -> Optional[float]:
    return round((atual - anterior) / anterior * 100, 1) if anterior else None


def _curto(nome: str) -> str:
    """'Avaré - Central Parque II - 13900' -> 'Central Parque II (Avaré)'."""
    partes = [p.strip() for p in re.split(r"\s+-\s+", str(nome or ""))]
    if len(partes) >= 3 and re.fullmatch(r"\d+", partes[-1]):
        return f"{' - '.join(partes[1:-1])} ({partes[0]})"
    if len(partes) == 2:
        return f"{partes[1]} ({partes[0]})"
    return str(nome)


def achado(
    id_: str, area: str, tipo: str, titulo: str, texto: str, recomendacao: str,
    evidencias: Optional[List[Dict[str, str]]] = None, tela: Optional[str] = None, impacto: float = 0.0,
) -> Dict[str, Any]:
    return {
        "id": id_, "area": area, "area_label": AREAS[area], "tipo": tipo, "tipo_label": TIPOS[tipo],
        "prioridade": round(PESO_TIPO[tipo] + max(0.0, min(40.0, impacto)), 1),
        "titulo": titulo, "texto": texto, "recomendacao": recomendacao,
        "evidencias": evidencias or [], "tela": tela,
    }


# ---------------------------------------------------------------------------
# Leads e investimento
# ---------------------------------------------------------------------------


def achados_leads(atual: Dict[str, Any]) -> List[Dict[str, Any]]:
    k = atual["kpis"]
    ant, agora, var = k["anterior"]["leads"], k["leads"], k["variacao"]["leads"]
    if ant < MIN_LEADS_VARIACAO or var is None or abs(var) < VAR_LEADS:
        return []
    queda = var < 0
    return [achado(
        "leads_variacao", "leads", "alerta" if queda else "destaque",
        f"Leads online {'caíram' if queda else 'subiram'} {_var(var)}",
        f"{_n(agora)} leads online no período contra {_n(ant)} no período anterior de mesmo tamanho.",
        ("Veja abaixo quais empreendimentos puxaram a queda e confira se o investimento e os anúncios ativos mudaram."
         if queda else "Veja quais empreendimentos e anúncios puxaram a alta para manter o que está funcionando."),
        [{"rotulo": "Período atual", "valor": _n(agora)}, {"rotulo": "Período anterior", "valor": _n(ant)}],
        tela="/empreendimentos", impacto=abs(var) / 2,
    )]


def _meta_por_emp(dados: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e["empreendimento"]: e for e in dados["por_empreendimento"] if e["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO}


def achados_empreendimentos(atual: Dict[str, Any], anterior: Dict[str, Any]) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    agora, antes = _meta_por_emp(atual), _meta_por_emp(anterior)

    for nome in sorted(set(agora) | set(antes)):
        e = agora.get(nome) or {"leads": 0, "meta": 0, "investimento_meta": 0.0, "cpl_meta_crm": None}
        a = antes.get(nome)
        curto = _curto(nome)

        # Volume de leads
        if a and a["leads"] >= MIN_LEADS_EMP:
            var = _variacao(e["leads"], a["leads"])
            if var is not None and abs(var) >= VAR_LEADS_EMP:
                queda = var < 0
                saida.append(achado(
                    f"emp_leads:{nome}", "leads", "alerta" if queda else "destaque",
                    f"{curto}: leads online {'caíram' if queda else 'subiram'} {_var(var)}",
                    f"{_n(e['leads'])} leads online contra {_n(a['leads'])} no período anterior."
                    + (f" Investimento na Meta: {_r(e['investimento_meta'])} agora, {_r(a['investimento_meta'])} antes."
                       if e["investimento_meta"] or a["investimento_meta"] else ""),
                    ("Confira em Anúncios se campanhas desse empreendimento foram pausadas ou perderam desempenho."
                     if queda else "Identifique em Anúncios o que puxou a alta e considere reforçar."),
                    tela="/empreendimentos", impacto=abs(e["leads"] - a["leads"]) / 4,
                ))

        # Custo por lead da Meta (lead que chegou ao CV)
        if (a and e["cpl_meta_crm"] and a["cpl_meta_crm"]
                and e["investimento_meta"] >= MIN_INVEST_CPL and a["investimento_meta"] >= MIN_INVEST_CPL):
            var = _variacao(e["cpl_meta_crm"], a["cpl_meta_crm"])
            if var is not None and abs(var) >= VAR_CPL:
                subiu = var > 0
                saida.append(achado(
                    f"emp_cpl:{nome}", "investimento", "alerta" if subiu else "destaque",
                    f"{curto}: custo por lead da Meta {'subiu' if subiu else 'caiu'} {_var(var)}",
                    f"{_rc(e['cpl_meta_crm'])} por lead que chegou ao CV, contra {_rc(a['cpl_meta_crm'])} no período anterior "
                    f"({_r(e['investimento_meta'])} investidos, {_n(e['meta'])} leads da Meta no CV).",
                    ("Abra Anúncios filtrando o empreendimento e veja quais anúncios encareceram; pause os que ficaram "
                     "muito acima da mediana." if subiu else "Os anúncios desse empreendimento ficaram mais eficientes: "
                     "veja quais foram e avalie mais verba neles."),
                    tela="/anuncios", impacto=abs(var) / 3 + e["investimento_meta"] / 1000,
                ))

        # Investimento sem lead no CV
        if e["investimento_meta"] >= MIN_INVEST_CPL and not e["meta"]:
            saida.append(achado(
                f"emp_invest_sem_lead:{nome}", "investimento", "alerta",
                f"{curto}: {_r(e['investimento_meta'])} investidos na Meta sem nenhum lead da Meta no CV",
                "A conta de anúncio desse empreendimento gastou no período, mas nenhum lead com origem Meta chegou ao CV.",
                "Confira em Conferências se o formulário está integrando ao CV e se os leads chegam com a mídia da Meta.",
                tela="/conferencias", impacto=e["investimento_meta"] / 100,
            ))

        # Leads da Meta sem investimento ligado (custo por lead fica sem base)
        if e["meta"] >= MIN_LEADS_SEM_INVEST and not e["investimento_meta"]:
            saida.append(achado(
                f"emp_leads_sem_invest:{nome}", "dados", "alerta",
                f"{curto}: {_n(e['meta'])} leads da Meta sem investimento ligado",
                "Os leads chegam ao CV com origem Meta, mas nenhuma conta de anúncio lida pelo sistema foi reconhecida como "
                "desse empreendimento. Custo por lead e retorno ficam indisponíveis.",
                "Libere a conta de anúncio para o usuário do sistema da Meta (pode estar em outra BM) ou inclua o nome do "
                "empreendimento no nome da conta.",
                tela="/bases", impacto=e["meta"] / 10,
            ))

    # Comparação entre empreendimentos: custo por lead muito acima ou abaixo dos demais
    comparaveis = [e for e in agora.values() if e["cpl_meta_crm"] and e["investimento_meta"] >= MIN_INVEST_CPL]
    if len(comparaveis) >= 3:
        mediana = statistics.median(e["cpl_meta_crm"] for e in comparaveis)
        barato = min(comparaveis, key=lambda e: e["cpl_meta_crm"])
        caro = max(comparaveis, key=lambda e: e["cpl_meta_crm"])
        if barato["cpl_meta_crm"] <= mediana * FATOR_BARATO:
            saida.append(achado(
                f"emp_cpl_menor:{barato['empreendimento']}", "investimento", "oportunidade",
                f"{_curto(barato['empreendimento'])} tem o menor custo por lead da Meta",
                f"{_rc(barato['cpl_meta_crm'])} por lead no CV, contra a mediana de {_rc(mediana)} dos "
                f"{len(comparaveis)} empreendimentos com investimento relevante.",
                "Se a qualidade dos leads (SQL e vendas) acompanhar, é o candidato natural a mais verba.",
                tela="/empreendimentos", impacto=10,
            ))
        if caro["cpl_meta_crm"] >= mediana * FATOR_CARO:
            saida.append(achado(
                f"emp_cpl_maior:{caro['empreendimento']}", "investimento", "alerta",
                f"{_curto(caro['empreendimento'])} tem custo por lead {caro['cpl_meta_crm'] / mediana:.1f}× a mediana".replace(".", ","),
                f"{_rc(caro['cpl_meta_crm'])} por lead no CV, contra a mediana de {_rc(mediana)} "
                f"({_r(caro['investimento_meta'])} investidos).",
                "Revise público, criativos e formulário desse empreendimento em Anúncios.",
                tela="/anuncios", impacto=caro["investimento_meta"] / 500,
            ))
    return saida


# ---------------------------------------------------------------------------
# Funil
# ---------------------------------------------------------------------------


def achados_funil(atual: Dict[str, Any]) -> List[Dict[str, Any]]:
    etapas, anteriores = atual["funil"]["online"], atual.get("funil_anterior") or []
    saida: List[Dict[str, Any]] = []
    maior_perda = None
    for n in range(1, len(etapas)):
        base, chegou = etapas[n - 1]["leads"], etapas[n]["leads"]
        if base >= MIN_BASE_ETAPA and (maior_perda is None or base - chegou > maior_perda[0]):
            maior_perda = (base - chegou, n)
        if n >= len(anteriores):
            continue
        p_agora, p_antes = etapas[n]["pct_da_etapa_anterior"], anteriores[n]["pct_da_etapa_anterior"]
        if (p_agora is None or p_antes is None or base < MIN_BASE_ETAPA
                or anteriores[n - 1]["leads"] < MIN_BASE_ETAPA):
            continue
        diff = round(p_agora - p_antes, 1)
        if abs(diff) >= VAR_PASSAGEM_PP:
            piorou = diff < 0
            de, para = etapas[n - 1]["label"], etapas[n]["label"]
            saida.append(achado(
                f"funil_passagem:{etapas[n]['etapa']}", "funil", "alerta" if piorou else "destaque",
                f"Passagem de {de} para {para} {'piorou' if piorou else 'melhorou'} {abs(diff):.1f} p.p.".replace(".", ",", 1),
                f"{_p(p_agora)} dos leads avançaram agora, contra {_p(p_antes)} no período anterior "
                f"({_n(chegou)} de {_n(base)}).",
                ("Converse com o time de atendimento sobre essa etapa: tempo de resposta, abordagem e qualidade dos leads "
                 "que chegaram." if piorou else "Registre o que mudou no atendimento para repetir."),
                tela="/funil", impacto=abs(diff),
            ))
    if maior_perda and etapas[0]["leads"]:
        perda, n = maior_perda
        base = etapas[n - 1]["leads"]
        saida.append(achado(
            "funil_maior_perda", "funil", "contexto",
            f"Onde o funil mais perde: de {etapas[n - 1]['label']} para {etapas[n]['label']}",
            f"{_n(perda)} de {_n(base)} leads ({_p(perda / base * 100)}) pararam nessa passagem.",
            "É a etapa com mais leads perdidos em número absoluto: melhorias aqui têm o maior efeito no fim do funil.",
            tela="/funil", impacto=5,
        ))
    return saida


# ---------------------------------------------------------------------------
# Anúncios
# ---------------------------------------------------------------------------


def _nome_anuncio(a: Dict[str, Any]) -> str:
    return f"{a['anuncio']} · {a.get('conjunto') or 'conjunto sem nome'} · {_curto(a['empreendimento'])}"


def achados_anuncios(ads: Dict[str, Any], ads_anterior: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not ads.get("disponivel"):
        return [achado("anuncios_indisponivel", "anuncios", "contexto", "Análise de anúncios indisponível",
                       "A base de anúncios da Meta ainda não foi baixada.", "Atualize a base em Bases e integrações.",
                       tela="/bases")]
    lista = ads["anuncios"]
    saida: List[Dict[str, Any]] = []
    elegiveis = [a for a in lista if a["leads_cv"] >= anuncios.MIN_LEADS_CPL and a["investimento"] >= anuncios.MIN_INVESTIMENTO_CPL
                 and a["cpl_real"]]
    mediana = statistics.median(a["cpl_real"] for a in elegiveis) if len(elegiveis) >= 5 else None

    sem_lead = sorted((a for a in lista if a["investimento"] >= MIN_ANUNCIO_SEM_LEAD and not a["leads_cv"]
                       and not a.get("sem_dados_da_plataforma")), key=lambda a: -a["investimento"])
    if sem_lead:
        total = sum(a["investimento"] for a in sem_lead)
        saida.append(achado(
            "anuncios_sem_lead", "anuncios", "alerta",
            f"{len(sem_lead)} anúncio(s) gastaram {_r(total)} sem nenhum lead no CV",
            f"Cada um investiu {_r(MIN_ANUNCIO_SEM_LEAD)} ou mais no período e nenhum lead atribuído a ele chegou ao CV.",
            "Pause ou revise esses anúncios. Se a Meta mostra leads neles, confira em Conferências se o formulário integra ao CV.",
            [{"rotulo": _nome_anuncio(a), "valor": f"{_r(a['investimento'])} · {_n(a['leads_plataforma'])} lead(s) na Meta"}
             for a in sem_lead[:5]],
            tela="/anuncios", impacto=total / 100,
        ))

    if mediana:
        baratos = sorted((a for a in elegiveis if a["cpl_real"] <= mediana * FATOR_BARATO),
                         key=lambda a: -(a.get("eficiencia") or 0))[:3]
        if baratos:
            saida.append(achado(
                "anuncios_escalar", "anuncios", "oportunidade",
                f"{len(baratos)} anúncio(s) com custo por lead bem abaixo da mediana",
                f"Custo por lead no CV até {int(FATOR_BARATO * 100)}% da mediana de {_rc(mediana)} dos "
                f"{len(elegiveis)} anúncios com amostra suficiente.",
                "São os candidatos a receber mais verba. Confira antes a qualidade (SQL e vendas) na tela de Anúncios.",
                [{"rotulo": _nome_anuncio(a), "valor": f"{_rc(a['cpl_real'])} por lead · {_n(a['leads_cv'])} leads · "
                  f"{_p(a['taxa_sql'])} SQL"} for a in baratos],
                tela="/anuncios", impacto=15,
            ))
        caros = sorted((a for a in elegiveis if a["cpl_real"] >= mediana * FATOR_CARO and a["investimento"] >= MIN_ANUNCIO_CARO),
                       key=lambda a: -a["investimento"])[:3]
        if caros:
            total = sum(a["investimento"] for a in caros)
            saida.append(achado(
                "anuncios_caros", "anuncios", "alerta",
                f"{len(caros)} anúncio(s) com custo por lead de 2× a mediana ou mais",
                f"Somam {_r(total)} investidos; a mediana do período é {_rc(mediana)} por lead no CV.",
                "Revise criativo e público ou redistribua a verba para os anúncios mais eficientes.",
                [{"rotulo": _nome_anuncio(a), "valor": f"{_rc(a['cpl_real'])} por lead · {_r(a['investimento'])}"} for a in caros],
                tela="/anuncios", impacto=total / 200,
            ))

    if ads_anterior and ads_anterior.get("anuncios"):
        antes = {a["chave"]: a for a in ads_anterior["anuncios"]
                 if a["leads_cv"] >= anuncios.MIN_LEADS_CPL and a["investimento"] >= anuncios.MIN_INVESTIMENTO_CPL and a["cpl_real"]}
        piorando = []
        for a in elegiveis:
            b = antes.get(a["chave"])
            if b and a["investimento"] >= MIN_ANUNCIO_CARO:
                var = _variacao(a["cpl_real"], b["cpl_real"])
                if var is not None and var >= PIORA_CPL:
                    piorando.append((var, a, b))
        piorando.sort(key=lambda x: -x[1]["investimento"])
        if piorando:
            saida.append(achado(
                "anuncios_piorando", "anuncios", "alerta",
                f"{len(piorando)} anúncio(s) ficaram bem mais caros que no período anterior",
                f"O custo por lead no CV subiu {int(PIORA_CPL)}% ou mais no mesmo anúncio. Costuma ser saturação do criativo "
                "ou do público.",
                "Troque o criativo ou amplie o público desses anúncios.",
                [{"rotulo": _nome_anuncio(a), "valor": f"{_rc(b['cpl_real'])} → {_rc(a['cpl_real'])} ({_var(v)})"}
                 for v, a, b in piorando[:5]],
                tela="/anuncios", impacto=len(piorando) * 5,
            ))

    campeao = next((c for c in ads.get("campeoes") or [] if c["id"] == "menor_custo_venda" and c["anuncio"]), None)
    if campeao:
        a = campeao["anuncio"]
        saida.append(achado(
            "anuncio_menor_custo_venda", "anuncios", "destaque",
            "Anúncio com menor custo por venda",
            f"{_nome_anuncio(a)}: {_n(a['vendas'])} venda(s) de leads do período com {_r(a['investimento'])} investidos "
            f"({_r(a['custo_por_venda'])} por venda).",
            "Use como referência de criativo e público para os próximos anúncios desse empreendimento.",
            tela="/anuncios", impacto=8,
        ))

    r = ads.get("resumo") or {}
    if r.get("cobertura") is not None and r["cobertura"] < 70:
        saida.append(achado(
            "anuncios_cobertura", "dados", "alerta",
            f"Só {_p(r['cobertura'])} dos leads da Meta têm o anúncio identificado",
            f"{_n(r['sem_anuncio'])} de {_n(r['leads_meta_cv'])} leads da Meta no CV não foram ligados a um anúncio.",
            "Garanta que todas as campanhas enviem a UTM do anúncio (utm_content) e que as contas estejam liberadas.",
            tela="/anuncios", impacto=(70 - r["cobertura"]) / 2,
        ))
    return saida


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------


def achados_vendas(atual: Dict[str, Any], auditoria: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    k = atual["kpis"]
    saida: List[Dict[str, Any]] = []
    ant, agora = k["anterior"]["vendas_online"], k["vendas_online"]
    var = _variacao(agora, ant)
    if ant >= MIN_VENDAS_VARIACAO and var is not None and abs(var) >= VAR_VENDAS:
        queda = var < 0
        saida.append(achado(
            "vendas_online_variacao", "vendas", "alerta" if queda else "destaque",
            f"Vendas de leads online {'caíram' if queda else 'subiram'} {_var(var)}",
            f"{_n(agora)} vendas ({_r(k['vgv_online'])}) contra {_n(ant)} no período anterior.",
            "Veja em Funil e vendas de onde vieram as vendas e em Vendas × leads se alguma ficou sem origem online.",
            tela="/funil", impacto=abs(var) / 3,
        ))
    investimento = (atual.get("investimento") or {})
    total_invest = (investimento.get("meta") or 0) + (investimento.get("google") or 0)
    if total_invest and k["vgv_online"]:
        saida.append(achado(
            "vendas_retorno", "vendas", "contexto",
            f"Cada R$ 1 investido em mídia corresponde a R$ {k['vgv_online'] / total_invest:,.2f} em vendas online".replace(".", ","),
            f"{_r(k['vgv_online'])} em vendas de leads online no período para {_r(total_invest)} investidos em Meta e Google.",
            "Leitura de ordem de grandeza: as vendas do período vêm de leads de vários meses, não só do investimento do período.",
            tela="/funil", impacto=3,
        ))
    if auditoria and auditoria.get("disponivel"):
        s = auditoria["resumo"]
        if s["online_nao_contabilizada"]:
            saida.append(achado(
                "vendas_online_nao_contabilizadas", "vendas", "alerta",
                f"{_n(s['online_nao_contabilizada'])} venda(s) com origem online comprovada fora do online",
                f"Somam {_r(s['vgv_online_nao_contabilizada'])}: a pessoa tem lead online recente, formulário da Meta ou "
                "indicação da BeeViral, mas a venda está ligada a um lead de outra origem.",
                "Abra Vendas × leads e associe cada reserva ao lead online no CV.",
                tela="/vendas", impacto=s["online_nao_contabilizada"] * 5,
            ))
        if s["provavel_online"] >= 5:
            saida.append(achado(
                "vendas_provavel_online", "vendas", "oportunidade",
                f"{_n(s['provavel_online'])} venda(s) com indício de origem online para confirmar",
                f"Somam {_r(s['vgv_provavel_online'])}. A mídia escolhida na reserva (ou um lead online antigo) indica online, "
                "mas nenhuma outra base confirma.",
                "Confirme com os corretores listados em Vendas × leads e corrija o lead no CV quando for online.",
                tela="/vendas", impacto=s["provavel_online"] / 3,
            ))
    if k.get("unidades_vendidas") and k.get("unidades_sem_lead", 0) >= 10:
        pct = k["unidades_sem_lead"] / k["unidades_vendidas"] * 100
        if pct >= 20:
            saida.append(achado(
                "vendas_sem_lead", "dados", "alerta",
                f"{_p(pct)} das unidades vendidas não têm lead no CV",
                f"{_n(k['unidades_sem_lead'])} de {_n(k['unidades_vendidas'])} reservas vendidas não estão ligadas a nenhum lead, "
                "nem pelo e-mail ou telefone do titular.",
                "Oriente o comercial a sempre fazer a reserva a partir do lead: sem isso, a origem da venda se perde.",
                tela="/vendas", impacto=pct / 2,
            ))
    return saida


# ---------------------------------------------------------------------------
# Qualidade dos dados
# ---------------------------------------------------------------------------


def achados_dados(atual: Dict[str, Any], diag: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    q = atual["qualidade"]
    if q["leads"] >= MIN_LEADS_VARIACAO and q["whatsapp_sem_rastreio"]:
        pct = q["whatsapp_sem_rastreio"] / q["leads"] * 100
        if pct >= 25:
            saida.append(achado(
                "dados_whatsapp_sem_rastreio", "dados", "oportunidade",
                f"{_p(pct)} dos leads online vêm de WhatsApp sem campanha identificada",
                f"{_n(q['whatsapp_sem_rastreio'])} de {_n(q['leads'])} leads online chegaram pelo WhatsApp sem UTM nem tag "
                "de origem: não dá para saber se vieram de anúncio.",
                "Use links de WhatsApp com UTM (ou mensagens pré-preenchidas por campanha) e anúncios Click to WhatsApp "
                "com a UTM configurada.",
                tela="/", impacto=pct / 3,
            ))
    if diag:
        pend = [i for i in diag.get("itens") or [] if i["situacao"] == "pendente" and i["severidade"] in ("critico", "atencao")]
        criticos = [i for i in pend if i["severidade"] == "critico"]
        if pend:
            saida.append(achado(
                "dados_diagnosticos", "dados", "alerta" if criticos else "contexto",
                f"{_n(len(pend))} problema(s) de dados pendentes"
                + (f", {_n(len(criticos))} crítico(s)" if criticos else ""),
                "Podem estar deixando números do período errados ou incompletos.",
                "Abra Diagnósticos: cada item diz o que aconteceu, por quê e como resolver.",
                [{"rotulo": i["titulo"], "valor": "crítico" if i["severidade"] == "critico" else "atenção"} for i in pend[:5]],
                tela="/diagnosticos", impacto=len(criticos) * 10 + len(pend),
            ))
    return saida


# ---------------------------------------------------------------------------
# Análise do período
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {}
CACHE_SEGUNDOS = 600


def _manchetes(achados: List[Dict[str, Any]], atual: Dict[str, Any]) -> List[str]:
    k = atual["kpis"]
    cont = {t: sum(1 for a in achados if a["tipo"] == t) for t in TIPOS}
    frases = [
        f"{_n(k['leads'])} leads online ({_var(k['variacao']['leads']) if k['variacao']['leads'] is not None else 'sem base de comparação'} "
        f"vs período anterior), {_n(k['vendas'])} vendas online e {_r(k['vgv'])} de VGV.",
        f"O analista encontrou {cont['alerta']} alerta(s), {cont['oportunidade']} oportunidade(s) e {cont['destaque']} destaque(s).",
    ]
    for a in [x for x in achados if x["tipo"] in ("alerta", "oportunidade")][:3]:
        frases.append(f"{a['tipo_label']}: {a['titulo']}.")
    return frases


def analisar(
    inicio: date, fim: date, empreendimentos: Optional[List[str]] = None, pracas: Optional[List[str]] = None
) -> Dict[str, Any]:
    versoes = "|".join(f"{k}:{(bases.carregar(k) or {}).get('atualizado_em')}" for k in bases.BASES)
    chave = f"{inicio}|{fim}|{sorted(empreendimentos or [])}|{sorted(pracas or [])}|{versoes}"
    guardado = _cache.get(chave)
    if guardado and time.time() - guardado[0] < CACHE_SEGUNDOS:
        return guardado[1]

    dias = (fim - inicio).days + 1
    ant_fim = inicio - timedelta(days=1)
    ant_inicio = ant_fim - timedelta(days=dias - 1)
    atual = bi.calcular_bi(inicio, fim, empreendimentos, pracas, escopo="online")
    anterior = bi.calcular_bi(ant_inicio, ant_fim, empreendimentos, pracas, escopo="online")

    achados: List[Dict[str, Any]] = []
    falhas: List[str] = []

    def rodar(nome: str, funcao: Callable[[], List[Dict[str, Any]]]) -> None:
        try:
            achados.extend(funcao())
        except Exception as e:  # uma análise com erro não pode esconder as demais
            falhas.append(nome)
            achados.append(achado(f"analise_com_erro:{nome}", "dados", "contexto", f"A análise de {nome} não pôde ser feita",
                                  str(e), "Atualize as bases e recarregue; se continuar, verifique o log da engine."))

    emp_unico = empreendimentos[0] if empreendimentos and len(empreendimentos) == 1 else None
    praca_unica = pracas[0] if pracas and len(pracas) == 1 else None
    rodar("leads", lambda: achados_leads(atual))
    rodar("empreendimentos", lambda: achados_empreendimentos(atual, anterior))
    rodar("funil", lambda: achados_funil(atual))
    rodar("anúncios", lambda: achados_anuncios(anuncios.auditoria(inicio, fim, empreendimentos, pracas),
                                               anuncios.auditoria(ant_inicio, ant_fim, empreendimentos, pracas)))
    rodar("vendas", lambda: achados_vendas(atual, auditoria_vendas.auditar(inicio, fim, emp_unico, praca_unica)))
    rodar("qualidade dos dados", lambda: achados_dados(atual, diagnosticos.calcular(inicio, fim)))

    achados.sort(key=lambda a: -a["prioridade"])
    k = atual["kpis"]
    resultado = {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(),
                    "anterior_inicio": ant_inicio.isoformat(), "anterior_fim": ant_fim.isoformat()},
        "manchetes": _manchetes(achados, atual),
        "contagem": {t: sum(1 for a in achados if a["tipo"] == t) for t in TIPOS},
        "panorama": {
            "leads": k["leads"], "variacao_leads": k["variacao"]["leads"],
            "vendas": k["vendas"], "variacao_vendas": k["variacao"]["vendas"], "vgv": k["vgv"],
            "investimento": round((atual["investimento"]["meta"] or 0) + (atual["investimento"]["google"] or 0), 2),
            "cpl_meta": round(atual["investimento"]["meta"] / sum(e["meta"] for e in atual["por_empreendimento"]), 2)
            if atual["investimento"]["meta"] and sum(e["meta"] for e in atual["por_empreendimento"]) else None,
        },
        "achados": achados,
        "areas": AREAS,
        "tipos": TIPOS,
        "falhas": falhas,
        "criterios": [
            f"Variações só são comentadas com amostra mínima (ex.: {MIN_LEADS_VARIACAO} leads no total, {MIN_LEADS_EMP} por "
            f"empreendimento, {_r(MIN_INVEST_CPL)} investidos para comparar custo por lead).",
            f"Leads e vendas contam só o online, como no BI gerencial; a comparação é com {ant_inicio:%d/%m/%Y} a {ant_fim:%d/%m/%Y}.",
            f"Anúncios: custo por lead comparado à mediana dos anúncios com {anuncios.MIN_LEADS_CPL}+ leads e "
            f"{_r(anuncios.MIN_INVESTIMENTO_CPL)}+ investidos.",
        ],
        "calculado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _cache.clear()
    _cache[chave] = (time.time(), resultado)
    return resultado
