"""Phase 5 — translation cache + /api/translate tests with stub translator."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app
from app.translation.base import NoopTranslator, TranslationFailureError, Translator
from app.translation.cache import TranslationCache

# --------------------------------------------------------------- cache


def test_cache_returns_set_value() -> None:
    cache = TranslationCache(ttl_seconds=60.0)
    cache.set(("en", "ru", "hello"), "привет")
    assert cache.get(("en", "ru", "hello")) == "привет"


def test_cache_miss_returns_none() -> None:
    cache = TranslationCache()
    assert cache.get(("en", "ru", "x")) is None


def test_cache_expires_after_ttl() -> None:
    cache = TranslationCache(ttl_seconds=0.0001)
    cache.set(("en", "ru", "hello"), "привет")
    time.sleep(0.002)
    assert cache.get(("en", "ru", "hello")) is None


def test_cache_lru_evicts_oldest_first() -> None:
    cache = TranslationCache(max_entries=2)
    cache.set(("en", "ru", "a"), "1")
    cache.set(("en", "ru", "b"), "2")
    cache.set(("en", "ru", "c"), "3")
    # "a" should have been evicted (LRU).
    assert cache.get(("en", "ru", "a")) is None
    assert cache.get(("en", "ru", "b")) == "2"
    assert cache.get(("en", "ru", "c")) == "3"


def test_cache_get_marks_recent() -> None:
    cache = TranslationCache(max_entries=2)
    cache.set(("en", "ru", "a"), "1")
    cache.set(("en", "ru", "b"), "2")
    # Access "a" → "b" becomes oldest.
    cache.get(("en", "ru", "a"))
    cache.set(("en", "ru", "c"), "3")
    assert cache.get(("en", "ru", "b")) is None
    assert cache.get(("en", "ru", "a")) == "1"
    assert cache.get(("en", "ru", "c")) == "3"


# --------------------------------------------------------------- HTTP route


class _CountingStub:
    """Translator stub that counts calls so we can verify caching."""

    def __init__(self) -> None:
        self.calls = 0

    async def translate(self, text: str, src: str, dst: str) -> str:
        self.calls += 1
        return f"<{src}→{dst}>{text}"


class _FailingStub:
    async def translate(self, text: str, src: str, dst: str) -> str:
        raise TranslationFailureError("upstream_failure")


def test_translate_endpoint_returns_translated_text() -> None:
    with TestClient(app) as client:
        # Override the lifespan-installed translator with our stub.
        stub = _CountingStub()
        app.state.translator = stub
        app.state.translation_cache = TranslationCache()
        r = client.post("/api/translate", json={"text": "hello", "src": "en", "dst": "ru"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["translated"] == "<en→ru>hello"
        assert body["provider"] == "_CountingStub"


def test_translate_endpoint_uses_cache_on_repeat() -> None:
    with TestClient(app) as client:
        stub = _CountingStub()
        app.state.translator = stub
        app.state.translation_cache = TranslationCache()

        r1 = client.post("/api/translate", json={"text": "hello", "src": "en", "dst": "ru"})
        r2 = client.post("/api/translate", json={"text": "hello", "src": "en", "dst": "ru"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert stub.calls == 1
        assert r2.json()["provider"] == "cache"


def test_translate_endpoint_handles_upstream_failure() -> None:
    with TestClient(app) as client:
        app.state.translator = _FailingStub()
        app.state.translation_cache = TranslationCache()
        r = client.post("/api/translate", json={"text": "hi", "src": "en", "dst": "ru"})
        assert r.status_code == 502
        assert r.json()["detail"]["error"]["code"] == "upstream_failure"


def test_same_language_pair_passes_through() -> None:
    with TestClient(app) as client:
        app.state.translator = _CountingStub()
        app.state.translation_cache = TranslationCache()
        r = client.post("/api/translate", json={"text": "hello", "src": "en", "dst": "en"})
        assert r.status_code == 200
        assert r.json()["translated"] == "hello"
        assert r.json()["provider"] == "passthrough"


def test_translate_endpoint_rejects_too_long_text() -> None:
    with TestClient(app) as client:
        app.state.translator = _CountingStub()
        app.state.translation_cache = TranslationCache()
        long_text = "x" * 600
        r = client.post("/api/translate", json={"text": long_text, "src": "en", "dst": "ru"})
        assert r.status_code == 422  # pydantic validation


async def test_noop_translator_echoes() -> None:
    t = NoopTranslator()
    assert await t.translate("hello", "en", "ru") == "[en>ru] hello"


def test_translator_protocol_is_satisfied_by_noop() -> None:
    t: Translator = NoopTranslator()  # just for type assignment
    assert t is not None
