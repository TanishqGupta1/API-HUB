"""Unit tests for FourOverClient.

Covers:
    1. Constructor input validation (missing base_url / keys rejected)
    2. Base URL trailing slash is stripped
    3. _sign() produces the documented HMAC-SHA256 header against a known vector
    4. _request() sends the signed headers + correct URL via httpx.MockTransport
    5. product_uuid is correctly embedded in option-group path

Run:
    cd backend && source .venv/bin/activate
    python test_fourover_client.py
"""

import asyncio
import hashlib
import hmac
import sys
from pathlib import Path

# Allow `python test_fourover_client.py` from backend/ without setting PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

import httpx  # noqa: E402

from modules.rest_connector.fourover_client import FourOverClient  # noqa: E402


# ---------------------------------------------------------------------- #
# Synchronous tests — signature format + validation
# ---------------------------------------------------------------------- #


def test_sign_header_format():
    """Known-input → known-output HMAC-SHA256 signature (RFC 4868)."""
    client = FourOverClient(
        base_url="https://sandbox-api.4over.com",
        auth_config={"api_key": "test_key", "private_key": "test_secret"},
    )
    ts = "2026-04-20T12:00:00Z"
    headers = client._sign("GET", "/printproducts/categories", timestamp=ts)

    expected_sig = hmac.new(
        b"test_secret",
        b"GET/printproducts/categories2026-04-20T12:00:00Z",
        hashlib.sha256,
    ).hexdigest()

    assert headers["X-Timestamp"] == ts, headers
    assert headers["Authorization"] == f"hmac test_key:{expected_sig}", headers
    assert headers["Accept"] == "application/json"
    print(f"  test_sign_header_format OK — sig={expected_sig[:16]}…")


def test_sign_is_deterministic_for_fixed_timestamp():
    """Same inputs → same signature, every time."""
    client = FourOverClient(
        base_url="https://sandbox-api.4over.com",
        auth_config={"api_key": "k", "private_key": "p"},
    )
    a = client._sign("POST", "/printproducts/productquote", timestamp="2026-01-01T00:00:00Z")
    b = client._sign("POST", "/printproducts/productquote", timestamp="2026-01-01T00:00:00Z")
    assert a == b
    print("  test_sign_is_deterministic_for_fixed_timestamp OK")


def test_sign_differs_per_method_and_path():
    """GET vs POST, or different paths, must produce different signatures."""
    client = FourOverClient(
        base_url="https://sandbox-api.4over.com",
        auth_config={"api_key": "k", "private_key": "p"},
    )
    ts = "2026-04-20T12:00:00Z"
    a = client._sign("GET", "/printproducts/categories", timestamp=ts)
    b = client._sign("POST", "/printproducts/categories", timestamp=ts)
    c = client._sign("GET", "/printproducts/products", timestamp=ts)
    assert a["Authorization"] != b["Authorization"], "method change must flip sig"
    assert a["Authorization"] != c["Authorization"], "path change must flip sig"
    print("  test_sign_differs_per_method_and_path OK")


def test_init_validation():
    """Constructor rejects missing base_url, api_key, private_key."""
    cases = [
        {"base_url": "", "auth_config": {"api_key": "k", "private_key": "p"}},
        {"base_url": "https://x", "auth_config": {"api_key": "k"}},
        {"base_url": "https://x", "auth_config": {"private_key": "p"}},
        {"base_url": "https://x", "auth_config": {"api_key": "", "private_key": "p"}},
    ]
    for i, kwargs in enumerate(cases):
        try:
            FourOverClient(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"case {i} should have raised ValueError: {kwargs}")
    print("  test_init_validation OK")


def test_base_url_trailing_slash_stripped():
    client = FourOverClient(
        base_url="https://sandbox-api.4over.com/",
        auth_config={"api_key": "k", "private_key": "p"},
    )
    assert client.base_url == "https://sandbox-api.4over.com"
    print("  test_base_url_trailing_slash_stripped OK")


# ---------------------------------------------------------------------- #
# Async tests — httpx MockTransport
# ---------------------------------------------------------------------- #


async def test_request_sends_signed_headers_and_correct_url():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=[{"category": "brochures"}])

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http:
        client = FourOverClient(
            base_url="https://sandbox-api.4over.com",
            auth_config={"api_key": "test_key", "private_key": "test_secret"},
        )
        result = await client.get_categories(http_client=http)

    assert result == [{"category": "brochures"}]
    assert captured["method"] == "GET"
    assert captured["url"] == "https://sandbox-api.4over.com/printproducts/categories"
    # httpx lowercases header keys in the captured dict
    assert captured["headers"]["authorization"].startswith("hmac test_key:"), captured["headers"]
    assert "x-timestamp" in captured["headers"]
    print("  test_request_sends_signed_headers_and_correct_url OK")


async def test_get_product_options_embeds_uuid_in_path():
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(200, json={"groups": []})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http:
        client = FourOverClient(
            base_url="https://sandbox-api.4over.com",
            auth_config={"api_key": "k", "private_key": "p"},
        )
        await client.get_product_options("abc-123", http_client=http)

    assert captured_paths == ["/printproducts/products/abc-123/optiongroups"], captured_paths
    print("  test_get_product_options_embeds_uuid_in_path OK")


async def test_get_quote_sends_post_with_json_body():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["body"] = request.content
        captured["content_type"] = request.headers.get("content-type")
        return httpx.Response(200, json={"total": 199.99})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http:
        client = FourOverClient(
            base_url="https://sandbox-api.4over.com",
            auth_config={"api_key": "k", "private_key": "p"},
        )
        result = await client.get_quote(
            "uuid-1", {"paper": "glossy", "qty": 500}, http_client=http
        )

    assert result == {"total": 199.99}
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/json"
    assert b"uuid-1" in captured["body"]
    assert b"glossy" in captured["body"]
    print("  test_get_quote_sends_post_with_json_body OK")


async def test_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid signature")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http:
        client = FourOverClient(
            base_url="https://sandbox-api.4over.com",
            auth_config={"api_key": "k", "private_key": "bad"},
        )
        try:
            await client.get_categories(http_client=http)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 401
            print("  test_http_error_propagates OK")
            return

    raise AssertionError("expected HTTPStatusError on 401")


# ---------------------------------------------------------------------- #
# Runner
# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    print("Running FourOverClient tests…\n")

    test_sign_header_format()
    test_sign_is_deterministic_for_fixed_timestamp()
    test_sign_differs_per_method_and_path()
    test_init_validation()
    test_base_url_trailing_slash_stripped()

    asyncio.run(test_request_sends_signed_headers_and_correct_url())
    asyncio.run(test_get_product_options_embeds_uuid_in_path())
    asyncio.run(test_get_quote_sends_post_with_json_body())
    asyncio.run(test_http_error_propagates())

    print("\nAll 9 tests passed ✅")
