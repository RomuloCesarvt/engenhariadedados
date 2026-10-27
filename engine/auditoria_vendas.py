"""
Auditoria de vendas × leads: cada venda do CV (reserva vendida) cruzada com todos os sinais de origem online.

A venda conta como online quando o lead ligado a ela é online (regra do BI gerencial). A auditoria procura as
vendas que ficaram de fora mas têm evidência de origem online em outra base, sempre anterior à venda:
  - outro lead da mesma pessoa (e-mail ou telefone) que veio de mídia online (forte);
  - formulário da Meta preenchido pela pessoa (forte);
  - indicação da BeeViral (forte);
  - mídia online registrada na própria reserva (média: o corretor escolhe a mídia na reserva e ela nem sempre
    concorda com a origem do lead; a auditoria mede e mostra essa confiabilidade);
  - contato na RD Station (fraco: a RD também recebe contatos cadastrados pelo comercial).

Nada disso muda os números do BI: a auditoria mostra o que conferir e corrigir no CV, com a análise do período.
Dados do titular (e-mail, telefone) só são usados para cruzar; nunca saem daqui.
"""

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from engine import bases, bi, identidade
from engine.normalizer import clean_email, clean_phone
from engine.taxonomy import classificar_lead_cv
from engine.verificacao import cv_busca_url, rd_perfil_url

BEEVIRAL_INDICACAO_URL = "https://account.beeviral.app/recommendation/edit/{id}"

STATUS = {
    "online": "Contada como online",
    "online_nao_contabilizada": "Online não contabilizada",
    "online_sem_vinculo": "Online, mas sem o lead vinculado à reserva",
    "provavel_online": "Provável online (mídia da reserva)",
    "possivel_online": "Possível online (só RD Station)",
    "sem_sinal_online": "Sem sinal de origem online",
}
ORDEM_STATUS = {"online_nao_contabilizada": 0, "online_sem_vinculo": 1, "provavel_online": 2, "possivel_online": 3,
                "sem_sinal_online": 4, "online": 5}

SINAIS = {
    "lead_online_sem_vinculo": ("Lead online da pessoa, não vinculado à reserva", "forte"),
    "outro_lead_online": ("Outro lead online da mesma pessoa", "forte"),
    "lead_online_antigo": ("Lead online antigo da mesma pessoa (mais de 1 ano antes)", "media"),
    "formulario_meta": ("Preencheu formulário da Meta", "forte"),
    "beeviral": ("Indicado pela BeeViral", "forte"),
    "midia_reserva_online": ("Mídia online registrada na reserva", "media"),
    "rd_station": ("Contato na RD Station", "fraco"),
}
ORDEM_FORCA = {"forte": 0, "media": 1, "fraco": 2}
DIAS_LEAD_RECENTE = 365  # lead online mais antigo que isso antes da venda é indício, não evidência forte

BASES_USADAS = ("cv_reservas", "cv_leads", "cv_indice", "meta_leads", "beeviral", "rd_leads")


def _br(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%Y") if d else "data desconhecida"


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def _pct(parte: float, total: float) -> Optional[float]:
    return round(parte / total * 100, 1) if total else None


def _p(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.1f}".replace(".", ",") + "%"


# ---------------------------------------------------------------------------
# Contatos das bases digitais
# ---------------------------------------------------------------------------


def _indice_contatos(base: str, campos_email: Tuple[str, ...], campos_fone: Tuple[str, ...], campo_data: str):
    mapa: Dict[Tuple[str, str], List[Tuple[Optional[date], Dict[str, Any]]]] = defaultdict(list)
    for reg in bases.registros(base):
        d = bi._data(reg.get(campo_data))
        for campo in campos_email:
            e = clean_email(reg.get(campo))
            if e:
                mapa[("e", e)].append((d, reg))
        for campo in campos_fone:
            f = clean_phone(reg.get(campo))
            if f:
                mapa[("f", f)].append((d, reg))
    return mapa


def _primeiro_ate(mapa, emails, fones, ate: date) -> Optional[Tuple[Optional[date], Dict[str, Any]]]:
    """Registro mais antigo da pessoa, criado até a data da venda."""
    achados = [x for e in emails for x in mapa.get(("e", e), [])] + [x for f in fones for x in mapa.get(("f", f), [])]
    achados = [x for x in achados if x[0] is None or x[0] <= ate]
    return min(achados, key=lambda x: x[0] or date.min) if achados else None


# ---------------------------------------------------------------------------
# Análise de cada venda
# ---------------------------------------------------------------------------


def _sugestao(venda: Dict[str, Any], tipos: set, status: str) -> str:
    if status == "online_sem_vinculo":
        return (f"A pessoa tem lead online no CV (lead {venda['id']}, {venda['canal_label']}), mas a reserva não está "
                "vinculada a lead nenhum: por isso a venda não entra no online. Vincule esse lead à reserva no CV.")
    if status == "possivel_online":
        return ("Só há contato na RD Station antes da compra. Abra o contato no RD e veja a primeira conversão: se veio de "
                "mídia online, ajuste a mídia do lead no CV.")
    if status == "sem_sinal_online":
        return "Nenhuma base mostra origem online para esta venda."
    if status == "provavel_online":
        if "lead_online_antigo" in tipos:
            return ("A pessoa já foi lead online, mas há mais de um ano. Confirme com o corretor se a compra veio desse "
                    "contato; se sim, associe a reserva a esse lead.")
        return ("Só a mídia escolhida na reserva indica origem online; nenhuma outra base confirma. Confirme com o "
                "corretor como o cliente chegou e, se foi online, associe ou cadastre o lead com essa mídia no CV.")
    if venda["ligacao"] == "sem_lead":
        return ("A venda não tem lead no CV. Associe a reserva ao lead da pessoa (ou cadastre o lead com a mídia "
                "correta) para a venda entrar no online.")
    if "outro_lead_online" in tipos:
        return ("A pessoa tem um lead online anterior, mas a reserva foi ligada a outro lead. Associe a reserva ao lead "
                "online ou ajuste a mídia do lead ligado.")
    return ("A pessoa chegou por um canal online antes da compra, mas o lead no CV está com outra origem. Ajuste a "
            "mídia do lead no CV.")


def _analisar_venda(venda, reserva, idx, contatos) -> Dict[str, Any]:
    data_venda: date = venda["data_venda"]
    sinais: List[Dict[str, Any]] = []

    def sinal(tipo, detalhe, data=None, link=None, link_label=None):
        label, forca = SINAIS[tipo]
        sinais.append({"tipo": tipo, "label": label, "forca": forca, "detalhe": detalhe,
                       "data": data.isoformat() if data else None, "link": link, "link_label": link_label})

    # O lead da pessoa foi achado pelo e-mail ou telefone, e não pelo vínculo com a reserva: a origem
    # aparece aqui, mas o CV não conta essa venda como online — só o lead vinculado faz isso.
    if venda["online"] and venda["ligacao"] != "lead_associado":
        sinal("lead_online_sem_vinculo",
              f"Lead {venda['id']} · {venda['canal_label']} · achado pelo {venda['ligacao']} do titular",
              venda["data_cadastro"] or venda["data"], venda["link"], "Abrir lead no CV")

    if not venda["online"]:
        emails = {clean_email(reserva.get("titular_email"))}
        fones = {clean_phone(reserva.get("titular_telefone"))}
        if venda["id"] is not None and idx.tem(venda["id"]):
            raw = idx.bruto(venda["id"])
            emails.add(clean_email(raw.get("email")))
            fones.add(clean_phone(raw.get("telefone")))
        emails.discard(None)
        fones.discard(None)

        candidatos = {}
        for e in emails:
            for l in idx.mapa("email")[e]:
                candidatos[l["id"]] = l
        for f in fones:
            for l in idx.mapa("fone")[f]:
                candidatos[l["id"]] = l
        online = [l for l in candidatos.values()
                  if l["online"] and l["id"] != venda["id"] and (l["data_cadastro"] or l["data"] or date.min) <= data_venda]
        if online:
            l = max(online, key=lambda x: x["data_cadastro"] or x["data"] or date.min)
            quando = l["data_cadastro"] or l["data"]
            recente = bool(quando) and (data_venda - quando).days <= DIAS_LEAD_RECENTE
            sinal("outro_lead_online" if recente else "lead_online_antigo",
                  f"Lead {l['id']} · {l['canal_label']} · cadastrado em {_br(quando)}",
                  quando, l["link"], "Abrir lead online no CV")

        midia = reserva.get("midia")
        if midia:
            c = classificar_lead_cv({"midia_principal": midia})
            if c.online:
                sinal("midia_reserva_online", f"Mídia na reserva: {midia} ({c.canal_label})")

        achado = _primeiro_ate(contatos["meta_leads"], emails, fones, data_venda)
        if achado:
            d, reg = achado
            sinal("formulario_meta", f"Formulário em {_br(d)} · campanha {reg.get('campaign_name') or 'não informada'}", d)

        achado = _primeiro_ate(contatos["beeviral"], emails, fones, data_venda)
        if achado:
            d, reg = achado
            sinal("beeviral", f"Indicação em {_br(d)}", d,
                  BEEVIRAL_INDICACAO_URL.format(id=reg["ID"]) if reg.get("ID") else None, "Abrir indicação na BeeViral")

        achado = _primeiro_ate(contatos["rd_leads"], emails, fones, data_venda)
        if achado:
            d, reg = achado
            canal = reg.get("origin_channel") or reg.get("utm_source")
            sinal("rd_station", f"Contato criado em {_br(d)}" + (f" · {canal}" if canal else ""), d,
                  rd_perfil_url(reg.get("source_lead_id")), "Abrir contato no RD")

    tipos = {s["tipo"] for s in sinais}
    if venda["online"]:
        # O BI gerencial conta a venda como online pelo lead VINCULADO à reserva. Achar o lead da
        # pessoa pelo e-mail ou telefone mostra a origem, mas não faz a venda contar como online.
        status = "online" if venda["ligacao"] == "lead_associado" else "online_sem_vinculo"
    elif any(s["forca"] == "forte" for s in sinais):
        status = "online_nao_contabilizada"
    elif any(s["forca"] == "media" for s in sinais):
        status = "provavel_online"
    elif sinais:
        status = "possivel_online"
    else:
        status = "sem_sinal_online"
    return {
        "idreserva": venda["idreserva"],
        "data_venda": data_venda,
        "empreendimento_comprado": venda["empreendimento_comprado"],
        "praca_comprada": venda["praca_comprada"],
        "unidade": venda["unidade"],
        "valor_venda": venda["valor_venda"],
        "status": status,
        "status_label": STATUS[status],
        "canal_atual": venda["canal_label"],
        "grupo_atual": venda["grupo"],
        "ligacao": venda["ligacao"],
        "lead_id": venda["id"],
        "lead_link": venda["link"],
        "empreendimento_interesse": venda["empreendimento"] if venda["ligacao"] != "sem_lead" else None,
        "midia_reserva": reserva.get("midia"),
        "corretor": reserva.get("corretor"),
        "imobiliaria": reserva.get("imobiliaria"),
        "sinais": sinais,
        "sugestao": _sugestao(venda, tipos, status),
        # Para medir a confiabilidade da mídia da reserva: ela concorda com a origem do lead ligado?
        "midia_reserva_online": bool(reserva.get("midia")) and classificar_lead_cv({"midia_principal": reserva.get("midia")}).online,
        "lead_online": venda["online"],
    }


_cache: Dict[str, Any] = {"chave": None, "analisadas": []}


def _analisadas() -> List[Dict[str, Any]]:
    vendas = bi.vendas_preparadas()
    if vendas is None:
        return []
    idx = identidade.indice()
    chave = "|".join(f"{b}:{(bases.carregar(b) or {}).get('atualizado_em')}:{(bases.carregar(b) or {}).get('total')}"
                     for b in BASES_USADAS) + f"#{id(idx)}#{id(vendas)}"
    if _cache["chave"] != chave:
        reservas = {str(r.get("idreserva")): r for r in bases.registros("cv_reservas")}
        contatos = {
            "meta_leads": _indice_contatos("meta_leads", ("email_clean", "email"), ("phone_clean", "phone"), "created_at"),
            "beeviral": _indice_contatos("beeviral", ("EMAIL",), ("PHONE",), "CREATION"),
            "rd_leads": _indice_contatos("rd_leads", ("email_clean", "email"), ("phone_clean", "phone"), "created_at"),
        }
        _cache.update(chave=chave, analisadas=[
            _analisar_venda(v, reservas.get(v["idreserva"]) or {}, idx, contatos) for v in vendas
        ])
    return _cache["analisadas"]


# ---------------------------------------------------------------------------
# Auditoria do período
# ---------------------------------------------------------------------------


def _leituras(resumo: Dict[str, Any], alvo: List[Dict[str, Any]], por_emp, midias, imobiliarias) -> List[str]:
    """A análise do período em frases: o que os números mostram, quanto confiar e onde agir primeiro."""
    frases = []
    if not resumo["vendas"]:
        return ["Nenhuma venda no período."]
    frases.append(
        f"{resumo['online']} de {resumo['vendas']} vendas ({_p(resumo['pct_online_contada'])}) contam como online hoje."
    )
    n, p = resumo["online_nao_contabilizada"], resumo["provavel_online"]
    sv = resumo["online_sem_vinculo"]
    if sv:
        frases.append(
            f"{sv} vendas ({_reais(resumo['vgv_online_sem_vinculo'])}) são de pessoas com lead online no CV, mas a "
            "reserva não foi vinculada a lead nenhum: basta vincular o lead à reserva para entrarem no online."
        )
    if n:
        frases.append(
            f"{n} vendas ({_reais(resumo['vgv_online_nao_contabilizada'])}) têm evidência forte de origem online (lead "
            f"online recente da pessoa, formulário da Meta ou BeeViral). Corrigidas no CV, as vendas online iriam de "
            f"{resumo['online']} para {resumo['online'] + n + sv} ({_p(resumo['pct_online_potencial'])} das vendas)."
        )
    elif not sv:
        frases.append("Nenhuma venda fora do online tem evidência forte de origem online.")
    if p:
        conf = resumo["confiabilidade_midia_reserva"]
        frases.append(
            f"Outras {p} vendas ({_reais(resumo['vgv_provavel_online'])}) só têm indício: a mídia online escolhida na reserva "
            "ou um lead online com mais de um ano. "
            + (f"Nas reservas ligadas a lead, a mídia online da reserva bate com um lead online em {_p(conf)} dos casos. "
               "Confirme com o corretor." if conf is not None else "Confirme com o corretor.")
        )
    if alvo:
        sem_lead = sum(1 for i in alvo if i["ligacao"] == "sem_lead")
        if sem_lead:
            frases.append(
                f"{sem_lead} das {len(alvo)} vendas a conferir ({_p(_pct(sem_lead, len(alvo)))}) não têm lead no CV: a reserva "
                "foi feita sem associar lead nenhum. Reservar sempre a partir do lead é a principal correção de processo."
            )
        dias = Counter(i["data_venda"] for i in alvo).most_common(1)
        if dias and dias[0][1] >= max(5, len(alvo) * 0.2):
            frases.append(
                f"{dias[0][1]} dessas vendas são de {_br(dias[0][0])}: concentração típica de lançamento ou registro em lote, "
                "quando a mídia costuma ser preenchida sem conferência."
            )
    if midias:
        frases.append("Mídias online mais escolhidas nessas reservas: " + ", ".join(f"{m} ({q})" for m, q in midias[:3]) + ".")
    if por_emp:
        e = por_emp[0]
        frases.append(f"O empreendimento com mais vendas a conferir é {e['empreendimento']} ({e['vendas']}).")
    if imobiliarias:
        frases.append(
            "Quem mais registrou essas vendas: " + ", ".join(f"{m} ({q})" for m, q in imobiliarias[:3])
            + ". Vale orientar esses times a reservar a partir do lead já existente."
        )
    if resumo["possivel_online"]:
        frases.append(
            f"{resumo['possivel_online']} vendas só têm contato na RD Station antes da compra: podem ser online, confira a "
            "primeira conversão no RD."
        )
    return frases


def auditar(inicio: date, fim: date, empreendimento: Optional[str] = None, praca: Optional[str] = None,
            limite: int = 2000) -> Dict[str, Any]:
    todas = _analisadas()
    itens = [
        a for a in todas
        if inicio <= a["data_venda"] <= fim
        and (not empreendimento or a["empreendimento_comprado"] == empreendimento)
        and (not praca or a["praca_comprada"] == praca)
    ]
    por_status: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STATUS}
    for a in itens:
        por_status[a["status"]].append(a)
    soma = lambda lista: round(sum(a["valor_venda"] for a in lista), 2)
    online, nao_cont = por_status["online"], por_status["online_nao_contabilizada"]
    sem_vinculo = por_status["online_sem_vinculo"]
    # Confiabilidade da mídia da reserva, medida em todas as vendas ligadas a lead (não só no período)
    com_midia = [a for a in todas if a["midia_reserva_online"] and a["ligacao"] != "sem_lead"]
    resumo = {
        "vendas": len(itens), "vgv": soma(itens),
        "online": len(online), "vgv_online": soma(online),
        "online_nao_contabilizada": len(nao_cont), "vgv_online_nao_contabilizada": soma(nao_cont),
        "online_sem_vinculo": len(sem_vinculo), "vgv_online_sem_vinculo": soma(sem_vinculo),
        "provavel_online": len(por_status["provavel_online"]), "vgv_provavel_online": soma(por_status["provavel_online"]),
        "confiabilidade_midia_reserva": _pct(sum(1 for a in com_midia if a["lead_online"]), len(com_midia)),
        "possivel_online": len(por_status["possivel_online"]), "vgv_possivel_online": soma(por_status["possivel_online"]),
        "sem_sinal_online": len(por_status["sem_sinal_online"]), "vgv_sem_sinal_online": soma(por_status["sem_sinal_online"]),
        "pct_online_contada": _pct(len(online), len(itens)),
        "pct_online_potencial": _pct(len(online) + len(nao_cont) + len(sem_vinculo), len(itens)),
    }

    fora = [a for a in itens if a["status"] != "online"]
    contagem_sinal = Counter(s["tipo"] for a in fora for s in a["sinais"])
    valor_sinal = defaultdict(float)
    for a in fora:
        for tipo in {s["tipo"] for s in a["sinais"]}:
            valor_sinal[tipo] += a["valor_venda"]
    por_sinal = sorted(
        ({"tipo": t, "label": l, "forca": f, "vendas": contagem_sinal[t], "vgv": round(valor_sinal[t], 2)}
         for t, (l, f) in SINAIS.items()),
        key=lambda x: (ORDEM_FORCA[x["forca"]], -x["vendas"]),
    )
    # Vendas a conferir: evidência forte ou provável
    alvo = nao_cont + sem_vinculo + por_status["provavel_online"]
    emp = defaultdict(lambda: {"vendas": 0, "vgv": 0.0, "fortes": 0})
    for a in alvo:
        emp[a["empreendimento_comprado"]]["vendas"] += 1
        emp[a["empreendimento_comprado"]]["fortes"] += int(a["status"] in ("online_nao_contabilizada", "online_sem_vinculo"))
        emp[a["empreendimento_comprado"]]["vgv"] += a["valor_venda"]
    por_empreendimento = sorted(
        ({"empreendimento": k, "vendas": v["vendas"], "fortes": v["fortes"], "vgv": round(v["vgv"], 2)} for k, v in emp.items()),
        key=lambda x: -x["vendas"],
    )
    midias = Counter(a["midia_reserva"] for a in alvo
                     if any(s["tipo"] == "midia_reserva_online" for s in a["sinais"])).most_common(8)
    imobiliarias = Counter(a["imobiliaria"] or a["corretor"] for a in alvo if a["imobiliaria"] or a["corretor"]).most_common(8)
    por_canal_atual = Counter(a["canal_atual"] for a in alvo).most_common()

    fora.sort(key=lambda a: (ORDEM_STATUS[a["status"]], -a["data_venda"].toordinal()))
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "disponivel": bi.vendas_preparadas() is not None,
        "resumo": resumo,
        "leituras": _leituras(resumo, alvo, por_empreendimento, midias, imobiliarias),
        "por_sinal": por_sinal,
        "por_empreendimento": por_empreendimento,
        "por_canal_atual": [{"canal": c, "vendas": q} for c, q in por_canal_atual],
        "midias_reserva": [{"midia": m, "vendas": q} for m, q in midias],
        "por_imobiliaria": [{"nome": m, "vendas": q} for m, q in imobiliarias],
        "itens": [{k: v for k, v in {**a, "data_venda": a["data_venda"].isoformat()}.items()
                   if k not in ("midia_reserva_online", "lead_online")} for a in fora[:limite]],
        "truncado": len(fora) > limite,
        "cv_busca_url": cv_busca_url(),
        "bases": [bases.resumo(b) for b in BASES_USADAS],
    }
