"""Rate-limit key derivation honors X-Forwarded-For behind a proxy."""
import types

import pytest

from limiter import _client_ip


@pytest.mark.no_db
def test_client_ip_prefers_xff_rightmost():
    req = types.SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"},
        client=types.SimpleNamespace(host="10.0.0.1"),
    )
    # Right-most entry is the most-recently-added hop (real client behind ALB)
    assert _client_ip(req) == "10.0.0.1"


@pytest.mark.no_db
def test_client_ip_falls_back_to_peer():
    req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="198.51.100.9"))
    assert _client_ip(req) == "198.51.100.9"


@pytest.mark.no_db
def test_client_ip_no_client():
    req = types.SimpleNamespace(headers={}, client=None)
    assert _client_ip(req) == "127.0.0.1"
