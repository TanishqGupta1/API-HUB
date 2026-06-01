import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, status
from slowapi import Limiter


def _client_ip(request) -> str:
    """Client IP for rate limiting. Behind the ALB the real client is the
    right-most X-Forwarded-For entry; fall back to the socket peer.

    Deploy note: uvicorn must be started with --proxy-headers
    --forwarded-allow-ips="<ALB-subnet-CIDR>" so it trusts the XFF header
    only from the load balancer. A Redis backend is required for a true
    shared limit across workers; in-process bucket is per-worker only.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_client_ip)


# ── Per-email login limiter ────────────────────────────────────────────────
# Independent of the per-IP limit so a distributed attacker spraying one
# password across many IPs is still capped per-account. In-process sliding
# window; a Redis backend is required for a true shared limit across workers
# (tracked as follow-up to plan Task 7).

_EMAIL_WINDOW_SECONDS = 15 * 60   # 15 minutes
_EMAIL_MAX_ATTEMPTS = 5           # per email per window

_email_attempts: dict[str, deque] = {}
_email_lock = Lock()


def enforce_email_login_limit(email: str) -> None:
    """Raise 429 if `email` has exceeded the login-attempt window.

    Call BEFORE the password verify. Both wrong-password attempts and
    nonexistent emails count, so an attacker can't use the endpoint to
    probe valid emails while also exhausting the bucket.
    """
    now = time.monotonic()
    key = email.strip().lower()
    cutoff = now - _EMAIL_WINDOW_SECONDS
    with _email_lock:
        bucket = _email_attempts.setdefault(key, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _EMAIL_MAX_ATTEMPTS:
            retry_in = int(bucket[0] + _EMAIL_WINDOW_SECONDS - now)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts for this account — try again in {retry_in}s",
                headers={"Retry-After": str(max(retry_in, 1))},
            )
        bucket.append(now)
