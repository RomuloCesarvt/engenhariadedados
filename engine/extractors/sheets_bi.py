"""
Extrator de Planilhas BI Interno / CSV (leads presenciais: estande, eventos, feirões).

O arquivo é indicado por parâmetro ou por SHEETS_BI_FILE_PATH.
"""

import os
from typing import List, Optional
from datetime import datetime

from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor, in_period, read_csv_rows
from engine.normalizer import normalize_lead


class SheetsBIExtractor(BaseExtractor):
    def __init__(self, file_path: Optional[str] = None):
        super().__init__(OriginChannel.SHEETS_BI)
        self.file_path = file_path or os.getenv("SHEETS_BI_FILE_PATH")

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if not self.file_path:
            self._set_status(
                "nao_configurado",
                message="Nenhuma planilha de leads presenciais configurada (opcional).",
                action="Para incluir leads de estande e eventos, aponte SHEETS_BI_FILE_PATH para o CSV/XLSX exportado do BI.",
            )
            return self._fallback(self._mock_leads)

        if not os.path.exists(self.file_path):
            self._set_status(
                "erro",
                message=f"Arquivo não encontrado: {self.file_path}",
                action="Confira o caminho em SHEETS_BI_FILE_PATH.",
            )
            return self._fallback(self._mock_leads)

        try:
            if self.file_path.lower().endswith(".csv"):
                linhas = read_csv_rows(self.file_path)
            else:
                import pandas as pd

                linhas = pd.read_excel(self.file_path).to_dict(orient="records")

            todos = [
                normalize_lead({str(k).strip().lower().replace(" ", "_"): v for k, v in row.items()}, self.channel)
                for row in linhas
            ]
            leads = [lead for lead in todos if in_period(lead.created_at, start_date, end_date)]
            self._set_status(
                "real", len(leads), f"{len(leads)} de {len(todos)} lead(s) da planilha estão no período."
            )
            return leads
        except Exception as e:
            self._set_status("erro", message=f"Falha ao ler {self.file_path}: {e}")
            return self._fallback(self._mock_leads)

    def _mock_leads(self) -> List[LeadRecord]:
        sample = [
            {"id": "bi_501", "email": "eduardo.estande@gmail.com", "phone": "11987654321", "campaign_name": "Atendimento Estande Vendas", "empreendimento": "Condomínio Horizonte", "created_at": "2026-07-25 14:15:00"},
            {"id": "bi_502", "email": "heloisa.evento@outlook.com", "phone": "21987654322", "campaign_name": "Feirão Imobiliário 2026", "empreendimento": "Residencial Sol", "created_at": "2026-07-26 10:45:00"},
        ]
        leads = []
        for item in sample:
            item["utm_source"] = "bi_sheets"
            leads.append(normalize_lead(item, self.channel))
        return leads
