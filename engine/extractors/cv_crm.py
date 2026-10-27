"""
Extrator CRM Construtor de Vendas (CV).
Conecta à API REST oficial do Construtor de Vendas ou faz fallback para simulação se as variáveis de ambiente não estiverem configuradas.
"""

import os
from typing import List, Optional
from datetime import datetime
from engine.config import CVLeadRecord
from engine.extractors.base import (
    BaseCVExtractor,
    STATUS_ERROR,
    STATUS_LIVE,
    STATUS_NOT_CONFIGURED,
    STATUS_SIMULATED,
    simulation_allowed,
)
from engine.normalizer import normalize_cv_lead


class CVCRMExtractor(BaseCVExtractor):
    def __init__(
        self,
        api_url: Optional[str] = None,
        email: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.api_url = api_url or os.getenv("CV_CRM_URL")
        self.email = email or os.getenv("CV_CRM_EMAIL")
        self.token = token or os.getenv("CV_CRM_TOKEN")

    def fetch_cv_leads(self, start_date: datetime, end_date: datetime) -> List[CVLeadRecord]:
        # Se as credenciais estiverem configuradas no .env ou via parâmetro, conecta à API do CV
        if self.api_url and self.token:
            try:
                import httpx

                base_url = self.api_url.rstrip("/")
                headers = {
                    "token": self.token,
                    "Content-Type": "application/json",
                }
                if self.email:
                    headers["email"] = self.email

                # Endpoint oficial do CV CRM para listagem de leads (v1)
                params = {
                    "data_inicio": start_date.strftime("%Y-%m-%d"),
                    "data_fim": end_date.strftime("%Y-%m-%d"),
                    "limite": 500,
                }

                response = httpx.get(f"{base_url}/api/v1/comercial/leads", headers=headers, params=params, timeout=15)

                if response.status_code != 200:
                    self._mark(STATUS_ERROR, f"HTTP {response.status_code} da API do CV")
                if response.status_code == 200:
                    payload = response.json()
                    leads_raw = payload.get("leads", []) or payload.get("data", []) or payload
                    
                    if isinstance(leads_raw, list):
                        cv_leads = []
                        for item in leads_raw:
                            cv_leads.append(normalize_cv_lead(item))
                        print(f"  [CV CRM API] Successfully fetched {len(cv_leads)} real leads from CV API.")
                        self._mark(STATUS_LIVE, count=len(cv_leads))
                        return cv_leads
                    self._mark(STATUS_ERROR, "Resposta do CV em formato inesperado")
            except Exception as e:
                print(f"  [CV CRM API Warning] Could not connect to CV API ({e}). Falling back to simulation.")
                self._mark(STATUS_ERROR, str(e))
        else:
            self._mark(STATUS_NOT_CONFIGURED, "CV_CRM_URL / CV_CRM_TOKEN ausentes")

        if not simulation_allowed():
            return []

        # Fallback para dados de simulação
        cv_leads = []
        sample_cv = [
            {"id": "cv_1001", "email": "carlos.silva@gmail.com", "telefone": "11988881111", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 10:32:00", "id_externo": "fb_click_101"},
            {"id": "cv_1002", "email": "ana.pereira@outlook.com", "telefone": "11988882222", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 11:17:00", "id_externo": "fb_click_102"},
            {"id": "cv_1003", "email": "marcos.souza@uol.com.br", "telefone": "21977773333", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 14:02:00", "id_externo": "fb_click_103"},
            {"id": "cv_1004", "email": "luciana.lima@hotmail.com", "telefone": "31966664444", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 09:22:00", "id_externo": "fb_click_104"},
            {"id": "cv_1006", "email": "juliana.mendes@yahoo.com.br", "telefone": "11944446666", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-27 08:12:00", "id_externo": "fb_click_106"},
            {"id": "cv_2001", "email": "fernando.alves@gmail.com", "telefone": "11933331111", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 09:12:00", "id_externo": "gclid_alpha_201"},
            {"id": "cv_2002", "email": "beatriz.costa@gmail.com", "telefone": "21922223333", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 16:32:00", "id_externo": "gclid_alpha_202"},
            {"id": "cv_2003", "email": "ricardo.oliveira@uol.com.br", "telefone": "31911114444", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 10:02:00", "id_externo": "gclid_alpha_203"},
            {"id": "cv_2004", "email": "camila.ferreira@outlook.com", "telefone": "41999995555", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 22:30:00", "id_externo": "gclid_alpha_204"},
            {"id": "cv_3001", "email": "patricia.rocha@gmail.com", "telefone": "11977778888", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-25 12:03:00", "id_externo": "rd_lead_301"},
            {"id": "cv_3002", "email": "thiago.martins@yahoo.com", "telefone": "21966669999", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-26 14:23:00", "id_externo": "rd_lead_302"},
            {"id": "cv_3003", "email": "vanessa.gomes@icloud.com", "telefone": "31955550000", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-26 17:48:00", "id_externo": "rd_lead_303"},
            {"id": "cv_4001", "email": "marcelo.indicação1@gmail.com", "telefone": "11944445555", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-25 15:35:00", "id_externo": "bee_ref_401"},
            {"id": "cv_4002", "email": "renata.indicação2@hotmail.com", "telefone": "21933334444", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-26 11:15:00", "id_externo": "bee_ref_402"},
            {"id": "cv_4004", "email": "sofi.indicada4@yahoo.com", "telefone": "41911112222", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-27 07:35:00", "id_externo": "bee_ref_404"},
            {"id": "cv_5001", "email": "eduardo.estande@gmail.com", "telefone": "11987654321", "origem": "Estande Vendas", "midia": "presencial", "data_cadastramento": "2026-07-25 14:30:00"},
            {"id": "cv_5002", "email": "heloisa.evento@outlook.com", "telefone": "21987654322", "origem": "Feirão Imobiliário", "midia": "presencial", "data_cadastramento": "2026-07-26 11:00:00"},
        ]

        for item in sample_cv:
            cv_leads.append(normalize_cv_lead(item))
        self._mark(STATUS_SIMULATED, self.detail, len(cv_leads))
        return cv_leads
