"""
Índice de identidade do CV: acha a pessoa em TODOS os leads do CV, de qualquer data.

A base cv_leads (13 meses, com todos os campos) alimenta o BI. O índice cv_indice (todos os
leads da conta, só com os campos de identificação) garante que um lead cadastrado há anos
nunca seja dado como "não chegou no CV" numa conferência.
"""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from engine import bases, bi
from engine.normalizer import clean_email, clean_phone, normalize_name


def fone8(valor: Any) -> Optional[str]:
    """Últimos 8 dígitos: o mesmo número com ou sem DDI, DDD ou nono dígito."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-8:] if len(digitos) >= 8 else None


class _Mapa:
    """Busca por uma chave (e-mail, telefone...) devolvendo os leads preparados do BI."""

    def __init__(self, indice: "IndiceCV", tipo: str):
        self._indice, self._tipo = indice, tipo

    def get(self, valor: Any) -> Optional[List[Dict[str, Any]]]:
        ids = self._indice._chaves[self._tipo].get(valor) if valor else None
        return [self._indice.lead(i) for i in ids] if ids else None

    def __getitem__(self, valor: Any) -> List[Dict[str, Any]]:
        return self.get(valor) or []


class IndiceCV:
    def __init__(self) -> None:
        self._preparados = {str(l["id"]): l for l in bi.leads_preparados()}
        self._brutos: Dict[str, Dict[str, Any]] = {str(r.get("idlead")): r for r in bases.registros("cv_indice")}
        self.cobre_todos_os_leads = bool(self._brutos)
        for r in bases.registros("cv_leads"):  # a base completa vence o registro enxuto
            self._brutos[str(r.get("idlead"))] = r
        self.total = len(self._brutos)
        self._memo: Dict[str, Dict[str, Any]] = {}
        self._chaves: Dict[str, Dict[str, List[str]]] = {t: defaultdict(list) for t in ("uuid", "email", "fone", "fone8", "nome")}
        for id_, raw in self._brutos.items():
            for tipo, valor in (
                ("uuid", raw.get("idrd_station")),
                ("email", clean_email(raw.get("email"))),
                ("fone", clean_phone(raw.get("telefone"))),
                ("fone8", fone8(raw.get("telefone"))),
                ("nome", normalize_name(raw.get("nome"))),
            ):
                if valor:
                    self._chaves[tipo][valor].append(id_)

    def lead(self, id_: str) -> Dict[str, Any]:
        """Lead preparado (BI) — os de fora dos 13 meses são preparados só quando encontrados."""
        if id_ in self._preparados:
            return self._preparados[id_]
        if id_ not in self._memo:
            self._memo[id_] = bi.preparar_lead(self._brutos[id_])
        return self._memo[id_]

    def tem(self, id_: Any) -> bool:
        return str(id_) in self._brutos

    def bruto(self, id_: Any) -> Dict[str, Any]:
        return self._brutos[str(id_)]

    def mapa(self, tipo: str) -> _Mapa:
        return _Mapa(self, tipo)

    def valores(self, tipo: str) -> Set[str]:
        return set(self._chaves[tipo])


_cache: Dict[str, Any] = {"chave": None, "indice": None}


def _limpar() -> None:
    _cache.update(chave=None, indice=None)


bi.ao_limpar_cache(_limpar)


def indice() -> IndiceCV:
    partes = []
    for chave in ("cv_leads", "cv_indice"):
        base = bases.carregar(chave) or {}
        partes.append(f"{base.get('dados_de')}|{base.get('atualizado_em')}|{base.get('total')}")
    versao = "#".join(partes)
    if _cache["chave"] != versao or _cache["indice"] is None:
        _cache.update(chave=versao, indice=IndiceCV())
    return _cache["indice"]
