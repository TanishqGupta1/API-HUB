from __future__ import annotations

import logging
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from database import async_session
from modules.audit_log.models import AuditLog
from modules.auth.security import decode_token

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if request.method not in _WRITE_METHODS:
            return response

        path = request.url.path
        # Skip ingest and auth routes — too noisy / pre-auth
        if path.startswith("/api/ingest") or path.startswith("/api/auth/login") or path.startswith("/api/auth/refresh"):
            return response

        user_email: str | None = None
        user_id: str | None = None
        # Cookie is the primary auth path (Phase 14c). Bearer kept as a
        # fallback for any service-to-service caller that may still use it.
        token = request.cookies.get("auth_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if token:
            try:
                payload = decode_token(token)
                user_email = payload.get("email")   # email claim added in _token_payload
                user_id = payload.get("sub")         # sub is the user UUID
            except Exception:
                pass

        try:
            async with async_session() as db:
                db.add(AuditLog(
                    user_email=user_email,
                    user_id=user_id,
                    method=request.method,
                    path=path,
                    status_code=response.status_code,
                    created_at=datetime.now(timezone.utc),
                ))
                await db.commit()
        except Exception:
            logger.exception("audit log write failed")

        return response
