"""
Extrator BeeViral (Plataforma de Indicação).
"""

import os
from typing import List, Optional
from datetime import datetime
from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import (
    BaseExtractor,
    STATUS_ERROR,
    STATUS_LIVE,
    STATUS_NOT_CONFIGURED,
    STATUS_SIMULATED,
    simulation_allowed,
)
from engine.normalizer import normalize_lead


class BeeViralExtractor(BaseExtractor):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(OriginChannel.BEEVIRAL)
        self.api_key = api_key or os.getenv("BEEVIRAL_API_KEY")

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if self.api_key:
            try:
                import httpx
                headers = {"x-token-beeviral": self.api_key, "Accept": "application/json"}
                url = "https://account.beeviral.app/api/v2/recommendation"
                params = {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                }
                res = httpx.get(url, headers=headers, params=params, timeout=10)
                if res.status_code != 200:
                    self._mark(STATUS_ERROR, f"HTTP {res.status_code} da API BeeViral")
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    leads = []
                    for item in data:
                        raw = {
                            "id": item.get("id"),
                            "email": item.get("referred_email") or item.get("email"),
                            "phone": item.get("referred_phone") or item.get("phone"),
                            "campaign_name": item.get("campaign_name", "BeeViral Indicação"),
                            "bee_id": str(item.get("id")),
                            "created_at": item.get("created_at"),
                            "utm_source": "beeviral",
                            "utm_medium": "referral",
                        }
                        leads.append(normalize_lead(raw, self.channel))
                    print(f"  [BeeViral API] Successfully fetched {len(leads)} real referrals.")
                    self._mark(STATUS_LIVE, count=len(leads))
                    return leads
            except Exception as e:
                print(f"  [BeeViral API Warning] {e}. Falling back to simulation.")
                self._mark(STATUS_ERROR, str(e))
        else:
            self._mark(STATUS_NOT_CONFIGURED, "BEEVIRAL_API_KEY ausente")

        if not simulation_allowed():
            return []

        # Fallback para dados de simulação
        leads = []
        sample_beeviral = [
            {"id": "bee_401", "email": "marcelo.indicação1@gmail.com", "phone": "11944445555", "campaign_name": "Programa Indique e Ganhe", "bee_id": "bee_ref_401", "created_at": "2026-07-25 15:30:00"},
            {"id": "bee_402", "email": "renata.indicação2@hotmail.com", "phone": "21933334444", "campaign_name": "Programa Indique e Ganhe", "bee_id": "bee_ref_402", "created_at": "2026-07-26 11:10:00"},
            {"id": "bee_403", "email": "leandro.perda.beeviral@gmail.com", "phone": "31922223333", "campaign_name": "Programa Indique e Ganhe", "bee_id": "bee_ref_403", "created_at": "2026-07-26 16:50:00"},
            {"id": "bee_404", "email": "sofi.indicada4@yahoo.com", "phone": "41911112222", "campaign_name": "Membro Indica Membro", "bee_id": "bee_ref_404", "created_at": "2026-07-27 07:30:00"},
        ]
        for item in sample_beeviral:
            item["utm_source"] = "beeviral"
            item["utm_medium"] = "referral"
            leads.append(normalize_lead(item, self.channel))
        self._mark(STATUS_SIMULATED, self.detail, len(leads))
        return leads
