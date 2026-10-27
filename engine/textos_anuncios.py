"""
Títulos e textos dos anúncios da Meta, para ligar o lead de clique no WhatsApp ao anúncio.

O CV registra a conversão desse lead assim: "Click To WhatsApp | Facebook Ads | <título que o lead viu> | M.I.A". Não há UTM,
mas o título do criativo identifica o anúncio (os anúncios dinâmicos têm um conjunto próprio de títulos). Os textos vêm da
API da Meta e ficam em `output/bases/meta_textos_anuncios.json`; só anúncios novos são lidos de novo.

Formato guardado: {"<anuncio_id>": {"titulos": [...], "corpos": [...], "lido_em": "2026-10-19"}}
"""

import json
import os
import re
from collections import defaultdict
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

from engine import bases, bi

ARQUIVO = os.path.join(bases.BASES_DIR, "meta_textos_anuncios.json")
MIDIAS = {"facebook ads", "instagram ads", "click to whatsapp", "meta ads", "facebook", "instagram", "m.i.a", ""}


def normalizar(texto: Any) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip().lower().rstrip("*").strip()


def lido() -> Dict[str, Dict[str, Any]]:
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _textos_do_criativo(ad: Dict[str, Any]) -> Dict[str, List[str]]:
    cr = ad.get("creative") or {}
    oss = cr.get("object_story_spec") or {}
    ld, vd = oss.get("link_data") or {}, oss.get("video_data") or {}
    afs = cr.get("asset_feed_spec") or {}
    titulos = [cr.get("title"), ld.get("name"), vd.get("title")] + [t.get("text") for t in afs.get("titles") or []]
    corpos = [cr.get("body"), ld.get("message"), vd.get("message")] + [t.get("text") for t in afs.get("bodies") or []]
    limpa = lambda xs: sorted({str(x).strip() for x in xs if x and str(x).strip()})
    return {"titulos": limpa(titulos), "corpos": limpa(corpos)}


def atualizar(desde: date = date(2026, 8, 1), limite: int = 400) -> Dict[str, int]:
    """Lê na Meta os textos dos anúncios com investimento desde `desde` que ainda não estão no arquivo."""
    from engine.criativos import _Meta

    token = os.getenv("META_ACCESS_TOKEN")
    guardados = lido()
    ids = {
        str(r["anuncio_id"]) for r in bases.registros("meta_anuncios")
        if r.get("anuncio_id") and (r.get("investimento") or 0) > 0 and (bi._data(r.get("data")) or date.min) >= desde
    }
    faltam = sorted(ids - set(guardados))[:limite]
    if not token or not faltam:
        return {"guardados": len(guardados), "novos": 0, "erros": 0}
    meta = _Meta(token)
    erros = 0
    for anuncio_id in faltam:
        try:
            ad = meta.get(anuncio_id, fields="id,creative{title,body,object_story_spec,asset_feed_spec}")
        except RuntimeError:
            erros += 1
            continue
        guardados[anuncio_id] = {**_textos_do_criativo(ad), "lido_em": date.today().isoformat()}
    os.makedirs(bases.BASES_DIR, exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(guardados, f, ensure_ascii=False)
    return {"guardados": len(guardados), "novos": len(faltam) - erros, "erros": erros}


def indice_de_titulos() -> Dict[str, Set[str]]:
    """título (ou texto) normalizado -> ids dos anúncios que o usam."""
    indice: Dict[str, Set[str]] = defaultdict(set)
    for anuncio_id, x in lido().items():
        for t in (x.get("titulos") or []) + (x.get("corpos") or []):
            if normalizar(t):
                indice[normalizar(t)].add(anuncio_id)
    return indice


def titulo_da_conversao(conversao: Any) -> Optional[str]:
    """'Click To WhatsApp | Facebook Ads | Entrega prevista... | M.I.A' -> 'Entrega prevista...' (sem o título devolve None)."""
    partes = [p.strip() for p in str(conversao or "").split(" | ")]
    if len(partes) < 3:
        return None
    candidato = partes[2]
    return None if normalizar(candidato) in MIDIAS else candidato


def conversoes_por_lead(ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    alvo = set(ids)
    saida: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in bases.registros("cv_conversoes"):
        if str(c.get("idlead")) in alvo:
            saida[str(c["idlead"])].append(c)
    return saida
