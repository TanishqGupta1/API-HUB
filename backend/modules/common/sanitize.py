"""Redact credential-shaped substrings before persisting/returning error text."""
import re

_PATTERNS = re.compile(
    r"(bearer\s+\S+"
    r"|client_secret=\S+"
    r"|password=\S+"
    r"|access_token\"?\s*[:=]\s*\"?[\w.\-]+"
    r"|refresh_token\"?\s*[:=]\s*\"?[\w.\-]+)",
    re.IGNORECASE,
)


def sanitize_error(value: object, limit: int = 300) -> str:
    """Return a redacted, length-capped string safe to store or return."""
    return _PATTERNS.sub("[REDACTED]", str(value))[:limit]
