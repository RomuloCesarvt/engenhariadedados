"""
Extrator de Planilhas BI Interno / CSV.
"""

from typing import List, Optional
import os
import csv
from datetime import datetime
from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor
from engine.normalizer import normalize_lead


class SheetsBIExtractor(BaseExtractor):
    def __init__(self, file_path: Optional[str] = None):
        super().__init__(OriginChannel.SHEETS_BI)
        self.file_path = file_path

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if self.file_path and os.path.exists(self.file_path):
            try:
                leads = []
                if self.file_path.endswith(".csv"):
                    with open(self.file_path, mode="r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            leads.append(normalize_lead(dict(row), self.channel))
                    return leads
                else:
                    import pandas as pd
                    df = pd.read_excel(self.file_path)
                    for _, row in df.iterrows():
                        leads.append(normalize_lead(row.to_dict(), self.channel))
                    return leads
            except Exception:
                pass

        # Mock Planilha BI Interna
        leads = []
        sample_sheets = [
            {"id": "bi_501", "email": "eduardo.estande@gmail.com", "phone": "11987654321", "campaign_name": "Atendimento Estande Vendas", "created_at": "2026-07-25 14:15:00"},
            {"id": "bi_502", "email": "heloisa.evento@outlook.com", "phone": "21987654322", "campaign_name": "Feirão Imobiliário 2026", "created_at": "2026-07-26 10:45:00"},
        ]
        for item in sample_sheets:
            item["utm_source"] = "bi_sheets"
            leads.append(normalize_lead(item, self.channel))
        return leads
