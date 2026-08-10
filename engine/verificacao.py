"""
Verificação ao vivo de um lead no CV e no RD Station: a prova de que o lead não integrou.

Consulta as APIs na hora, e não as bases salvas. No CV a busca vale para todos os leads,
de qualquer data de cadastro; no RD, para todos os contatos da conta.

As conferências usam esta verificação como última barreira: nenhum lead é mostrado como
"não chegou no CV" sem ter sido confirmado aqui. Os resultados ficam em cache em disco.
"""

import json
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from engine import bases
from engine.extractors.cv_crm import CVCRMExtractor
from engine.extractors.rd_station import API as RD_API, RDStationExtractor
from engine.normalizer import clean_email

RD_PERFIL_URL = "https://app.rdstation.com.br/leads/public/{uuid}"
CACHE_PATH = os.path.join(bases.BASES_DIR, "verificacoes_ao_vivo.json")
# "Não existe no CV" vale por pouco tempo: o lead pode entrar a qualquer momento
VALIDADE_NAO_ENCONTRADO_HORAS = float(os.getenv("VERIFICACAO_VALIDADE_HORAS", "6"))
CONSULTAS_SIMULTANEAS = 3

_token_rd: Dict[str, Any] = {"valor": None, "expira": 0.0}


def rd_perfil_url(uuid: Optional[str]) -> Optional[str]:
    return RD_PERFIL_URL.format(uuid=uuid) if uuid else None


def cv_busca_url() -> Optional[str]:
    """Tela de leads do CV, onde a equipe cola o e-mail ou telefone para procurar."""
    base = (os.getenv("CV_CRM_URL") or "").rstrip("/")
    return f"{base}/gestor/comercial/leads" if base else None


def _fone8(valor: Any) -> Optional[str]:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-8:] if len(digitos) >= 8 else None


def variantes_telefone(telefone: Any) -> List[str]:
    """
    DDD + número, só dígitos (é assim que a API do CV filtra), com e sem o nono dígito:
    "+55 14 99638-2351" -> ["14996382351", "1496382351"].
    """
    d = re.sub(r"\D", "", str(telefone or ""))
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    elif len(d) in (11, 12) and d.startswith("0"):
        d = d[1:]  # prefixo de longa distância: "015 99839-3926"
    if len(d) == 11 and d[2] == "9":
        return [d, d[:2] + d[3:]]
    if len(d) == 10:
        return [d, d[:2] + "9" + d[2:]]
    return [d] if len(d) >= 8 else []


def mesma_pessoa(lead_cv: Dict[str, Any], email: Optional[str], telefone: Optional[str]) -> bool:
    """A API filtra de forma ampla: só vale o lead cujo e-mail ou telefone batem de verdade."""
    alvo_email, alvo_fone = clean_email(email), _fone8(telefone)
    return bool(
        (alvo_email and clean_email(lead_cv.get("email")) == alvo_email)
        or (alvo_fone and _fone8(lead_cv.get("telefone")) == alvo_fone)
    )


def _resumo_lead_cv(lead: Dict[str, Any]) -> Dict[str, Any]:
    situacao = lead.get("situacao")
    empreendimentos = lead.get("empreendimento") or []
    return {
        "idlead": lead.get("idlead"),
        "link": lead.get("link_interesses") or lead.get("link_interacoes"),
        "data_cad": lead.get("data_cad"),
        "situacao": situacao.get("nome") if isinstance(situacao, dict) else situacao,
        "midia": lead.get("midia_principal"),
        "empreendimentos": [e.get("nome") for e in empreendimentos if isinstance(e, dict)],
    }


def _cv_nao_encontrado(res: Any) -> bool:
    if res.status_code != 400:
        return False
    try:
        mensagem = str((res.json() or {}).get("mensagem") or "")
    except ValueError:
        return False
    return "não encontrado" in mensagem.lower() or "nao encontrado" in mensagem.lower()


def verificar_no_cv(email: Optional[str], telefone: Optional[str]) -> Dict[str, Any]:
    cv = CVCRMExtractor()
    base = {"busca_url": cv_busca_url(), "consultas": [], "leads": [], "erros": []}
    if not (cv.api_url and cv.token):
        return {**base, "consultado": False, "encontrado": False, "erros": ["CV não configurado (CV_CRM_URL / CV_CRM_TOKEN)."]}

    buscas = []
    if clean_email(email):
        buscas.append(("e-mail", {"email": clean_email(email)}))
    buscas += [(f"telefone {v}", {"telefone": v}) for v in variantes_telefone(telefone)]

    encontrados: Dict[str, Dict[str, Any]] = {}
    with httpx.Client(timeout=30) as client:
        for rotulo, params in buscas:
            try:
                res = client.get(f"{cv.api_url}/api/cvio/lead", headers=cv._headers(), params={**params, "limit": 20})
                if _cv_nao_encontrado(res):
                    # A API do CV responde 400 "Lead não encontrado" quando a busca não acha ninguém
                    base["consultas"].append({"por": rotulo, "encontrados": 0})
                    continue
                if res.status_code != 200:
                    base["erros"].append(f"Busca por {rotulo}: HTTP {res.status_code}")
                    continue
                leads = [l for l in (res.json().get("leads") or []) if mesma_pessoa(l, email, telefone)]
                base["consultas"].append({"por": rotulo, "encontrados": len(leads)})
                for lead in leads:
                    encontrados[str(lead.get("idlead"))] = _resumo_lead_cv(lead)
            except Exception as e:  # rede, JSON inválido
                base["erros"].append(f"Busca por {rotulo}: {e}")

    # Só conclui "não existe" se TODAS as buscas responderam
    consultado = bool(buscas) and not base["erros"]
    return {**base, "consultado": consultado or bool(encontrados), "encontrado": bool(encontrados), "leads": list(encontrados.values())}


def verificar_no_rd(email: Optional[str]) -> Dict[str, Any]:
    rd = RDStationExtractor()
    if not (rd.client_id and rd.client_secret and rd.refresh_token):
        return {"consultado": False, "encontrado": False, "erro": "RD Station sem OAuth configurado."}
    alvo = clean_email(email)
    if not alvo:
        return {"consultado": False, "encontrado": False, "erro": "Lead sem e-mail: o RD só busca contato por e-mail."}
    try:
        with httpx.Client(timeout=30) as client:
            # Várias consultas seguidas: reaproveita o token por 50 minutos
            if not _token_rd["valor"] or time.time() > _token_rd["expira"]:
                _token_rd.update(valor=rd._access_token(client), expira=time.time() + 50 * 60)
            res = client.get(
                f"{RD_API}/platform/contacts/email:{urllib.parse.quote(alvo)}",
                headers={"Authorization": f"Bearer {_token_rd['valor']}"},
            )
        if res.status_code == 404:
            return {"consultado": True, "encontrado": False}
        if res.status_code == 401:
            _token_rd.update(valor=None)
        if res.status_code != 200:
            return {"consultado": False, "encontrado": False, "erro": f"HTTP {res.status_code}"}
        uuid = res.json().get("uuid")
        return {"consultado": True, "encontrado": True, "uuid": uuid, "link": rd_perfil_url(uuid)}
    except Exception as e:
        return {"consultado": False, "encontrado": False, "erro": str(e)}


# ---------------------------------------------------------------------------
# Cache em disco
# ---------------------------------------------------------------------------

_trava_cache = threading.Lock()
_cache: Dict[str, Any] = {"mtime": None, "dados": {}}


def chave_verificacao(email: Optional[str], telefone: Optional[str]) -> str:
    return f"{clean_email(email) or ''}|{_fone8(telefone) or ''}"


def _ler_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_PATH):
        return {}
    mtime = os.path.getmtime(CACHE_PATH)
    if _cache["mtime"] != mtime:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache.update(mtime=mtime, dados=json.load(f))
        except (OSError, ValueError):
            return _cache["dados"]
    return _cache["dados"]


def _gravar_no_cache(chave: str, resultado: Dict[str, Any]) -> None:
    with _trava_cache:
        dados = dict(_ler_cache())
        dados[chave] = resultado
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
        _cache.update(mtime=os.path.getmtime(CACHE_PATH), dados=dados)


def resultado_valido(email: Optional[str], telefone: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verificação guardada que ainda vale: "encontrado" vale sempre; "não existe", por poucas horas."""
    if not (clean_email(email) or _fone8(telefone)):
        return None
    r = _ler_cache().get(chave_verificacao(email, telefone))
    if not r or not r.get("cv", {}).get("consultado"):
        return None
    if r["cv"].get("encontrado"):
        return r
    idade_h = (datetime.now(timezone.utc) - datetime.fromisoformat(r["verificado_em"])).total_seconds() / 3600
    return r if idade_h < VALIDADE_NAO_ENCONTRADO_HORAS else None


def verificar_lead(email: Optional[str], telefone: Optional[str]) -> Dict[str, Any]:
    resultado = {
        "verificado_em": datetime.now(timezone.utc).isoformat(),
        "cv": verificar_no_cv(email, telefone),
        "rd": verificar_no_rd(email),
    }
    if resultado["cv"]["consultado"]:
        _gravar_no_cache(chave_verificacao(email, telefone), resultado)
    return resultado


# ---------------------------------------------------------------------------
# Confirmação em lote, em segundo plano
# ---------------------------------------------------------------------------

_trava_lote = threading.Lock()
_estado: Dict[str, Any] = {"em_andamento": False, "total": 0, "feitos": 0, "iniciado_em": None, "concluido_em": None}


def estado_confirmacao() -> Dict[str, Any]:
    return dict(_estado)


def iniciar_confirmacao(pedidos: List[Tuple[Optional[str], Optional[str]]]) -> Dict[str, Any]:
    """Confirma ao vivo os leads ainda sem verificação válida. Ignora se já houver um lote rodando."""
    unicos: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for email, telefone in pedidos:
        if (clean_email(email) or _fone8(telefone)) and not resultado_valido(email, telefone):
            unicos.setdefault(chave_verificacao(email, telefone), (email, telefone))
    if not unicos or not _trava_lote.acquire(blocking=False):
        return estado_confirmacao()

    def rodar():
        try:
            _estado.update(em_andamento=True, total=len(unicos), feitos=0,
                           iniciado_em=datetime.now(timezone.utc).isoformat(), concluido_em=None)

            def um(par):
                try:
                    verificar_lead(*par)
                finally:
                    _estado["feitos"] += 1

            with ThreadPoolExecutor(max_workers=CONSULTAS_SIMULTANEAS) as pool:
                list(pool.map(um, unicos.values()))
        finally:
            _estado.update(em_andamento=False, concluido_em=datetime.now(timezone.utc).isoformat())
            _trava_lote.release()

    threading.Thread(target=rodar, daemon=True, name="confirmacao-ao-vivo").start()
    return {**estado_confirmacao(), "em_andamento": True, "total": len(unicos)}
