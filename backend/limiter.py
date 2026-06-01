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
