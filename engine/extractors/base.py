"""
Classes base dos extratores e rastreio do estado de cada integração.
"""

import csv
import io
from abc import ABC, abstractmethod
from typing import Callable, List, Optional
from datetime import datetime, timezone

from engine.config import LeadRecord, CVLeadRecord, OriginChannel, SourceStatus


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coloca datas de APIs diferentes numa base única de comparação: UTC sem fuso."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def in_period(dt: Optional[datetime], start: datetime, end: datetime) -> bool:
    d = to_naive_utc(dt)
    return d is not None and to_naive_utc(start) <= d <= to_naive_utc(end)


def read_csv_rows(path: str) -> List[dict]:
    """
    Lê um CSV exportado de qualquer ferramenta: UTF-8 (com ou sem BOM) ou Windows-1252,
    que é como o Excel salva no Windows; separador vírgula ou ponto e vírgula.
    """
    with open(path, "rb") as f:
        bruto = f.read()
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    amostra = texto[:4096]
    delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    return [dict(r) for r in csv.DictReader(io.StringIO(texto), delimiter=delimitador)]


class StatusMixin:
    """
    Cada extrator registra COMO obteve os dados — real, erro, não configurado ou
    simulado — para que o relatório nunca apresente simulação como realidade.
    """

    source_key: str = ""
    status: Optional[SourceStatus] = None

    def _set_status(
        self, mode: str, records: int = 0, message: str = "", action: Optional[str] = None
    ) -> SourceStatus:
        from engine.integrations import build_status

        self.status = build_status(self.source_key, mode, records, message, action)
        return self.status

    def _fallback(self, mock_factory: Callable[[], list]) -> list:
        """
        Chamado quando a fonte real não entregou dados. Só devolve simulação com
        ALLOW_SIMULATED_DATA ligado — e, nesse caso, marca a fonte como simulada.
        """
        from engine.integrations import simulated_data_allowed

        if not simulated_data_allowed():
            return []
        registros = mock_factory()
        motivo = self.status.message if self.status else ""
        acao = self.status.action if self.status else None
        self._set_status(
            "simulado",
            len(registros),
            f"DADOS SIMULADOS (modo demonstração). Motivo: {motivo}".strip(),
            acao,
        )
        return registros


class BaseExtractor(StatusMixin, ABC):
    def __init__(self, channel: OriginChannel):
        self.channel = channel
        self.source_key = channel.value
        self.status = None

    @abstractmethod
    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        """Extrai leads da plataforma de origem no intervalo de datas especificado."""
        pass


class BaseCVExtractor(StatusMixin, ABC):
    source_key = "cv_crm"

    @abstractmethod
    def fetch_cv_leads(self, start_date: datetime, end_date: datetime) -> List[CVLeadRecord]:
        """Extrai leads cadastrados no CRM Construtor de Vendas (CV)."""
        pass
