"""
Concorrência nos anúncios: o que a Biblioteca de Anúncios da Meta mostra sobre quem anuncia nas nossas praças.

A biblioteca não tem API para anúncio comercial no Brasil (a API oficial só devolve anúncio político) e cada busca mostra só
os ~20 anúncios de maior alcance. Por isso a coleta é feita em muitas buscas por cidade (termos gerais e nomes de concorrentes),
lidas no navegador, e este módulo junta tudo num arquivo só (`output/bases/concorrencia_coleta.json`).

Formato guardado:
  {"atualizado_em": ..., "consultas": {"<busca>": {"praca": "...", "coletado_em": "...", "total": 73,
       "anunciantes": {"<nome>": {"anuncios": 3, "desde": "2026-09-15"}}}}}
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from engine import bases

ARQUIVO = os.path.join(bases.BASES_DIR, "concorrencia_coleta.json")
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
PRACAS = ("Avaré", "Itu", "Tatuí", "Taguaí", "Itatinga", "Botucatu", "Boituva", "Cerqueira César", "Piraju", "Fartura")


def data_iso(texto: str) -> Optional[str]:
    """'15 de set de 2026' -> '2026-09-15'."""
    m = re.match(r"\s*(\d{1,2}) de (\w{3})\w* de (\d{4})", texto or "")
    if not m or m.group(2).lower() not in MESES:
        return None
    return f"{int(m.group(3)):04d}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def praca_da_busca(busca: str) -> Optional[str]:
    limpo = busca.lower()
    for p in PRACAS:
        if p.lower() in limpo or p.lower().replace("í", "i").replace("é", "e") in limpo:
            return p
    return None


def lido() -> Dict[str, Any]:
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"atualizado_em": None, "consultas": {}}


def guardar(texto: str) -> Dict[str, Any]:
    """Recebe {"<busca>": {"t": "73", "a": {"<nome>": [n, "15 de set de 2026"]}}} e junta ao que já existe."""
    novo = json.loads(texto)
    dados = lido()
    agora = datetime.now().isoformat(timespec="seconds")
    for busca, v in novo.items():
        dados["consultas"][busca] = {
            "praca": praca_da_busca(busca), "coletado_em": agora, "total": int(v.get("t") or 0),
            "anunciantes": {nome: {"anuncios": int(x[0]), "desde": data_iso(x[1]) or x[1]} for nome, x in (v.get("a") or {}).items()},
        }
    dados["atualizado_em"] = agora
    os.makedirs(bases.BASES_DIR, exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    return {"consultas": len(dados["consultas"]), "novas": len(novo)}


# ---------------------------------------------------------------------------------------------------------------------
# Quem anuncia na praça
# ---------------------------------------------------------------------------------------------------------------------

INICIO_CAMPANHA = "2026-08-16"
ANTIGO = os.path.join(bases.BASES_DIR, "concorrencia.json")

# Os anúncios da própria Moura Leite (páginas e empreendimentos) não contam como concorrência
NOSSOS = re.compile(r"moura leite|mirante dos ramos|reserva dos ramos|central parque|jardim dos ip|alta ?vista|novo horizonte|reserva do ara", re.I)
LOTEADORA = re.compile(
    r"loteament|urbanismo|empreendiment|construtora|incorporad|engenharia|resort|villas?\b|terras de|terrenos|riviera|represa|recanto|pacaembu|cyrela|"
    r"lote f[aá]cil|costa verde|campos de|^vila |bh ranch|brasil terrenos|astoria|royal parma|altos da|ch[aá]caras|k[eé]ke|\brs empreend|ellenco|"
    r"lidera|rio branco|fenix|vertaz|santo ant[oô]nio|monte rei", re.I)
CORRETOR = re.compile(r"im[oó]ve|imobili|corretor|corretora|broker|neg[oó]cios imob|consult(or|oria)|creci|real estate|estrat[eé]gia imob|mcmv|minha casa minha vida|antecipa|imovline", re.I)
NAO_IMOVEL = re.compile(
    r"academia|viajando|collab|clinika|raices|arquitet|remax ve|win leil|leil[oõ]es|cons[oó]rcio|magalu|laticinio|toyota|chevrolet|colch|sushi|seminovos|"
    r"fertiliz|supermercado|m[oó]veis|moveis|pisos|tapetes|cursos|seguran[cç]a|internet|fibra|camping|golden fruits|book|gotas de leite|net infinito|"
    r"way s[aã]o paulo|donnini|brasil preparado|mk imports|aromas|solar|samba|eventos|studio|tronco|gferro|cowmed|cobel|rustika|cardoso|casagrande",
    re.I)


GRANDES = re.compile(r"pacaembu|cyrela|\bmrv\b|direcional|tenda|alphaville|plano ?& ?plano|rossi|gafisa|\beven\b|lote f[aá]cil", re.I)


def classificar(nome: str) -> Optional[str]:
    """'loteadora' (loteadora, construtora, incorporadora), 'corretor' (corretor e imobiliária) ou None (não é do setor)."""
    if NAO_IMOVEL.search(nome):
        return None
    if CORRETOR.search(nome) and not re.search(r"empreendiment|construtora|loteament", nome, re.I):
        return "corretor"
    if LOTEADORA.search(nome):
        return "loteadora"
    return None


def _desde_antigo(texto: str) -> Optional[str]:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def compilar() -> Dict[str, Any]:
    """Anunciantes por praça, juntando a coleta antiga (duas buscas por praça) e a nova (muitas buscas, com nomes de concorrentes)."""
    consultas: Dict[str, Dict[str, Any]] = {}
    try:
        with open(ANTIGO, encoding="utf-8") as f:
            antigo = json.load(f)
        for praca, buscas in antigo.get("pracas", {}).items():
            for termo, b in buscas.items():
                consultas[f"{termo}"] = {
                    "praca": praca, "total": int(b.get("total_resultados") or 0), "coletado_em": antigo.get("coletado_em"),
                    "anunciantes": {a["nome"]: {"anuncios": int(a["anuncios"]), "desde": _desde_antigo(a.get("desde", "")) or a.get("desde")} for a in b.get("anunciantes", [])},
                }
    except (OSError, ValueError):
        antigo = {}
    nova = lido()
    consultas.update(nova.get("consultas", {}))

    pracas: Dict[str, Dict[str, Any]] = {}
    for busca, c in consultas.items():
        praca = c.get("praca")
        if not praca:
            continue
        pr = pracas.setdefault(praca, {"praca": praca, "buscas": {}, "anunciantes": {}, "descartados": 0})
        pr["buscas"][busca] = c.get("total", 0)
        for nome, x in (c.get("anunciantes") or {}).items():
            if NOSSOS.search(nome):
                continue
            tipo = classificar(nome)
            if tipo is None:
                pr["descartados"] += 1
                continue
            it = pr["anunciantes"].setdefault(nome, {"nome": nome, "tipo": tipo, "anuncios": 0, "buscas": 0, "desde": x.get("desde")})
            it["anuncios"] = max(it["anuncios"], int(x.get("anuncios") or 0))
            it["buscas"] += 1
            if x.get("desde") and (not it["desde"] or x["desde"] < it["desde"]):
                it["desde"] = x["desde"]

    saida: Dict[str, Any] = {}
    for praca, pr in pracas.items():
        lista = list(pr["anunciantes"].values())
        for it in lista:
            it["novo"] = bool(it["desde"]) and it["desde"] >= INICIO_CAMPANHA
            it["grande"] = bool(GRANDES.search(it["nome"]))
            # Quanto o anunciante aparece: anúncios achados e em quantas buscas diferentes ele apareceu
            it["presenca"] = it["anuncios"] * it["buscas"]
        lista.sort(key=lambda x: (-x["presenca"], -x["anuncios"], x["nome"]))
        saida[praca] = {
            "praca": praca, "buscas": pr["buscas"], "maior_busca": max(pr["buscas"].values()) if pr["buscas"] else 0,
            "anunciantes": len(lista), "loteadoras": sum(1 for x in lista if x["tipo"] == "loteadora"),
            "corretores": sum(1 for x in lista if x["tipo"] == "corretor"), "novos": sum(1 for x in lista if x["novo"]),
            "descartados": pr["descartados"], "lista": lista[:16] + [x for x in lista[16:] if x["grande"]],
            "principais": [x for x in lista if x["tipo"] == "loteadora"][:5],
        }
    return {
        "disponivel": bool(saida), "coletado_em": nova.get("atualizado_em") or antigo.get("coletado_em"), "consultas": len(consultas), "inicio_campanha": INICIO_CAMPANHA,
        "pracas": saida,
    }
