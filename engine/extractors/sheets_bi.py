"""
Extrator de Planilhas BI Interno / CSV.
"""

from typing import List, Optional
import os
import csv
import io
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


class SheetsBIExtractor(BaseExtractor):
    def __init__(self, file_path: Optional[str] = None, csv_url: Optional[str] = None):
        super().__init__(OriginChannel.SHEETS_BI)
        self.file_path = file_path or os.getenv("SHEETS_BI_FILE")
        # Link CSV público da planilha (ex.: Google Sheets > Arquivo > Publicar na web > CSV)
        self.csv_url = csv_url or os.getenv("SHEETS_BI_CSV_URL")

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if self.csv_url:
            try:
                import httpx
                res = httpx.get(self.csv_url, timeout=15, follow_redirects=True)
                if res.status_code == 200:
                    reader = csv.DictReader(io.StringIO(res.text))
                    leads = [normalize_lead(dict(row), self.channel) for row in reader]
                    self._mark(STATUS_LIVE, count=len(leads))
                    return leads
                self._mark(STATUS_ERROR, f"HTTP {res.status_code} ao baixar a planilha")
            except Exception as e:
                self._mark(STATUS_ERROR, str(e))
        elif self.file_path and os.path.exists(self.file_path):
            try:
                leads = []
                if self.file_path.endswith(".csv"):
                    with open(self.file_path, mode="r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            leads.append(normalize_lead(dict(row), self.channel))
                else:
                    import pandas as pd
                    df = pd.read_excel(self.file_path)
                    for _, row in df.iterrows():
                        leads.append(normalize_lead(row.to_dict(), self.channel))
                self._mark(STATUS_LIVE, count=len(leads))
                return leads
            except Exception as e:
                self._mark(STATUS_ERROR, str(e))
        else:
            self._mark(STATUS_NOT_CONFIGURED, "SHEETS_BI_CSV_URL / SHEETS_BI_FILE ausentes")

        if not simulation_allowed():
            return []

        # Mock Planilha BI Interna
        leads = []
        sample_sheets = [
            {"id": "bi_501", "email": "eduardo.estande@gmail.com", "phone": "11987654321", "campaign_name": "Atendimento Estande Vendas", "created_at": "2026-07-25 14:15:00"},
            {"id": "bi_502", "email": "heloisa.evento@outlook.com", "phone": "21987654322", "campaign_name": "Feirão Imobiliário 2026", "created_at": "2026-07-26 10:45:00"},
        ]
        for item in sample_sheets:
            item["utm_source"] = "bi_sheets"
            leads.append(normalize_lead(item, self.channel))
        self._mark(STATUS_SIMULATED, self.detail, len(leads))
        return leads
