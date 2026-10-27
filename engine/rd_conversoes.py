"""
Como cada contato da RD Station que NÃO está no CV entrou na RD.

A RD guarda muito mais que leads: listas de compradores, bases importadas para
comunicados, disparos de WhatsApp. Esses contatos nunca deveriam ir para o CV, então
contar "contato da RD fora do CV" como lead perdido seria um alarme falso. A primeira
conversão de cada contato separa o que é lead de verdade (formulário, landing page,
atendimento) do que é base importada.

Consultar a conversão custa uma chamada por contato; por isso o resultado fica guardado
na base "rd_conversoes" e cada atualização classifica só os contatos ainda não vistos.
"""

import os
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Tuple

from engine import bases
from engine.config import SourceStatus
from engine.integrations import build_status

POR_RODADA = int(os.getenv("RD_CONVERSOES_POR_RODADA", "1500"))

TIPOS_ENTRADA = {
    "inbound": "Formulário, landing page ou atendimento",
    "importacao": "Lista ou base importada",
    "disparo": "Disparo de campanha (WhatsApp / e-mail)",
    "cadastro_manual": "Cadastro manual (painel)",
    "sem_conversao": "Sem conversão registrada",
    "outro": "Outra entrada",
}

_IMPORTACAO = (
    "lista", "planilha", "importa", "base ", "base_", "base-", "clientes ativos", "compradores",
    "pesquisa", "comunicado", "limpeza", "leads qualificados", "reservas ",
)
_DISPARO = ("disparo", "campaign | whatsapp", "newsletter", "email marketing", "e-mail marketing")
_INBOUND = ("lp", "landing", "site", "fale-conosco", "zapier", "meta_ads", "m.i.a", "blip", "whatsapp", "lancamento")


def _limpo(texto: Any) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower().strip()


def tipo_de_entrada(identificador: Any) -> str:
    """Classifica o identificador da primeira conversão do contato na RD."""
    t = _limpo(identificador)
    if not t:
        return "sem_conversao"
    if "painel" in t:
        return "cadastro_manual"
    if any(p in t for p in _DISPARO):
        return "disparo"
    if t.startswith("base") or any(p in t for p in _IMPORTACAO):
        return "importacao"
    if t.startswith(("fmd_", "form", "/")) or any(p in t for p in _INBOUND):
        return "inbound"
    return "outro"


def contatos_fora_do_cv() -> List[Dict[str, Any]]:
    """Contatos da base da RD que não aparecem no CV (todos os leads) nem pelo UUID nem pelo e-mail."""
    from engine import identidade

    idx = identidade.indice()
    uuids_cv, emails_cv = idx.valores("uuid"), idx.valores("email")
    return [
        l for l in bases.registros("rd_leads")
        if l.get("integration_id") not in uuids_cv and l.get("email_clean") not in emails_cv
    ]


def baixar(inicio: datetime, fim: datetime) -> Tuple[List[Dict[str, Any]], SourceStatus]:
    """Classifica os contatos fora do CV ainda não vistos e devolve o acumulado."""
    anteriores = {r["uuid"]: r for r in bases.registros("rd_conversoes") if r.get("uuid")}
    pendentes = [l for l in contatos_fora_do_cv() if l.get("integration_id") and l["integration_id"] not in anteriores]
    lote = pendentes[:POR_RODADA]

    if lote:
        import httpx
        from engine.extractors.rd_station import API, RDStationExtractor

        ex = RDStationExtractor()
        try:
            with httpx.Client(timeout=30) as client:
                token = ex._access_token(client)
                for contato in lote:
                    uuid = contato["integration_id"]
                    try:
                        eventos = ex._get(client, f"{API}/platform/contacts/{uuid}/events", token, {"event_type": "CONVERSION"})
                    except PermissionError:
                        raise
                    except Exception:
                        continue  # fica pendente para a próxima rodada
                    eventos = eventos if isinstance(eventos, list) else []
                    primeiro = min(eventos, key=lambda e: str(e.get("event_timestamp"))) if eventos else None
                    identificador = primeiro.get("event_identifier") if primeiro else None
                    anteriores[uuid] = {
                        "uuid": uuid,
                        "primeira_conversao": identificador,
                        "data_primeira_conversao": primeiro.get("event_timestamp") if primeiro else None,
                        "conversoes": len(eventos),
                        "tipo": tipo_de_entrada(identificador),
                    }
        except Exception as e:
            return list(anteriores.values()), build_status(
                "rd_station", "erro", len(anteriores), f"Falha ao classificar contatos da RD: {e}"
            )

    restantes = max(len(pendentes) - len(lote), 0)
    mensagem = f"{len(anteriores)} contato(s) da RD fora do CV classificados pela primeira conversão."
    if restantes:
        mensagem += f" {restantes} na fila para as próximas atualizações (até {POR_RODADA} por rodada)."
    return list(anteriores.values()), build_status("rd_station", "real", len(anteriores), mensagem)
