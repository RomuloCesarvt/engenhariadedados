"""
Criativo de um anúncio da Meta, buscado na hora (os links da Meta expiram):

  - Pré-visualização oficial em cada formato (feed e stories do Facebook, feed, stories e reels do
    Instagram): o anúncio como o público viu, com o vídeo tocando.
  - Imagens em tamanho original, com o formato (9:16, 1:1, 4:5, 1,91:1) e os posicionamentos em
    que cada uma é usada nos anúncios dinâmicos.
  - Vídeos com o player da Meta.
  - Títulos e textos usados.
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import httpx

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
CACHE_SEGUNDOS = 30 * 60

FORMATOS_PREVIEW = [
    ("MOBILE_FEED_STANDARD", "Feed do Facebook"),
    ("INSTAGRAM_STANDARD", "Feed do Instagram"),
    ("INSTAGRAM_STORY", "Stories do Instagram"),
    ("INSTAGRAM_REELS", "Reels do Instagram"),
    ("FACEBOOK_STORY_MOBILE", "Stories do Facebook"),
]

POSICOES = {
    "feed": "feed", "story": "stories", "reels": "reels", "facebook_reels": "reels", "instream_video": "vídeo in-stream",
    "marketplace": "marketplace", "video_feeds": "feed de vídeos", "right_hand_column": "coluna da direita",
    "search": "busca", "explore": "explorar", "explore_home": "explorar", "profile_feed": "feed do perfil",
    "messenger_home": "Messenger", "classic": "nativo", "rewarded_video": "vídeo premiado", "ig_search": "busca",
    "instagram_explore_grid_home": "explorar", "facebook_reels_overlay": "reels", "profile_reels": "reels do perfil",
    "notification": "notificações", "status": "status",
}
PLATAFORMAS = {"facebook": "Facebook", "instagram": "Instagram", "audience_network": "Audience Network",
               "messenger": "Messenger", "whatsapp": "WhatsApp"}

_cache: Dict[str, Any] = {}

# A Meta devolve imagens em servidores regionais (ex.: scontent.faqa2-1.fna.fbcdn.net) que algumas redes
# não alcançam; o mesmo arquivo responde pelo servidor global (scontent.xx.fbcdn.net).
_CDN_REGIONAL = re.compile(r"^(https?://)(scontent|external|video)[\w.-]*\.fbcdn\.net/", re.I)


def url_global_meta(url: Optional[str]) -> Optional[str]:
    if not url or os.getenv("META_CDN_GLOBAL", "true").lower() == "false":
        return url
    return _CDN_REGIONAL.sub(lambda m: f"{m.group(1)}{m.group(2).lower()}.xx.fbcdn.net/", url, count=1)


def formato_da_imagem(largura: Optional[int], altura: Optional[int]) -> str:
    """Proporção da peça → formato em que ela aparece."""
    if not largura or not altura:
        return "Tamanho desconhecido"
    razao = altura / largura
    if razao >= 1.7:
        return "Stories e Reels (9:16)"
    if 1.15 <= razao < 1.7:
        return "Feed vertical (4:5)"
    if 0.9 <= razao < 1.15:
        return "Feed quadrado (1:1)"
    if razao <= 0.6:
        return "Link / coluna (1,91:1)"
    return f"{largura}×{altura}"


def posicionamentos(spec: Dict[str, Any]) -> str:
    """customization_spec da regra → 'Instagram: stories, reels · Facebook: stories'."""
    partes = []
    for plataforma in spec.get("publisher_platforms") or []:
        posicoes = spec.get(f"{plataforma}_positions") or []
        nome = PLATAFORMAS.get(plataforma, plataforma)
        rotulos = sorted({POSICOES.get(p, p.replace("_", " ")) for p in posicoes})
        partes.append(f"{nome}: {', '.join(rotulos)}" if rotulos else nome)
    return " · ".join(partes)


def _src(html: str) -> Optional[str]:
    achado = re.search(r'src="([^"]+)"', html or "")
    return achado.group(1).replace("&amp;", "&") if achado else None


def _dimensao(html: str, atributo: str) -> Optional[int]:
    achado = re.search(rf'{atributo}="(\d+)"', html or "")
    return int(achado.group(1)) if achado else None


class _Meta:
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://graph.facebook.com/{GRAPH_VERSION}"
        self.client = httpx.Client(timeout=45)

    def get(self, caminho: str, **params: Any) -> Dict[str, Any]:
        res = self.client.get(f"{self.base}/{caminho}", params={**params, "access_token": self.token})
        dados = res.json() if "json" in res.headers.get("content-type", "") else {}
        if res.status_code != 200:
            raise RuntimeError((dados.get("error") or {}).get("message") or f"HTTP {res.status_code}")
        return dados


def _conteudo_do_quadro(uri: str) -> Optional[float]:
    """Variação de cor do quadro (0 = cor lisa): o quadro de abertura dos vídeos da marca é só o fundo, com variação de 3 a 4; um quadro com conteúdo passa de 25."""
    try:
        import io

        from PIL import Image, ImageStat

        corpo = httpx.get(uri, timeout=30, follow_redirects=True).content
        imagem = Image.open(io.BytesIO(corpo)).convert("RGB").resize((96, 96))
        return sum(ImageStat.Stat(imagem).stddev) / 3
    except Exception:  # noqa: BLE001 — sem Pillow ou sem rede, fica a capa que a Meta marcou como preferida
        return None


def _quadro_com_conteudo(capas: List[Dict[str, Any]], preferida: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    A Meta marca como "preferida" o primeiro quadro do vídeo, que nos anúncios da Moura Leite é o fundo liso da abertura: o cartão do anúncio saía
    com um bloco verde ou roxo, igual em todos (e parecia ser de outra praça). Se o quadro preferido é liso, escolhe entre alguns quadros de
    dentro do vídeo (a 1/4, 1/3 e 1/2) o de maior variação de cor.
    """
    if not preferida or len(capas) < 4:
        return preferida
    nota = _conteudo_do_quadro(preferida.get("uri") or "")
    if nota is None or nota >= 20:
        return preferida
    posicoes = sorted({max(1, len(capas) // 4), max(1, len(capas) // 3), max(1, len(capas) // 2)})
    melhor, melhor_nota = preferida, nota
    for k in posicoes:
        n = _conteudo_do_quadro(capas[k].get("uri") or "")
        if n is not None and n > melhor_nota:
            melhor, melhor_nota = capas[k], n
    return melhor


_cache_capa: Dict[str, Any] = {}
CAPA_CACHE_SEGUNDOS = 6 * 3600


def capa(anuncio_id: str) -> Dict[str, Any]:
    """
    Imagem grande que representa o anúncio (para cards): a capa oficial do vídeo (1080px) ou a
    imagem original do anúncio (1080px); na falta das duas, a miniatura do criativo em 600px.
    A miniatura que vem na base de anúncios tem só 64×64 e fica borrada.
    """
    em_cache = _cache_capa.get(anuncio_id)
    if em_cache and time.time() - em_cache[0] < CAPA_CACHE_SEGUNDOS:
        return em_cache[1]
    resultado: Dict[str, Any] = {"anuncio_id": anuncio_id, "url": None, "largura": None, "altura": None,
                                 "tipo": None, "duracao_s": None, "erro": None}
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        return {**resultado, "erro": "META_ACCESS_TOKEN não configurado."}

    meta = _Meta(token)
    try:
        ad = meta.get(
            anuncio_id,
            fields="account_id,creative{id,video_id,image_hash,asset_feed_spec{images,videos},"
                   "object_story_spec{video_data{video_id,image_hash},link_data{image_hash}}}",
        )
        cr = ad.get("creative") or {}
        afs = cr.get("asset_feed_spec") or {}
        oss = cr.get("object_story_spec") or {}
        video_id = next((v for v in [a.get("video_id") for a in afs.get("videos") or []]
                         + [cr.get("video_id"), (oss.get("video_data") or {}).get("video_id")] if v), None)

        if video_id:
            try:
                video = meta.get(str(video_id), fields="thumbnails{uri,width,height,is_preferred},length")
                capas = (video.get("thumbnails") or {}).get("data") or []
                preferida = next((c for c in capas if c.get("is_preferred")), capas[0] if capas else None)
                preferida = _quadro_com_conteudo(capas, preferida)
                if preferida and preferida.get("uri"):
                    resultado.update(url=url_global_meta(preferida["uri"]), largura=preferida.get("width"),
                                     altura=preferida.get("height"), tipo="video", duracao_s=round(video.get("length") or 0))
            except RuntimeError:
                pass

        if not resultado["url"]:
            image_hash = next((h for h in [i.get("hash") for i in afs.get("images") or []]
                               + [cr.get("image_hash"), (oss.get("link_data") or {}).get("image_hash")] if h), None)
            if image_hash and ad.get("account_id"):
                try:
                    imagem = (meta.get(f"act_{ad['account_id']}/adimages", hashes=json.dumps([image_hash]),
                                       fields="url,width,height").get("data") or [{}])[0]
                except RuntimeError:
                    imagem = {}
                if imagem.get("url"):
                    resultado.update(url=url_global_meta(imagem["url"]), largura=imagem.get("width"),
                                     altura=imagem.get("height"), tipo="imagem")

        if not resultado["url"] and cr.get("id"):
            try:
                miniatura = meta.get(cr["id"], fields="thumbnail_url", thumbnail_width=600, thumbnail_height=600)
            except RuntimeError:
                miniatura = {}
            if miniatura.get("thumbnail_url"):
                resultado.update(url=url_global_meta(miniatura["thumbnail_url"]), tipo="video" if video_id else "imagem")
    except RuntimeError as e:
        resultado["erro"] = f"Não foi possível ler o anúncio na Meta: {e}"
    finally:
        meta.client.close()

    if resultado["url"]:
        _cache_capa[anuncio_id] = (time.time(), resultado)
    return resultado


def _preview(meta: _Meta, anuncio_id: str, formato: str, rotulo: str) -> Optional[Dict[str, Any]]:
    try:
        corpo = ((meta.get(f"{anuncio_id}/previews", ad_format=formato).get("data") or [{}])[0]).get("body") or ""
    except RuntimeError:
        return None  # formato não se aplica a este anúncio
    src = _src(corpo)
    if not src:
        return None
    return {"formato": formato, "rotulo": rotulo, "src": src,
            "largura": _dimensao(corpo, "width"), "altura": _dimensao(corpo, "height")}


def criativo(anuncio_id: str) -> Dict[str, Any]:
    em_cache = _cache.get(anuncio_id)
    if em_cache and time.time() - em_cache[0] < CACHE_SEGUNDOS:
        return em_cache[1]

    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        return {"anuncio_id": anuncio_id, "erro": "META_ACCESS_TOKEN não configurado."}
    meta = _Meta(token)
    try:
        ad = meta.get(
            anuncio_id,
            fields="id,name,account_id,effective_status,creative{id,title,body,thumbnail_url,image_url,image_hash,video_id,"
                   "object_type,object_story_spec,asset_feed_spec,effective_object_story_id,instagram_permalink_url}",
        )
    except RuntimeError as e:
        return {"anuncio_id": anuncio_id, "erro": f"Não foi possível ler o anúncio na Meta: {e}"}

    cr = ad.get("creative") or {}
    oss = cr.get("object_story_spec") or {}
    link_data = oss.get("link_data") or {}
    video_data = oss.get("video_data") or {}
    afs = cr.get("asset_feed_spec") or {}

    # Regras de posicionamento dos anúncios dinâmicos: rótulo da imagem/vídeo → onde aparece
    onde_por_rotulo: Dict[str, str] = {}
    for regra in afs.get("asset_customization_rules") or []:
        onde = posicionamentos(regra.get("customization_spec") or {})
        for chave in ("image_label", "video_label"):
            rotulo = regra.get(chave) or {}
            if rotulo.get("id"):
                onde_por_rotulo[str(rotulo["id"])] = onde

    def onde(ativo: Dict[str, Any]) -> Optional[str]:
        locais = {onde_por_rotulo[str(l.get("id"))] for l in ativo.get("adlabels") or [] if str(l.get("id")) in onde_por_rotulo}
        return " | ".join(sorted(locais)) or None

    # Imagens
    ativos_imagem = list(afs.get("images") or [])
    for h in [cr.get("image_hash"), link_data.get("image_hash")] + [c.get("image_hash") for c in link_data.get("child_attachments") or []]:
        if h and h not in {a.get("hash") for a in ativos_imagem}:
            ativos_imagem.append({"hash": h})
    imagens: List[Dict[str, Any]] = []
    hashes = [a["hash"] for a in ativos_imagem if a.get("hash")]
    if hashes and ad.get("account_id"):
        try:
            por_hash = {
                i["hash"]: i for i in meta.get(f"act_{ad['account_id']}/adimages", hashes=json.dumps(hashes), fields="hash,url,width,height").get("data", [])
            }
        except RuntimeError:
            por_hash = {}
        for ativo in ativos_imagem:
            info = por_hash.get(ativo.get("hash"))
            if info and info.get("url"):
                imagens.append({"url": url_global_meta(info["url"]), "largura": info.get("width"), "altura": info.get("height"),
                                "formato": formato_da_imagem(info.get("width"), info.get("height")), "onde": onde(ativo)})
    if not imagens and (cr.get("image_url") or cr.get("thumbnail_url")):
        imagens.append({"url": url_global_meta(cr.get("image_url") or cr.get("thumbnail_url")), "largura": None, "altura": None,
                        "formato": "Miniatura", "onde": None})

    # Vídeos
    ativos_video = list(afs.get("videos") or [])
    for v in (cr.get("video_id"), video_data.get("video_id")):
        if v and v not in {a.get("video_id") for a in ativos_video}:
            ativos_video.append({"video_id": v})
    videos: List[Dict[str, Any]] = []
    for ativo in ativos_video:
        try:
            v = meta.get(str(ativo["video_id"]), fields="picture,permalink_url,length,embed_html,format")
        except RuntimeError:
            continue
        nativo = next((f for f in v.get("format") or [] if f.get("filter") == "native"), None) or {}
        videos.append({
            "video_id": str(ativo["video_id"]),
            "player": _src(v.get("embed_html") or nativo.get("embed_html") or ""),
            "capa": url_global_meta(v.get("picture")),
            "duracao_s": round(v.get("length") or 0),
            "largura": nativo.get("width"),
            "altura": nativo.get("height"),
            "formato": formato_da_imagem(nativo.get("width"), nativo.get("height")),
            "onde": onde(ativo),
            "link": f"https://www.facebook.com{v['permalink_url']}" if str(v.get("permalink_url") or "").startswith("/") else v.get("permalink_url"),
        })

    # Pré-visualizações por formato (em paralelo)
    with ThreadPoolExecutor(max_workers=len(FORMATOS_PREVIEW)) as pool:
        previews = [p for p in pool.map(lambda f: _preview(meta, anuncio_id, *f), FORMATOS_PREVIEW) if p]
    meta.client.close()

    textos = {
        "titulos": [t.get("text") for t in afs.get("titles") or [] if t.get("text")] or [x for x in (cr.get("title"), link_data.get("name")) if x],
        "textos": [t.get("text") for t in afs.get("bodies") or [] if t.get("text")] or [x for x in (cr.get("body"), link_data.get("message"), video_data.get("message")) if x],
        "descricoes": [t.get("text") for t in afs.get("descriptions") or [] if t.get("text")],
    }
    story = cr.get("effective_object_story_id")
    resultado = {
        "anuncio_id": anuncio_id,
        "nome": ad.get("name"),
        "status": ad.get("effective_status"),
        "tipo": "dinâmico" if afs else ("vídeo" if videos else "imagem"),
        "previews": previews,
        "imagens": imagens,
        "videos": videos,
        "textos": {k: list(dict.fromkeys(v)) for k, v in textos.items()},
        "links": [l for l in (
            {"label": "Publicação no Facebook", "url": f"https://www.facebook.com/{story}"} if story else None,
            {"label": "Publicação no Instagram", "url": cr["instagram_permalink_url"]} if cr.get("instagram_permalink_url") else None,
        ) if l],
        "erro": None,
    }
    _cache[anuncio_id] = (time.time(), resultado)
    return resultado
