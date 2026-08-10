"""
Conferências entre bases: cada uma responde a UMA pergunta de negócio.

  - BeeViral × CV:        cada indicação chegou no CRM? E chegou creditada à BeeViral?
  - Meta / Google × CV:   a plataforma diz que gerou X leads — quantos chegaram no CRM?

As listas trazem o link para abrir o lead no CV. Nome, e-mail e telefone aparecem só nos
leads de formulário da Meta que NÃO foram achados no CV, para a equipe procurá-los manualmente.
"""

import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from engine import bases, bi
from engine.extractors.beeviral import beeviral_item_to_raw
from engine.extractors.meta_ads import PLATAFORMAS_META
from engine import identidade, verificacao
from engine.taxonomy import classificar_lead_cv
from engine.verificacao import cv_busca_url, rd_perfil_url
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO, clean_email, clean_phone, match_empreendimento, normalize_name

# Painel da BeeViral: abre exatamente a indicação (exige login na BeeViral)
BEEVIRAL_INDICACAO_URL = "https://account.beeviral.app/recommendation/edit/{id}"

STATUS_INDICACAO = {
    "creditada": "No CV e creditada à BeeViral",
    "sem_credito": "No CV, mas sem crédito à BeeViral",
    "ja_era_lead": "Já era lead do CV antes da indicação",
    "nao_chegou": "Não chegou no CV",
}


def _pct(parte: float, total: float) -> Optional[float]:
    return round(parte / total * 100, 1) if total else None


# ---------------------------------------------------------------------------
# BeeViral × CV
# ---------------------------------------------------------------------------


def _indice_cv():
    """Buscas no CV (TODOS os leads, de qualquer data) por UUID da RD, e-mail e telefone."""
    idx = identidade.indice()
    return idx.mapa("uuid"), idx.mapa("email"), idx.mapa("fone")


def _vendas_das_indicacoes(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Uma linha por VENDA (lead do CV), mesmo que a pessoa tenha sido indicada várias vezes — senão a
    mesma venda e o mesmo VGV contam uma vez por indicação. Venda anterior à primeira indicação não é
    resultado dela: fica marcada e fora da soma.
    """
    por_lead: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for i in itens:
        if i["cv_vendido"]:
            por_lead[i["cv_id"]].append(i)
    vendas = []
    for grupo in por_lead.values():
        grupo.sort(key=lambda i: i["data"])
        primeira = grupo[0]
        vendas.append({
            **primeira,
            "indicacoes_do_lead": len(grupo),
            "campanhas_do_lead": sorted({g["campanha"] for g in grupo if g["campanha"]}),
            "venda_antes_da_indicacao": bool(primeira["cv_data_venda"] and primeira["cv_data_venda"] < primeira["data"]),
        })
    return sorted(vendas, key=lambda v: v["cv_data_venda"] or "", reverse=True)


def conferencia_beeviral(inicio: date, fim: date, empreendimento: Optional[str] = None) -> Dict[str, Any]:
    base = bases.resumo("beeviral")
    indicacoes = bases.registros("beeviral")
    catalogo = bases.registros("cv_empreendimentos")
    por_uuid, por_email, por_fone = _indice_cv()

    itens: List[Dict[str, Any]] = []
    for item in indicacoes:
        criada = bi._data(item.get("CREATION"))
        if not criada or not (inicio <= criada <= fim):
            continue
        raw = beeviral_item_to_raw(item)

        candidatos, chave = [], None
        for nome_chave, indice, valor in (
            ("UUID da RD Station", por_uuid, raw.get("rd_contact_uuid")),
            ("e-mail", por_email, clean_email(raw.get("email"))),
            ("telefone", por_fone, clean_phone(raw.get("phone"))),
        ):
            if valor and indice.get(valor):
                candidatos, chave = indice[valor], nome_chave
                break

        emp_bee = match_empreendimento(raw.get("empreendimento"), catalogo) if raw.get("empreendimento") else None
        emp_bee = emp_bee or match_empreendimento(raw.get("campaign_name"), catalogo)

        lead_cv = None
        if candidatos:
            lead_cv = min(candidatos, key=lambda l: abs((l["data_cadastro"] - criada).days) if l["data_cadastro"] else 10**6)

        if not lead_cv:
            status = "nao_chegou"
        elif lead_cv["data_cadastro"] and (criada - lead_cv["data_cadastro"]).days > 1:
            status = "ja_era_lead"
        elif lead_cv["canal"] == "beeviral":
            status = "creditada"
        else:
            status = "sem_credito"

        emp_final = emp_bee or (lead_cv["empreendimento"] if lead_cv else None) or EMPREENDIMENTO_DESCONHECIDO
        if empreendimento and emp_final != empreendimento:
            continue

        itens.append({
            "indicacao_id": item.get("ID"),
            "data": criada.isoformat(),
            "campanha": raw.get("campaign_name"),
            "empreendimento": emp_final,
            "status": status,
            "status_label": STATUS_INDICACAO[status],
            "chave_encontrada": chave,
            "convertida_na_beeviral": raw.get("convertido"),
            "cv_id": lead_cv["id"] if lead_cv else None,
            "cv_link": lead_cv["link"] if lead_cv else None,
            "cv_data": lead_cv["data_cadastro"].isoformat() if lead_cv and lead_cv["data_cadastro"] else None,
            "cv_canal": lead_cv["canal_label"] if lead_cv else None,
            "cv_evidencia": lead_cv["evidencia"] if lead_cv else None,
            "cv_situacao": lead_cv["situacao"] if lead_cv else None,
            "cv_vendido": bool(lead_cv and lead_cv["vendido"]),
            "dias_ate_cv": (lead_cv["data_cadastro"] - criada).days if lead_cv and lead_cv["data_cadastro"] else None,
            "cv_data_venda": lead_cv["data_venda"].isoformat() if lead_cv and lead_cv["data_venda"] else None,
            "cv_valor_venda": lead_cv["valor_venda"] if lead_cv and lead_cv["vendido"] else None,
            "bee_link": BEEVIRAL_INDICACAO_URL.format(id=item.get("ID")) if item.get("ID") else None,
            "rd_uuid": raw.get("rd_contact_uuid"),
            "rd_link": rd_perfil_url(raw.get("rd_contact_uuid")),
            # Contato só de quem não foi achado no CV, para a equipe procurar manualmente
            **({"nome": raw.get("nome"), "email": raw.get("email"), "telefone": raw.get("phone")} if status == "nao_chegou" else {}),
        })

    # Última barreira, como nos formulários da Meta: "não chegou" só depois da confirmação ao vivo no CV
    pendentes = []
    for i in itens:
        if i["status"] != "nao_chegou":
            continue
        ao_vivo = verificacao.resultado_valido(i.get("email"), i.get("telefone"))
        if not ao_vivo:
            i["confirmacao"] = {"estado": "pendente"}
            pendentes.append((i.get("email"), i.get("telefone")))
            continue
        i["confirmacao"] = {"estado": "confirmado", "verificado_em": ao_vivo["verificado_em"]}
        if ao_vivo["cv"]["encontrado"]:
            achado = min(ao_vivo["cv"]["leads"], key=lambda c: str(c.get("data_cad") or "9999"))
            cadastro = bi._data(achado.get("data_cad"))
            if cadastro and (date.fromisoformat(i["data"]) - cadastro).days > 1:
                i["status"] = "ja_era_lead"
            else:
                canal = classificar_lead_cv({"midia_principal": achado.get("midia")}).canal
                i["status"] = "creditada" if canal == "beeviral" else "sem_credito"
            i["status_label"] = STATUS_INDICACAO[i["status"]]
            i.update(cv_link=achado.get("link"), cv_situacao=achado.get("situacao"), cv_canal=achado.get("midia"),
                     cv_data=str(achado.get("data_cad") or "")[:10] or None, chave_encontrada="verificação ao vivo",
                     corrigido_ao_vivo=True)
            for campo in ("nome", "email", "telefone"):
                i.pop(campo, None)
    if pendentes:
        verificacao.iniciar_confirmacao(pendentes)

    total = len(itens)
    por_status = Counter(i["status"] for i in itens)

    def agrupar(campo: str) -> List[Dict[str, Any]]:
        grupos: Dict[str, Counter] = defaultdict(Counter)
        for i in itens:
            grupos[i[campo] or "—"][i["status"]] += 1
        linhas = []
        for nome, c in grupos.items():
            n = sum(c.values())
            linhas.append({
                campo: nome, "indicacoes": n, **{s: c[s] for s in STATUS_INDICACAO},
                "pct_no_cv": _pct(n - c["nao_chegou"], n),
                "pct_creditada": _pct(c["creditada"], n - c["nao_chegou"] - c["ja_era_lead"]),
            })
        return sorted(linhas, key=lambda x: -x["indicacoes"])

    chegaram = total - por_status["nao_chegou"]
    elegiveis_credito = chegaram - por_status["ja_era_lead"]
    vendas = _vendas_das_indicacoes(itens)
    vendas_validas = [v for v in vendas if not v["venda_antes_da_indicacao"]]
    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "base": base,
        "resumo": {
            "indicacoes": total,
            **{s: por_status[s] for s in STATUS_INDICACAO},
            "pct_no_cv": _pct(chegaram, total),
            "pct_creditada": _pct(por_status["creditada"], elegiveis_credito),
            # Vendas únicas (por lead do CV) feitas depois da indicação
            "vendidas": len(vendas_validas),
            "vgv_vendidas": round(sum(v["cv_valor_venda"] or 0 for v in vendas_validas), 2),
            "vendas_antes_da_indicacao": len(vendas) - len(vendas_validas),
        },
        "status_labels": STATUS_INDICACAO,
        "cv_busca_url": cv_busca_url(),
        "confirmacao": {"pendentes": len(pendentes), **verificacao.estado_confirmacao()},
        # Origem das vendas: cada indicação do período que virou venda, com o canal que o CV registrou
        "vendas": vendas,
        "credito_no_cv": [
            {"canal": canal, "indicacoes": q}
            for canal, q in Counter(i["cv_canal"] for i in itens if i["status"] == "sem_credito").most_common()
        ],
        "por_empreendimento": agrupar("empreendimento"),
        "por_campanha": agrupar("campanha"),
        "itens": sorted(itens, key=lambda i: i["data"], reverse=True),
    }


# ---------------------------------------------------------------------------
# Meta / Google × CV
# ---------------------------------------------------------------------------

PLATAFORMAS = {"meta": ("meta_insights", "Meta Ads"), "google": ("google_insights", "Google Ads")}


def _nome_campanha(nome: Optional[str]) -> str:
    return (nome or "").strip().lower()


def conferencia_plataforma(inicio: date, fim: date, plataforma: str, empreendimento: Optional[str] = None) -> Dict[str, Any]:
    chave_base, label = PLATAFORMAS[plataforma]
    base = bases.resumo(chave_base)
    catalogo = bases.registros("cv_empreendimentos")

    linhas = [
        r for r in bi._insights_com_empreendimento(catalogo)
        if r["plataforma"] == plataforma and r["data_d"] and inicio <= r["data_d"] <= fim
        and (not empreendimento or r["empreendimento"] == empreendimento)
    ]
    leads_crm = [
        l for l in bi.leads_preparados()
        if l["canal"] == plataforma and l["data_cadastro"] and inicio <= l["data_cadastro"] <= fim
        and (not empreendimento or l["empreendimento_lead"] == empreendimento)
    ]

    disponivel = bool(linhas) or (base.get("status") or {}).get("mode") == "real"

    # ---- por empreendimento ----
    emps: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in linhas:
        e = emps[r["empreendimento"]]
        e["leads_plataforma"] += r["leads_plataforma"]
        e["conversas_whatsapp"] += r.get("conversas_whatsapp", 0)
        e["investimento"] += r["investimento"]
        e["cliques"] += r["cliques"]
    for l in leads_crm:
        emps[l["empreendimento_lead"]]["leads_crm"] += 1
        emps[l["empreendimento_lead"]]["vendas_coorte"] += int(l["vendido"])

    por_empreendimento = []
    for nome, e in emps.items():
        lp, lc, inv = int(e["leads_plataforma"]), int(e["leads_crm"]), round(e["investimento"], 2)
        por_empreendimento.append({
            "empreendimento": nome,
            "leads_plataforma": lp,
            "conversas_whatsapp": int(e["conversas_whatsapp"]),
            "leads_crm": lc,
            "diferenca": lc - lp,
            "pct_chegou": _pct(lc, lp),
            "investimento": inv,
            "cpl_plataforma": round(inv / lp, 2) if inv and lp else None,
            "cpl_crm": round(inv / lc, 2) if inv and lc else None,
            "vendas_coorte": int(e["vendas_coorte"]),
            "custo_por_venda": round(inv / e["vendas_coorte"], 2) if inv and e["vendas_coorte"] else None,
        })
    por_empreendimento.sort(key=lambda x: -(x["leads_plataforma"] or x["leads_crm"]))

    # ---- por campanha (nome da campanha na plataforma x utm_campaign no CV) ----
    camps: Dict[str, Dict[str, Any]] = {}
    for r in linhas:
        c = camps.setdefault(_nome_campanha(r["campanha_nome"]), {"campanha": r["campanha_nome"], "leads_plataforma": 0, "investimento": 0.0, "leads_crm": 0})
        c["leads_plataforma"] += r["leads_plataforma"]
        c["investimento"] = round(c["investimento"] + r["investimento"], 2)
    for l in leads_crm:
        if l["campanha"]:
            c = camps.setdefault(_nome_campanha(l["campanha"]), {"campanha": l["campanha"], "leads_plataforma": 0, "investimento": 0.0, "leads_crm": 0})
            c["leads_crm"] += 1
    por_campanha = sorted(
        ({**c, "pct_chegou": _pct(c["leads_crm"], c["leads_plataforma"])} for c in camps.values()),
        key=lambda x: -(x["leads_plataforma"] + x["leads_crm"]),
    )

    # ---- série diária ----
    dias: Dict[str, Dict[str, int]] = {}
    d = inicio
    while d <= fim:
        dias[d.isoformat()] = {"data": d.isoformat(), "leads_plataforma": 0, "leads_crm": 0}
        d += timedelta(days=1)
    for r in linhas:
        dias[r["data_d"].isoformat()]["leads_plataforma"] += r["leads_plataforma"]
    for l in leads_crm:
        dias[l["data_cadastro"].isoformat()]["leads_crm"] += 1

    formularios = _conferencia_formularios_meta(inicio, fim, empreendimento, catalogo) if plataforma == "meta" else None

    total_plat = sum(r["leads_plataforma"] for r in linhas)
    total_inv = round(sum(r["investimento"] for r in linhas), 2)
    return {
        "plataforma": plataforma,
        "label": label,
        "disponivel": disponivel,
        "base": base,
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "resumo": {
            "leads_plataforma": total_plat,
            "leads_crm": len(leads_crm),
            "pct_chegou": _pct(len(leads_crm), total_plat),
            "investimento": total_inv,
            "cpl_plataforma": round(total_inv / total_plat, 2) if total_inv and total_plat else None,
            "cpl_crm": round(total_inv / len(leads_crm), 2) if total_inv and leads_crm else None,
            "conversas_whatsapp": sum(r.get("conversas_whatsapp", 0) for r in linhas),
        },
        "por_empreendimento": por_empreendimento,
        "por_campanha": por_campanha[:30],
        "serie": [dias[k] for k in sorted(dias)],
        "formularios": formularios,
        "notas": [
            f"Leads no CRM = leads do CV classificados como {label} (pela UTM ou mídia) com cadastro no período.",
            "Diferenças são esperadas em pequena escala: a plataforma conta o lead no dia da conversão e o CV no dia do cadastro; "
            "a mesma pessoa pode gerar mais de um lead na plataforma e um só no CV.",
            "Conversas iniciadas no WhatsApp aparecem separadas: a plataforma não as conta como lead, mas elas viram lead no CV.",
        ],
    }


# ---------------------------------------------------------------------------
# RD Station × CV
# ---------------------------------------------------------------------------

STATUS_RD = {
    "no_cv": "Chegou no CV",
    "inbound_fora": "Converteu em formulário e NÃO chegou no CV",
    "importado": "Lista ou base importada (não é lead novo)",
    "disparo": "Entrou por disparo de campanha",
    "outro_fora": "Fora do CV — outra entrada",
    "pendente": "Fora do CV — origem ainda em classificação",
}

_TIPO_PARA_STATUS = {
    "inbound": "inbound_fora",
    "importacao": "importado",
    "disparo": "disparo",
    "cadastro_manual": "outro_fora",
    "sem_conversao": "outro_fora",
    "outro": "outro_fora",
}


def conferencia_rd(inicio: date, fim: date) -> Dict[str, Any]:
    """Cada contato criado na RD no período: chegou no CV? Se não, era lead de verdade?"""
    from engine.rd_conversoes import TIPOS_ENTRADA

    idx = identidade.indice()
    uuids_cv, emails_cv = idx.valores("uuid"), idx.valores("email")
    conversoes = {r["uuid"]: r for r in bases.registros("rd_conversoes") if r.get("uuid")}

    itens: List[Dict[str, Any]] = []
    for contato in bases.registros("rd_leads"):
        criado = bi._data(contato.get("created_at"))
        if not criado or not (inicio <= criado <= fim):
            continue
        uuid = contato.get("integration_id")
        conv = conversoes.get(uuid)
        if uuid in uuids_cv:
            status, chave = "no_cv", "UUID da RD Station"
        elif contato.get("email_clean") in emails_cv:
            status, chave = "no_cv", "e-mail"
        elif not conv:
            status, chave = "pendente", None
        else:
            status, chave = _TIPO_PARA_STATUS.get(conv.get("tipo"), "outro_fora"), None
        itens.append({
            "uuid": uuid,
            "data": criado.isoformat(),
            "status": status,
            "status_label": STATUS_RD[status],
            "chave_encontrada": chave,
            "primeira_conversao": conv.get("primeira_conversao") if conv else None,
            "tipo_entrada": TIPOS_ENTRADA.get(conv.get("tipo")) if conv else None,
            "link_rd": f"https://app.rdstation.com.br/leads/public/{uuid}" if uuid else None,
        })

    total = len(itens)
    por_status = Counter(i["status"] for i in itens)
    fora = total - por_status["no_cv"]
    classificados_fora = fora - por_status["pendente"]

    def top_conversoes(status: str) -> List[Dict[str, Any]]:
        c = Counter(i["primeira_conversao"] or "(sem conversão)" for i in itens if i["status"] == status)
        return [{"conversao": k, "contatos": q} for k, q in c.most_common(25)]

    por_mes: Dict[str, Counter] = defaultdict(Counter)
    for i in itens:
        por_mes[i["data"][:7]][i["status"]] += 1

    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "base": bases.resumo("rd_leads"),
        "base_conversoes": bases.resumo("rd_conversoes"),
        "status_labels": STATUS_RD,
        "resumo": {
            "contatos": total,
            **{s: por_status[s] for s in STATUS_RD},
            "pct_no_cv": _pct(por_status["no_cv"], total),
            "pct_classificado": _pct(classificados_fora, fora) if fora else 100.0,
            # Taxa de falha real: dos contatos que converteram em formulário, quantos não chegaram
            # Só existe com a classificação completa: com pendentes, "0%" esconderia falhas ainda não vistas
            "pct_inbound_perdido": None if por_status["pendente"] else _pct(
                por_status["inbound_fora"], por_status["inbound_fora"] + por_status["no_cv"]
            ),
        },
        "inbound_fora_por_conversao": top_conversoes("inbound_fora"),
        "importados_por_lista": top_conversoes("importado"),
        "por_mes": [{"mes": m, **{s: c[s] for s in STATUS_RD}} for m, c in sorted(por_mes.items())],
        "itens_inbound_fora": sorted(
            (i for i in itens if i["status"] == "inbound_fora"), key=lambda i: i["data"], reverse=True
        )[:2000],
    }


# ---------------------------------------------------------------------------
# Formulários da Meta × CV (lead a lead)
# ---------------------------------------------------------------------------

STATUS_FORMULARIO = {
    "no_cv": "Chegou no CV",
    "provavel_no_cv": "Provável no CV (telefone ou nome parecido)",
    "ja_era_lead": "Já era lead do CV antes do formulário",
    "nao_chegou": "Não chegou no CV",
}


def _fone8(valor: Any) -> Optional[str]:
    """Últimos 8 dígitos: o mesmo número com ou sem DDI, DDD ou nono dígito."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-8:] if len(digitos) >= 8 else None


def _mais_proximo(candidatos: List[Dict[str, Any]], criado: date) -> Dict[str, Any]:
    return min(candidatos, key=lambda l: abs((l["data_cadastro"] - criado).days) if l["data_cadastro"] else 10**6)


def _conferencia_formularios_meta(inicio: date, fim: date, empreendimento: Optional[str], catalogo: List[str]) -> Dict[str, Any]:
    """
    Cada lead dos formulários nativos da Meta procurado no CV por e-mail e telefone.
    Quem não é encontrado ganha uma segunda busca (telefone com DDD/DDI diferente ou mesmo nome)
    e a verificação no RD Station, para mostrar onde a integração parou.
    A API da Meta só devolve leads de formulário dos últimos 90 dias.
    """
    base = bases.resumo("meta_leads")
    # A conta de anúncio diz o empreendimento com mais segurança que o nome da campanha
    emp_por_campanha = {
        row.get("campanha_nome"): row["empreendimento"]
        for row in bi._insights_com_empreendimento(catalogo)
        if row.get("plataforma") == "meta" and row["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO
    }
    # Busca em TODOS os leads do CV, de qualquer data (índice), não só nos 13 meses do BI
    idx = identidade.indice()
    por_email, por_fone, por_fone8, por_nome = idx.mapa("email"), idx.mapa("fone"), idx.mapa("fone8"), idx.mapa("nome")

    # RD Station: o lead passou pelo RD? Mostra se a integração parou entre o RD e o CV
    conversoes_rd = {c.get("uuid"): c for c in bases.registros("rd_conversoes")}
    rd_por_email: Dict[str, Dict[str, Any]] = {}
    for contato in bases.registros("rd_leads"):
        if contato.get("email_clean"):
            rd_por_email.setdefault(contato["email_clean"], contato)

    itens: List[Dict[str, Any]] = []
    datas: List[date] = []
    for form_lead in bases.registros("meta_leads"):
        criado = bi._data(form_lead.get("created_at"))
        if not criado:
            continue
        datas.append(criado)
        if not (inicio <= criado <= fim):
            continue
        payload = form_lead.get("raw_payload") or {}
        campanha = form_lead.get("campaign_name")
        emp = emp_por_campanha.get(campanha) or match_empreendimento(re.sub(r"[-_]", " ", campanha or ""), catalogo) or match_empreendimento(
            re.sub(r"[-_]", " ", payload.get("formulario") or ""), catalogo
        )

        candidatos, chave = [], None
        for nome_chave, indice, valor in (
            ("e-mail", por_email, form_lead.get("email_clean")),
            ("telefone", por_fone, form_lead.get("phone_clean")),
        ):
            if valor and indice.get(valor):
                candidatos, chave = indice[valor], nome_chave
                break
        lead_cv = _mais_proximo(candidatos, criado) if candidatos else None

        telefone = payload.get("phone") or form_lead.get("phone")
        provavel, motivo = None, None
        if not lead_cv:
            f8, nome_n = _fone8(telefone), normalize_name(payload.get("nome"))
            if f8 and por_fone8.get(f8):
                provavel, motivo = _mais_proximo(por_fone8[f8], criado), "Mesmo telefone, com DDD, DDI ou nono dígito diferente"
            elif nome_n and por_nome.get(nome_n):
                provavel, motivo = _mais_proximo(por_nome[nome_n], criado), "Mesmo nome, com e-mail e telefone diferentes"

        if lead_cv:
            status = "ja_era_lead" if lead_cv["data_cadastro"] and (criado - lead_cv["data_cadastro"]).days > 1 else "no_cv"
        else:
            status = "provavel_no_cv" if provavel else "nao_chegou"

        referencia = lead_cv or provavel
        emp_final = emp or (referencia["empreendimento_lead"] if referencia else None) or EMPREENDIMENTO_DESCONHECIDO
        if empreendimento and emp_final != empreendimento:
            continue

        contato_rd = rd_por_email.get(form_lead.get("email_clean"))
        conversao_rd = conversoes_rd.get(contato_rd.get("source_lead_id")) if contato_rd else None
        item = {
            "id": form_lead.get("source_lead_id"),
            "data": criado.isoformat(),
            "data_hora": form_lead.get("created_at"),
            "campanha": campanha,
            "conjunto": payload.get("conjunto"),
            "anuncio": payload.get("anuncio"),
            "formulario": payload.get("formulario"),
            "pagina": payload.get("pagina"),
            "plataforma": PLATAFORMAS_META.get(payload.get("plataforma"), payload.get("plataforma")),
            "organico": payload.get("organico"),
            "respostas": payload.get("respostas") or {},
            "empreendimento": emp_final,
            "status": status,
            "status_label": STATUS_FORMULARIO[status],
            "chave_encontrada": chave,
            "cv_link": lead_cv["link"] if lead_cv else None,
            "cv_canal": lead_cv["canal_label"] if lead_cv else None,
            "cv_situacao": lead_cv["situacao"] if lead_cv else None,
            "cv_vendido": bool(lead_cv and lead_cv["vendido"]),
            "dias_ate_cv": (lead_cv["data_cadastro"] - criado).days if lead_cv and lead_cv["data_cadastro"] else None,
            "provavel_link": provavel["link"] if provavel else None,
            "provavel_motivo": motivo,
            "provavel_situacao": provavel["situacao"] if provavel else None,
            "rd": {
                "no_rd": bool(contato_rd),
                "uuid": contato_rd.get("source_lead_id") if contato_rd else None,
                "link": rd_perfil_url(contato_rd.get("source_lead_id")) if contato_rd else None,
                "entrada": str(contato_rd.get("created_at") or "")[:10] or None if contato_rd else None,
                "primeira_conversao": conversao_rd.get("primeira_conversao") if conversao_rd else None,
                "tipo": conversao_rd.get("tipo") if conversao_rd else None,
            },
        }
        # Dados de contato só de quem precisa ser procurado manualmente no CV
        if status in ("nao_chegou", "provavel_no_cv"):
            item.update(
                nome=payload.get("nome"),
                email=payload.get("email") or form_lead.get("email") or form_lead.get("email_clean"),
                telefone=telefone or form_lead.get("phone_clean"),
            )
        itens.append(item)

    # Última barreira: ninguém aparece como "não chegou" sem confirmação ao vivo na API do CV
    pendentes = []
    for i in itens:
        if i["status"] not in ("nao_chegou", "provavel_no_cv"):
            continue
        ao_vivo = verificacao.resultado_valido(i.get("email"), i.get("telefone"))
        if not ao_vivo:
            i["confirmacao"] = {"estado": "pendente"}
            pendentes.append((i.get("email"), i.get("telefone")))
            continue
        i["confirmacao"] = {"estado": "confirmado", "verificado_em": ao_vivo["verificado_em"]}
        rd_vivo = ao_vivo.get("rd") or {}
        if rd_vivo.get("consultado"):
            i["rd"].update(no_rd=rd_vivo["encontrado"], uuid=rd_vivo.get("uuid") or i["rd"]["uuid"],
                           link=rd_vivo.get("link") or i["rd"]["link"])
        if ao_vivo["cv"]["encontrado"]:
            # A pessoa existe no CV: vale o cadastro mais antigo para saber se já era lead
            achado = min(ao_vivo["cv"]["leads"], key=lambda c: str(c.get("data_cad") or "9999"))
            cadastro = bi._data(achado.get("data_cad"))
            i["status"] = "ja_era_lead" if cadastro and (date.fromisoformat(i["data"]) - cadastro).days > 1 else "no_cv"
            i["status_label"] = STATUS_FORMULARIO[i["status"]]
            i.update(cv_link=achado.get("link"), cv_situacao=achado.get("situacao"), corrigido_ao_vivo=True)
            for campo in ("nome", "email", "telefone"):
                i.pop(campo, None)
    if pendentes:
        verificacao.iniciar_confirmacao(pendentes)

    total = len(itens)
    por_status = Counter(i["status"] for i in itens)
    novos = total - por_status["ja_era_lead"]

    def agrupar(campo: str) -> List[Dict[str, Any]]:
        grupos: Dict[str, Counter] = defaultdict(Counter)
        for i in itens:
            grupos[i[campo] or "—"][i["status"]] += 1
        linhas = []
        for nome, c in grupos.items():
            n = sum(c.values())
            linhas.append({campo: nome, "leads": n, **{s: c[s] for s in STATUS_FORMULARIO},
                           "pct_nao_chegou": _pct(c["nao_chegou"], n - c["ja_era_lead"])})
        return sorted(linhas, key=lambda x: -x["leads"])

    nao_chegaram = sorted((i for i in itens if i["status"] == "nao_chegou"), key=lambda i: i["data_hora"] or i["data"], reverse=True)
    provaveis = sorted((i for i in itens if i["status"] == "provavel_no_cv"), key=lambda i: i["data_hora"] or i["data"], reverse=True)
    creditados_errado = Counter(i["cv_canal"] for i in itens if i["status"] == "no_cv" and i["cv_canal"] and "Meta" not in i["cv_canal"])
    return {
        "disponivel": bool(bases.registros("meta_leads")),
        "base": base,
        "rd_disponivel": bool(rd_por_email),
        "cv_busca_url": cv_busca_url(),
        "cobertura": {"inicio": min(datas).isoformat() if datas else None, "fim": max(datas).isoformat() if datas else None},
        "status_labels": STATUS_FORMULARIO,
        "resumo": {
            "leads": total,
            **{s: por_status[s] for s in STATUS_FORMULARIO},
            "pct_nao_chegou": _pct(por_status["nao_chegou"], novos),
            "vendidos": sum(1 for i in itens if i["cv_vendido"]),
            # Onde a integração parou
            "nao_chegou_mas_no_rd": sum(1 for i in nao_chegaram if i["rd"]["no_rd"]),
            "nao_chegou_nem_no_rd": sum(1 for i in nao_chegaram if not i["rd"]["no_rd"]),
        },
        "credito_errado_no_cv": [{"canal": k, "leads": q} for k, q in creditados_errado.most_common()],
        "por_empreendimento": agrupar("empreendimento"),
        "por_formulario": agrupar("formulario")[:30],
        "itens_nao_chegaram": nao_chegaram[:2000],
        "itens_provaveis": provaveis[:2000],
        # Situação de cada lead, sem dados pessoais: base dos diagnósticos por período
        "linhas": [
            {
                "data": i["data"], "formulario": i["formulario"], "pagina": i["pagina"], "campanha": i["campanha"],
                "empreendimento": i["empreendimento"], "status": i["status"], "cv_canal": i.get("cv_canal"),
                "no_rd": i["rd"]["no_rd"], "confirmado": (i.get("confirmacao") or {}).get("estado") == "confirmado",
            }
            for i in itens
        ],
        "indice_cv": {"leads": idx.total, "cobre_todos_os_leads": idx.cobre_todos_os_leads},
        "confirmacao": {
            "pendentes": len(pendentes),
            "confirmados": sum(1 for i in nao_chegaram + provaveis if (i.get("confirmacao") or {}).get("estado") == "confirmado"),
            "corrigidos": sum(1 for i in itens if i.get("corrigido_ao_vivo")),
            **verificacao.estado_confirmacao(),
        },
    }
