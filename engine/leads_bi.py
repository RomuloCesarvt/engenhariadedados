"""
Leads e origem do jeito do Power BI da gestão, a partir da tabela de conversões do CV.

Uma regra só, usada pela apresentação e pelas telas de Visão geral e Empreendimentos, para os números nunca divergirem:
  - o lead conta no período em que converteu (a última conversão dentro dele);
  - o empreendimento é o da última conversão do lead;
  - a origem é a mídia DAQUELA conversão, e só valem as origens que o BI considera online.
Conferido contra o BI: outubro/Reserva Central Parque II deu 12 = 12 (Facebook Ads 5, Instagram Ads 1, WhatsApp 6).
"""

import re
from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional, Set

from engine import bases, bi, palavras
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO


def _passa(emp: str, praca: str, emp_f: Set[str], praca_f: Set[str]) -> bool:
    return (not emp_f or emp in emp_f) and (not praca_f or praca in praca_f)


# O BI só conta como online as origens desta lista (a mesma do filtro "Origem (Online)", mais as que apareceram
# nos números dele). Qualquer outra mídia — corretor, indicação, "pesquisa", "Referência: site"... — fica fora.
def _chave_origem(texto: Any) -> str:
    return bi._limpo(texto)


# O BI conta TODA origem, menos a offline (painéis de corretor, imobiliária, PDV e gestor, mídia de rua, indicação de corretor) e o lead sem
# origem. Por isso aqui não há lista do que entra: qualquer origem nova do CV (um anúncio de outra rede, um site, um portal) já conta.
ORIGENS_OFFLINE = ("painel", "indicacao corretor", "outdoor", "panfleto", "campanha de ativacao", "nao definido", "null", "none")


class _OrigensOnline:
    """Conjunto 'ao contrário': `chave in ORIGENS_ONLINE_BI` vale para tudo que não é offline nem vazio."""

    def __contains__(self, chave: Any) -> bool:
        k = _chave_origem(chave)
        return bool(k) and not k.startswith(ORIGENS_OFFLINE)


ORIGENS_ONLINE_BI = _OrigensOnline()
ORIGENS_META = {_chave_origem(o) for o in ("Facebook Ads", "Instagram Ads", "meta_ads", "ig", "Facebook", "Click To WhatsApp", "Meta")}
ORIGENS_GOOGLE = {_chave_origem(o) for o in ("Google", "Google Ads", "pesquisa", "pesquisa / cpc | altavista")}

_cache_bi: Dict[str, Any] = {"chave": None, "ids": {}, "leads": {}}


def _ids_de_empreendimento() -> Dict[str, str]:
    """id do empreendimento no CV -> nome do catálogo (o lead traz os dois juntos)."""
    base = bases.carregar("cv_leads") or {}
    chave = f"{base.get('atualizado_em')}|{base.get('total')}"
    if _cache_bi["chave"] != chave:
        ids: Dict[str, str] = {}
        for r in base.get("registros") or []:
            for e in r.get("empreendimento") or []:
                if isinstance(e, dict) and e.get("id") is not None and e.get("nome"):
                    ids.setdefault(str(e["id"]), bi.unificar_empreendimento(e["nome"]) if hasattr(bi, "unificar_empreendimento") else e["nome"])
        _cache_bi.update(chave=chave, ids=ids)
    return _cache_bi["ids"]


def _lead_bruto(idlead: Any) -> Dict[str, Any]:
    if "brutos" not in _cache_bi or _cache_bi.get("brutos_chave") != _cache_bi["chave"]:
        brutos = {str(r.get("idlead")): r for r in bases.registros("cv_indice")}
        brutos.update({str(r.get("idlead")): r for r in bases.registros("cv_leads")})
        _cache_bi.update(brutos=brutos, brutos_chave=_cache_bi["chave"])
    return _cache_bi["brutos"].get(str(idlead)) or {}


def origem_do_bi(evento: Dict[str, Any]) -> str:
    """Mídia da conversão; se o CV não registrou, a mídia do evento e, por último, a mídia principal do lead."""
    bruto = _lead_bruto(evento.get("idlead")) if not (evento.get("midia_conversao") or evento.get("midia")) else {}
    principal = bruto.get("midia_principal")
    principal = principal.get("nome") if isinstance(principal, dict) else principal
    return str(evento.get("midia_conversao") or evento.get("midia") or principal or "").strip()


# Origem do BI -> canal do sistema (as chaves e os nomes de engine/taxonomy.py). O WhatsApp mantém o nome do BI.
_CANAL_DA_ORIGEM = {
    **{o: ("meta", "Meta Ads (Facebook/Instagram)") for o in ORIGENS_META},
    **{o: ("google", "Google Ads") for o in ORIGENS_GOOGLE},
    _chave_origem("Bing"): ("midia_paga", "Mídia paga não identificada"),
    _chave_origem("ads"): ("midia_paga", "Mídia paga não identificada"),
    _chave_origem("WhatsApp"): ("whatsapp_organico", "WhatsApp"),
    _chave_origem("Tráfego Direto"): ("site", "Site / busca orgânica"),
    _chave_origem("Busca Orgânica"): ("site", "Site / busca orgânica"),
    _chave_origem("Linktree"): ("site", "Site / busca orgânica"),
    _chave_origem("Linktr.ee"): ("site", "Site / busca orgânica"),
    _chave_origem("Indicação"): ("indicacao", "Indicação (Indique e Ganhe)"),
    _chave_origem("TikTok Ads"): ("midia_paga", "Mídia paga não identificada"),
    _chave_origem("API Morada.ai"): ("chat", "Chat do site / chatbot"),
    _chave_origem("Instagram (orgânico)"): ("redes_sociais", "Redes sociais (orgânico)"),
    _chave_origem("VivaReal"): ("site", "Site / busca orgânica"),
    _chave_origem("Eventos"): ("site", "Site / busca orgânica"),
    _chave_origem("Redes Sociais"): ("redes_sociais", "Redes sociais (orgânico)"),
    _chave_origem("Blip"): ("chat", "Chat do site / chatbot"),
    _chave_origem("Chatbot"): ("chat", "Chat do site / chatbot"),
    _chave_origem("M.I.A."): ("chat", "Chat do site / chatbot"),
    _chave_origem("Disparos M.I.A."): ("chat", "Chat do site / chatbot"),
    _chave_origem("E-mail"): ("email_rd", "E-mail / RD Station"),
}
CANAIS_PAGOS = {"meta", "google", "midia_paga"}


def canal_da_origem(origem: str):
    """(canal, nome do canal) de uma origem do BI."""
    return _CANAL_DA_ORIGEM.get(_chave_origem(origem), ("site", "Site / busca orgânica"))


def _conversoes_do_filtro(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], fora: Optional[Counter] = None) -> Dict[Any, Dict[str, Any]]:
    """
    Para cada lead, a última conversão ONLINE do período dentro do filtro (produto/praça escolhidos). Sem filtro é a última conversão do lead;
    com um produto escolhido, é a última conversão dele NAQUELE produto: o lead que converteu no produto e depois em outro continua contando
    nos dois (como o Power BI). Conferido: Reserva Central Parque II (70 = 70 do BI) e Jardim dos Ipês III (64 = 64), Central Parque II 124 contra 125.
    """
    ids = _ids_de_empreendimento()
    ultimas: Dict[Any, Dict[str, Any]] = {}
    offline: Dict[Any, Dict[str, Any]] = {}
    for e in bases.registros("cv_conversoes"):
        dia = palavras._dia(e.get("data_cad"))
        if dia is None or not (inicio <= dia <= fim):
            continue
        empreendimento = ids.get(str(e.get("empreendimento_ultimo"))) or EMPREENDIMENTO_DESCONHECIDO
        praca = bi.praca_do_empreendimento(empreendimento) or "Não identificada"
        if not _passa(empreendimento, praca, emp_f, praca_f):
            continue
        destino = ultimas if _chave_origem(origem_do_bi(e)) in ORIGENS_ONLINE_BI else offline
        atual = destino.get(e["idlead"])
        if atual is None or str(e["data_cad"]) >= str(atual["data_cad"]):
            destino[e["idlead"]] = e
    if fora is not None:
        for idlead, e in offline.items():
            if idlead not in ultimas:
                fora[origem_do_bi(e) or "(sem mídia)"] += 1
    return ultimas


def leads_do_bi(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], fora: Optional[Counter] = None, completo: bool = False) -> List[Dict[str, Any]]:
    """
    MQL como o BI conta: o lead que converteu no período (a última conversão dentro dele), no empreendimento
    da última conversão, com a origem sendo a mídia DAQUELA conversão. Origem offline (corretor, indicação,
    painel) fica de fora.

    `completo=True` devolve o lead com todos os campos que o BI das telas usa (o lead preparado, com origem,
    canal, data e empreendimento trocados pelos da conversão).
    """
    ids = _ids_de_empreendimento()
    ultimas = _conversoes_do_filtro(inicio, fim, emp_f, praca_f, fora)

    saida = []
    for idlead, e in ultimas.items():
        origem = origem_do_bi(e)
        empreendimento = ids.get(str(e.get("empreendimento_ultimo"))) or EMPREENDIMENTO_DESCONHECIDO
        praca = bi.praca_do_empreendimento(empreendimento) or "Não identificada"
        bruto = _lead_bruto(idlead)
        tags_do_lead = {bi._limpo(bi._nome(t)) for t in (bruto.get("tags") or []) if bi._nome(t)}
        canal, rotulo = canal_da_origem(origem)
        registro = {
            "id": idlead,
            "data": palavras._dia(e["data_cad"]),
            "origem": origem,
            "conversao": e.get("conversao"),
            "canal": canal,
            "canal_label": rotulo,
            "grupo": "online_pago" if canal in CANAIS_PAGOS else ("indicacao_digital" if canal == "indicacao" else "online_organico"),
            "online": True,
            "empreendimento_lead": empreendimento,
            "praca_lead": praca,
            # O assistente marca "mia-organico" quando a conversa chegou sem anúncio de origem
            "mia_organico": "mia-organico" in tags_do_lead,
            "etapa": bi.etapa_alcancada(bruto) if bruto else 0,
            "vendido": bool(bruto.get("data_venda")) if bruto else False,
        }
        if completo:
            base = bi.preparar_lead(bruto) if bruto else {
                "tem_email": False, "tem_utm": False, "motivo_perda": None, "campanha": None, "situacao": None, "link": None,
                "data_venda": None, "valor_venda": 0.0, "data_cadastro": None,
            }
            registro = {
                **base, **registro,
                "confianca": "alta", "evidencia": f"Mídia da conversão no CV: {origem}",
                "data_conversao": registro["data"], "empreendimento": empreendimento, "praca": praca,
                "empreendimentos": [empreendimento], "pracas": [praca],
                "empreendimento_comprado": empreendimento, "praca_comprada": praca,
            }
        saida.append(registro)
    return saida


# Situações do CV em que o lead já passou pela qualificação (SQL) ou foi além
SITUACOES_SQL_OU_ALEM = {
    "Lead Qualificado (SQL)", "Agendado (OPPS)", "Atendimento Realizado", "Atendimento Não Realizado", "Reserva", "Vendido",
}


def _ultima_conversao_de_cada_lead() -> Dict[Any, Dict[str, Any]]:
    ultimas: Dict[Any, Dict[str, Any]] = {}
    for e in bases.registros("cv_conversoes"):
        atual = ultimas.get(e["idlead"])
        if atual is None or str(e["data_cad"]) >= str(atual["data_cad"]):
            ultimas[e["idlead"]] = e
    return ultimas


def _entradas_do_historico(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str], situacoes: Set[str]) -> List[Dict[str, Any]]:
    """
    Leads que ENTRARAM em uma das `situacoes` dentro do período, pelo histórico de situações do CV (a mesma tabela que o Power BI usa).
    Origem e empreendimento são os da última conversão do lead, como no MQL do BI; cada lead entra uma vez.
    """
    ids = _ids_de_empreendimento()
    ultimas = _ultima_conversao_de_cada_lead()
    entradas: Dict[Any, Any] = {}
    for h in bases.registros("cv_leads_historico"):
        if h.get("para_nome") not in situacoes:
            continue
        dia = palavras._dia(h.get("data_cad"))
        if dia is None or not (inicio <= dia <= fim):
            continue
        if h["idlead"] not in entradas or dia < entradas[h["idlead"]]:
            entradas[h["idlead"]] = dia
    saida = []
    for idlead, dia in entradas.items():
        conversao = ultimas.get(idlead)
        if not conversao:
            continue
        origem = origem_do_bi(conversao)
        if _chave_origem(origem) not in ORIGENS_ONLINE_BI:
            continue
        empreendimento = ids.get(str(conversao.get("empreendimento_ultimo"))) or EMPREENDIMENTO_DESCONHECIDO
        praca = bi.praca_do_empreendimento(empreendimento) or "Não identificada"
        if not _passa(empreendimento, praca, emp_f, praca_f):
            continue
        bruto = _lead_bruto(idlead)
        canal, rotulo = canal_da_origem(origem)
        saida.append({
            "id": idlead, "data": dia, "origem": origem, "conversao": conversao.get("conversao"), "canal": canal, "canal_label": rotulo,
            "grupo": "online_pago" if canal in CANAIS_PAGOS else ("indicacao_digital" if canal == "indicacao" else "online_organico"), "online": True,
            "empreendimento_lead": empreendimento, "praca_lead": praca, "etapa": max(2, bi.etapa_alcancada(bruto) if bruto else 2),
            "vendido": bool(bruto.get("data_venda")) if bruto else False,
        })
    return saida


def sql_do_bi(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]) -> List[Dict[str, Any]]:
    """SQL do período. Com o histórico de situações do CV, conta quem entrou em SQL (ou além) no período, como o Power BI; sem ele, a aproximação antiga."""
    if bases.registros("cv_leads_historico"):
        return _entradas_do_historico(inicio, fim, emp_f, praca_f, SITUACOES_SQL_OU_ALEM)
    return _sql_aproximado(inicio, fim, emp_f, praca_f)


def _sql_aproximado(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]) -> List[Dict[str, Any]]:
    """
    SQL do período, o mais próximo possível do Power BI da gestão.

    O BI conta o MOMENTO em que o lead foi qualificado, de uma tabela de histórico que o CV não entrega. Duas coisas
    aproximam isso, e o resultado é a união delas (cada lead uma vez):
      a) os leads do MQL do período que já chegaram a SQL pelo histórico (situação, tags e tarefas);
      b) os leads que estão hoje em SQL ou além e cuja última alteração caiu no período — inclui lead antigo que só agora foi
         qualificado. Só origem online, como o BI.
    Conferido na Reserva Central Parque II: 01–05/10 deu 9 (BI: 10 no cartão, 8 na tabela); setembro, 41 (BI: 39 e 34).
    Em mês fechado tende a passar um pouco; no recorte curto, a ficar um pouco abaixo.
    """
    # A situação ANTERIOR do lead também conta: quem hoje está cancelado mas estava em SQL (ou além) antes já foi qualificado
    anterior = {x.get("idlead"): (x.get("nome_situacao_anterior_lead") or "") for x in bases.registros("cv_leads_dw")}
    saida = [l for l in leads_do_bi(inicio, fim, emp_f, praca_f) if l["etapa"] >= 2 or anterior.get(l["id"]) in SITUACOES_SQL_OU_ALEM]
    vistos = {l["id"] for l in saida}
    ids = _ids_de_empreendimento()
    ultimas = _ultima_conversao_de_cada_lead()
    for x in bases.registros("cv_leads_dw"):
        idlead = x.get("idlead")
        if idlead in vistos or (x.get("situacao") or "") not in SITUACOES_SQL_OU_ALEM:
            continue
        dia = palavras._dia(x.get("data_ultima_alteracao"))
        if dia is None or not (inicio <= dia <= fim):
            continue
        conversao = ultimas.get(idlead)
        if not conversao:
            continue
        origem = origem_do_bi(conversao)
        if _chave_origem(origem) not in ORIGENS_ONLINE_BI:
            continue
        empreendimento = ids.get(str(x.get("idempreendimento_ultimo"))) or EMPREENDIMENTO_DESCONHECIDO
        praca = bi.praca_do_empreendimento(empreendimento) or "Não identificada"
        if not _passa(empreendimento, praca, emp_f, praca_f):
            continue
        canal, rotulo = canal_da_origem(origem)
        vistos.add(idlead)
        saida.append({
            "id": idlead, "data": dia, "origem": origem, "conversao": conversao.get("conversao"), "canal": canal, "canal_label": rotulo,
            "grupo": "online_pago" if canal in CANAIS_PAGOS else ("indicacao_digital" if canal == "indicacao" else "online_organico"), "online": True,
            "empreendimento_lead": empreendimento, "praca_lead": praca, "etapa": 2, "vendido": False,
        })
    return saida


# Situações do CV de quem já foi agendado para atendimento (OPPS) ou além
SITUACOES_OPPS = {"Agendado (OPPS)", "Atendimento Realizado", "Atendimento Não Realizado", "Reserva", "Vendido"}


def opps_do_bi(inicio: date, fim: date, emp_f: Set[str], praca_f: Set[str]) -> List[Dict[str, Any]]:
    """
    OPPS do período, como o card do Power BI: os leads do MQL do período que estão, ou estavam antes da última mudança, agendados
    para atendimento (ou além). Conferido na Central Parque II, outubro: 14 contra 13 do BI.
    """
    if bases.registros("cv_leads_historico"):
        # Pelo histórico: quem foi agendado (OPPS) dentro do período. Conferido: 8 e 13 contra 8 e 13 do BI (Reserva Central Parque II e Central Parque II, outubro)
        return _entradas_do_historico(inicio, fim, emp_f, praca_f, {"Agendado (OPPS)"})
    atual = {x.get("idlead"): (x.get("situacao") or "") for x in bases.registros("cv_leads_dw")}
    anterior = {x.get("idlead"): (x.get("nome_situacao_anterior_lead") or "") for x in bases.registros("cv_leads_dw")}
    return [l for l in leads_do_bi(inicio, fim, emp_f, praca_f) if atual.get(l["id"]) in SITUACOES_OPPS or anterior.get(l["id"]) in SITUACOES_OPPS]
