"""
Classe abstrata base para os Extratores de Origem de Dados.
"""

from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from engine.config import LeadRecord, CVLeadRecord, OriginChannel


class BaseExtractor(ABC):
    def __init__(self, channel: OriginChannel):
        self.channel = channel

    @abstractmethod
    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        """Extrai leads da plataforma de origem no intervalo de datas especificado."""
        pass


class BaseCVExtractor(ABC):
    @abstractmethod
    def fetch_cv_leads(self, start_date: datetime, end_date: datetime) -> List[CVLeadRecord]:
        """Extrai leads cadastrados no CRM Construtor de Vendas (CV)."""
        pass
