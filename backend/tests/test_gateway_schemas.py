"""T14 regression: integration-gateway envelope schemas exist with the names
and shapes that the Rev 3 spec mandates.

These tests are deliberately schema-only — no DB, no route, no HTTP — so they
serve as the contract baseline for downstream tasks (T15, T17-T19) that build
on the envelope.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# PushRequest envelope
# ---------------------------------------------------------------------------

def test_push_request_minimal_valid():
    from modules.integrations.schemas import (
        PushRequest,
        PushRequestTarget,
        PushRequestSource,
        PushRequestProductRef,
    )

    req = PushRequest(
        target=PushRequestTarget(customer_id=uuid4()),
        source=PushRequestSource(supplier_slug="sanmar"),
        product_ref=PushRequestProductRef(product_id=uuid4()),
        dry_run=False,
    )
    assert req.dry_run is False
    assert req.target.system == "ops"
    assert req.callback is None
    assert req.decorations == []


def test_push_request_accepts_product_id_or_supplier_sku():
    """Spec says product_ref may identify a product by either UUID or sku."""
    from modules.integrations.schemas import (
        PushRequest,
        PushRequestTarget,
        PushRequestSource,
        PushRequestProductRef,
    )

    by_pid = PushRequest(
        target=PushRequestTarget(customer_id=uuid4()),
        source=PushRequestSource(supplier_slug="sanmar"),
        product_ref=PushRequestProductRef(product_id=uuid4()),
    )
    by_sku = PushRequest(
        target=PushRequestTarget(customer_id=uuid4()),
        source=PushRequestSource(supplier_slug="sanmar"),
        product_ref=PushRequestProductRef(supplier_sku="PC61"),
    )
    assert by_pid.product_ref.product_id is not None
    assert by_sku.product_ref.supplier_sku == "PC61"


def test_push_request_rejects_missing_target():
    from modules.integrations.schemas import (
        PushRequest,
        PushRequestSource,
        PushRequestProductRef,
    )

    with pytest.raises(ValidationError):
        PushRequest(  # type: ignore[call-arg]
            source=PushRequestSource(supplier_slug="sanmar"),
            product_ref=PushRequestProductRef(supplier_sku="PC61"),
        )


def test_push_request_target_system_locked_to_ops():
    from modules.integrations.schemas import PushRequestTarget

    PushRequestTarget(customer_id=uuid4())  # default system="ops" ok
    with pytest.raises(ValidationError):
        PushRequestTarget(system="legacy", customer_id=uuid4())  # type: ignore[arg-type]


def test_push_request_callback_secret_optional():
    from modules.integrations.schemas import PushRequestCallback

    cb = PushRequestCallback(url="https://n8n.example/done")
    assert cb.secret is None


# ---------------------------------------------------------------------------
# Status envelope
# ---------------------------------------------------------------------------

def test_push_request_status_defaults():
    """PushRequestStatus is the spec-named poll-response envelope."""
    from modules.integrations.schemas import PushRequestStatus

    out = PushRequestStatus(
        push_log_id=uuid4(),
        status="accepted",
        customer_id=uuid4(),
    )
    assert out.callback_attempts == 0
    assert out.step_results is None or out.step_results == []
    assert out.error is None


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

def test_error_envelope_minimal():
    """ErrorEnvelope is the spec name for gateway error responses."""
    from modules.integrations.schemas import ErrorEnvelope

    err = ErrorEnvelope(code="IDEMPOTENCY_CONFLICT", message="payload hash differs")
    assert err.status == "error"
    assert err.code == "IDEMPOTENCY_CONFLICT"
    assert err.details == {} or err.details is None


def test_error_envelope_carries_details_dict():
    from modules.integrations.schemas import ErrorEnvelope

    err = ErrorEnvelope(
        code="PREFLIGHT_BLOCKER",
        message="decoration_required",
        details={"product_id": "abc", "missing": ["decoration"]},
    )
    assert err.details["missing"] == ["decoration"]


# ---------------------------------------------------------------------------
# Backwards-compat aliases — existing call sites use shorter names
# ---------------------------------------------------------------------------

def test_legacy_short_names_still_exported():
    """gateway.py and routes.py import PushTarget/PushSource/PushProductRef;
    keep those as aliases so we don't break the active code paths."""
    from modules.integrations import schemas as s

    assert s.PushTarget is s.PushRequestTarget
    assert s.PushSource is s.PushRequestSource
    assert s.PushProductRef is s.PushRequestProductRef
    assert s.PushCallback is s.PushRequestCallback
