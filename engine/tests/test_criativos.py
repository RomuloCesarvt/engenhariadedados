"""
Testes do criativo dos anúncios (sem chamar a Meta).
"""

from engine import criativos


def test_formato_pela_proporcao_da_peca():
    assert criativos.formato_da_imagem(1080, 1920) == "Stories e Reels (9:16)"
    assert criativos.formato_da_imagem(1080, 1350) == "Feed vertical (4:5)"
    assert criativos.formato_da_imagem(1080, 1080) == "Feed quadrado (1:1)"
    assert criativos.formato_da_imagem(1080, 565) == "Link / coluna (1,91:1)"
    assert criativos.formato_da_imagem(None, 100) == "Tamanho desconhecido"


def test_posicionamentos_legiveis():
    spec = {"publisher_platforms": ["instagram", "facebook"], "instagram_positions": ["story", "reels"],
            "facebook_positions": ["story", "facebook_reels"]}
    assert criativos.posicionamentos(spec) == "Instagram: reels, stories · Facebook: reels, stories"


def test_criativo_monta_previews_imagens_videos_e_textos(monkeypatch):
    respostas = {
        "123": {"id": "123", "name": "video-a", "account_id": "999", "effective_status": "ACTIVE", "creative": {
            "effective_object_story_id": "10_20",
            "asset_feed_spec": {
                "images": [{"hash": "h1", "adlabels": [{"id": "L1"}]}, {"hash": "h2"}],
                "videos": [{"video_id": "555"}],
                "titles": [{"text": "Seu terreno"}], "bodies": [{"text": "Saia do aluguel"}, {"text": "Saia do aluguel"}],
                "asset_customization_rules": [{"customization_spec": {"publisher_platforms": ["instagram"], "instagram_positions": ["story"]},
                                               "image_label": {"id": "L1"}}],
            },
        }},
        "act_999/adimages": {"data": [{"hash": "h1", "url": "https://img/1", "width": 1080, "height": 1920},
                                      {"hash": "h2", "url": "https://img/2", "width": 1080, "height": 1080}]},
        "555": {"picture": "https://capa", "permalink_url": "/reel/555", "length": 30.2,
                "embed_html": '<iframe src="https://www.facebook.com/plugins/video.php?href=x&amp;w=1080" width="1080"></iframe>',
                "format": [{"filter": "native", "width": 1080, "height": 1920}]},
        "123/previews": {"data": [{"body": '<iframe src="https://business.facebook.com/ads/api/preview_iframe.php?d=1&amp;t=2" width="335" height="450"></iframe>'}]},
    }

    class MetaFalsa:
        def __init__(self, token):
            self.client = type("C", (), {"close": lambda self: None})()

        def get(self, caminho, **params):
            if caminho == "123/previews" and params.get("ad_format") != "MOBILE_FEED_STANDARD":
                raise RuntimeError("formato não suportado")
            return respostas[caminho]

    monkeypatch.setenv("META_ACCESS_TOKEN", "t")
    monkeypatch.setattr(criativos, "_Meta", MetaFalsa)
    criativos._cache.clear()

    r = criativos.criativo("123")
    assert r["erro"] is None and r["tipo"] == "dinâmico"
    assert [p["rotulo"] for p in r["previews"]] == ["Feed do Facebook"]
    assert r["previews"][0]["src"] == "https://business.facebook.com/ads/api/preview_iframe.php?d=1&t=2"
    assert r["imagens"][0] == {"url": "https://img/1", "largura": 1080, "altura": 1920, "formato": "Stories e Reels (9:16)", "onde": "Instagram: stories"}
    assert r["imagens"][1]["formato"] == "Feed quadrado (1:1)" and r["imagens"][1]["onde"] is None
    assert r["videos"][0]["player"].startswith("https://www.facebook.com/plugins/video.php") and r["videos"][0]["duracao_s"] == 30
    assert r["videos"][0]["link"] == "https://www.facebook.com/reel/555"
    assert r["textos"]["textos"] == ["Saia do aluguel"] and r["links"][0]["url"] == "https://www.facebook.com/10_20"


def test_imagens_da_meta_saem_pelo_servidor_global(monkeypatch):
    monkeypatch.delenv("META_CDN_GLOBAL", raising=False)
    regional = "https://scontent.faqa2-1.fna.fbcdn.net/v/t45.1600-4/1_n.png?stp=dst&_nc_ht=scontent.faqa2-1.fna&oh=abc&oe=69"
    assert criativos.url_global_meta(regional) == "https://scontent.xx.fbcdn.net/v/t45.1600-4/1_n.png?stp=dst&_nc_ht=scontent.faqa2-1.fna&oh=abc&oe=69"
    assert criativos.url_global_meta("https://external.faqa2-1.fna.fbcdn.net/emg1/v/t13/1?url=x").startswith("https://external.xx.fbcdn.net/emg1/")
    assert criativos.url_global_meta("https://img.exemplo.com/a.png") == "https://img.exemplo.com/a.png"
    assert criativos.url_global_meta(None) is None
    monkeypatch.setenv("META_CDN_GLOBAL", "false")
    assert criativos.url_global_meta(regional) == regional


def _meta_falsa(respostas):
    class MetaFalsa:
        def __init__(self, token):
            self.client = type("C", (), {"close": lambda self: None})()

        def get(self, caminho, **params):
            if caminho not in respostas:
                raise RuntimeError("não encontrado")
            return respostas[caminho]

    return MetaFalsa


def test_capa_de_video_usa_a_capa_oficial_grande(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "t")
    monkeypatch.delenv("META_CDN_GLOBAL", raising=False)
    monkeypatch.setattr(criativos, "_Meta", _meta_falsa({
        "900": {"account_id": "1", "creative": {"id": "c9", "asset_feed_spec": {"videos": [{"video_id": "77"}]}}},
        "77": {"length": 30.4, "thumbnails": {"data": [
            {"uri": "https://scontent.faqa2-1.fna.fbcdn.net/v/pequena.jpg", "width": 130, "height": 130, "is_preferred": False},
            {"uri": "https://scontent.faqa2-1.fna.fbcdn.net/v/grande.jpg", "width": 1080, "height": 1920, "is_preferred": True},
        ]}},
    }))
    criativos._cache_capa.clear()
    c = criativos.capa("900")
    assert c == {"anuncio_id": "900", "url": "https://scontent.xx.fbcdn.net/v/grande.jpg", "largura": 1080, "altura": 1920,
                 "tipo": "video", "duracao_s": 30, "erro": None}


def test_capa_de_imagem_usa_a_imagem_original_e_cai_para_a_miniatura(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "t")
    monkeypatch.setattr(criativos, "_Meta", _meta_falsa({
        "901": {"account_id": "1", "creative": {"id": "c1", "image_hash": "h1"}},
        "act_1/adimages": {"data": [{"url": "https://img/original.jpg", "width": 1080, "height": 1080}]},
        "902": {"account_id": "1", "creative": {"id": "c2"}},
        "c2": {"thumbnail_url": "https://img/600.jpg"},
    }))
    criativos._cache_capa.clear()
    assert criativos.capa("901")["url"] == "https://img/original.jpg" and criativos.capa("901")["tipo"] == "imagem"
    reserva = criativos.capa("902")
    assert reserva["url"] == "https://img/600.jpg" and reserva["tipo"] == "imagem"
