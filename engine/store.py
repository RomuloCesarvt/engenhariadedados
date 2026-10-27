"""
Persistência de estado para o ambiente serverless (Vercel).

Funções serverless não compartilham memória entre requisições, então o estado do
monitor ao vivo e o último relatório precisam ficar num armazenamento externo.
Usa Upstash Redis via REST (integração gratuita do Marketplace da Vercel).
Sem credenciais, cai para memória do processo — suficiente apenas para
desenvolvimento local.
"""

import json
import os
import threading
import time
from typing import Any, Dict, Optional


class MemoryStore:
    kind = "memory"
    persistent = False

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._locks: Dict[str, float] = {}
        self._mutex = threading.Lock()

    def get_json(self, key: str) -> Optional[Any]:
        with self._mutex:
            return json.loads(self._data[key]) if key in self._data else None

    def set_json(self, key: str, value: Any) -> None:
        with self._mutex:
            self._data[key] = json.dumps(value, ensure_ascii=False, default=str)

    def acquire_lock(self, name: str, ttl_seconds: int) -> bool:
        with self._mutex:
            now = time.time()
            if self._locks.get(name, 0) > now:
                return False
            self._locks[name] = now + ttl_seconds
            return True

    def release_lock(self, name: str) -> None:
        with self._mutex:
            self._locks.pop(name, None)


class UpstashStore:
    """Cliente mínimo da API REST do Upstash Redis (sem dependências além de httpx)."""

    kind = "upstash"
    persistent = True

    def __init__(self, url: str, token: str):
        import httpx

        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

    def _command(self, *args: Any) -> Any:
        res = self._client.post("/", json=[str(a) for a in args])
        res.raise_for_status()
        body = res.json()
        if "error" in body:
            raise RuntimeError(f"Upstash: {body['error']}")
        return body.get("result")

    def get_json(self, key: str) -> Optional[Any]:
        raw = self._command("GET", key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any) -> None:
        self._command("SET", key, json.dumps(value, ensure_ascii=False, default=str))

    def acquire_lock(self, name: str, ttl_seconds: int) -> bool:
        return self._command("SET", f"lock:{name}", "1", "NX", "EX", ttl_seconds) == "OK"

    def release_lock(self, name: str) -> None:
        self._command("DEL", f"lock:{name}")


_store: Optional[Any] = None


def _rest_credentials() -> Optional[tuple]:
    # A integração do Marketplace injeta KV_REST_API_*; o Upstash direto usa UPSTASH_REDIS_REST_*
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    return (url, token) if url and token else None


def get_store():
    global _store
    if _store is None:
        creds = _rest_credentials()
        _store = UpstashStore(*creds) if creds else MemoryStore()
    return _store


def reset_store_for_tests() -> None:
    global _store
    _store = None
