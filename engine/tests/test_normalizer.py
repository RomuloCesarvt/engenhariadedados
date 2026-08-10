"""
Testes unitários para o módulo normalizer.
"""

from engine.normalizer import clean_email, clean_phone, normalize_channel_alias
from engine.config import OriginChannel


def test_clean_email():
    assert clean_email(" CARLOS.SILVA@GMAIL.COM ") == "carlos.silva@gmail.com"
    assert clean_email("invalid-email") is None
    assert clean_email(None) is None


def test_clean_phone():
    assert clean_phone("(11) 98888-1111") == "5511988881111"
    assert clean_phone("5511988881111") == "5511988881111"
    assert clean_phone("11988881111") == "5511988881111"
    assert clean_phone(None) is None


def test_normalize_channel_alias():
    assert normalize_channel_alias("facebook_ads") == OriginChannel.META_ADS
    assert normalize_channel_alias("gads") == OriginChannel.GOOGLE_ADS
    assert normalize_channel_alias("rd_station") == OriginChannel.RD_STATION
    assert normalize_channel_alias("beeviral") == OriginChannel.BEEVIRAL
    assert normalize_channel_alias("planilha") == OriginChannel.SHEETS_BI
