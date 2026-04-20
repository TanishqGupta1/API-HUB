"""Self-running smoke tests for RESTConnectorClient — matches the project's
`test_route.py` style (no pytest infra yet).

Run: python test_rest_connector.py
"""

import asyncio
import sys

import httpx

from modules.rest_connector.client import (
    RESTConnectorAuthError,
    RESTConnectorClient,
    RESTConnectorHTTPError,
)


def _transport(handler):
    return httpx.MockTransport(handler)


def _client(transport, max_retries=3):
    return RESTConnectorClient(
        "https://api.example.com/V2",
        {"account_number": "acct", "api_key": "key"},
        max_retries=max_retries,
        transport=transport,
    )


async def test_happy_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[{"sku": "AA1070"}])

    c = _client(_transport(handler))
    result = await c.get_products()

    assert result == [{"sku": "AA1070"}], result
    assert captured["path"] == "/V2/Products/", captured
    assert captured["auth"] and captured["auth"].startswith("Basic "), captured


async def test_all_three_paths():
    hits = []

    def handler(request):
        hits.append(request.url.path)
        return httpx.Response(200, json=[])

    c = _client(_transport(handler))
    await c.get_products()
    await c.get_styles()
    await c.get_categories()
    assert hits == ["/V2/Products/", "/V2/Styles/", "/V2/Categories/"], hits


async def test_retry_on_500_then_succeed():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json=[{"ok": True}])

    c = _client(_transport(handler), max_retries=3)
    result = await c.get_products()
    assert result == [{"ok": True}], result
    assert attempts["n"] == 3, attempts


async def test_retry_exhausted_on_persistent_500():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(503, text="down")

    c = _client(_transport(handler), max_retries=2)
    try:
        await c.get_products()
    except RESTConnectorHTTPError as exc:
        assert exc.status_code == 503, exc.status_code
        assert attempts["n"] == 2, attempts
    else:
        raise AssertionError("expected RESTConnectorHTTPError")


async def test_no_retry_on_401():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(401, text="unauthorized")

    c = _client(_transport(handler), max_retries=5)
    try:
        await c.get_products()
    except RESTConnectorHTTPError as exc:
        assert exc.status_code == 401, exc.status_code
        assert attempts["n"] == 1, ("client errors must not retry", attempts)
    else:
        raise AssertionError("expected RESTConnectorHTTPError")


async def test_retry_on_429():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json=[])

    c = _client(_transport(handler), max_retries=3)
    await c.get_products()
    assert attempts["n"] == 2, attempts


def test_missing_auth_keys():
    try:
        RESTConnectorClient("https://x", {"account_number": "acct"})
    except RESTConnectorAuthError as exc:
        assert "api_key" in str(exc), exc
    else:
        raise AssertionError("expected RESTConnectorAuthError")


def test_empty_base_url():
    try:
        RESTConnectorClient("", {"account_number": "a", "api_key": "k"})
    except ValueError as exc:
        assert "base_url" in str(exc), exc
    else:
        raise AssertionError("expected ValueError")


ASYNC_TESTS = [
    test_happy_path,
    test_all_three_paths,
    test_retry_on_500_then_succeed,
    test_retry_exhausted_on_persistent_500,
    test_no_retry_on_401,
    test_retry_on_429,
]
SYNC_TESTS = [test_missing_auth_keys, test_empty_base_url]


async def main():
    # Speed up tests by collapsing the backoff sleep.
    from modules.rest_connector import client as mod
    mod.RETRY_BACKOFF_BASE = 0.01  # type: ignore[misc]

    failed = 0
    for t in ASYNC_TESTS:
        try:
            await t()
            print(f"ok   {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc!r}")
    for t in SYNC_TESTS:
        try:
            t()
            print(f"ok   {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc!r}")

    total = len(ASYNC_TESTS) + len(SYNC_TESTS)
    print(f"\n{total - failed}/{total} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
