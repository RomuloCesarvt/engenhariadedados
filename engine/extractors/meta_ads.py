"""
Extrator Meta Ads (Facebook / Instagram Lead Ads).
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


class MetaAdsExtractor(BaseExtractor):
    def __init__(self, access_token: Optional[str] = None, page_id: Optional[str] = None):
        super().__init__(OriginChannel.META_ADS)
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        self.page_id = page_id or os.getenv("META_PAGE_ID")

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if self.access_token and self.page_id:
            try:
                import httpx
                url = f"https://graph.facebook.com/v18.0/{self.page_id}/leads"
                params = {
                    "access_token": self.access_token,
                    "filtering": f"[{{'field':'time_created','operator':'GREATER_THAN','value':{int(start_date.timestamp())}}}]"
                }
                res = httpx.get(url, params=params, timeout=10)
                if res.status_code != 200:
                    self._mark(STATUS_ERROR, f"HTTP {res.status_code} da Graph API")
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    leads = []
                    for item in data:
                        raw = {
                            "id": item.get("id"),
                            "created_time": item.get("created_time"),
                            "fbclid": item.get("id"),
                            "utm_source": "meta_ads",
                        }
                        for field in item.get("field_data", []):
                            fname = field.get("name", "").lower()
                            fval = field.get("values", [None])[0]
                            if "email" in fname:
                                raw["email"] = fval
                            elif "phone" in fname or "telef" in fname or "celular" in fname:
                                raw["phone"] = fval
                        leads.append(normalize_lead(raw, self.channel))
                    print(f"  [Meta Ads API] Successfully fetched {len(leads)} real leads.")
                    self._mark(STATUS_LIVE, count=len(leads))
                    return leads
            except Exception as e:
                print(f"  [Meta Ads API Warning] {e}. Falling back to simulation.")
                self._mark(STATUS_ERROR, str(e))
        else:
            self._mark(STATUS_NOT_CONFIGURED, "META_ACCESS_TOKEN / META_PAGE_ID ausentes")

        if not simulation_allowed():
            return []

        # Fallback para dados de simulação
        leads = []
        sample_meta = [
            {"id": "meta_101", "email": "carlos.silva@gmail.com", "phone": "11988881111", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_101", "created_at": "2026-07-25 10:30:00"},
            {"id": "meta_102", "email": "ana.pereira@outlook.com", "phone": "11988882222", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_102", "created_at": "2026-07-25 11:15:00"},
            {"id": "meta_103", "email": "marcos.souza@uol.com.br", "phone": "21977773333", "campaign_name": "Condomínio Horizonte", "fbclid": "fb_click_103", "created_at": "2026-07-25 14:00:00"},
            {"id": "meta_104", "email": "luciana.lima@hotmail.com", "phone": "31966664444", "campaign_name": "Condomínio Horizonte", "fbclid": "fb_click_104", "created_at": "2026-07-26 09:20:00"},
            {"id": "meta_105", "email": "roberto.dias.perdido@gmail.com", "phone": "11955555555", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_105", "created_at": "2026-07-26 15:45:00"},
            {"id": "meta_106", "email": "juliana.mendes@yahoo.com.br", "phone": "11944446666", "campaign_name": "Campanha Retargeting", "fbclid": "fb_click_106", "created_at": "2026-07-27 08:10:00"},
        ]
        for item in sample_meta:
            item["utm_source"] = "facebook"
            item["utm_medium"] = "cpc"
            leads.append(normalize_lead(item, self.channel))
        self._mark(STATUS_SIMULATED, self.detail, len(leads))
        return leads
