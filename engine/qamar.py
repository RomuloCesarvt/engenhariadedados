"""
Relatório mensal da Qamar (agência de comunicação): redes sociais, site, blog, imprensa e tráfego pago.

Cada bloco do relatório sai da fonte oficial, sem digitação:
  - Instagram: Graph API da Meta (insights da conta, publicações, público). Stories só ficam disponíveis por 24 horas, então
    o sistema guarda um retrato a cada coleta (`qamar_stories.json`) e o bloco cresce a partir do dia em que a coleta começou.
  - Facebook: Graph API, mas só com a permissão `read_insights` no token. Sem ela o bloco diz o que falta.
  - Site: Google Analytics 4 (mesma conta de serviço do bloco de site do sistema).
  - Blog: lista pública de posts do site.
  - Tráfego pago: Meta Ads, conta "CA Moura Leite" (os impulsionamentos que a Qamar faz).
  - Imprensa e observações: texto digitado (não existe API), guardado em `qamar_manual.json`.
  - LinkedIn, TikTok e Google Meu Negócio: ainda sem conexão; o bloco traz o passo a passo para conectar.

Cada bloco devolve {"status": "real" | "parcial" | "nao_conectado" | "erro" | "manual", "mensagem": ..., ...dados}.
Um bloco que falha não derruba os outros.
"""

import html
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from concurrent.futures import ThreadPoolExecutor

import httpx

from engine import bases

GRAPH = f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION', 'v23.0')}"
IG_ID = os.getenv("QAMAR_INSTAGRAM_ID", "17841405780720722")  # @mouraleiteloteamentos
FB_PAGE_ID = os.getenv("QAMAR_FACEBOOK_PAGE_ID", "339732052772751")  # Moura Leite Loteamentos
CONTA_ANUNCIOS = os.getenv("QAMAR_META_ACCOUNT", "act_1229310424373738")  # CA Moura Leite
GA4_PROPRIEDADE = os.getenv("QAMAR_GA4_PROPERTY", "372419098")
BLOG_URL = os.getenv("QAMAR_BLOG_URL", "https://www.mouraleite.com.br/blog/")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
FUSO = timezone(timedelta(hours=-3))
ARQ_STORIES = "qamar_stories"
ARQ_RETRATOS = "qamar_retratos"
ARQ_MANUAL = "qamar_manual"

_cache: Dict[str, Tuple[float, Any]] = {}


# ---------------------------------------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------------------------------------

def _token() -> str:
    return os.getenv("META_ACCESS_TOKEN") or ""


def _g(caminho: str, token: Optional[str] = None, **params) -> Dict[str, Any]:
    """GET na Graph API, com uma nova tentativa quando a Meta responde erro passageiro."""
    for tentativa in range(3):
        r = httpx.get(f"{GRAPH}/{caminho}", params={**params, "access_token": token or _token()}, timeout=90).json()
        erro = r.get("error") if isinstance(r, dict) else None
        if erro and (erro.get("is_transient") or erro.get("code") in (1, 2)) and tentativa < 2:
            time.sleep(3)
            continue
        return r
    return r


def _com_cache(chave: str, ttl: int, fabrica: Callable[[], Any]) -> Any:
    agora = time.time()
    if chave in _cache and agora - _cache[chave][0] < ttl:
        return _cache[chave][1]
    valor = fabrica()
    _cache[chave] = (agora, valor)
    return valor


def _mes(mes: str) -> Tuple[date, date]:
    ano, m = int(mes[:4]), int(mes[5:7])
    ini = date(ano, m, 1)
    fim = (date(ano + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
    return ini, fim


def mes_anterior(mes: str) -> str:
    ini, _ = _mes(mes)
    ant = ini - timedelta(days=1)
    return f"{ant.year}-{ant.month:02d}"


def rotulo_mes(mes: str) -> str:
    return MESES[int(mes[5:7]) - 1].capitalize()


def _ts(d: date, fim_do_dia: bool = False) -> int:
    base = datetime(d.year, d.month, d.day, tzinfo=FUSO)
    return int((base + timedelta(days=1)).timestamp()) - 1 if fim_do_dia else int(base.timestamp())


def _janelas(ini: date, fim: date, dias: int = 30) -> List[Tuple[date, date]]:
    """A Graph API só aceita até 30 dias por consulta de insights."""
    saida, atual = [], ini
    while atual <= fim:
        ate = min(atual + timedelta(days=dias - 1), fim)
        saida.append((atual, ate))
        atual = ate + timedelta(days=1)
    return saida


def _variacao(atual: Optional[float], antes: Optional[float]) -> Optional[float]:
    if atual is None or antes in (None, 0):
        return None
    return round((atual - antes) / antes * 100, 1)


def _ler(chave: str, padrao: Any) -> Any:
    caminho = os.path.join(bases.BASES_DIR, f"{chave}.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def _gravar(chave: str, dados: Any) -> None:
    os.makedirs(bases.BASES_DIR, exist_ok=True)
    with open(os.path.join(bases.BASES_DIR, f"{chave}.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def _bloco(fn: Callable[..., Dict[str, Any]], *args) -> Dict[str, Any]:
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 — um bloco com problema não derruba o relatório
        return {"status": "erro", "mensagem": f"Não foi possível ler esta fonte: {e}"}


# ---------------------------------------------------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------------------------------------------------

METRICAS_CONTA = ["reach", "views", "total_interactions", "likes", "comments", "shares", "saves", "reposts", "replies",
                  "profile_views", "website_clicks", "accounts_engaged"]


def _ig_totais(ini: date, fim: date) -> Dict[str, Optional[float]]:
    """Totais do mês. Meses de 31 dias vão em duas consultas; o alcance (pessoas únicas) fica um pouco acima nesse caso."""
    def uma(metrica: str) -> Tuple[str, Optional[float]]:
        soma, achou = 0, False
        for a, b in _janelas(ini, fim):
            r = _g(f"{IG_ID}/insights", metric=metrica, metric_type="total_value", period="day", since=_ts(a), until=_ts(b, True))
            if r.get("data"):
                soma += r["data"][0]["total_value"]["value"]
                achou = True
        return metrica, (soma if achou else None)

    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(uma, METRICAS_CONTA))


def _ig_formatos(ini: date, fim: date) -> Dict[str, Dict[str, int]]:
    """Totais do mês por formato (STORY, REEL, POST, CAROUSEL_CONTAINER, AD), direto da conta: valem para qualquer mês passado."""
    def uma(metrica: str) -> Tuple[str, Dict[str, int]]:
        total: Dict[str, int] = {}
        for a, b in _janelas(ini, fim):
            r = _g(f"{IG_ID}/insights", metric=metrica, metric_type="total_value", period="day", breakdown="media_product_type", since=_ts(a), until=_ts(b, True))
            try:
                resultados = r["data"][0]["total_value"]["breakdowns"][0]["results"]
            except (KeyError, IndexError, TypeError):
                continue
            for x in resultados:
                chave = x["dimension_values"][0]
                total[chave] = total.get(chave, 0) + x["value"]
        return metrica, total

    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(pool.map(uma, ["views", "reach", "total_interactions", "shares", "likes"]))


def _ig_publicacoes(ini: date, fim: date, detalhar_insights: bool = True) -> List[Dict[str, Any]]:
    """Posts e reels do mês, cada um com o que o Instagram mediu."""
    itens: List[Dict[str, Any]] = []
    url = f"{IG_ID}/media"
    params: Dict[str, Any] = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count,thumbnail_url,media_url", "limit": 100}
    for _ in range(8):
        r = _g(url, **params)
        for m in r.get("data", []):
            dia = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).astimezone(FUSO).date()
            if ini <= dia <= fim:
                m["dia"] = dia.isoformat()
                itens.append(m)
        data = r.get("data", [])
        if not data or "next" not in (r.get("paging") or {}):
            break
        ultimo = datetime.fromisoformat(data[-1]["timestamp"].replace("Z", "+00:00")).astimezone(FUSO).date()
        if ultimo < ini:
            break
        url = r["paging"]["next"].replace(f"{GRAPH}/", "")
        params = {}
    def detalhar(m: Dict[str, Any]) -> None:
        tipo = "reel" if m.get("media_product_type") == "REELS" else "post"
        metricas = "reach,views,total_interactions,saved,shares,likes,comments" + (",ig_reels_avg_watch_time" if tipo == "reel" else "")
        r = _g(f"{m['id']}/insights", metric=metricas)
        valores = {x["name"]: x["values"][0]["value"] for x in r.get("data", [])} if r.get("data") else {}
        m.update(tipo=tipo, alcance=valores.get("reach"), visualizacoes=valores.get("views"), interacoes=valores.get("total_interactions"),
                 salvamentos=valores.get("saved"), compartilhamentos=valores.get("shares"), curtidas=valores.get("likes", m.get("like_count")),
                 comentarios=valores.get("comments", m.get("comments_count")), tempo_medio_ms=valores.get("ig_reels_avg_watch_time"))

    if not detalhar_insights:
        for m in itens:
            m["tipo"] = "reel" if m.get("media_product_type") == "REELS" else "post"
        return itens
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(detalhar, itens))
    return itens


PASTA_MIDIA = os.path.join(bases.BASES_DIR, "..", "qamar_midia")


def _baixar_imagem(url: Optional[str], nome: str) -> Optional[str]:
    """Guarda a imagem no disco; devolve o nome do arquivo (ou None se não deu)."""
    if not url:
        return None
    destino = os.path.join(PASTA_MIDIA, nome)
    if os.path.exists(destino):
        return nome
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            return None
        os.makedirs(PASTA_MIDIA, exist_ok=True)
        with open(destino, "wb") as f:
            f.write(r.content)
        return nome
    except Exception:  # noqa: BLE001
        return None


def coletar_stories() -> int:
    """Guarda os stories no ar agora, com a imagem (a API só os mostra por 24 horas). Roda a cada leitura do relatório e na coleta diária."""
    r = _g(f"{IG_ID}/stories", fields="id,timestamp,caption,permalink,media_type,media_url,thumbnail_url")
    guardados: Dict[str, Any] = _ler(ARQ_STORIES, {"inicio_da_coleta": date.today().isoformat(), "stories": {}})
    novos = 0
    for s in r.get("data", []):
        ins = _g(f"{s['id']}/insights", metric="reach,views,total_interactions,replies,shares")
        valores = {x["name"]: x["values"][0]["value"] for x in ins.get("data", [])} if ins.get("data") else {}
        antigo = guardados["stories"].get(s["id"])
        url_imagem = s.get("media_url") if s.get("media_type") == "IMAGE" else (s.get("thumbnail_url") or s.get("media_url"))
        arquivo = (antigo or {}).get("arquivo") or _baixar_imagem(url_imagem, f"story_{s['id']}.jpg")
        guardados["stories"][s["id"]] = {
            "id": s["id"], "timestamp": s["timestamp"], "permalink": s.get("permalink"), "titulo": (s.get("caption") or "").strip().split("\n")[0][:90],
            "miniatura": url_imagem, "arquivo": arquivo,
            "alcance": valores.get("reach"), "visualizacoes": valores.get("views"), "interacoes": valores.get("total_interactions"),
            "respostas": valores.get("replies"), "compartilhamentos": valores.get("shares"),
        }
        novos += 0 if antigo else 1
    _gravar(ARQ_STORIES, guardados)
    return novos


def _stories_do_mes(ini: date, fim: date) -> Dict[str, Any]:
    dados = _ler(ARQ_STORIES, {"inicio_da_coleta": None, "stories": {}})
    lista = []
    for s in dados["stories"].values():
        dia = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00").replace("+0000", "+00:00")).astimezone(FUSO).date()
        if ini <= dia <= fim:
            local = f"/api/qamar/midia/{s['arquivo']}" if s.get("arquivo") else None
            lista.append({**s, "dia": dia.isoformat(), "miniatura": local or s.get("miniatura")})
    inicio = dados.get("inicio_da_coleta")
    cobre = bool(inicio) and date.fromisoformat(inicio) <= ini
    return {"coletados": len(lista), "inicio_da_coleta": inicio, "cobre_o_mes_inteiro": cobre, "lista": lista}


def _ig_publico(total_seguidores: Optional[int] = None) -> Dict[str, Any]:
    saida: Dict[str, Any] = {}
    for quebra in ("age", "gender", "city"):
        r = _g(f"{IG_ID}/insights", metric="follower_demographics", period="lifetime", metric_type="total_value", breakdown=quebra)
        try:
            resultados = r["data"][0]["total_value"]["breakdowns"][0]["results"]
        except (KeyError, IndexError, TypeError):
            continue
        saida[quebra] = [(x["dimension_values"][0], x["value"]) for x in resultados]
    genero = {k: v for k, v in saida.get("gender", []) if k in ("F", "M")}
    total_g = sum(genero.values()) or 1
    faixas = sorted(saida.get("age", []), key=lambda kv: kv[0])
    total_f = sum(v for _, v in faixas) or 1
    cidades = sorted(saida.get("city", []), key=lambda kv: -kv[1])[:5]
    total_c = total_seguidores or sum(v for _, v in saida.get("city", [])) or 1
    return {
        "genero": [{"rotulo": "Mulheres", "pct": round(genero.get("F", 0) / total_g * 100, 1)}, {"rotulo": "Homens", "pct": round(genero.get("M", 0) / total_g * 100, 1)}],
        "faixas": [{"rotulo": k.replace("-", "–"), "pct": round(v / total_f * 100, 1)} for k, v in faixas],
        "cidades": [{"rotulo": k.split(",")[0], "pct": round(v / total_c * 100, 1)} for k, v in cidades],
    }


def _resumo_publicacoes(itens: List[Dict[str, Any]]) -> Dict[str, Any]:
    posts = [m for m in itens if m["tipo"] == "post"]
    reels = [m for m in itens if m["tipo"] == "reel"]
    soma = lambda lista, campo: sum(m.get(campo) or 0 for m in lista)
    media = lambda lista, campo: round(soma(lista, campo) / len(lista), 1) if lista else None
    engajamento = [m["interacoes"] / m["alcance"] * 100 for m in posts if m.get("alcance") and m.get("interacoes") is not None]
    return {
        "posts": {"quantidade": len(posts), "interacoes": soma(posts, "interacoes"), "media_interacoes": media(posts, "interacoes"),
                  "media_visualizacoes": media(posts, "visualizacoes"), "engajamento_medio": round(sum(engajamento) / len(engajamento), 2) if engajamento else None,
                  "comentarios": soma(posts, "comentarios"), "alcance": soma(posts, "alcance")},
        "reels": {"quantidade": len(reels), "visualizacoes": soma(reels, "visualizacoes"), "media_visualizacoes": media(reels, "visualizacoes"),
                  "interacoes": soma(reels, "interacoes"), "alcance": soma(reels, "alcance")},
    }


def _destaque(m: Dict[str, Any], rotulo: str) -> Dict[str, Any]:
    legenda = (m.get("caption") or "").strip().split("\n")[0]
    return {
        "rotulo": rotulo, "tipo": m["tipo"], "dia": m["dia"], "titulo": legenda[:90] or "(sem legenda)", "link": m.get("permalink"),
        "visualizacoes": m.get("visualizacoes"), "interacoes": m.get("interacoes"), "comentarios": m.get("comentarios"), "curtidas": m.get("curtidas"),
        "alcance": m.get("alcance"), "miniatura": m.get("thumbnail_url") or m.get("media_url"),
    }


def _instagram(mes: str, comparar: bool = False) -> Dict[str, Any]:
    if not _token():
        return {"status": "nao_conectado", "mensagem": "META_ACCESS_TOKEN não está no engine/.env."}
    ini, fim = _mes(mes)
    ant = mes_anterior(mes) if comparar else None
    atual = _ig_totais(ini, fim)
    antes = _ig_totais(*_mes(ant)) if ant else {}
    pub_a = _ig_publicacoes(ini, fim)
    pub_b = _ig_publicacoes(*_mes(ant)) if ant else []
    res_a = _resumo_publicacoes(pub_a)
    res_b = _resumo_publicacoes(pub_b) if ant else None
    fmt_a = _ig_formatos(ini, fim)
    fmt_b = _ig_formatos(*_mes(ant)) if ant else None
    seguidores = _seguidores_do_mes(mes, "instagram")

    def vistas(f, formato):
        if f is None:
            return None
        v = f.get("views", {})
        return (v.get("POST", 0) + v.get("CAROUSEL_CONTAINER", 0)) if formato == "posts" else v.get("REEL" if formato == "reels" else "STORY", 0)

    def linha(nome, chave, fmt="n"):
        return {"metrica": nome, "atual": atual.get(chave), "antes": antes.get(chave), "variacao": _variacao(atual.get(chave), antes.get(chave)), "fmt": fmt}

    def taxa(t):
        return round(t["total_interactions"] / t["reach"] * 100, 2) if t.get("reach") and t.get("total_interactions") is not None else None

    visao = [linha("Alcance (contas alcançadas)", "reach"), linha("Visualizações", "views"), linha("Interações", "total_interactions"),
             {"metrica": "Taxa de engajamento", "atual": taxa(atual), "antes": taxa(antes), "variacao": None, "fmt": "pct",
              "delta_pp": round(taxa(atual) - taxa(antes), 2) if taxa(atual) is not None and taxa(antes) is not None else None},
             {"metrica": "Seguidores líquidos", "atual": seguidores["atual"], "antes": seguidores["antes"], "variacao": None, "fmt": "sinal"},
             linha("Visitas ao perfil", "profile_views"), linha("Toques no link da bio", "website_clicks")]
    tipos = [linha("Curtidas", "likes"), linha("Comentários", "comments"), linha("Compartilhamentos", "shares"), linha("Salvamentos", "saves"),
             linha("Reposts", "reposts"), linha("Respostas", "replies")]

    stories_a = _stories_do_mes(ini, fim)
    stories_b = _stories_do_mes(*_mes(ant)) if ant else None
    reels_a = sorted([m for m in pub_a if m["tipo"] == "reel"], key=lambda m: -(m.get("visualizacoes") or 0))
    posts_a = sorted([m for m in pub_a if m["tipo"] == "post"], key=lambda m: -(m.get("interacoes") or 0))
    por_comentarios = sorted(pub_a, key=lambda m: -(m.get("comentarios") or 0))
    destaques = []
    if reels_a:
        destaques.append(_destaque(reels_a[0], "Reel mais visto"))
    if posts_a:
        destaques.append(_destaque(posts_a[0], "Melhor post do feed"))
    if por_comentarios and por_comentarios[0].get("comentarios"):
        destaques.append(_destaque(por_comentarios[0], "Campeão de comentários"))
    if len(reels_a) > 1:
        destaques.append(_destaque(reels_a[1], "2º reel mais visto"))

    def par(fn):
        return [fn(res_b) if res_b else None, fn(res_a)]

    soma_stories = lambda st: sum(x.get("alcance") or 0 for x in st["lista"]) if st else None
    return {
        "status": "real", "mensagem": "Instagram (Graph API da Meta). Os números podem diferir um pouco da ferramenta de gestão da agência.",
        "visao_geral": visao, "tipos_de_interacao": tipos,
        "publicacoes": {"posts": par(lambda r: r["posts"]["quantidade"]), "reels": par(lambda r: r["reels"]["quantidade"]),
                        "stories": [stories_b["coletados"] if stories_b else None, stories_a["coletados"]]},
        "alcance_por_formato": {k: [vistas(fmt_b, k), vistas(fmt_a, k)] for k in ("posts", "reels", "stories")},
        "conteudo": {"antes": ({"posts": res_b["posts"], "reels": res_b["reels"]} if res_b else None), "atual": {"posts": res_a["posts"], "reels": res_a["reels"]}},
        "stories": {
            "atual": {k: stories_a[k] for k in ("coletados", "inicio_da_coleta", "cobre_o_mes_inteiro")},
            "visualizacoes": sum(x.get("visualizacoes") or 0 for x in stories_a["lista"]),
            "conta": {"visualizacoes": fmt_a.get("views", {}).get("STORY"), "alcance": fmt_a.get("reach", {}).get("STORY"),
                      "interacoes": fmt_a.get("total_interactions", {}).get("STORY"), "compartilhamentos": fmt_a.get("shares", {}).get("STORY"),
                      "curtidas": fmt_a.get("likes", {}).get("STORY")},
            "melhores": sorted(stories_a["lista"], key=lambda x: -(x.get("alcance") or 0))[:6],
        },
        "destaques": destaques,
        "conteudos": [_destaque(m, "") for m in sorted(pub_a, key=lambda m: m["dia"])],
        "mais_comentados": [_destaque(m, "Mais comentado") for m in por_comentarios[:4] if m.get("comentarios")],
        "publico": _ig_publico(seguidores["total"]),
        "seguidores_total": seguidores["total"],
        "seguidores_obs": seguidores["obs"],
    }


def _seguidores_do_mes(mes: str, rede: str) -> Dict[str, Any]:
    """O saldo de seguidores do mês sai de retratos diários guardados (a API só dá os últimos 30 dias)."""
    retratos = _ler(ARQ_RETRATOS, {})
    if rede == "instagram":
        r = _g(IG_ID, fields="followers_count")
        total = r.get("followers_count")
    else:
        total = None
    hoje = date.today().isoformat()
    if total is not None:
        retratos.setdefault(rede, {})[hoje] = total
        _gravar(ARQ_RETRATOS, retratos)
    serie = retratos.get(rede, {})

    def saldo(m: str) -> Optional[int]:
        ini, fim = _mes(m)
        dias = sorted(d for d in serie if ini.isoformat() <= d <= fim.isoformat())
        antes = sorted(d for d in serie if d < ini.isoformat())
        base = serie[antes[-1]] if antes else (serie[dias[0]] if dias else None)
        if not dias or base is None:
            return None
        cobre_fim = dias[-1] >= (fim - timedelta(days=2)).isoformat()
        return serie[dias[-1]] - base if cobre_fim and (antes or dias[0] <= (ini + timedelta(days=2)).isoformat()) else None

    return {"atual": saldo(mes), "antes": saldo(mes_anterior(mes)), "total": total,
            "obs": "O saldo mensal aparece quando há retratos diários do mês; a coleta começou em "
                   f"{min(serie) if serie else hoje}." if saldo(mes) is None else None}


# ---------------------------------------------------------------------------------------------------------------------
# Facebook
# ---------------------------------------------------------------------------------------------------------------------

def _contas_de_anuncio() -> List[str]:
    return sorted({r["conta_id"] for r in bases.registros("meta_insights") if r.get("conta_id")})


def _facebook_pago(mes: str, comparar: bool) -> List[Dict[str, Any]]:
    """Impressões, alcance e gasto dos anúncios no posicionamento Facebook, somando as contas de anúncio do sistema."""
    def do_mes(m: str) -> Dict[str, float]:
        ini, fim = _mes(m)

        def conta(cid: str) -> Tuple[int, int, float]:
            r = _g(f"{cid}/insights", time_range=json.dumps({"since": ini.isoformat(), "until": fim.isoformat()}), breakdowns="publisher_platform",
                   fields="impressions,reach,spend", limit=50)
            for x in r.get("data", []):
                if x.get("publisher_platform") == "facebook":
                    return int(x.get("impressions") or 0), int(x.get("reach") or 0), float(x.get("spend") or 0)
            return 0, 0, 0.0

        with ThreadPoolExecutor(max_workers=5) as pool:
            partes = list(pool.map(conta, _contas_de_anuncio()))
        return {"impressoes": sum(p[0] for p in partes), "alcance": sum(p[1] for p in partes), "gasto": round(sum(p[2] for p in partes), 2)}

    atual = do_mes(mes)
    antes = do_mes(mes_anterior(mes)) if comparar else {}
    nomes = [("Visualizações pagas (impressões)", "impressoes", "n"), ("Alcance dos anúncios (soma das contas)", "alcance", "n"), ("Investimento no Facebook", "gasto", "reais")]
    return [{"metrica": n, "atual": atual[k], "antes": antes.get(k), "variacao": _variacao(atual[k], antes.get(k)), "fmt": f} for n, k, f in nomes]


def _facebook(mes: str, comparar: bool = False) -> Dict[str, Any]:
    # Token próprio do relatório (com read_insights); sem ele, vale o token geral do sistema
    paginas = _g("me/accounts", os.getenv("QAMAR_FACEBOOK_TOKEN") or None, fields="id,name,access_token", limit=50)
    tok = next((p["access_token"] for p in paginas.get("data", []) if p["id"] == FB_PAGE_ID), None)
    if not tok:
        return {"status": "nao_conectado", "mensagem": "O token da Meta não enxerga a página Moura Leite Loteamentos."}
    ini, fim = _mes(mes)
    r = _g(f"{FB_PAGE_ID}/insights", tok, metric="page_media_view", period="day", since=ini.isoformat(), until=fim.isoformat())
    if not r.get("data") or not r["data"][0].get("values"):
        info = _g(FB_PAGE_ID, tok, fields="followers_count,fan_count,name")
        # Sem read_insights a Meta não entrega os números da página. O que dá para mostrar com o token atual é a entrega
        # dos anúncios no Facebook (Meta Ads) e os seguidores de hoje; o orgânico fica para quando a permissão vier.
        pago = _facebook_pago(mes, comparar)
        return {
            "status": "parcial",
            "mensagem": "Entrega dos anúncios no Facebook (Meta Ads) e seguidores de hoje. Visualizações orgânicas, alcance da página e interações nos posts dependem da permissão read_insights.",
            "visao_geral": pago,
            "seguidores_hoje": info.get("followers_count") or info.get("fan_count"),
            "passos": ["Um administrador do negócio Moura Leite gera um token novo do usuário do sistema \"App de dados\" com read_insights e pages_read_user_content.",
                       "Guardar o token em QAMAR_FACEBOOK_TOKEN no engine/.env e reiniciar o motor."],
        }
    # Com a permissão, os números saem daqui (métricas atuais da página, em soma diária)
    def soma(m: str, a: date, b: date) -> Optional[float]:
        x = _g(f"{FB_PAGE_ID}/insights", tok, metric=m, period="day", since=a.isoformat(), until=b.isoformat())
        v = x["data"][0]["values"] if x.get("data") else []
        return sum(i["value"] for i in v) if v else None
    ini_a, fim_a = _mes(mes_anterior(mes))
    metricas = [("Visualizações", "page_media_view"), ("Alcance acumulado", "page_total_media_view_unique"), ("Interações nos posts", "page_post_engagements")]
    linhas = [{"metrica": n, "atual": soma(m, ini, fim), "antes": soma(m, ini_a, fim_a) if comparar else None} for n, m in metricas]
    for l in linhas:
        l["variacao"] = _variacao(l["atual"], l["antes"])
    return {"status": "real", "mensagem": "Facebook (Graph API da Meta).", "visao_geral": linhas}


# ---------------------------------------------------------------------------------------------------------------------
# Fontes ainda sem conexão
# ---------------------------------------------------------------------------------------------------------------------

def _seguidores_linkedin() -> Optional[int]:
    """Número de seguidores que a própria página pública da empresa mostra (sem login). Nada além disso é público."""
    try:
        r = httpx.get(os.getenv("QAMAR_LINKEDIN_URL", "https://www.linkedin.com/company/moura-leite-loteamentos/"), timeout=30, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"})
        m = re.search(r"([\d.]+)\s*seguidores", r.text)
        return int(m.group(1).replace(".", "")) if m else None
    except Exception:  # noqa: BLE001
        return None


def _linkedin(_: str) -> Dict[str, Any]:
    return {
        "status": "nao_conectado",
        "mensagem": "O LinkedIn só libera os números da página por um app aprovado (Community Management API).",
        "passos": ["Em linkedin.com/developers, criar um app ligado à página Moura Leite e pedir o produto Community Management API.",
                   "Um administrador da página autoriza o app (escopos r_organization_social e r_organization_admin).",
                   "Guardar LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET e o token no engine/.env.",
                   "Enquanto a aprovação não sai: exportar o relatório do LinkedIn Analytics (planilha) e subir aqui."],
        "campos": ["impressões", "reações", "comentários", "cliques", "seguidores novos", "visualizações da página", "função e localização do público"],
        "seguidores_hoje": _seguidores_linkedin(),
    }


def _tiktok(_: str) -> Dict[str, Any]:
    return {
        "status": "nao_conectado",
        "mensagem": "O TikTok libera vídeos e métricas por um app da TikTok for Developers, com a conta da marca autorizando.",
        "passos": ["Em developers.tiktok.com, criar um app com Login Kit e a Display API (escopos user.info.basic, user.info.stats e video.list).",
                   "A conta da Moura Leite autoriza o app uma vez; guardar TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET e o refresh token no engine/.env.",
                   "Lista de vídeos com visualizações, curtidas, comentários e compartilhamentos vem da API. O tempo médio assistido não vem: a agência informa."],
        "campos": ["vídeos", "visualizações", "interações", "curtidas", "comentários", "compartilhamentos", "seguidores"],
    }


ARQ_YOUTUBE = "qamar_youtube"


def _youtube(mes: str, comparar: bool = False) -> Dict[str, Any]:
    cabecalho = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"}
    canal = os.getenv("QAMAR_YOUTUBE_URL", "https://www.youtube.com/@mouraleiteloteamentos")
    pagina = _com_cache("yt-pagina", 3600, lambda: httpx.get(canal, timeout=40, follow_redirects=True, headers=cabecalho).text)
    # A página cita outros canais (em destaque); o do dono é o externalId / o endereço canônico
    achado = re.search(r'"externalId":"(UC[\w-]{20,})"', pagina) or re.search(r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{20,})"', pagina)
    canal_id = os.getenv("QAMAR_YOUTUBE_CHANNEL_ID") or (achado.group(1) if achado else None)
    if not canal_id:
        return {"status": "nao_conectado", "mensagem": "Não consegui identificar o canal do YouTube.",
                "passos": ["Informar QAMAR_YOUTUBE_CHANNEL_ID no engine/.env (ID do canal, começa com UC)."], "campos": ["vídeos", "visualizações", "inscritos"]}
    inscritos = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"', pagina)

    # O feed público traz só os 15 vídeos mais recentes: cada leitura grava o que viu, para os meses antigos não se perderem
    feed = httpx.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={canal_id}", timeout=40, headers=cabecalho).text
    guardados: Dict[str, Any] = _ler(ARQ_YOUTUBE, {"canal": canal_id, "videos": {}})
    if guardados.get("canal") != canal_id:
        guardados = {"canal": canal_id, "videos": {}}
    for e in re.findall(r"<entry>.*?</entry>", feed, re.S):
        vid = re.search(r"<yt:videoId>([\w-]+)</yt:videoId>", e)
        dia = re.search(r"<published>(\d{4}-\d{2}-\d{2})", e)
        if not vid or not dia:
            continue
        views = re.search(r'<media:statistics views="(\d+)"', e)
        curtidas = re.search(r'<media:starRating count="(\d+)"', e)
        link = re.search(r'<link rel="alternate" href="([^"]+)"', e)
        guardados["videos"][vid.group(1)] = {
            "id": vid.group(1), "dia": dia.group(1), "titulo": html.unescape(re.search(r"<title>(.*?)</title>", e).group(1)),
            "visualizacoes": int(views.group(1)) if views else None, "curtidas": int(curtidas.group(1)) if curtidas else None,
            "link": link.group(1) if link else None, "miniatura": f"https://i.ytimg.com/vi/{vid.group(1)}/hqdefault.jpg",
        }
    _gravar(ARQ_YOUTUBE, guardados)

    todos = list(guardados["videos"].values())
    ini, fim = _mes(mes)
    videos = [v for v in todos if ini.isoformat() <= v["dia"] <= fim.isoformat()]
    mais_antigo = min((v["dia"] for v in todos), default=None)
    cobre = bool(mais_antigo) and mais_antigo <= ini.isoformat()
    return {
        "status": "real",
        "mensagem": "YouTube (feed público do canal). Visualizações e curtidas são o acumulado até hoje; tempo assistido e impressões só pelo YouTube Analytics (acesso do dono do canal).",
        "videos": sorted(videos, key=lambda v: v["dia"]), "inscritos": inscritos.group(1).strip() if inscritos else None,
        "ultimo_video": max((v["dia"] for v in todos), default=None),
        "cobre_o_mes": cobre, "mais_antigo_lido": mais_antigo,
        "passos": ["Para tempo assistido, impressões e origem do tráfego: ligar o YouTube Analytics (OAuth do dono do canal, escopo yt-analytics.readonly)."],
    }


def _gmn(_: str) -> Dict[str, Any]:
    return {
        "status": "nao_conectado",
        "mensagem": "O Perfil da Empresa no Google tem API de desempenho (chamadas, rotas, cliques e termos buscados), mas pede acesso aprovado.",
        "passos": ["Pedir acesso à Business Profile API no projeto do Google Cloud do sistema (formulário de acesso da Google).",
                   "No perfil da empresa, adicionar o e-mail da conta de serviço do sistema como administrador, ou autorizar por OAuth (escopo business.manage).",
                   "Informar o ID do local; o sistema passa a puxar chamadas, pedidos de rota, cliques no site, pesquisas e termos mais buscados."],
        "campos": ["chamadas", "pedidos de rota", "cliques no site", "interações", "pessoas que viram o perfil", "termos mais buscados"],
    }


# ---------------------------------------------------------------------------------------------------------------------
# Site (GA4) e blog
# ---------------------------------------------------------------------------------------------------------------------

def _nome_da_pagina(titulo: str) -> str:
    limpo = re.sub(r"\s*-\s*Moura Leite Institucional\s*$", "", titulo or "").strip()
    partes = [p.strip() for p in limpo.split("|")]
    if len(partes) > 1 and partes[0].lower() in ("loteamento fechado", "loteamento aberto"):
        return partes[1]
    return partes[0]


def _site(mes: str, comparar: bool = False) -> Dict[str, Any]:
    from engine.extractors import ga4

    cliente = httpx.Client(timeout=60)
    cabecalho = {"Authorization": f"Bearer {ga4._GA4Extractor()._token(cliente)}"}

    def relatorio(corpo: Dict[str, Any]) -> Dict[str, Any]:
        r = cliente.post(f"{ga4.API}/properties/{GA4_PROPRIEDADE}:runReport", headers=cabecalho, json=corpo).json()
        if "error" in r:
            raise RuntimeError(r["error"].get("message", "erro do Google Analytics"))
        return r

    def do_mes(m: str) -> Dict[str, Any]:
        ini, fim = _mes(m)
        faixa = [{"startDate": ini.isoformat(), "endDate": fim.isoformat()}]
        t = relatorio({"dateRanges": faixa, "metrics": [{"name": n} for n in ("activeUsers", "newUsers", "userEngagementDuration", "eventCount")]})
        v = [float(x["value"]) for x in t["rows"][0]["metricValues"]]
        p = relatorio({"dateRanges": faixa, "dimensions": [{"name": "unifiedScreenName"}], "metrics": [{"name": "screenPageViews"}],
                       "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}], "limit": 12})
        paginas: Dict[str, int] = {}
        for linha in p.get("rows", []):
            nome = _nome_da_pagina(linha["dimensionValues"][0]["value"])
            paginas[nome] = paginas.get(nome, 0) + int(linha["metricValues"][0]["value"])
        return {"usuarios": int(v[0]), "novos": int(v[1]), "tempo_engajamento_s": int(v[2] / v[0]) if v[0] else None, "eventos": int(v[3]),
                "paginas": sorted(paginas.items(), key=lambda kv: -kv[1])[:7]}

    atual, antes = do_mes(mes), (do_mes(mes_anterior(mes)) if comparar else None)
    return {"status": "real", "mensagem": "Google Analytics 4 (páginas e telas).", "atual": atual, "antes": antes}


def _blog(mes: str, comparar: bool = False) -> Dict[str, Any]:
    def posts_do_blog() -> List[Dict[str, str]]:
        achados: List[Dict[str, str]] = []
        pagina, maximo = 1, 1
        while pagina <= maximo and pagina <= 10:
            r = httpx.post("https://www.mouraleite.com.br/wp-admin/admin-ajax.php", timeout=40,
                           data={"action": "ml_filter_blog_posts", "term": "", "paged": pagina, "per_page": 30},
                           headers={"User-Agent": "Mozilla/5.0 (relatorio-qamar)"}).json()
            if not r.get("success"):
                break
            maximo = int(r["data"].get("max_pages") or 1)
            for b in re.findall(r"<article.*?</article>", r["data"].get("html", ""), re.S):
                data = re.search(r"(\d{2})/(\d{2})/(\d{4})", b)
                href = re.search(r'href="([^"]+)"', b)
                titulo = re.search(r"<h\d[^>]*>(.*?)</h\d>", b, re.S)
                foto = re.search(r'<img[^>]*\ssrc="([^"]+)"', b)
                categoria = re.search(r'class="[^"]*(?:categ|tag|label)[^"]*"[^>]*>(.*?)<', b, re.S)
                if data and href:
                    texto = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", titulo.group(1) if titulo else ""))).strip()
                    achados.append({"data": f"{data.group(3)}-{data.group(2)}-{data.group(1)}", "titulo": texto, "link": href.group(1), "imagem": foto.group(1).replace("http://", "https://") if foto else None,
                                    "categoria": html.unescape(re.sub(r"<[^>]+>", "", categoria.group(1))).strip() if categoria else ""})
            pagina += 1
        return achados

    todos = _com_cache("blog", 600, posts_do_blog)
    ini, fim = _mes(mes)
    ini_a, fim_a = _mes(mes_anterior(mes))
    no = lambda a, b: sorted((p for p in todos if a.isoformat() <= p["data"] <= b.isoformat()), key=lambda p: p["data"])
    return {"status": "real", "mensagem": "Lista pública de posts do blog do site.", "atual": no(ini, fim), "antes": no(ini_a, fim_a) if comparar else []}


# ---------------------------------------------------------------------------------------------------------------------
# Tráfego pago (os impulsionamentos da Qamar)
# ---------------------------------------------------------------------------------------------------------------------

OBJETIVOS = {"OUTCOME_ENGAGEMENT": "Engajamento", "LINK_CLICKS": "Tráfego", "OUTCOME_TRAFFIC": "Tráfego", "VIDEO_VIEWS": "Visualização de vídeo",
             "OUTCOME_AWARENESS": "Reconhecimento", "REACH": "Alcance", "POST_ENGAGEMENT": "Engajamento", "OUTCOME_LEADS": "Leads"}


def _acao(anuncio: Dict[str, Any], tipo: str) -> float:
    for a in anuncio.get("actions") or []:
        if a["action_type"] == tipo:
            return float(a["value"])
    return 0.0


def _trafego_pago(mes: str) -> Dict[str, Any]:
    if not _token():
        return {"status": "nao_conectado", "mensagem": "META_ACCESS_TOKEN não está no engine/.env."}
    ini, fim = _mes(mes)
    campos = "ad_id,ad_name,campaign_name,objective,spend,impressions,reach,frequency,cpm,actions,video_thruplay_watched_actions,date_start,date_stop"
    r = _g(f"{CONTA_ANUNCIOS}/insights", level="ad", time_range=json.dumps({"since": ini.isoformat(), "until": fim.isoformat()}), fields=campos, limit=200)
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    anuncios = []
    for x in r.get("data", []):
        gasto = float(x.get("spend") or 0)
        if gasto <= 0:
            continue
        objetivo = OBJETIVOS.get(x.get("objective"), x.get("objective") or "—")
        if objetivo == "Engajamento":
            resultado, rotulo = _acao(x, "post_engagement"), "interações"
        elif objetivo == "Tráfego":
            resultado, rotulo = (_acao(x, "landing_page_view") or _acao(x, "link_click")), ("visitas à página" if _acao(x, "landing_page_view") else "cliques no link")
        elif objetivo == "Visualização de vídeo":
            tp = x.get("video_thruplay_watched_actions") or []
            resultado, rotulo = (float(tp[0]["value"]) if tp else 0.0), "ThruPlays"
        else:
            resultado, rotulo = _acao(x, "post_engagement"), "interações"
        anuncios.append({
            "anuncio": x["ad_name"], "campanha": x["campaign_name"], "objetivo": objetivo, "periodo": [x["date_start"], x["date_stop"]],
            "investimento": round(gasto, 2), "resultado": int(resultado), "resultado_rotulo": rotulo,
            "custo_por_resultado": round(gasto / resultado, 2) if resultado else None,
            "alcance": int(x.get("reach") or 0), "impressoes": int(x.get("impressions") or 0),
            "frequencia": round(float(x.get("frequency") or 0), 2), "cpm": round(float(x.get("cpm") or 0), 2), "ad_id": x["ad_id"],
        })
    # Período real de cada anúncio: do primeiro ao último dia com gasto dentro do mês
    diario = _g(f"{CONTA_ANUNCIOS}/insights", level="ad", time_increment=1, fields="ad_id,spend,date_start", limit=500,
                time_range=json.dumps({"since": ini.isoformat(), "until": fim.isoformat()}))
    dias: Dict[str, List[str]] = {}
    for x in diario.get("data", []):
        if float(x.get("spend") or 0) > 0:
            dias.setdefault(x["ad_id"], []).append(x["date_start"])
    for a in anuncios:
        if dias.get(a["ad_id"]):
            a["periodo"] = [min(dias[a["ad_id"]]), max(dias[a["ad_id"]])]
    anuncios.sort(key=lambda a: -a["investimento"])
    # Miniatura do criativo e o grupo: o nome "Instagram post: ..." é o impulsionamento automático do app, não campanha da agência
    def miniatura(a: Dict[str, Any]) -> None:
        cr = _g(a["ad_id"], fields="creative{thumbnail_url,image_url}").get("creative") or {}
        a["miniatura"] = cr.get("image_url") or cr.get("thumbnail_url")
        a["grupo"] = "automatico" if a["anuncio"].lower().startswith("instagram post:") else "agencia"

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(miniatura, anuncios))
    return {"status": "real", "mensagem": "Meta Ads, conta CA Moura Leite. Só o gasto dentro do mês; campanhas que passam para o mês seguinte aparecem de novo no próximo relatório.",
            "anuncios": anuncios, "total": round(sum(a["investimento"] for a in anuncios), 2),
            "total_agencia": round(sum(a["investimento"] for a in anuncios if a["grupo"] == "agencia"), 2)}


# ---------------------------------------------------------------------------------------------------------------------
# Texto digitado
# ---------------------------------------------------------------------------------------------------------------------

def manual(mes: str) -> Dict[str, Any]:
    return _ler(ARQ_MANUAL, {}).get(mes, {"imprensa": [], "observacoes": ""})


def salvar_manual(mes: str, dados: Dict[str, Any]) -> Dict[str, Any]:
    todos = _ler(ARQ_MANUAL, {})
    todos[mes] = {"imprensa": list(dados.get("imprensa") or []), "observacoes": str(dados.get("observacoes") or "")}
    _gravar(ARQ_MANUAL, todos)
    return todos[mes]


def _imprensa(mes: str) -> Dict[str, Any]:
    m = manual(mes)
    return {"status": "manual", "mensagem": "Assessoria de imprensa não tem API: o texto é digitado aqui.", "itens": m["imprensa"], "observacoes": m["observacoes"]}


# ---------------------------------------------------------------------------------------------------------------------
# Relatório completo
# ---------------------------------------------------------------------------------------------------------------------

def compilar(mes: str, atualizar: bool = False, comparar: bool = False) -> Dict[str, Any]:
    chave = f"qamar|{mes}|{int(comparar)}"
    if atualizar:
        _cache.pop(chave, None)
        _cache.pop("blog", None)
    return _com_cache(chave, 900, lambda: _compilar(mes, comparar))


def _compilar(mes: str, comparar: bool) -> Dict[str, Any]:
    if not re.fullmatch(r"\d{4}-\d{2}", mes or ""):
        raise ValueError("Informe o mês como AAAA-MM.")
    try:
        coletar_stories()
    except Exception:  # noqa: BLE001 — a coleta de stories não pode impedir o relatório
        pass
    ant = mes_anterior(mes)
    return {
        "mes": mes, "anterior": ant, "comparar": comparar,
        "rotulo": f"{rotulo_mes(ant)} e {rotulo_mes(mes)} {mes[:4]}" if comparar else f"{rotulo_mes(mes)} {mes[:4]}",
        "rotulos": {"atual": rotulo_mes(mes), "antes": rotulo_mes(ant) if comparar else None},
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "instagram": _bloco(_instagram, mes, comparar),
        "facebook": _bloco(_facebook, mes, comparar),
        "linkedin": _linkedin(mes),
        "tiktok": _tiktok(mes),
        "youtube": _bloco(_youtube, mes, comparar),
        "gmn": _gmn(mes),
        "site": _bloco(_site, mes, comparar),
        "blog": _bloco(_blog, mes, comparar),
        "imprensa": _imprensa(mes),
        "trafego_pago": _bloco(_trafego_pago, mes),
    }


# ---------------------------------------------------------------------------------------------------------------------
# Comparativo entre meses (só números e tendência, sem as listas de conteúdos)
# ---------------------------------------------------------------------------------------------------------------------

def _resumo_do_mes(mes: str) -> Dict[str, Any]:
    ini, fim = _mes(mes)
    saida: Dict[str, Any] = {"mes": mes, "rotulo": f"{rotulo_mes(mes)[:3]}/{mes[2:4]}"}

    def ig() -> Dict[str, Any]:
        t = _ig_totais(ini, fim)
        f = _ig_formatos(ini, fim)
        pubs = _ig_publicacoes(ini, fim, detalhar_insights=False)
        taxa = round(t["total_interactions"] / t["reach"] * 100, 2) if t.get("reach") and t.get("total_interactions") is not None else None
        return {"alcance": t.get("reach"), "visualizacoes": t.get("views"), "interacoes": t.get("total_interactions"), "taxa_engajamento": taxa,
                "visitas_perfil": t.get("profile_views"), "toques_link": t.get("website_clicks"), "curtidas": t.get("likes"), "comentarios": t.get("comments"),
                "compartilhamentos": t.get("shares"), "salvamentos": t.get("saves"), "visualizacoes_stories": f.get("views", {}).get("STORY"),
                "posts": sum(1 for m in pubs if m["tipo"] == "post"), "reels": sum(1 for m in pubs if m["tipo"] == "reel")}

    def site() -> Dict[str, Any]:
        d = _site(mes, False)["atual"]
        return {"usuarios": d["usuarios"], "novos": d["novos"], "tempo_engajamento_s": d["tempo_engajamento_s"], "eventos": d["eventos"]}

    def blog() -> Dict[str, Any]:
        return {"posts": len(_blog(mes, False)["atual"])}

    def pago() -> Dict[str, Any]:
        d = _trafego_pago(mes)
        ag = [a for a in d["anuncios"] if a["grupo"] == "agencia"]
        return {"investimento_agencia": d["total_agencia"], "investimento_total": d["total"], "alcance": sum(a["alcance"] for a in ag),
                "impressoes": sum(a["impressoes"] for a in ag), "anuncios": len(ag)}

    def facebook() -> Dict[str, Any]:
        l = {x["metrica"]: x["atual"] for x in _facebook_pago(mes, False)}
        return {"impressoes_pagas": l.get("Visualizações pagas (impressões)"), "alcance_pago": l.get("Alcance dos anúncios (soma das contas)"),
                "investimento": l.get("Investimento no Facebook")}

    def youtube() -> Dict[str, Any]:
        d = _youtube(mes, False)
        return {"videos": len(d["videos"]), "visualizacoes": sum(v.get("visualizacoes") or 0 for v in d["videos"]), "completo": bool(d.get("cobre_o_mes"))}

    for nome, fn in (("instagram", ig), ("site", site), ("blog", blog), ("trafego_pago", pago), ("facebook", facebook), ("youtube", youtube)):
        try:
            saida[nome] = fn()
        except Exception as e:  # noqa: BLE001 — uma fonte fora do ar não derruba o comparativo
            saida[nome] = {"erro": str(e)[:160]}
    return saida


def comparativo(meses: List[str], atualizar: bool = False) -> Dict[str, Any]:
    """Os mesmos números de cada mês escolhido, lado a lado, para responder "como foram os últimos meses"."""
    meses = sorted({m for m in meses if re.fullmatch(r"\d{4}-\d{2}", m or "")})
    if len(meses) < 2:
        raise ValueError("Escolha pelo menos dois meses para comparar.")
    if len(meses) > 12:
        raise ValueError("Escolha no máximo 12 meses.")
    hoje = date.today()
    atual = f"{hoje.year}-{hoje.month:02d}"

    def um(mes: str) -> Dict[str, Any]:
        chave = f"resumo|{mes}"
        if atualizar:
            _cache.pop(chave, None)
        # mês fechado muda pouco: guarda por mais tempo
        return _com_cache(chave, 900 if mes >= atual else 6 * 3600, lambda: _resumo_do_mes(mes))

    if atualizar:
        _cache.pop("blog", None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        lista = list(pool.map(um, meses))
    return {"meses": meses, "resumos": lista, "mes_em_andamento": atual if atual in meses else None, "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds")}


def coletar() -> Dict[str, Any]:
    """Coleta diária: guarda os stories no ar e o retrato de seguidores. Rodar uma vez por dia (python -m engine.qamar)."""
    hoje = date.today()
    novos = coletar_stories()
    seg = _seguidores_do_mes(f"{hoje.year}-{hoje.month:02d}", "instagram")
    return {"stories_novos": novos, "seguidores": seg["total"]}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    print(json.dumps(coletar(), ensure_ascii=False))
