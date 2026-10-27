"""
Testes do ciclo do monitor ao vivo (estado serializável, sem SSE).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from engine.config import CVLeadRecord, LeadRecord, OriginChannel
from engine import lead_monitor as lm
from engine.lead_monitor import TrackedLead


class FakeExtractor:
    """Extrator de fonte que devolve leads fixos."""

    status = "live"
    detail = None

    def __init__(self, leads):
        self._leads = leads

    def fetch_leads(self, start, end):
        return self._leads

    def status_dict(self):
        return {"source": "meta_ads", "status": self.status, "detail": None, "count": len(self._leads)}


class FakeCV:
    def __init__(self, leads, status="live"):
        self._leads = leads
        self.status = status
        self.detail = None

    def fetch_cv_leads(self, start, end):
        return self._leads

    def status_dict(self):
        return {"source": "cv_crm", "status": self.status, "detail": self.detail, "count": len(self._leads)}


def source_lead(lead_id="meta_1", email="a@x.com", now=None):
    return LeadRecord(
        source_lead_id=lead_id, email=email, email_clean=email, phone=None, phone_clean=None,
        origin_channel=OriginChannel.META_ADS, created_at=now or datetime.now(timezone.utc),
    )


def cv_lead(email="a@x.com", origem="Facebook Ads", now=None):
    return CVLeadRecord(
        cv_id="cv_1", email=email, email_clean=email, origem_cv=origem,
        created_at=now or datetime.now(timezone.utc),
    )


@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "x")
    monkeypatch.setenv("ALLOW_SIMULATION", "0")
    for var in ("GOOGLE_ADS_DEVELOPER_TOKEN", "RD_STATION_API_TOKEN", "BEEVIRAL_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setitem(lm.SOURCE_EXTRACTORS, "meta_ads", lambda: FakeExtractor([source_lead()]))


def test_state_survives_json_roundtrip_between_cycles(real_mode, monkeypatch):
    monkeypatch.setattr(lm, "CVCRMExtractor", lambda: FakeCV([cv_lead()]))
    now = datetime.now(timezone.utc)

    state = lm.run_cycle(lm.new_state(), now)
    state = json.loads(json.dumps(state))  # simula Redis entre duas requisições serverless

    lead = state["leads"]["meta_1"]
    assert lead["status"] == lm.STATUS_FOUND
    assert lead["cv_origin"] == "Facebook Ads"


def test_origin_mismatch_is_flagged(real_mode, monkeypatch):
    monkeypatch.setattr(lm, "CVCRMExtractor", lambda: FakeCV([cv_lead(origem="Google Ads")]))
    state = lm.run_cycle(lm.new_state(), datetime.now(timezone.utc))
    assert state["leads"]["meta_1"]["status"] == lm.STATUS_MISMATCH


def test_lead_is_lost_only_after_timeout(real_mode, monkeypatch):
    monkeypatch.setattr(lm, "CVCRMExtractor", lambda: FakeCV([]))
    t0 = datetime.now(timezone.utc)

    state = lm.run_cycle(lm.new_state(), t0)
    assert state["leads"]["meta_1"]["status"] == lm.STATUS_WAITING

    state = lm.run_cycle(state, t0 + timedelta(seconds=lm.MAX_WAIT_SECONDS + 1))
    assert state["leads"]["meta_1"]["status"] == lm.STATUS_LOST


def test_lead_is_not_marked_lost_when_cv_is_down(real_mode, monkeypatch):
    monkeypatch.setattr(lm, "CVCRMExtractor", lambda: FakeCV([], status="error"))
    t0 = datetime.now(timezone.utc)

    state = lm.run_cycle(lm.new_state(), t0)
    state = lm.run_cycle(state, t0 + timedelta(seconds=lm.MAX_WAIT_SECONDS + 60))

    assert state["leads"]["meta_1"]["status"] == lm.STATUS_WAITING


def test_known_leads_are_not_detected_twice(real_mode, monkeypatch):
    monkeypatch.setattr(lm, "CVCRMExtractor", lambda: FakeCV([cv_lead()]))
    t0 = datetime.now(timezone.utc)

    state = lm.run_cycle(lm.new_state(), t0)
    state = lm.run_cycle(state, t0 + timedelta(minutes=2))

    assert lm.get_stats(state["leads"].values())["total"] == 1


def test_cycle_is_throttled_to_poll_interval():
    now = datetime.now(timezone.utc)
    state = lm.new_state()
    assert lm.cycle_is_due(state, now)
    state["last_cycle_at"] = now.isoformat()
    assert not lm.cycle_is_due(state, now + timedelta(seconds=lm.POLL_INTERVAL_SECONDS - 1))
    assert lm.cycle_is_due(state, now + timedelta(seconds=lm.POLL_INTERVAL_SECONDS))


def test_no_demo_data_when_simulation_is_disabled(monkeypatch):
    for var in lm.SOURCE_ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_SIMULATION", "0")
    assert not lm.is_demo_mode()
    state = lm.run_cycle(lm.new_state(), datetime.now(timezone.utc))
    assert state["leads"] == {}


def test_demo_mode_generates_leads_locally(monkeypatch):
    for var in lm.SOURCE_ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALLOW_SIMULATION", "1")
    assert lm.is_demo_mode()
    state = lm.run_cycle(lm.new_state(), datetime.now(timezone.utc))
    assert len(state["leads"]) == 1
    assert state["demo_index"] == 1
