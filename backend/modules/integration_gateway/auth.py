"""X-Orchestrator-Key auth dependency (env-driven for V1).

Reads keys from env vars matching `INTEGRATION_KEY_<key_id>=<raw_secret>`.
Walks every matching env var and uses `hmac.compare_digest` to find one
that matches the header — constant time, no timing leak.

NOTE: parallel to `modules/integrations/auth.py` (Vidhi's DB-backed
variant). Per M1 plan (docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md
§Task 12), env is the source of truth for V1; the DB-backed
`integration_keys` table is deferred. Reconciliation is a separate
follow-up so this task can land independently.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status


_KEY_ENV_PREFIX = "INTEGRATION_KEY_"


@dataclass(frozen=True)
class OrchestratorContext:
    """What the handler receives after a successful key match.

    `raw_key` is included for completeness but must NEVER be logged or
    persisted — it's the live secret that arrived in the header.
    """

    key_id: str
    raw_key: str


def _find_matching_key(provided: str) -> str | None:
    """Walk `INTEGRATION_KEY_*` env vars; return the `key_id` whose value
    matches `provided`. Returns None on no match.

    Uses `hmac.compare_digest` to prevent timing attacks. Empty / missing
    env values are skipped so an unset variable can't masquerade as a
    valid key.
    """
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
    """FastAPI dependency — 401 if missing, 403 if invalid, OrchestratorContext if OK."""
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
