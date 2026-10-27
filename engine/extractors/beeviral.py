"""
Extrator BeeViral (Plataforma de Indicação).

A API v2 devolve as indicações da conta paginadas e ordenadas da mais nova para a
mais antiga, no formato:
    [{"Result": [...], "Paging": {"TOTAL": páginas, "PAGE": n, "LIMIT": 20, "RECORDS": total}}]
Os parâmetros de data são ignorados pela API; o período é filtrado aqui.
"""

import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor, in_period, to_naive_utc
from engine.normalizer import normalize_lead, parse_datetime

BEEVIRAL_URL = "https://account.beeviral.app/api/v2/recommendation"
MAX_PAGES = 200


def parse_beeviral_page(payload: Any) -> Tuple[List[dict], Dict[str, Any]]:
    """Extrai (indicações, paginação) de uma resposta da API."""
    block = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(block, dict):
        return [], {}
    return block.get("Result") or [], block.get("Paging") or {}


def beeviral_item_to_raw(item: Dict[str, Any]) -> Dict[str, Any]:
    """Converte uma indicação da BeeViral para o formato aceito por normalize_lead."""
    campanha = item.get("CAMPAIGN") or {}

    # O formulário da BeeViral tem um campo "Empreendimento de interesse em <cidade>"
    empreendimento = None
    for campo in item.get("ADDITIONAL_FIELD") or []:
        if "empreendimento" in str(campo.get("FIELD", "")).lower() and campo.get("VALUE"):
            empreendimento = str(campo["VALUE"]).strip()
            break

    rd_uuid = next(
        (
            info.get("VALUE")
            for info in item.get("ADDITIONAL_INFO") or []
            if info.get("FIELD") == "rd_contact_uuid" and info.get("VALUE")
        ),
        None,
    )

    raw = {
        "id": item.get("ID"),
        "nome": item.get("NAME"),
        "email": item.get("EMAIL"),
        "phone": item.get("PHONE"),
        "created_at": item.get("CREATION"),
        "campaign_name": campanha.get("NAME") or "BeeViral Indicação",
        # Com o UUID da RD Station a indicação casa direto com o lead do CV (idrd_station)
        "rd_id": rd_uuid,
        "bee_id": None if rd_uuid else item.get("ID"),
        "utm_source": "beeviral",
        "utm_medium": "referral",
        "status_beeviral": item.get("STATUS"),
        "convertido": item.get("CONVERT") == "Y",
        "corretor": ((item.get("COLLABORATOR") or {}).get("NAME") or "").strip() or None,
        "rd_contact_uuid": rd_uuid,
    }
    if empreendimento:
        raw["empreendimento"] = empreendimento
    return raw


class BeeViralExtractor(BaseExtractor):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(OriginChannel.BEEVIRAL)
        self.api_key = api_key or os.getenv("BEEVIRAL_API_KEY")

    def fetch_raw(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """Indicações brutas da API (todos os campos) criadas no período."""
        if not self.api_key:
            self._set_status(
                "nao_configurado",
                message="BEEVIRAL_API_KEY não configurada.",
                action="Copie a chave de API no painel da BeeViral e preencha BEEVIRAL_API_KEY.",
            )
            return []

        try:
            import httpx

            headers = {"x-token-beeviral": self.api_key, "Accept": "application/json"}
            itens: List[dict] = []
            total_conta = 0
            pagina, total_paginas = 1, 1
            inicio = to_naive_utc(start_date)

            with httpx.Client(timeout=25) as client:
                while pagina <= min(total_paginas, MAX_PAGES):
                    res = client.get(BEEVIRAL_URL, headers=headers, params={"page": pagina})
                    if res.status_code != 200:
                        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:160]}")

                    resultado, paginacao = parse_beeviral_page(res.json())
                    total_paginas = int(paginacao.get("TOTAL") or 1)
                    total_conta = int(paginacao.get("RECORDS") or total_conta)
                    if not resultado:
                        break
                    itens.extend(resultado)

                    # Ordenação é da mais nova para a mais antiga: a página já passou
                    # do início do período, as seguintes também passaram.
                    datas = [to_naive_utc(parse_datetime(x.get("CREATION"))) for x in resultado if x.get("CREATION")]
                    if datas and min(datas) < inicio:
                        break
                    pagina += 1

            itens = [
                item for item in itens
                if item.get("CREATION") and in_period(parse_datetime(item["CREATION"]), start_date, end_date)
            ]
            self._set_status(
                "real", len(itens), f"{len(itens)} indicação(ões) no período — a conta tem {total_conta} no total."
            )
            print(f"  [BeeViral API] {len(itens)} indicações reais no período.")
            return itens

        except Exception as e:
            self._set_status(
                "erro",
                message=f"Falha ao consultar a BeeViral: {e}",
                action="Confira se a BEEVIRAL_API_KEY continua ativa no painel da BeeViral.",
            )
            print(f"  [BeeViral API Erro] {e}")
            return []

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        itens = self.fetch_raw(start_date, end_date)
        if self.status.mode != "real":
            return self._fallback(self._mock_leads)
        return [normalize_lead(beeviral_item_to_raw(item), self.channel) for item in itens]

    def _mock_leads(self) -> List[LeadRecord]:
        sample = [
            {"id": "bee_401", "email": "marcelo.indicação1@gmail.com", "phone": "11944445555", "campaign_name": "Programa Indique e Ganhe", "empreendimento": "Residencial Sol", "bee_id": "bee_ref_401", "created_at": "2026-07-25 15:30:00"},
            {"id": "bee_402", "email": "renata.indicação2@hotmail.com", "phone": "21933334444", "campaign_name": "Programa Indique e Ganhe", "empreendimento": "Condomínio Horizonte", "bee_id": "bee_ref_402", "created_at": "2026-07-26 11:10:00"},
            {"id": "bee_403", "email": "leandro.perda.beeviral@gmail.com", "phone": "31922223333", "campaign_name": "Programa Indique e Ganhe", "empreendimento": "Residencial Sol", "bee_id": "bee_ref_403", "created_at": "2026-07-26 16:50:00"},
            {"id": "bee_404", "email": "sofi.indicada4@yahoo.com", "phone": "41911112222", "campaign_name": "Membro Indica Membro", "bee_id": "bee_ref_404", "created_at": "2026-07-27 07:30:00"},
        ]
        leads = []
        for item in sample:
            item["utm_source"] = "beeviral"
            item["utm_medium"] = "referral"
            leads.append(normalize_lead(item, self.channel))
        return leads
