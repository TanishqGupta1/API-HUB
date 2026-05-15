"""X-Orchestrator-Key auth dependency. Env-driven for V1 (see M1 plan T12)."""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status


_KEY_ENV_PREFIX = "INTEGRATION_KEY_"


@dataclass(frozen=True)
class OrchestratorContext:
    """Matched key_id + the raw header value (never log raw_key)."""

    key_id: str
    raw_key: str


def _find_matching_key(provided: str) -> str | None:
    """Constant-time scan of INTEGRATION_KEY_* env vars; returns key_id or None."""
    if not provided:
        return None
    for name, val in os.environ.items():
        if not name.startswith(_KEY_ENV_PREFIX):
            continue
        if not val:
            continue
        if hmac.compare_digest(provided.encode("utf-8"), val.encode("utf-8")):
            return name[len(_KEY_ENV_PREFIX):]
    return None


async def require_orchestrator_key(
    x_orchestrator_key: Annotated[
        str | None, Header(alias="X-Orchestrator-Key")
    ] = None,
) -> OrchestratorContext:
    """401 missing / 403 invalid / OrchestratorContext on match."""
    if not x_orchestrator_key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "BAD_SIGNATURE", "message": "Missing X-Orchestrator-Key"},
        )
    key_id = _find_matching_key(x_orchestrator_key)
    if not key_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "BAD_SIGNATURE", "message": "Invalid X-Orchestrator-Key"},
        )
    return OrchestratorContext(key_id=key_id, raw_key=x_orchestrator_key)
