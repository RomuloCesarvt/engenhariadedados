"""
Casos de venda a investigar como possível origem SDR, do período analisado em engine/vendas_online.py.

A análise de vendas online decide o que CONTA como venda SDR/online. Este módulo pega o que ficou de fora e ordena por
força da pista, usando o histórico de cada comprador (assistente virtual, SDR, corretor), sem decidir nada: quem decide
é a leitura da conversa. Prioridades:

  1  Investigar — pode ser SDR: a assistente/SDR atendeu o comprador, o corretor veio depois (ou não veio) e a venda é do
     time Moura Leite (ou sem tipo).
  2  Possível venda perdida: a assistente/SDR atendeu e a venda saiu por imobiliária/outro corretor.
  3  Pista fraca: o vínculo com o lead é fraco (nome diferente ou parente) ou o contato foi há mais de 90 dias.
  4  Corretor veio antes do SDR/assistente: não é SDR.
  5  Sem rastro de SDR/assistente.
"""

from datetime import date
from typing import Any, Dict, List, Optional

JANELA_DIAS = 90
TIPOS_SDR = ("assistente", "sdr")
VENDA_NOSSA = ("SDR", "Corretor (Time Moura Leite)", "Sem tipo de venda")

ROTULO = {
    1: "Investigar — pode ser SDR",
    2: "Possível venda perdida (saiu por imobiliária/outro corretor)",
    3: "Pista fraca",
    4: "Corretor veio antes do SDR/assistente",
    5: "Sem rastro de SDR/assistente",
}


def _dia(texto: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def avaliar(venda: Dict[str, Any]) -> Dict[str, Any]:
    """Evidência e prioridade de uma venda, a partir do histórico dos leads do comprador."""
    dv = _dia(venda.get("data_venda"))
    todos: List[Dict[str, Any]] = []
    for lead in venda.get("leads") or []:
        forte = lead.get("parentesco") == "mesma pessoa"
        for e in lead.get("eventos") or []:
            if e[1] in TIPOS_SDR and _dia(e[0]):
                todos.append({"data": _dia(e[0]), "tipo": e[1], "texto": e[2], "lead": lead["id"], "forte": forte})
    todos.sort(key=lambda e: e["data"])
    # Só o que aconteceu até a venda; e, dentro disso, a janela de 90 dias antes dela
    ate_venda = [e for e in todos if not dv or e["data"] <= dv]
    janela = [e for e in ate_venda if not dv or (dv - e["data"]).days <= JANELA_DIAS]
    fortes = [e for e in janela if e["forte"]]
    corretor_antes = sorted(_dia(c[0]) for c in (venda.get("corretor_antes") or []) if _dia(c[0]))
    if venda.get("data_precadastro") and _dia(venda["data_precadastro"]):
        corretor_antes = sorted(corretor_antes + [_dia(venda["data_precadastro"])])
    primeiro_corretor = corretor_antes[0] if corretor_antes else None
    primeiro = fortes[0]["data"] if fortes else None
    ultimo = fortes[-1]["data"] if fortes else None
    repasse = next((e["data"] for e in fortes if "repassou" in e["texto"].lower() or "agendou visita" in e["texto"].lower()), None)
    humano = any(e["tipo"] == "sdr" for e in fortes)
    nossa = bool(venda.get("do_time")) or venda.get("canal") == "SDR"

    if not ate_venda:
        prioridade, motivo = 5, "Nenhum atendimento de assistente ou SDR no histórico do comprador."
    elif not janela:
        antigo = ate_venda[-1]["data"]
        prioridade, motivo = 3, f"O último atendimento da assistente/SDR foi em {antigo:%d/%m/%Y}, mais de {JANELA_DIAS} dias antes da venda."
    elif not fortes:
        prioridade, motivo = 3, "O atendimento está num lead com nome diferente ou parente do comprador: o vínculo é fraco."
    elif primeiro_corretor and primeiro_corretor < primeiro:
        prioridade, motivo = 4, f"O corretor registrou o cliente em {primeiro_corretor:%d/%m}, antes do primeiro atendimento da assistente/SDR ({primeiro:%d/%m})."
    elif nossa:
        prioridade = 1
        igual = primeiro_corretor and primeiro == primeiro_corretor
        motivo = ("Assistente/SDR e corretor do time aparecem no mesmo dia" if igual else "A assistente/SDR atendeu antes do corretor do time" if primeiro_corretor
                  else "A assistente/SDR atendeu e nenhum corretor aparece antes") + f" (primeiro atendimento em {primeiro:%d/%m}" + (f", repasse para vendas em {repasse:%d/%m}" if repasse else "") + ")."
    else:
        prioridade = 2
        motivo = (f"A assistente/SDR atendeu em {primeiro:%d/%m}" + (f" (repasse em {repasse:%d/%m})" if repasse else "") +
                  f" e a venda saiu pelo corretor {venda.get('corretor') or 'de fora do time'}.")
    return {
        "prioridade": prioridade, "prioridade_label": ROTULO[prioridade], "motivo": motivo,
        "primeiro_atendimento": primeiro.isoformat() if primeiro else None, "ultimo_atendimento": ultimo.isoformat() if ultimo else None,
        "repasse_para_vendas": repasse.isoformat() if repasse else None, "atendimento_humano_sdr": humano, "eventos": len(fortes),
        "corretor_antes": primeiro_corretor.isoformat() if primeiro_corretor else None, "do_time": nossa,
    }


def casos(analise: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Vendas que NÃO contam como SDR/online (as 20 já contadas ficam de fora), com evidência e prioridade."""
    saida = []
    for v in analise.get("vendas") or []:
        if v.get("resultado") in ("online_cv_sdr", "online_cv_lead"):
            continue
        ev = avaliar(v)
        saida.append({
            "idreserva": v["idreserva"], "produto": v["produto"], "praca": v.get("praca"), "data_venda": v["data_venda"], "valor": v.get("valor"),
            "canal": v.get("canal"), "corretor": v.get("corretor"), "imobiliaria": v.get("imobiliaria"), "cliente": v.get("cliente"),
            "classe_analise": v.get("resultado_label"), "link_reserva": v.get("link_reserva"),
            "leads": [{"id": l["id"], "parentesco": l.get("parentesco"), "link": l.get("link")} for l in (v.get("leads") or [])][:3],
            **ev,
        })
    saida.sort(key=lambda c: (c["prioridade"], c["data_venda"]))
    return saida


# ---------------------------------------------------------------------------
# Critério da gestão: venda SDR = atendimento do SDR/assistente até o repasse ou agendamento + origem online + recente
# ---------------------------------------------------------------------------

VEREDITOS = {
    "sdr": "Pode ser SDR",
    "perdida": "Pode ser venda perdida",
    "sdr_cv_sem_evidencia": "Confirmar com o SDR",
    "parcial": "Provavelmente não é SDR",
    "sem_rastro": "Sem sinal de SDR",
    "remanescente": "Fora: praça sem anúncio no ar",
}
FALHAS = {"atendimento": "não há atendimento do SDR/assistente registrado", "repasse": "não houve repasse para vendas nem agendamento",
          "origem": "o lead não veio de origem online", "recente": "o último atendimento foi há mais de 90 dias"}


def _origem_online_do_lead(lead: Dict[str, Any], conversoes: Dict[Any, List[Dict[str, Any]]], dv: Optional[date]) -> bool:
    """
    O lead teve conversão online na janela de 90 dias antes da venda (mídia da conversão na lista do BI)? Sem conversões na
    base (leads antigos), vale a mídia/origem registrada no lead. Assim uma reentrada posterior pelo corretor não apaga a
    origem de campanha.
    """
    from engine import leads_bi

    try:
        eventos = conversoes.get(int(lead["id"]), [])
    except (TypeError, ValueError):
        eventos = []
    janela = [e for e in eventos if not dv or (_dia(e["data_cad"]) and 0 <= (dv - _dia(e["data_cad"])).days <= JANELA_DIAS)]
    if janela:
        return any(leads_bi._chave_origem(leads_bi.origem_do_bi(e)) in leads_bi.ORIGENS_ONLINE_BI for e in janela)
    return leads_bi._chave_origem(lead.get("midia_cv") or lead.get("origem_cv") or "") in leads_bi.ORIGENS_ONLINE_BI


MIDIAS_PAGAS = {"facebook ads", "instagram ads", "meta_ads", "ig", "facebook", "google", "bing", "ads"}


def _origem_paga_do_lead(lead: Dict[str, Any], conversoes: Dict[Any, List[Dict[str, Any]]], dv: Optional[date]) -> bool:
    """
    O lead nasceu de mídia paga (Meta/Google)? Vale a conversão da janela vinda de mídia paga OU a origem do próprio lead
    (UTM de anúncio, "Busca Compartilhada" do Facebook, categoria de campanha paga): o lead gerado pela campanha meses antes
    e reativado pela assistente agora continua sendo lead de campanha.
    """
    from engine import leads_bi

    try:
        eventos = conversoes.get(int(lead["id"]), [])
    except (TypeError, ValueError):
        eventos = []
    janela = [e for e in eventos if not dv or (_dia(e["data_cad"]) and 0 <= (dv - _dia(e["data_cad"])).days <= JANELA_DIAS)]
    if any(leads_bi._chave_origem(leads_bi.origem_do_bi(e)) in MIDIAS_PAGAS for e in janela):
        return True
    utm = str(lead.get("utm") or "").lower()
    do_lead = (
        leads_bi._chave_origem(lead.get("midia_cv") or "") in MIDIAS_PAGAS or "meta ads" in utm or "google" in utm
        or "busca compartilhada" in str(lead.get("origem_cv") or "").lower() or str(lead.get("categoria") or "").startswith("Campanha paga")
    )
    # Cadastro manual na janela (corretor/PDV/gestor) não é campanha, mesmo que o lead tenha uma origem antiga paga
    manual = any(leads_bi._chave_origem(leads_bi.origem_do_bi(e)) not in leads_bi.ORIGENS_ONLINE_BI for e in janela)
    return do_lead and not (manual and not any(leads_bi._chave_origem(leads_bi.origem_do_bi(e)) in leads_bi.ORIGENS_ONLINE_BI for e in janela))


def _nome_da_origem(lead: Dict[str, Any], conversoes: Dict[Any, List[Dict[str, Any]]], dv: Optional[date]) -> str:
    """Origem do lead em palavras simples: a mídia da conversão online da janela ou, sem ela, a mídia registrada no lead."""
    from engine import leads_bi

    try:
        eventos = conversoes.get(int(lead["id"]), [])
    except (TypeError, ValueError):
        eventos = []
    janela = [e for e in eventos if not dv or (_dia(e["data_cad"]) and 0 <= (dv - _dia(e["data_cad"])).days <= JANELA_DIAS)]
    online = [leads_bi.origem_do_bi(e) for e in sorted(janela, key=lambda e: e["data_cad"], reverse=True)
              if leads_bi._chave_origem(leads_bi.origem_do_bi(e)) in leads_bi.ORIGENS_ONLINE_BI]
    bruto = online[0] if online else (lead.get("midia_cv") or lead.get("origem_cv") or "")
    chave = leads_bi._chave_origem(bruto)
    if chave in leads_bi.ORIGENS_META:
        return "anúncio da Meta (Facebook/Instagram)"
    return {"google": "anúncio do Google", "bing": "anúncio pago", "whatsapp": "WhatsApp", "busca organica": "busca orgânica no Google",
            "trafego direto": "acesso direto ao site", "linktree": "link da bio", "redes sociais": "redes sociais", "e-mail": "e-mail",
            "blip": "chat do site", "chatbot": "chat do site", "m.i.a.": "assistente virtual", "disparos m.i.a.": "disparo da assistente virtual"}.get(chave, bruto or "origem não registrada")


def _repasse(texto: str, tipo: str) -> bool:
    t = texto.lower()
    return tipo == "corretor_atribuido" or "repassou" in t or "agendou visita" in t or "agendamento" in t


def criterio(venda: Dict[str, Any], conversoes: Dict[Any, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Os requisitos da gestão, um a um, para a melhor pessoa/lead do comprador (o que atende mais requisitos)."""
    dv = _dia(venda.get("data_venda"))
    melhor = None
    for lead in venda.get("leads") or []:
        if lead.get("parentesco") != "mesma pessoa":
            continue
        eventos = [(_dia(e[0]), e[1], e[2]) for e in lead.get("eventos") or [] if e[1] in TIPOS_SDR + ("corretor_atribuido",) and _dia(e[0])]
        eventos = [e for e in eventos if not dv or e[0] <= dv]
        recentes = [e for e in eventos if not dv or (dv - e[0]).days <= JANELA_DIAS]
        atendimento = any(e[1] in TIPOS_SDR for e in eventos)
        r = {
            "atendimento": atendimento,
            "recente": any(e[1] in TIPOS_SDR for e in recentes),
            "repasse": any(_repasse(e[2], e[1]) for e in recentes),
            "origem": _origem_online_do_lead(lead, conversoes, dv),
            "origem_paga": _origem_paga_do_lead(lead, conversoes, dv),
            "origem_nome": _nome_da_origem(lead, conversoes, dv),
            "quem": sorted({e[1] for e in recentes if e[1] in TIPOS_SDR}),
            "lead": lead["id"], "link": lead.get("link"),
            "primeiro_recente": min((e[0] for e in recentes if e[1] in TIPOS_SDR), default=None),
            "ultimo_atendimento": max((e[0] for e in eventos if e[1] in TIPOS_SDR), default=None),
            "ultimo_repasse": max((e[0] for e in recentes if _repasse(e[2], e[1])), default=None),
        }
        r["atendidos"] = sum(r[k] for k in ("atendimento", "recente", "repasse", "origem"))
        if melhor is None or r["atendidos"] > melhor["atendidos"]:
            melhor = r
    if melhor is None:
        melhor = {"atendimento": False, "recente": False, "repasse": False, "origem": False, "origem_paga": False, "origem_nome": None, "quem": [], "lead": None, "link": None,
                  "ultimo_atendimento": None, "ultimo_repasse": None, "atendidos": 0}
    nossa = bool(venda.get("do_time")) or venda.get("canal") == "SDR"
    cv_sdr = venda.get("resultado") == "online_cv_sdr" or venda.get("canal") == "SDR"
    datas_corretor = sorted(d for d in [_dia(c[0]) for c in (venda.get("corretor_antes") or [])] + [_dia(venda.get("data_precadastro"))] if d)
    primeiro_recente = melhor.get("primeiro_recente")
    corretor_primeiro = bool(datas_corretor and primeiro_recente and datas_corretor[0] < primeiro_recente)
    melhor["corretor_primeiro"] = corretor_primeiro
    completo = all(melhor[k] for k in ("atendimento", "recente", "repasse", "origem")) and not corretor_primeiro
    if completo and nossa:
        veredito = "sdr"
    elif completo:
        veredito = "perdida"
    elif (cv_sdr or venda.get("resultado") == "online_cv_lead") and not corretor_primeiro:
        veredito = "sdr_cv_sem_evidencia"
    elif melhor["atendimento"]:
        veredito = "parcial"
    else:
        veredito = "sem_rastro"
    faltas = [FALHAS[k] for k in ("atendimento", "repasse", "origem", "recente") if not melhor[k] and (k != "recente" or melhor["atendimento"])]
    if corretor_primeiro:
        faltas.append("o corretor registrou o cliente antes do SDR/assistente")
    return {**melhor, "venda_do_time": nossa, "cv_marca_sdr": cv_sdr, "veredito": veredito, "veredito_label": VEREDITOS[veredito],
            "faltas": faltas, "dias_ultimo_atendimento": (dv - melhor["ultimo_atendimento"]).days if dv and melhor["ultimo_atendimento"] else None}


def explicar(t: Dict[str, Any]) -> str:
    """Uma frase simples dizendo por que a venda pode (ou não) ser SDR."""
    quem = t.get("quem") or []
    atendeu = ("a assistente virtual e o SDR" if len(quem) == 2 else "a assistente virtual" if quem == ["assistente"] else "o SDR" if quem == ["sdr"] else "o SDR/assistente")
    ult, rep = t.get("ultimo_atendimento"), t.get("ultimo_repasse")
    dias = t.get("dias_ultimo_atendimento")
    verbo = "atenderam" if len(quem) == 2 else "atendeu"
    contato = f"o cliente (último contato em {ult:%d/%m})" if ult else "o cliente"
    passou = f" e passou para vendas em {rep:%d/%m}" if rep else ""
    origem = f"o lead veio de {t['origem_nome']}" if t.get("origem_nome") else "o lead tem origem online"
    depois = f"{dias} dias depois" if dias is not None else "depois"
    v = t["veredito"]
    if v == "sdr":
        return f"Pode ser SDR porque {atendeu} {verbo} {contato}{passou}; {origem}; e a venda saiu {depois} do último contato, pelo nosso time ({t.get('corretor')})."
    if v == "perdida":
        return (f"Pode ser venda perdida porque {atendeu} {verbo} {contato}{passou}; {origem}; "
                f"mas a venda saiu {depois} do último contato, pelo corretor {t.get('corretor')}, de fora do nosso time.")
    if v == "sdr_cv_sem_evidencia":
        return "Confirmar com o SDR: o CV marca esta venda como SDR, mas " + "; ".join(t.get("faltas") or ["não há atendimento recente registrado"]) + "."
    if v == "parcial":
        return "Provavelmente não é SDR: " + "; ".join(t.get("faltas") or ["falta algum requisito"]) + "."
    if v == "remanescente":
        return "Fora da análise: " + (t.get("faltas") or ["a praça não teve anúncio no ar"])[0] + "."
    return "Sem sinal de SDR ou assistente no histórico do cliente."


def todas(analise: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    As vendas do período com o veredito pelo critério da gestão. Praça sem investimento online (Meta/Google) nos 90 dias antes da
    venda é remanescente: sai da análise e fica à parte, só para conferência.
    """
    from engine import apresentacao as ap, bases, bi

    conversoes: Dict[Any, List[Dict[str, Any]]] = {}
    for c in bases.registros("cv_conversoes"):
        conversoes.setdefault(c["idlead"], []).append(c)
    insights = ap.insights_resolvidos(bi._insights_com_empreendimento(bases.registros("cv_empreendimentos")))

    def investimento_da_praca(produto: str, dv: Optional[date]) -> float:
        praca = bi._limpo(bi.praca_do_empreendimento(produto))
        return sum(
            r["investimento"] or 0 for r in insights
            if r["data_d"] and dv and 0 <= (dv - r["data_d"]).days <= JANELA_DIAS and r["plataforma"] in ("meta", "google")
            and bi._limpo(bi.praca_do_empreendimento(r["empreendimento"])) == praca
        )

    saida = []
    for v in analise.get("vendas") or []:
        c = criterio(v, conversoes)
        invest_praca = investimento_da_praca(v["produto"], _dia(v.get("data_venda")))
        c["investimento_praca_90d"] = round(invest_praca, 2)
        c["veredito_sem_filtro_de_praca"] = c["veredito"]
        if invest_praca <= 0 and c["veredito"] != "sem_rastro":
            c["veredito"], c["veredito_label"] = "remanescente", VEREDITOS["remanescente"]
            c["faltas"] = [f"a praça não teve investimento online nos {JANELA_DIAS} dias antes da venda"]
        saida.append({
            "idreserva": v["idreserva"], "produto": v["produto"], "praca": v.get("praca"), "data_venda": v["data_venda"], "valor": v.get("valor") or 0,
            "canal": v.get("canal"), "corretor": v.get("corretor"), "imobiliaria": v.get("imobiliaria"), "cliente": v.get("cliente"),
            "classe_analise": v.get("resultado_label"), "link_reserva": v.get("link_reserva"), **c,
        })
        saida[-1]["explicacao"] = explicar(saida[-1])
    ordem = {k: i for i, k in enumerate(VEREDITOS)}
    saida.sort(key=lambda x: (ordem[x["veredito"]], x["data_venda"]))
    return saida
