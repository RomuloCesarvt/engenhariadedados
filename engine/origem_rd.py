"""
Origem dos leads que chegam ao CV sem origem registrada, descoberta na RD Station.

Uma parte dos leads entra no CV pela integração da RD sem mídia, sem UTM e sem origem:
no CV eles ficam em "Sem origem registrada" e desaparecem dos indicadores de canal. A RD
guarda as conversões desses contatos — formulário do site, landing page, anúncio, disparo
— e é por elas que a origem é recuperada.

Consultar a RD custa uma chamada por contato; por isso o resultado fica guardado na base
"origem_rd" e cada atualização consulta só os leads ainda não vistos.

O que a RD responde vira canal da taxonomia (`aplicar`), então o lead recuperado aparece
no BI como qualquer outro lead do canal — com a evidência dizendo que veio da RD.
"""

import base64
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote

from engine import bases
from engine.config import SourceStatus
from engine.integrations import build_status
from engine.normalizer import clean_email
from engine.taxonomy import CANAIS, GRUPOS, GRUPOS_ONLINE, Classificacao, classificar_lead_cv

POR_RODADA = int(os.getenv("ORIGEM_RD_POR_RODADA", "800"))
PARALELAS = int(os.getenv("ORIGEM_RD_PARALELAS", "4"))
TENTATIVAS = int(os.getenv("ORIGEM_RD_TENTATIVAS", "3"))

# A integração da assistente virtual cria conversão para todo lead: não diz de onde ele veio.
IGNORAR = re.compile(r"m\.i\.a|sem conversão|^painel", re.I)
# Nomes de conversão que são base importada / lista do comercial, não lead que chegou sozinho.
LISTA = re.compile(r"base |base$|clientes|lista|leads cancelados|leads qualificados|compradores", re.I)
SITE = re.compile(r"^form|lp|site|fale-conosco|botao-whatsapp", re.I)
# Formulários de anúncio que não trazem UTM: o nome da conversão é a única pista.
ANUNCIO = re.compile(r"anuncio|reserva central parque avare", re.I)

SEM_CONVERSAO = "A RD não tem conversão identificável (só a integração da assistente ou nenhuma)."


# ---------------------------------------------------------------------------
# Leitura das conversões
# ---------------------------------------------------------------------------


def _url_da_primeira_sessao(fonte: Any) -> Optional[str]:
    """traffic_source 'encoded_<base64>' guarda a URL (com UTMs) da primeira sessão do contato."""
    if not isinstance(fonte, str) or not fonte.startswith("encoded_"):
        return None
    try:
        dados = json.loads(base64.b64decode(fonte[8:] + "==").decode("utf-8", "ignore"))
        return unquote((dados.get("first_session") or {}).get("value") or "")
    except Exception:  # noqa: BLE001 — pista opcional: URL ilegível não invalida a conversão
        return None


def _midia_paga(url: Optional[str]) -> Optional[Tuple[str, str]]:
    """(canal, frase) quando a URL da primeira sessão mostra clique de anúncio."""
    if not url:
        return None
    query = url.split("?", 1)[-1] if "?" in url else url
    params = {k: v[0].lower() for k, v in parse_qs(query).items()}
    src, med = params.get("utm_source", ""), params.get("utm_medium", "")
    if "gclid" in params or (src == "google" and med in ("cpc", "paid")):
        return "google", "Campanha paga Google (via site/LP)"
    if src in ("facebook", "ig", "fb", "instagram", "meta") and med in ("cpc", "paid", "paid_social"):
        return "meta", "Campanha paga Meta (via site/LP)"
    if "instagram.com" in url or "facebook.com" in url:
        return "meta", "Instagram/Facebook (link, via site/LP)"
    return None


def classificar_conversoes(eventos: List[Dict[str, Any]], email: Optional[str], emails_meta: set) -> Dict[str, Any]:
    """Origem do lead a partir das conversões dele na RD. canal=None quando a RD também não sabe."""
    ordenados = sorted(eventos or [], key=lambda e: str(e.get("data") or ""))
    identificaveis = [e for e in ordenados if e.get("identificador") and not IGNORAR.search(e["identificador"])]
    paga = next((p for p in (_midia_paga(_url_da_primeira_sessao(e.get("traffic_source"))) for e in ordenados) if p), None)

    if not identificaveis:
        return {"categoria": "Sem origem (nem na RD)", "canal": None, "online": False,
                "detalhe": SEM_CONVERSAO, "identificador": None, "data": None}

    primeira = identificaveis[0]
    ident = primeira["identificador"]
    detalhe = f"1ª conversão na RD: {ident} em {str(primeira.get('data'))[:10]}"
    base_registro = {"identificador": ident, "data": str(primeira.get("data") or "")[:10] or None}

    if (email and email in emails_meta) or ANUNCIO.search(ident):
        return {"categoria": "Campanha paga (Meta/Google)", "canal": "meta", "online": True,
                "detalhe": detalhe + " (formulário de anúncio)", **base_registro}
    if paga:
        return {"categoria": "Campanha paga (Meta/Google)", "canal": paga[0], "online": True,
                "detalhe": f"{detalhe} — {paga[1]}", **base_registro}
    if SITE.search(ident):
        return {"categoria": "Site / landing page (formulário)", "canal": "site", "online": True,
                "detalhe": detalhe, **base_registro}
    if "whatsapp" in ident.lower() or "guarda chuva" in ident.lower():
        return {"categoria": "WhatsApp (remarketing do comercial)", "canal": "campanha_ativacao", "online": False,
                "detalhe": detalhe, **base_registro}
    if LISTA.search(ident):
        return {"categoria": "Lista/base importada (remarketing do comercial)", "canal": "campanha_ativacao",
                "online": False, "detalhe": detalhe, **base_registro}
    return {"categoria": "Outra conversão na RD (confirmar)", "canal": None, "online": False,
            "detalhe": detalhe, **base_registro}


# ---------------------------------------------------------------------------
# Base "origem_rd"
# ---------------------------------------------------------------------------


def _todos_os_leads() -> Dict[str, Dict[str, Any]]:
    todos = {str(l["idlead"]): l for l in bases.registros("cv_indice") if l.get("idlead")}
    todos.update({str(l["idlead"]): l for l in bases.registros("cv_leads") if l.get("idlead")})
    return todos


def alvos() -> Dict[str, str]:
    """{idlead: uuid da RD} dos leads que estão sem origem no CV e vieram da integração da RD."""
    return {
        lid: str(l["idrd_station"])
        for lid, l in _todos_os_leads().items()
        if l.get("idrd_station") and classificar_lead_cv(l).canal == "nao_rastreado"
    }


def _na_fila(idlead: str, consultados: Dict[str, Dict[str, Any]]) -> bool:
    """
    O lead ainda precisa ser consultado na RD?

    Contato que a RD não devolve (apagado, sem permissão) é tentado algumas vezes e depois sai
    da fila: senão ele voltaria em toda rodada no lugar de quem nunca foi consultado.
    """
    registro = consultados.get(idlead)
    if registro is None:
        return True
    return "erro" in registro and registro.get("tentativas", 0) < TENTATIVAS


def baixar(inicio: datetime, fim: datetime) -> Tuple[List[Dict[str, Any]], SourceStatus]:
    """Consulta na RD os leads sem origem ainda não vistos e devolve o acumulado."""
    from engine.extractors.rd_station import API, RDStationExtractor

    anteriores = {str(r["idlead"]): r for r in bases.registros("origem_rd") if r.get("idlead")}
    pendentes = [(lid, uuid) for lid, uuid in alvos().items() if _na_fila(lid, anteriores)]
    lote = pendentes[:POR_RODADA]

    if lote:
        import httpx

        emails_meta = {clean_email(m.get("email_clean") or m.get("email")) for m in bases.registros("meta_leads")} - {None}
        leads = _todos_os_leads()
        ex = RDStationExtractor()
        try:
            with httpx.Client(timeout=30, limits=httpx.Limits(max_connections=PARALELAS)) as client:
                token = ex._access_token(client)

                def consultar(item: Tuple[str, str]) -> Optional[Dict[str, Any]]:
                    lid, uuid = item
                    try:
                        eventos = ex._get(client, f"{API}/platform/contacts/{uuid}/events", token,
                                          {"event_type": "CONVERSION"})
                    except PermissionError:
                        raise
                    except Exception as e:  # noqa: BLE001 — volta na próxima rodada, até o limite
                        tentativas = (anteriores.get(lid) or {}).get("tentativas", 0) + 1
                        return {"idlead": lid, "uuid": uuid, "tentativas": tentativas, "erro": str(e)[:160],
                                "categoria": "Não foi possível consultar na RD", "canal": None, "online": False,
                                "detalhe": f"A RD não respondeu por esse contato ({str(e)[:80]}).",
                                "identificador": None, "data": None, "conversoes": 0}
                    conversoes = [
                        {"identificador": e.get("event_identifier"), "data": e.get("event_timestamp"),
                         "traffic_source": (e.get("payload") or {}).get("traffic_source")}
                        for e in (eventos if isinstance(eventos, list) else [])
                    ]
                    email = clean_email((leads.get(lid) or {}).get("email"))
                    return {"idlead": lid, "uuid": uuid, "conversoes": len(conversoes),
                            **classificar_conversoes(conversoes, email, emails_meta)}

                with ThreadPoolExecutor(PARALELAS) as pool:
                    for registro in pool.map(consultar, lote):
                        if registro:
                            anteriores[registro["idlead"]] = registro
        except Exception as e:  # noqa: BLE001
            return list(anteriores.values()), build_status(
                "rd_station", "erro", len(anteriores), f"Falha ao buscar a origem dos leads na RD: {e}"
            )

    recuperados = sum(1 for r in anteriores.values() if r.get("canal"))
    restantes = max(len(pendentes) - len(lote), 0)
    mensagem = f"{recuperados} de {len(anteriores)} lead(s) sem origem no CV tiveram a origem recuperada na RD."
    if restantes:
        mensagem += f" {restantes} na fila para as próximas atualizações (até {POR_RODADA} por rodada)."
    return list(anteriores.values()), build_status("rd_station", "real", len(anteriores), mensagem)


# ---------------------------------------------------------------------------
# Uso pelo resto do sistema
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {"chave": None, "mapa": {}}


def versao() -> str:
    base = bases.carregar("origem_rd") or {}
    return f"{base.get('atualizado_em')}|{base.get('total')}"


def por_lead() -> Dict[str, Dict[str, Any]]:
    """{idlead: origem descoberta na RD} — só os leads em que a RD respondeu alguma coisa."""
    chave = versao()
    if _cache["chave"] != chave:
        _cache.update(chave=chave, mapa={str(r["idlead"]): r for r in bases.registros("origem_rd") if r.get("idlead")})
    return _cache["mapa"]


def aplicar(classificacao: Classificacao, idlead: Any) -> Classificacao:
    """Troca 'Sem origem registrada' pela origem que a RD mostrou. Sem resposta útil, nada muda."""
    if classificacao.canal != "nao_rastreado":
        return classificacao
    origem = por_lead().get(str(idlead))
    if not origem or not origem.get("canal"):
        return classificacao
    canal = origem["canal"]
    label, grupo = CANAIS[canal]
    return replace(
        classificacao,
        canal=canal,
        canal_label=label,
        grupo=grupo,
        grupo_label=GRUPOS[grupo],
        online=grupo in GRUPOS_ONLINE,
        confianca="media",
        evidencia=f"Origem descoberta na RD Station — {origem['detalhe']}",
    )


def resumo() -> Dict[str, Any]:
    """Quantos leads sem origem no CV já foram consultados e no que deu."""
    consultados = por_lead()
    registros = list(consultados.values())
    contagem: Dict[str, int] = {}
    for r in registros:
        contagem[r["categoria"]] = contagem.get(r["categoria"], 0) + 1
    return {
        "consultados": len(registros),
        "recuperados": sum(1 for r in registros if r.get("canal")),
        "pendentes": sum(1 for lid in alvos() if _na_fila(lid, consultados)),
        "por_categoria": dict(sorted(contagem.items(), key=lambda kv: -kv[1])),
    }
