"""
Pacote de extratores de dados.
"""

from .base import BaseExtractor, BaseCVExtractor
from .meta_ads import MetaAdsExtractor
from .google_ads import GoogleAdsExtractor
from .rd_station import RDStationExtractor
from .beeviral import BeeViralExtractor
from .sheets_bi import SheetsBIExtractor
from .cv_crm import CVCRMExtractor

__all__ = [
    "BaseExtractor",
    "BaseCVExtractor",
    "MetaAdsExtractor",
    "GoogleAdsExtractor",
    "RDStationExtractor",
    "BeeViralExtractor",
    "SheetsBIExtractor",
    "CVCRMExtractor",
]
