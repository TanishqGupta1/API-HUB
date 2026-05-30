"""SSRF guard shared by every code path that fetches a URL from DB/user input.

Blocks non-http(s) schemes and hosts that resolve to private / loopback /
link-local / reserved IPs (cloud metadata 169.254.169.254, localhost,
RFC-1918, etc.). Validates ALL resolved records, not just the first.
"""
import ipaddress
import socket
from urllib.parse import urlparse


def assert_safe_url(url: str) -> None:
    """Raise ValueError if `url` must not be fetched from server-side code."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"URL resolves to a disallowed address ({ip}) — SSRF guard")
