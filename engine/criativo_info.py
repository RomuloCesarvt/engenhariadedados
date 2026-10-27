"""
O que cada anúncio da Meta realmente é: formato (vídeo, imagem, carrossel), a peça (vídeo/imagem) e os textos.

O nome do anúncio é escrito pela agência e nem sempre diz o formato; aqui o formato vem do próprio criativo na API da Meta.
A mesma peça copiada para outra campanha ou conjunto gera outro `anuncio_id`, mas tem o mesmo vídeo ou a mesma imagem:
a `chave_peca` junta essas cópias, e é por ela que se conta quantos criativos existem de fato.

Guardado em `output/bases/meta_criativos.json`: {"<anuncio_id>": {"formato", "chave_peca", "video_ids", "imagens", "titulos", "corpos", "lido_em"}}.
Correções manuais em `output/bases/criativos_rotulos.json`: {"<chave_peca ou nome do anúncio, minúsculo>": {"formato": "...", "tema": "..."}}.
"""

import json
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional

from engine import bases, bi
from engine.textos_anuncios import _textos_do_criativo

ARQUIVO = os.path.join(bases.BASES_DIR, "meta_criativos.json")
ROTULOS = os.path.join(bases.BASES_DIR, "criativos_rotulos.json")
CAMPOS = ("id,creative{id,video_id,image_hash,image_url,object_type,title,body,instagram_permalink_url,"
          "object_story_spec{video_data{video_id,image_hash},link_data{image_hash,child_attachments{video_id,image_hash}}},"
          "asset_feed_spec{images{hash},videos{video_id},titles,bodies,ad_formats}}")


def _ler(caminho: str) -> Dict[str, Any]:
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def lido() -> Dict[str, Dict[str, Any]]:
    return _ler(ARQUIVO)


def rotulos() -> Dict[str, Dict[str, str]]:
    return {str(k).strip().lower(): v for k, v in _ler(ROTULOS).items()}


def _descrever(ad: Dict[str, Any]) -> Dict[str, Any]:
    cr = ad.get("creative") or {}
    oss = cr.get("object_story_spec") or {}
    ld, vd = oss.get("link_data") or {}, oss.get("video_data") or {}
    afs = cr.get("asset_feed_spec") or {}
    filhos = ld.get("child_attachments") or []
    videos = [v for v in [cr.get("video_id"), vd.get("video_id")] + [a.get("video_id") for a in afs.get("videos") or []]
              + [c.get("video_id") for c in filhos] if v]
    imagens = [h for h in [cr.get("image_hash"), vd.get("image_hash"), ld.get("image_hash")] + [a.get("hash") for a in afs.get("images") or []]
               + [c.get("image_hash") for c in filhos] if h]
    videos, imagens = sorted(set(map(str, videos))), sorted(set(map(str, imagens)))
    ad_formats = set(afs.get("ad_formats") or [])
    tipo = str(cr.get("object_type") or "").upper()
    # Ordem: o que a Meta declara (carrossel / formato do anúncio / tipo do objeto) e depois as peças. Vídeo com imagem de capa continua sendo vídeo.
    if len(filhos) > 1 or "CAROUSEL" in ad_formats:
        formato = "Carrossel"
    elif {"SINGLE_VIDEO", "SINGLE_IMAGE"} <= ad_formats:
        formato = "Imagem e vídeo"
    elif "SINGLE_VIDEO" in ad_formats or tipo == "VIDEO" or videos:
        formato = "Vídeo"
    elif "SINGLE_IMAGE" in ad_formats or tipo == "PHOTO" or imagens or cr.get("image_url"):
        formato = "Imagem"
    else:
        formato = None      # anúncio feito de uma publicação já existente: a Meta não expõe o formato; quem usa cai no nome
    # A peça: o vídeo (ou os vídeos) se houver; senão as imagens. A capa de um vídeo não conta como peça de imagem.
    permalink = cr.get("instagram_permalink_url")
    chave = ("v:" + "+".join(videos) if videos else "i:" + "+".join(imagens) if imagens
             else f"p:{permalink}" if permalink else f"c:{cr.get('id')}" if cr.get("id") else None)
    return {"formato": formato, "chave_peca": chave, "video_ids": videos, "imagens": imagens, **_textos_do_criativo(ad)}


_cache_criados: Dict[str, Any] = {}
STATUS_NO_AR = {"ACTIVE", "IN_PROCESS", "PENDING_REVIEW", "WITH_ISSUES"}


def criados_desde(desde: date) -> List[Dict[str, Any]]:
    """
    Anúncios criados na Meta desde `desde` que estão no ar, mesmo os que ainda não gastaram nada (por isso não existem na base de gasto).
    Devolve [{"anuncio_id", "nome", "conta_id", "conta_nome", "criado": "AAAA-MM-DD"}]. Guardado em memória por 30 minutos.
    """
    em_cache = _cache_criados.get(desde.isoformat())
    if em_cache and time.time() - em_cache[0] < 1800:
        return em_cache[1]
    from engine.criativos import _Meta

    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        return []
    meta = _Meta(token)
    contas = {r["conta_id"]: r.get("conta_nome") for r in bases.registros("meta_anuncios") if r.get("conta_id")}
    corte = int(time.mktime((desde.year, desde.month, desde.day, 0, 0, 0, 0, 0, -1)))
    filtro = json.dumps([{"field": "created_time", "operator": "GREATER_THAN", "value": corte}])
    saida: List[Dict[str, Any]] = []
    for conta_id, conta_nome in contas.items():
        depois = None
        for _ in range(20):                     # no máximo 20 páginas por conta
            params: Dict[str, Any] = {"fields": "name,created_time,effective_status", "limit": 200, "filtering": filtro}
            if depois:
                params["after"] = depois
            try:
                d = meta.get(f"{conta_id}/ads", **params)
            except RuntimeError:
                break
            for a in d.get("data") or []:
                if a.get("effective_status") in STATUS_NO_AR and str(a.get("created_time") or "")[:10] >= desde.isoformat():
                    saida.append({"anuncio_id": str(a["id"]), "nome": a.get("name") or "", "conta_id": conta_id, "conta_nome": conta_nome,
                                  "criado": str(a["created_time"])[:10]})
            paging = d.get("paging") or {}
            depois = (paging.get("cursors") or {}).get("after") if paging.get("next") else None
            if not depois:
                break
    _cache_criados[desde.isoformat()] = (time.time(), saida)
    return saida


def atualizar(desde: date = date(2026, 8, 1), limite: int = 500) -> Dict[str, int]:
    """Lê na Meta os criativos dos anúncios com investimento desde `desde` que ainda não estão guardados."""
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
            ad = meta.get(anuncio_id, fields=CAMPOS)
        except RuntimeError:
            erros += 1
            continue
        guardados[anuncio_id] = {**_descrever(ad), "lido_em": date.today().isoformat()}
        time.sleep(0.15)
    os.makedirs(bases.BASES_DIR, exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(guardados, f, ensure_ascii=False)
    return {"guardados": len(guardados), "novos": len(faltam) - erros, "erros": erros}
