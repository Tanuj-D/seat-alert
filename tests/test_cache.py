import pytest

from app.cache import TTLCache


def test_returns_cached_value_until_expiry(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("app.cache.time.monotonic", lambda: now[0])
    cache, calls = TTLCache(ttl_seconds=60), []

    def compute():
        calls.append(1)
        return len(calls)

    assert cache.get_or_set("k", compute) == 1
    assert cache.get_or_set("k", compute) == 1
    now[0] = 61
    assert cache.get_or_set("k", compute) == 2


def test_errors_are_not_cached():
    cache = TTLCache(ttl_seconds=60)
    with pytest.raises(RuntimeError):
        cache.get_or_set("k", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert cache.get_or_set("k", lambda: "ok") == "ok"
