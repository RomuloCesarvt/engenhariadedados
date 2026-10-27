"""
Testes do cliente REST do Upstash Redis (com transporte HTTP simulado).
"""

import json

import httpx

from engine.store import UpstashStore


def make_store(handler):
    store = UpstashStore("https://redis.example.upstash.io", "token")
    store._client = httpx.Client(
        base_url="https://redis.example.upstash.io",
        headers={"Authorization": "Bearer token"},
        transport=httpx.MockTransport(handler),
    )
    return store


def test_set_get_roundtrip_and_auth_header():
    db, seen = {}, []

    def handler(request):
        seen.append(request.headers["authorization"])
        cmd = json.loads(request.content)
        if cmd[0] == "SET":
            db[cmd[1]] = cmd[2]
            return httpx.Response(200, json={"result": "OK"})
        return httpx.Response(200, json={"result": db.get(cmd[1])})

    store = make_store(handler)
    store.set_json("k", {"leads": {"a": 1}, "nome": "João"})
    assert store.get_json("k") == {"leads": {"a": 1}, "nome": "João"}
    assert store.get_json("missing") is None
    assert set(seen) == {"Bearer token"}


def test_lock_uses_set_nx_ex():
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"result": "OK" if len(sent) == 1 else None})

    store = make_store(handler)
    assert store.acquire_lock("monitor", 55) is True
    assert store.acquire_lock("monitor", 55) is False
    assert sent[0] == ["SET", "lock:monitor", "1", "NX", "EX", "55"]
