import httpx
import pytest

from gaffer.config import BASE_URL, MAX_RETRIES
from gaffer.fpl_client import FPLClient


def _client(handler) -> FPLClient:
    transport = httpx.MockTransport(handler)
    return FPLClient(client=httpx.Client(base_url=BASE_URL, transport=transport))


def test_429_honours_retry_after_then_succeeds(no_sleep) -> None:
    calls = {"n": 0}

    # Mock out a single 429 response followed by success
    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={})
        return httpx.Response(200, json={"ok": True})

    result = _client(handler).bootstrap_static()
    assert result == {"ok": True}
    assert calls["n"] == 2  # one 429, one success


def test_5xx_backs_off_then_succeeds(no_sleep) -> None:
    calls = {"n": 0}

    # Mock out a single backoff followed by success (i.e retrying works)
    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    result = _client(handler).bootstrap_static()
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_404_raises_immediately_zero_retries(no_sleep) -> None:
    calls = {"n": 0}

    # Mock out situation with a client error 404
    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        _client(handler).bootstrap_static()

    assert calls["n"] == 1  # no retry on a client error


def test_retries_exhaust_then_last_error_propagates(no_sleep) -> None:
    calls = {"n": 0}

    # Mock out situation where we're always getting 500 responses
    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)  # never recovers

    with pytest.raises(httpx.HTTPStatusError):
        _client(handler).bootstrap_static()

    assert calls["n"] == MAX_RETRIES + 1  # initial try + MAX_RETRIES retries
