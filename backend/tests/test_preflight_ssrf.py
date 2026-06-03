"""SSRF guard on check_image_urls_reachable — no outbound request for blocked URLs."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.ops_push import preflight
from modules.ops_push.preflight import _PreflightContext

pytestmark = pytest.mark.no_db


def _make_ctx(*urls: str) -> _PreflightContext:
    """Minimal context with only the images list populated."""
    images = [MagicMock(url=u) for u in urls]
    return _PreflightContext(
        customer=MagicMock(),
        product=MagicMock(),
        supplier=MagicMock(),
        variants=[],
        images=images,
        options=[],
        markup_rules=[],
        push_mapping=None,
        push_mapping_options=[],
        decoration_options=[],
    )


@pytest.mark.asyncio
async def test_metadata_url_blocked_before_probe():
    """AWS metadata endpoint must be blocked; HEAD must never fire."""
    probed: list[str] = []

    async def _fake_head(url: str, **_):
        probed.append(url)
        raise AssertionError("HEAD must not run on a blocked URL")

    with patch.object(preflight.httpx, "AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.head.side_effect = _fake_head
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await preflight.check_image_urls_reachable(
            _make_ctx("http://169.254.169.254/latest/meta-data/"),
            dry_run=False,
            timeout_seconds=1.0,
        )

    assert result.ok is False
    assert probed == []
    assert "BlockedURL" in result.detail or "blocked" in result.detail.lower()


@pytest.mark.asyncio
async def test_private_ip_blocked_before_probe():
    """RFC-1918 private IPs must be blocked without making a request."""
    probed: list[str] = []

    with patch.object(preflight.httpx, "AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.head.side_effect = lambda url, **_: probed.append(url)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await preflight.check_image_urls_reachable(
            _make_ctx("http://192.168.1.100/image.jpg"),
            dry_run=False,
            timeout_seconds=1.0,
        )

    assert result.ok is False
    assert probed == []


@pytest.mark.asyncio
async def test_loopback_blocked_before_probe():
    """Loopback (127.x) must be blocked without making a request."""
    probed: list[str] = []

    with patch.object(preflight.httpx, "AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.head.side_effect = lambda url, **_: probed.append(url)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await preflight.check_image_urls_reachable(
            _make_ctx("http://127.0.0.1/image.jpg"),
            dry_run=False,
            timeout_seconds=1.0,
        )

    assert result.ok is False
    assert probed == []


@pytest.mark.asyncio
async def test_safe_url_passes_through_to_head():
    """A legitimate supplier URL should reach the HEAD probe."""
    probed: list[str] = []

    async def _fake_head(url: str, **_):
        probed.append(url)
        return MagicMock(status_code=200)

    with patch("modules.ops_push.preflight.assert_safe_url", return_value=None):
        with patch.object(preflight.httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.head.side_effect = _fake_head
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await preflight.check_image_urls_reachable(
                _make_ctx("https://cdn.supplier.com/images/pc61-black.jpg"),
                dry_run=False,
                timeout_seconds=1.0,
            )

    assert result.ok is True
    assert len(probed) == 1
