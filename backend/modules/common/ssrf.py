"""SSRF guard shared by every code path that fetches a URL from DB/user input.

Blocks non-http(s) schemes and hosts that resolve to private / loopback /
link-local / reserved IPs (cloud metadata 169.254.169.254, localhost,
RFC-1918, etc.). Validates ALL resolved records, not just the first.
"""
import ipaddress
import socket
from urllib.parse import urlparse

# CGNAT range (RFC 6598) — Python's ip.is_private doesn't include this, but
# many cloud / on-prem environments use 100.64/10 for internal services that
# should never be reachable from server-side fetches.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _is_disallowed(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return True
    # ipaddress.IPv4Address has __contains__ via the network; check both families.
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return True
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) — re-check the embedded v4 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_disallowed(ip.ipv4_mapped)
    return False


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
        if _is_disallowed(ip):
            raise ValueError(f"URL resolves to a disallowed address ({ip}) — SSRF guard")
