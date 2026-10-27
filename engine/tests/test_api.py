"""
Testes da API FastAPI (app.py) usada na Vercel.
"""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from engine import store as store_module
from engine import pipeline


@pytest.fixture
def client(monkeypatch):
    store_module.reset_store_for_tests()
    for var in ("KV_REST_API_URL", "UPSTASH_REDIS_REST_URL", "VERCEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ENGINE_API_KEY", "segredo")
    monkeypatch.setenv("ALLOW_SIMULATION", "0")
    yield TestClient(app_module.app)
    store_module.reset_store_for_tests()


AUTH = {"Authorization": "Bearer segredo"}


def test_health_is_public_and_hides_data(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["simulation_allowed"] is False
    assert set(body["sources_configured"]) >= {"meta_ads", "google_ads", "rd_station", "beeviral", "sheets_bi", "cv_crm"}


@pytest.mark.parametrize("path", ["/api/monitor/status", "/api/report/latest", "/api/cron/monitor"])
def test_data_routes_require_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer errada"}).status_code == 401
    assert client.get(path, headers=AUTH).status_code == 200


def test_fails_closed_on_vercel_without_key(client, monkeypatch):
    monkeypatch.delenv("ENGINE_API_KEY", raising=False)
    monkeypatch.delenv("CRON_SECRET", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert client.get("/api/monitor/status").status_code == 503


def test_reconcile_refuses_when_cv_is_unavailable(client, monkeypatch):
    for var in ("CV_CRM_URL", "CV_CRM_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    res = client.post("/api/reconcile", json={"start_date": "2026-07-20", "end_date": "2026-07-27"}, headers=AUTH)
    assert res.status_code == 424
    assert "CV" in res.json()["detail"]


def test_reconcile_with_simulation_returns_report_and_source_status(client, monkeypatch):
    monkeypatch.setenv("ALLOW_SIMULATION", "1")
    res = client.post("/api/reconcile", json={"start_date": "2026-07-20", "end_date": "2026-07-27"}, headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["report"]["total_source_leads"] > 0
    assert {s["source"] for s in body["sources"]} >= {"meta_ads", "cv_crm"}
    assert all(s["status"] == "simulated" for s in body["sources"])


def test_reconcile_rejects_bad_dates(client):
    assert client.post("/api/reconcile", json={"start_date": "xx"}, headers=AUTH).status_code == 422
    res = client.post("/api/reconcile", json={"start_date": "2026-08-01", "end_date": "2026-07-01"}, headers=AUTH)
    assert res.status_code == 422


def test_monitor_tick_then_reset(client, monkeypatch):
    monkeypatch.setenv("ALLOW_SIMULATION", "1")  # modo demo local
    for var in ("META_ACCESS_TOKEN", "GOOGLE_ADS_DEVELOPER_TOKEN", "RD_STATION_API_TOKEN", "BEEVIRAL_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    body = client.post("/api/monitor/tick", headers=AUTH).json()
    assert body["stats"]["total"] == 1
    assert body["mode"] == "demo"

    # Segundo tick dentro de 60s não avança o ciclo
    assert client.post("/api/monitor/tick", headers=AUTH).json()["stats"]["total"] == 1

    client.post("/api/monitor/reset", headers=AUTH)
    assert client.get("/api/monitor/status", headers=AUTH).json()["stats"]["total"] == 0


def test_memory_store_lock_is_exclusive():
    s = store_module.MemoryStore()
    assert s.acquire_lock("x", 30)
    assert not s.acquire_lock("x", 30)
    s.release_lock("x")
    assert s.acquire_lock("x", 30)
