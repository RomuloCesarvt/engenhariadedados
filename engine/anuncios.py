"""
Auditoria de anúncios: cada anúncio com o que a plataforma diz (investimento, impressões,
cliques, leads) e o que aconteceu de verdade no CV (leads que chegaram, qualificados,
visitas, vendas e VGV) — e os campeões de cada critério.

Ligação anúncio → lead do CV, da evidência mais forte para a mais fraca:
  1. Lead de formulário da Meta achado no CV por e-mail ou telefone (a Meta informa o anúncio).
  2. UTM do lead no CV: utm_content "Adset Name: X || Ad Name: Y" (padrão das campanhas).
  3. utm_term com o ID do anúncio.
  4. (estimativa) Título do anúncio na conversão do CV ("Click To WhatsApp | Facebook Ads | <título> | M.I.A"): liga o lead ao grupo
     de anúncios que usam aquele título; com mais de um candidato, o lead é repartido pelas conversas de WhatsApp de cada anúncio.
O anúncio é identificado por conjunto + nome do anúncio, porque as UTMs trazem nomes, não IDs.
Rankings só consideram anúncios com amostra mínima: 1 venda em 3 leads não é "melhor conversão".
"""

import re
from collections import Counter, defaultdict
from datetime import date
from statistics import median
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from engine import bases, bi, identidade, textos_anuncios
from engine.criativos import url_global_meta
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO, match_empreendimento
from engine.taxonomy import utms_do_lead

MIN_LEADS_CONVERSAO = 10
MIN_LEADS_CPL = 5
MIN_INVESTIMENTO_CPL = 100.0
DIAS_FORMULARIO_X_LEAD = 60
SEM_ANUNCIO = "__sem_anuncio__"

FONTES = {
    "titulo": "Título do anúncio na conversão do CV (estimativa: repartido entre os anúncios com o mesmo título)",
    "formulario": "Formulário da Meta (lead achado no CV por e-mail ou telefone)",
    "utm": "UTM do anúncio registrada no CV",
    "utm_id": "ID do anúncio na UTM",
}


# ---------------------------------------------------------------------------
# Identificação do anúncio
# ---------------------------------------------------------------------------


def _norm(texto: Any) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip().lower()


def chave_anuncio(conjunto: Any, anuncio: Any) -> Optional[str]:
    return f"{_norm(conjunto)}||{_norm(anuncio)}" if _norm(anuncio) else None


def ler_utm_content(valor: Any) -> Tuple[Optional[str], Optional[str]]:
    """'Adset Name: X || Ad Name: Y' -> ('X', 'Y'). Sem esse padrão devolve (None, None)."""
    texto = str(valor or "")
    anuncio = re.search(r"(?<![a-z])ad\s*name\s*:\s*(.*?)\s*(?:\|\||$)", texto, re.I)
    if not anuncio or not anuncio.group(1).strip():
        return None, None
    conjunto = re.search(r"adset\s*name\s*:\s*(.*?)\s*(?:\|\||$)", texto, re.I)
    return (conjunto.group(1).strip() if conjunto and conjunto.group(1).strip() else None), anuncio.group(1).strip()


def _empreendimento(row: Dict[str, Any], catalogo: List[str], cache: Dict[Tuple, str]) -> str:
    chave = (row.get("conta_nome"), row.get("campanha_nome"))
    if chave not in cache:
        conta = re.sub(r"[-_]", " ", row.get("conta_nome") or "")
        campanha = re.sub(r"[-_]", " ", row.get("campanha_nome") or "")
        cache[chave] = match_empreendimento(conta, catalogo) or match_empreendimento(campanha, catalogo) or EMPREENDIMENTO_DESCONHECIDO
    return cache[chave]


def _novo_anuncio(chave: str, **campos: Any) -> Dict[str, Any]:
    return {
        "chave": chave, "anuncio": None, "conjunto": None, "campanha": None, "conta": None,
        "empreendimento": EMPREENDIMENTO_DESCONHECIDO, "status": None, "miniatura": None,
        "sem_dados_da_plataforma": False,
        "investimento": 0.0, "impressoes": 0, "cliques": 0, "leads_plataforma": 0, "conversas_whatsapp": 0,
        "leads_cv": 0, "sql": 0, "agendamentos": 0, "vendas": 0, "vgv": 0.0,
        "leads_est": 0.0, "sql_est": 0.0, "vendas_est": 0.0,
        "_ids": set(), "_dias": set(), "_ultima": None, "_primeiro": None, "_fontes": Counter(),
        **campos,
    }


def _catalogo(inicio: date, fim: date, catalogo: List[str]):
    """Anúncios da base da Meta: métricas somadas no período e dados descritivos do dia mais recente."""
    anuncios: Dict[str, Dict[str, Any]] = {}
    id_para_chave: Dict[str, str] = {}
    nome_para_chaves: Dict[str, Set[str]] = defaultdict(set)
    cache: Dict[Tuple, str] = {}
    for row in bases.registros("meta_anuncios"):
        chave = chave_anuncio(row.get("conjunto_nome"), row.get("anuncio_nome"))
        if not chave:
            continue
        if row.get("anuncio_id"):
            id_para_chave[str(row["anuncio_id"])] = chave
        nome_para_chaves[_norm(row.get("anuncio_nome"))].add(chave)
        a = anuncios.setdefault(chave, _novo_anuncio(chave))
        d = bi._data(row.get("data"))
        if row.get("anuncio_id"):
            a["_ids"].add(str(row["anuncio_id"]))
        if d and (a["_ultima"] is None or d >= a["_ultima"]):
            a.update(
                anuncio=row.get("anuncio_nome"), conjunto=row.get("conjunto_nome"), campanha=row.get("campanha_nome"),
                conta=row.get("conta_nome"), status=row.get("status"), miniatura=row.get("miniatura"),
                empreendimento=_empreendimento(row, catalogo, cache), _ultima=d,
            )
        if d and (row.get("investimento") or 0) > 0 and (a["_primeiro"] is None or d < a["_primeiro"]):
            a["_primeiro"] = d
        if d and inicio <= d <= fim:
            for campo in ("investimento", "impressoes", "cliques", "leads_plataforma", "conversas_whatsapp"):
                a[campo] += row.get(campo) or 0
            if (row.get("investimento") or 0) > 0:
                a["_dias"].add(d)
    return anuncios, id_para_chave, nome_para_chaves


def _formularios_por_lead_cv() -> Dict[str, List[Dict[str, Any]]]:
    """Leads de formulário da Meta achados no CV (todos os leads): id do lead no CV -> anúncios do formulário."""
    idx = identidade.indice()
    por_email, por_fone = idx.mapa("email"), idx.mapa("fone")
    resultado: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for form in bases.registros("meta_leads"):
        payload = form.get("raw_payload") or {}
        if not payload.get("anuncio"):
            continue
        candidatos = (form.get("email_clean") and por_email.get(form["email_clean"])) or (
            form.get("phone_clean") and por_fone.get(form["phone_clean"])
        ) or []
        for lead in candidatos:
            resultado[str(lead["id"])].append({
                "data": bi._data(form.get("created_at")),
                "conjunto": payload.get("conjunto"),
                "anuncio": payload.get("anuncio"),
                "anuncio_id": payload.get("anuncio_id"),
            })
    return resultado


def _atribuir(lead, utms, formularios, anuncios, id_para_chave, nome_para_chaves):
    """(chave do anúncio, fonte, dados do anúncio) ou (None, motivo, {}) quando não dá para saber."""
    forms = formularios.get(str(lead["id"]))
    if forms and lead["data"]:
        form = min(forms, key=lambda f: abs((f["data"] - lead["data"]).days) if f["data"] else 10**6)
        if form["data"] and abs((form["data"] - lead["data"]).days) <= DIAS_FORMULARIO_X_LEAD:
            chave = id_para_chave.get(str(form.get("anuncio_id") or "")) or chave_anuncio(form["conjunto"], form["anuncio"])
            return chave, "formulario", {"anuncio": form["anuncio"], "conjunto": form["conjunto"]}

    conteudo = utms.get("cf_utm_content")
    conjunto, anuncio = ler_utm_content(conteudo)
    if anuncio:
        chave = chave_anuncio(conjunto, anuncio)
        if chave not in anuncios and not conjunto:
            opcoes = nome_para_chaves.get(_norm(anuncio)) or set()
            chave = next(iter(opcoes)) if len(opcoes) == 1 else chave
        return chave, "utm", {"anuncio": anuncio, "conjunto": conjunto}
    if conteudo:
        opcoes = nome_para_chaves.get(_norm(conteudo)) or set()
        if len(opcoes) == 1:
            return next(iter(opcoes)), "utm", {"anuncio": conteudo, "conjunto": None}

    termo = str(utms.get("cf_utm_term") or "").strip()
    if termo.isdigit() and termo in id_para_chave:
        return id_para_chave[termo], "utm_id", {}

    motivo = "UTM sem nome de anúncio" if conteudo else ("sem UTM de anúncio" if not utms else "UTM sem utm_content")
    return None, motivo, {}


def _passa_filtro(empreendimento: str, emp_f: Set[str], praca_f: Set[str]) -> bool:
    praca = bi.praca_do_empreendimento(empreendimento) if empreendimento != EMPREENDIMENTO_DESCONHECIDO else None
    return (not emp_f or empreendimento in emp_f) and (not praca_f or (praca or "Não identificada") in praca_f)


def _leads_com_anuncio(inicio: date, fim: date, empreendimentos: Optional[List[str]], pracas: Optional[List[str]] = None):
    """Percorre os leads de Meta do período com o anúncio atribuído (e o catálogo de anúncios)."""
    catalogo = bases.registros("cv_empreendimentos")
    anuncios, id_para_chave, nome_para_chaves = _catalogo(inicio, fim, catalogo)
    formularios = _formularios_por_lead_cv()
    brutos = {str(r.get("idlead")): r for r in bases.registros("cv_leads")}
    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    indice_titulos = textos_anuncios.indice_de_titulos()
    conversoes: Dict[str, List[Dict[str, Any]]] = {}

    def candidatos_por_titulo(lead: Dict[str, Any]) -> Tuple[List[str], Optional[str]]:
        """Anúncios com investimento no período e do mesmo empreendimento do lead que usam o título que o lead viu."""
        if not indice_titulos:
            return [], None
        if not conversoes:
            conversoes.update(textos_anuncios.conversoes_por_lead(
                str(l["id"]) for l in bi.leads_preparados() if l["canal"] == "meta" and l["data"] and inicio <= l["data"] <= fim))
            conversoes.setdefault("", [])
        for c in conversoes.get(str(lead["id"]), []):
            titulo = textos_anuncios.titulo_da_conversao(c.get("conversao"))
            ids = indice_titulos.get(textos_anuncios.normalizar(titulo)) if titulo else None
            if not ids:
                continue
            chaves = {id_para_chave[i] for i in ids if i in id_para_chave}
            ativos = sorted(k for k in chaves if anuncios[k]["investimento"] > 0 and anuncios[k]["empreendimento"] == lead["empreendimento_lead"])
            if ativos:
                return ativos, titulo
        return [], None

    def gerar() -> Iterator[Tuple[Dict[str, Any], Optional[str], str, Dict[str, Any]]]:
        for lead in bi.leads_preparados():
            if lead["canal"] != "meta" or not lead["data"] or not (inicio <= lead["data"] <= fim):
                continue
            chave, fonte, info = _atribuir(
                lead, utms_do_lead(brutos.get(str(lead["id"])) or {}), formularios, anuncios, id_para_chave, nome_para_chaves
            )
            if not chave:
                candidatos, titulo = candidatos_por_titulo(lead)
                if len(candidatos) == 1:
                    chave, fonte, info = candidatos[0], "titulo", {"anuncio": anuncios[candidatos[0]]["anuncio"], "conjunto": None, "titulo": titulo}
                elif candidatos:
                    # Mais de um anúncio com o mesmo título: o lead fica no grupo (não conta como "sem anúncio")
                    if _passa_filtro(lead["empreendimento_lead"], emp_f, praca_f):
                        yield lead, None, "titulo", {"candidatos": candidatos, "titulo": titulo}
                    continue
            if chave and chave not in anuncios:
                # Anúncio com lead no CV que não veio nas contas lidas da Meta (ex.: conta sem acesso)
                anuncios[chave] = _novo_anuncio(
                    chave, anuncio=info.get("anuncio"), conjunto=info.get("conjunto"),
                    empreendimento=lead["empreendimento_lead"], sem_dados_da_plataforma=True,
                )
            empreendimento = anuncios[chave]["empreendimento"] if chave else lead["empreendimento_lead"]
            if not _passa_filtro(empreendimento, emp_f, praca_f):
                continue
            yield lead, chave, fonte, info

    return anuncios, gerar


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


def _div(a: float, b: float, casas: int = 2) -> Optional[float]:
    return round(a / b, casas) if b else None


def _finalizar(a: Dict[str, Any]) -> Dict[str, Any]:
    inv = round(a["investimento"], 2)
    saida = {k: v for k, v in a.items() if not k.startswith("_")}
    saida.update(
        investimento=inv,
        vgv=round(a["vgv"], 2),
        leads_est=round(a["leads_est"], 1), sql_est=round(a["sql_est"], 1), vendas_est=round(a["vendas_est"], 1),
        anuncio=a["anuncio"] or "(anúncio sem nome)",
        miniatura=url_global_meta(a["miniatura"]),
        anuncio_ids=sorted(a["_ids"], key=lambda i: (len(i), i)),  # ordem numérica: o último é o criado por último
        dias_com_investimento=len(a["_dias"]),
        primeiro_dia=a["_primeiro"].isoformat() if a["_primeiro"] else None,
        fontes={FONTES.get(k, k): v for k, v in a["_fontes"].items()},
        ctr=_div(a["cliques"] * 100, a["impressoes"]),
        cpc=_div(inv, a["cliques"]),
        cpl_plataforma=_div(inv, a["leads_plataforma"]),
        cpl_real=_div(inv, a["leads_cv"]) if inv else None,
        pct_chegou=_div(a["leads_cv"] * 100, a["leads_plataforma"], 1),
        taxa_sql=_div(a["sql"] * 100, a["leads_cv"], 1),
        taxa_venda=_div(a["vendas"] * 100, a["leads_cv"], 1),
        custo_por_sql=_div(inv, a["sql"]) if inv else None,
        custo_por_venda=_div(inv, a["vendas"]) if inv else None,
        roas=_div(a["vgv"], inv),
        # CPL × leads: mais leads com menor custo = leads ÷ CPL real (= leads² ÷ investimento)
        eficiencia=_div(a["leads_cv"] ** 2, inv, 4) if inv and a["leads_cv"] else None,
    )
    return saida


def _campeao(id_: str, titulo: str, criterio: str, metrica: str, anuncio: Optional[Dict[str, Any]], motivo: str) -> Dict[str, Any]:
    return {
        "id": id_, "titulo": titulo, "criterio": criterio, "metrica": metrica,
        "valor": anuncio.get(metrica) if anuncio else None,
        "anuncio": anuncio, "motivo_vazio": None if anuncio else motivo,
    }


def campeoes(lista: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    com_leads = [a for a in lista if a["leads_cv"]]
    elegiveis_custo = [a for a in com_leads if a["leads_cv"] >= MIN_LEADS_CPL and a["investimento"] >= MIN_INVESTIMENTO_CPL]
    elegiveis_conversao = [a for a in com_leads if a["leads_cv"] >= MIN_LEADS_CONVERSAO]
    elegiveis_criativo = [
        a
        for a in elegiveis_conversao
        if not a["sem_dados_da_plataforma"] and (a["miniatura"] or a["anuncio_ids"])
    ]
    com_venda = [a for a in com_leads if a["vendas"] and a["investimento"] > 0]
    sem_custo = f"Nenhum anúncio com {MIN_LEADS_CPL}+ leads no CV e R$ {MIN_INVESTIMENTO_CPL:.0f}+ investidos no período."
    sem_conversao = f"Nenhum anúncio com {MIN_LEADS_CONVERSAO}+ leads no CV no período."
    return [
        _campeao("mais_leads", "Mais leads no CV", "Anúncio com mais leads que chegaram ao CV no período.", "leads_cv",
                 max(com_leads, key=lambda a: (a["leads_cv"], -(a["cpl_real"] or 10**9)), default=None),
                 "Nenhum anúncio com lead no CV no período."),
        _campeao("eficiencia", "Mais leads com menor custo (CPL × leads)",
                 f"Maior relação leads ÷ CPL real (= leads² ÷ investimento), entre anúncios com {MIN_LEADS_CPL}+ leads "
                 f"e R$ {MIN_INVESTIMENTO_CPL:.0f}+ investidos.", "eficiencia",
                 max(elegiveis_custo, key=lambda a: a["eficiencia"] or 0, default=None), sem_custo),
        _campeao("menor_cpl", "Menor CPL real",
                 f"Menor investimento ÷ leads que chegaram ao CV, entre anúncios com {MIN_LEADS_CPL}+ leads e "
                 f"R$ {MIN_INVESTIMENTO_CPL:.0f}+ investidos.", "cpl_real",
                 min(elegiveis_custo, key=lambda a: a["cpl_real"], default=None), sem_custo),
        _campeao("maior_qualificacao", "Mais leads qualificados (SQL)",
                 f"Maior % de leads que chegaram a SQL, entre anúncios com {MIN_LEADS_CONVERSAO}+ leads no CV, "
                 "ao menos 1 SQL e criativo disponível.", "taxa_sql",
                 max([a for a in elegiveis_criativo if a["sql"]], key=lambda a: (a["taxa_sql"] or 0, a["sql"]), default=None),
                 f"Nenhum anúncio com criativo disponível e {MIN_LEADS_CONVERSAO}+ leads no CV teve lead qualificado no período."),
        _campeao("maior_conversao", "Maior conversão em venda",
                 f"Maior % de leads que viraram venda, entre anúncios com {MIN_LEADS_CONVERSAO}+ leads no CV e ao menos 1 venda.",
                 "taxa_venda", max([a for a in elegiveis_conversao if a["vendas"]], key=lambda a: (a["taxa_venda"], a["vendas"]), default=None),
                 f"Nenhum anúncio com {MIN_LEADS_CONVERSAO}+ leads no CV teve venda no período."),
        _campeao("menor_custo_venda", "Menor custo por venda",
                 "Menor investimento ÷ vendas, entre anúncios com venda e investimento no período.", "custo_por_venda",
                 min(com_venda, key=lambda a: a["custo_por_venda"], default=None),
                 "Nenhum anúncio com investimento teve venda no período."),
    ]


def auditoria(
    inicio: date, fim: date, empreendimentos: Optional[List[str]] = None, pracas: Optional[List[str]] = None
) -> Dict[str, Any]:
    base = bases.resumo("meta_anuncios")
    anuncios, leads = _leads_com_anuncio(inicio, fim, empreendimentos, pracas)

    total = atribuidos = vendas_total = estimados = 0
    vgv_total = 0.0
    motivos_sem_anuncio: Counter = Counter()
    for lead, chave, fonte, _info in leads():
        total += 1
        vendas_total += int(lead["vendido"])
        vgv_total += lead["valor_venda"] if lead["vendido"] else 0
        if not chave and fonte == "titulo":
            candidatos = _info["candidatos"]
            pesos = [max(anuncios[k]["conversas_whatsapp"] or 0, 0) for k in candidatos]
            soma = sum(pesos)
            pesos = [p / soma for p in pesos] if soma else [1 / len(candidatos)] * len(candidatos)
            estimados += 1
            for k, w in zip(candidatos, pesos):
                a = anuncios[k]
                a["leads_est"] += w
                a["sql_est"] += w * int(lead["etapa"] >= 2)
                a["vendas_est"] += w * int(lead["vendido"])
            continue
        if not chave:
            motivos_sem_anuncio[fonte] += 1
            continue
        atribuidos += 1
        a = anuncios[chave]
        a["leads_cv"] += 1
        a["sql"] += int(lead["etapa"] >= 2)
        a["agendamentos"] += int(lead["etapa"] >= 3)
        a["vendas"] += int(lead["vendido"])
        a["vgv"] += lead["valor_venda"] if lead["vendido"] else 0
        a["_fontes"][fonte] += 1

    emp_f, praca_f = set(empreendimentos or []), set(pracas or [])
    com_atividade = [a for a in anuncios.values() if a["investimento"] or a["impressoes"] or a["leads_cv"]]
    lista = [_finalizar(a) for a in com_atividade if _passa_filtro(a["empreendimento"], emp_f, praca_f)]

    # Onde há anúncio no período: para a tela orientar quando o filtro não tem nenhum
    por_empreendimento: Dict[str, Dict[str, Any]] = {}
    for a in com_atividade:
        if a["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO:
            continue
        e = por_empreendimento.setdefault(a["empreendimento"], {"empreendimento": a["empreendimento"], "anuncios": 0, "investimento": 0.0})
        e["anuncios"] += 1
        e["investimento"] = round(e["investimento"] + a["investimento"], 2)
    lista.sort(key=lambda a: (-a["leads_cv"], -a["investimento"]))

    investimento = round(sum(a["investimento"] for a in lista), 2)
    elegiveis = [a for a in lista if a["leads_cv"] >= MIN_LEADS_CPL and a["investimento"] >= MIN_INVESTIMENTO_CPL]
    cobertura = _div(atribuidos * 100, total, 1)

    avisos = []
    if not bases.registros("meta_anuncios"):
        avisos.append("A base 'Meta Ads — Anúncios' ainda não foi baixada: investimento e leads da Meta por anúncio ficam zerados.")
    if cobertura is not None and cobertura < 70:
        avisos.append(
            f"Só {cobertura}% dos leads de Meta no CV têm o anúncio identificado ({total - atribuidos} sem anúncio). "
            "Os números por anúncio ficam abaixo do real — veja os motivos em 'Leads sem anúncio identificado'."
        )
    sem_plataforma = [a for a in lista if a["sem_dados_da_plataforma"]]
    if sem_plataforma:
        avisos.append(
            f"{len(sem_plataforma)} anúncio(s) têm leads no CV mas não aparecem nas contas lidas da Meta (conta sem acesso "
            "do token ou anúncio renomeado): aparecem sem investimento."
        )
    if (date.today() - fim).days < 90:
        avisos.append("Vendas e conversão contam os leads do período que já venderam: nos últimos 90 dias a conversão ainda está amadurecendo.")

    filtro_ativo = bool(emp_f or praca_f)
    motivo_vazio = None
    if not lista:
        if total:
            sem_utm = motivos_sem_anuncio.get("sem UTM de anúncio", 0)
            motivo_vazio = (
                f"Há {total} lead(s) de Meta no CV {'para este filtro ' if filtro_ativo else ''}no período, mas nenhum anúncio "
                f"da Meta ligado a eles nas contas que o sistema lê ({sem_utm} chegaram sem UTM de anúncio). A conta de anúncio "
                "desse empreendimento não está liberada para o usuário do sistema da Meta, ou as campanhas não enviam a UTM do anúncio."
            )
        else:
            motivo_vazio = (
                "Nenhum anúncio da Meta com investimento ou lead no período para o filtro selecionado."
                if filtro_ativo else "Nenhum anúncio da Meta com investimento ou lead no período."
            )

    return {
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "base": base,
        "disponivel": bool(bases.registros("meta_anuncios")),
        "filtro_ativo": filtro_ativo,
        "motivo_vazio": motivo_vazio,
        "empreendimentos_com_anuncios": sorted(por_empreendimento.values(), key=lambda e: -e["investimento"]),
        "criterios": {
            "min_leads_conversao": MIN_LEADS_CONVERSAO,
            "min_leads_cpl": MIN_LEADS_CPL,
            "min_investimento_cpl": MIN_INVESTIMENTO_CPL,
        },
        "resumo": {
            "investimento": investimento,
            "leads_plataforma": sum(a["leads_plataforma"] for a in lista),
            "leads_meta_cv": total,
            "leads_atribuidos": atribuidos,
            "leads_por_titulo": estimados,
            "sem_anuncio": total - atribuidos,
            "cobertura": cobertura,
            "cpl_real": _div(investimento, total),
            "vendas": vendas_total,
            "vgv": round(vgv_total, 2),
            "roas": _div(vgv_total, investimento),
            "anuncios": len(lista),
            "anuncios_com_leads": sum(1 for a in lista if a["leads_cv"]),
        },
        "motivos_sem_anuncio": [{"motivo": m, "leads": q} for m, q in motivos_sem_anuncio.most_common()],
        "medianas": {
            "leads_cv": median([a["leads_cv"] for a in elegiveis]) if elegiveis else None,
            "cpl_real": round(median([a["cpl_real"] for a in elegiveis]), 2) if elegiveis else None,
        },
        "campeoes": campeoes(lista),
        "anuncios": lista,
        "avisos": avisos,
    }


def leads_do_anuncio(
    inicio: date, fim: date, chave: str, empreendimentos: Optional[List[str]] = None, pracas: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Leads por trás de cada número do anúncio (ou os sem anúncio identificado). Sem dados pessoais."""
    _anuncios, leads = _leads_com_anuncio(inicio, fim, empreendimentos, pracas)
    itens = []
    for lead, chave_lead, fonte, _info in leads():
        if (chave == SEM_ANUNCIO and chave_lead) or (chave != SEM_ANUNCIO and chave_lead != chave):
            continue
        itens.append({
            "id": lead["id"],
            "data": lead["data"].isoformat() if lead["data"] else None,
            "data_cadastro": lead["data_cadastro"].isoformat() if lead["data_cadastro"] else None,
            "empreendimento": lead["empreendimento_lead"],
            "situacao": lead["situacao"],
            "etapa_label": bi.ETAPAS[lead["etapa"]][1],
            "vendido": lead["vendido"],
            "valor_venda": lead["valor_venda"],
            "data_venda": lead["data_venda"].isoformat() if lead["data_venda"] else None,
            "fonte": FONTES.get(fonte, fonte),
            "evidencia": lead["evidencia"],
            "link": lead["link"],
        })
    itens.sort(key=lambda i: i["data"] or "", reverse=True)
    return {"chave": chave, "total": len(itens), "itens": itens}
