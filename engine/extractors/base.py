"""
Classe abstrata base para os Extratores de Origem de Dados.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from engine.config import LeadRecord, CVLeadRecord, OriginChannel

# Estados possíveis de uma fonte após uma extração
STATUS_LIVE = "live"                      # API real respondeu com sucesso
STATUS_SIMULATED = "simulated"            # dados fictícios de demonstração
STATUS_NOT_CONFIGURED = "not_configured"  # credenciais ausentes (e simulação desligada)
STATUS_ERROR = "error"                    # API configurada, mas a chamada falhou


def simulation_allowed() -> bool:
    """
    Dados de simulação só devem aparecer em desenvolvimento local.
    Em produção (Vercel) defina ALLOW_SIMULATION=0 para que uma fonte sem
    credenciais ou com erro retorne vazio em vez de leads fictícios.
    """
    return os.getenv("ALLOW_SIMULATION", "1").strip().lower() not in ("0", "false", "no")


class ExtractionStatus:
    """Registra como a última extração de uma fonte terminou."""

    source_name: str = ""
    status: str = STATUS_NOT_CONFIGURED
    detail: Optional[str] = None
    count: int = 0

    def _mark(self, status: str, detail: Optional[str] = None, count: int = 0) -> None:
        self.status = status
        self.detail = detail
        self.count = count

    def status_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_name,
            "status": self.status,
            "detail": self.detail,
            "count": self.count,
        }


class BaseExtractor(ExtractionStatus, ABC):
    def __init__(self, channel: OriginChannel):
        self.channel = channel
        self.source_name = channel.value

    @abstractmethod
    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        """Extrai leads da plataforma de origem no intervalo de datas especificado."""
        pass


class BaseCVExtractor(ExtractionStatus, ABC):
    source_name = OriginChannel.CV_CRM.value

    @abstractmethod
    def fetch_cv_leads(self, start_date: datetime, end_date: datetime) -> List[CVLeadRecord]:
        """Extrai leads cadastrados no CRM Construtor de Vendas (CV)."""
        pass
