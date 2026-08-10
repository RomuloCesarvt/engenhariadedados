"""
Taxonomia de origem dos leads: decide, lead a lead, o CANAL e se ele é ONLINE.

A classificação usa a evidência mais forte disponível e registra qual foi usada:

  1. UTM (campos adicionais do CV)  -> confiança ALTA   ex.: utm_source=meta ads
  2. Mídia registrada no CV          -> confiança MÉDIA  ex.: midia_principal=Facebook Ads
  3. Tag do atendimento da IA         -> confiança BAIXA  ex.: mia-organico
  4. Origem genérica do CV            -> confiança BAIXA  ex.: origem=Instagram

Nada é chutado: sem evidência o lead fica em "Não rastreado", que é mostrado no BI
como indicador de qualidade de dados — não some dentro de outro canal.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Grupos e canais
# ---------------------------------------------------------------------------

GRUPOS = {
    "online_pago": "Online — mídia paga",
    "online_organico": "Online — orgânico",
    "indicacao_digital": "Indicação digital",
    "offline": "Offline / comercial",
    "nao_rastreado": "Não rastreado",
}

# Grupos que contam como "lead online" nos indicadores
GRUPOS_ONLINE = {"online_pago", "online_organico", "indicacao_digital"}

CANAIS = {
    # online pago
    "meta": ("Meta Ads (Facebook/Instagram)", "online_pago"),
    "google": ("Google Ads", "online_pago"),
    "tiktok": ("TikTok Ads", "online_pago"),
    "midia_paga": ("Mídia paga não identificada", "online_pago"),
    # online orgânico
    "whatsapp_organico": ("WhatsApp orgânico", "online_organico"),
    "site": ("Site / busca orgânica", "online_organico"),
    "chat": ("Chat do site / chatbot", "online_organico"),
    "redes_sociais": ("Redes sociais (orgânico)", "online_organico"),
    "email_rd": ("E-mail / RD Station", "online_organico"),
    # indicação digital
    "beeviral": ("BeeViral (Indique e Ganhe)", "indicacao_digital"),
    # offline
    "comercial": ("Cadastro comercial (corretor, imobiliária, PDV)", "offline"),
    "indicacao_pessoal": ("Indicação pessoal (corretor, amigo)", "offline"),
    "midia_offline": ("Mídia offline (panfleto, outdoor, rádio)", "offline"),
    "campanha_ativacao": ("Campanha de ativação da base", "offline"),
    # WhatsApp é canal digital: conta como online mesmo sem saber se veio de anúncio (regra do BI gerencial)
    "whatsapp_nao_rastreado": ("WhatsApp sem campanha identificada", "online_organico"),
    # sem evidência
    "nao_rastreado": ("Sem origem registrada", "nao_rastreado"),
}


@dataclass(frozen=True)
class Classificacao:
    canal: str
    canal_label: str
    grupo: str
    grupo_label: str
    online: bool
    confianca: str          # alta | media | baixa | nenhuma
    evidencia: str          # frase legível: de onde veio a decisão
    campanha: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    anuncio: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classificacao(canal: str, confianca: str, evidencia: str, **extra) -> Classificacao:
    label, grupo = CANAIS[canal]
    return Classificacao(
        canal=canal,
        canal_label=label,
        grupo=grupo,
        grupo_label=GRUPOS[grupo],
        online=grupo in GRUPOS_ONLINE,
        confianca=confianca,
        evidencia=evidencia,
        **extra,
    )


def _limpo(texto: Any) -> str:
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower().strip()
    return "" if t in ("null", "none", "nan", "undefined") else t


def _nome(valor: Any) -> Optional[str]:
    if isinstance(valor, dict):
        return valor.get("nome") or valor.get("descricao")
    return valor


def utms_do_lead(raw: Dict[str, Any]) -> Dict[str, str]:
    """UTMs e campos de indicação gravados em campos_adicionais do CV."""
    campos = {}
    for campo in raw.get("campos_adicionais") or []:
        if isinstance(campo, dict) and campo.get("slug"):
            valor = str(campo.get("valor") or "").strip()
            if _limpo(valor):
                campos[campo["slug"]] = valor
    return campos


def tags_do_lead(raw: Dict[str, Any]) -> set:
    return {_limpo(_nome(t)) for t in raw.get("tags") or [] if _nome(t)}


# ---------------------------------------------------------------------------
# Regras por evidência
# ---------------------------------------------------------------------------

META_TERMOS = ("facebook", "instagram", "meta")
META_TOKENS = {"fb", "ig", "an", "meta_ads", "facebook_ads", "instagram_ads"}


def _por_utm(utm: Dict[str, str]) -> Optional[Classificacao]:
    src, med = _limpo(utm.get("cf_utm_source")), _limpo(utm.get("cf_utm_medium"))
    camp = utm.get("cf_utm_campaign")
    camp_l = _limpo(camp)
    extra = {
        "campanha": None if camp_l.startswith("http") else camp,
        "utm_source": utm.get("cf_utm_source"),
        "utm_medium": utm.get("cf_utm_medium"),
        "anuncio": utm.get("cf_utm_content"),
    }

    if utm.get("cf_nome_da_pessoa_que_indicou") or src == "beeviral" or "indique" in camp_l or "indicam" in camp_l:
        return _classificacao("beeviral", "alta", "Campos de indicação / UTM da BeeViral no CV", **extra)
    if not src and not med:
        return None
    if src == "google" or (med == "cpc" and "google" in camp_l):
        return _classificacao("google", "alta", f"UTM: source={utm.get('cf_utm_source')}, medium={utm.get('cf_utm_medium')}", **extra)
    if any(t in src for t in META_TERMOS) or src in META_TOKENS or med in META_TOKENS:
        return _classificacao("meta", "alta", f"UTM: source={utm.get('cf_utm_source')}, medium={utm.get('cf_utm_medium')}", **extra)
    if "tiktok" in src:
        return _classificacao("tiktok", "alta", f"UTM: source={utm.get('cf_utm_source')}", **extra)
    if "rd" in src.replace("+", " ").split() or "rdstation" in src or src == "email" or med in ("email", "rd-station"):
        return _classificacao("email_rd", "alta", f"UTM: source={utm.get('cf_utm_source')}", **extra)
    if src in ("chatgpt.com", "referral") or src.startswith("http"):
        return _classificacao("site", "alta", f"UTM: source={utm.get('cf_utm_source')}", **extra)
    return None


def _por_midia(midia: str) -> Optional[Classificacao]:
    m = _limpo(midia)
    if not m or m in ("outros", "nao definido", "desconhecido"):
        return None
    tokens = set(re.split(r"[^a-z0-9]+", m))
    ev = f"Mídia no CV: {midia}"

    if "click to whatsapp" in m:
        return _classificacao("meta", "media", ev)
    if any(t in m for t in META_TERMOS) or tokens & {"fb", "ig"} or m in ("meta_ads",):
        return _classificacao("meta", "media", ev)
    if "google" in m and not m.startswith("http"):
        return _classificacao("google", "media", ev)
    if "pesquisa" in m or "bing" in m:
        return _classificacao("google" if "cpc" in m else "site", "media", ev)
    if "tiktok" in m:
        return _classificacao("tiktok", "media", ev)
    if m in ("paid", "pago", "ads", "midia paga"):
        return _classificacao("midia_paga", "media", ev)
    if "rdstation" in m or "rd station" in m or m == "email":
        return _classificacao("email_rd", "media", ev)
    if m in ("blip", "chat", "chat web", "chat online", "chatbot") or "morada.ai" in m:
        return _classificacao("chat", "media", ev)
    if "redes sociais" in m or m == "social":
        return _classificacao("redes_sociais", "media", ev)
    if (
        m.startswith("http") or m.startswith("referencia") or re.search(r"\.(com|br|ee|co)\b", m)
        or m in ("trafego direto", "busca organica", "instapage")
    ):
        return _classificacao("site", "media", ev)
    if m.startswith("painel") or m in ("atendimento ao cliente", "ligacao", "modulo de atendimento"):
        return _classificacao("comercial", "media", ev)
    if m.startswith("indicacao"):
        return _classificacao("indicacao_pessoal", "media", ev)
    if m in ("panfleto", "outdoor", "radio", "imprensa", "jornal", "tv"):
        return _classificacao("midia_offline", "media", ev)
    if "campanha de ativacao" in m:
        return _classificacao("campanha_ativacao", "media", ev)
    return None


def classificar_lead_cv(raw: Dict[str, Any]) -> Classificacao:
    """Classifica um lead bruto da API cvio do CV."""
    utm = utms_do_lead(raw)

    c = _por_utm(utm)
    if c:
        return c

    midia = _nome(raw.get("midia_principal")) or next((_nome(m) for m in raw.get("midias") or [] if _nome(m)), None)
    tags = tags_do_lead(raw)

    if _limpo(midia) == "whatsapp":
        if "mia-organico" in tags:
            return _classificacao("whatsapp_organico", "baixa", "Mídia WhatsApp + tag mia-organico, sem UTM de anúncio")
        return _classificacao(
            "whatsapp_nao_rastreado", "nenhuma",
            "Mídia WhatsApp sem UTM e sem tag de orgânico — não dá para saber se veio de anúncio",
        )

    c = _por_midia(midia)
    if c:
        return c

    origem = _nome(raw.get("origem"))
    o = _limpo(origem)
    if o in ("facebook", "instagram"):
        return _classificacao("meta", "baixa", f"Origem no CV: {origem} (sem mídia nem UTM)")
    if o in ("busca organica", "trafego direto", "referencia", "instapage", "social"):
        return _classificacao("site", "baixa", f"Origem no CV: {origem}")
    if o in ("chat online", "chatbot"):
        return _classificacao("chat", "baixa", f"Origem no CV: {origem}")
    if o == "whatsapp":
        if "mia-organico" in tags:
            return _classificacao("whatsapp_organico", "baixa", "Origem WhatsApp + tag mia-organico")
        return _classificacao("whatsapp_nao_rastreado", "nenhuma", "Origem WhatsApp sem UTM nem tag de orgânico")
    if o.startswith("painel") or o in ("ligacao", "modulo de atendimento"):
        return _classificacao("comercial", "baixa", f"Origem no CV: {origem}")
    if "mia-organico" in tags:
        return _classificacao("whatsapp_organico", "baixa", "Só a tag mia-organico (atendimento orgânico pela IA)")

    return _classificacao(
        "nao_rastreado", "nenhuma",
        f"Sem UTM, sem mídia reconhecível e origem genérica ({origem or 'vazia'})",
    )
