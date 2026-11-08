from app.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks():
    rl = RateLimiter(limit=2, window_seconds=60)
    assert [rl.allow("ip") for _ in range(3)] == [True, True, False]


def test_keys_are_independent():
    rl = RateLimiter(limit=1, window_seconds=60)
    assert rl.allow("a") and rl.allow("b")


def test_window_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.ratelimit.time.monotonic", lambda: now[0])
    rl = RateLimiter(limit=1, window_seconds=10)
    assert rl.allow("ip")
    assert not rl.allow("ip")
    now[0] += 11
    assert rl.allow("ip")
