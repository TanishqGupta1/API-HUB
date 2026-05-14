"""Integration Gateway core — prepare_push_intent() + execute_push().

Stub swap guide (replace when parallel tasks merge):
  Task 6 → replace _stub_build_push_payload with: from .payload_builder import build_push_payload
  Task 7 → replace _stub_run_preflight with:       from .preflight import run_preflight
  Task 4 → replace _stub_ops_client with real OPSClient mutation methods
  Task 5 → replace _stub_fake_ops_client with:     from .fake_ops_client import FakeOpsClient
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import async_session
from modules.catalog.models import Product, CustomerProductSelection
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.integrations.schemas import PushRequest, PushRequestAccepted, PushRequestLinks
from modules.markup.engine import calculate_price
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping
from modules.suppliers.models import Supplier

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stubs — swap these out when parallel tasks merge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _PreflightStub:
    blockers: list[str] = []
    warnings: list[str] = []


async def _stub_run_preflight(product, customer, db) -> _PreflightStub:
    """TODO Task 7: replace with → from .preflight import run_preflight"""
    logger.warning("preflight stub active — Task 7 not yet merged")
    return _PreflightStub()


class _PushPayloadStub:
    def __init__(self, product, customer, markup_rules, push_mappings):
        self._product = product
        self._customer = customer

    def mutation_plan(self) -> list[dict]:
        return [{"step": 1, "mutation": "setProduct", "variables": {"stub": True}}]

    def payload_hash(self) -> str:
        raw = json.dumps({
            "product_id": str(self._product.id),
            "customer_id": str(self._customer.id),
        }, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


def _stub_build_push_payload(product, customer, markup_rules, push_mappings) -> _PushPayloadStub:
    """TODO Task 6: replace with → from .payload_builder import build_push_payload"""
    logger.warning("payload_builder stub active — Task 6 not yet merged")
    return _PushPayloadStub(product, customer, markup_rules, push_mappings)


class _StubOpsClient:
    """TODO Task 4: replace with real OPSClient mutation methods"""
    async def set_product_category(self, input: dict) -> dict:
        logger.warning("OpsClient stub — Task 4 not yet merged")
        return {"products_id": 99001}

    async def set_product(self, input: dict) -> dict:
        return {"products_id": 99001}

    async def set_product_size(self, input: dict) -> dict:
        return {"products_id": 99001, "size_id": 1}

    async def set_product_price(self, input: dict) -> dict:
        return {}

    async def set_assign_options(self, input: dict) -> dict:
        return {}

    async def set_product_design(self, input: dict) -> dict:
        return {}


class _StubFakeOpsClient:
    """TODO Task 5: replace with → from .fake_ops_client import FakeOpsClient"""
    def __init__(self):
        self.calls: list[dict] = []
        self._counter = 10000

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    async def set_product_category(self, input: dict) -> dict:
        r = {"products_id": 1}
        self.calls.append({"method": "set_product_category", "input": input, "response": r})
        return r

    async def set_product(self, input: dict) -> dict:
        r = {"products_id": self._next_id()}
        self.calls.append({"method": "set_product", "input": input, "response": r})
        return r

    async def set_product_size(self, input: dict) -> dict:
        r = {"products_id": self._counter, "size_id": self._next_id()}
        self.calls.append({"method": "set_product_size", "input": input, "response": r})
        return r

    async def set_product_price(self, input: dict) -> dict:
        r = {}
        self.calls.append({"method": "set_product_price", "input": input, "response": r})
        return r

    async def set_assign_options(self, input: dict) -> dict:
        r = {}
        self.calls.append({"method": "set_assign_options", "input": input, "response": r})
        return r

    async def set_product_design(self, input: dict) -> dict:
        r = {}
        self.calls.append({"method": "set_product_design", "input": input, "response": r})
        return r


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _redact_auth(steps: list[dict]) -> list[dict]:
    """Redact Authorization header values before persisting to step_results."""
    out = []
    for step in steps:
        s = dict(step)
        headers = s.get("headers", {})
        if headers:
            s["headers"] = {
                k: ("Bearer ***" if k.lower() == "authorization" else v)
                for k, v in headers.items()
            }
        out.append(s)
    return out


async def _fire_callback(push_log_id: str, callback_url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                callback_url,
                json=payload,
                headers={"X-ApiHub-Event": "push.completed"},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning("callback failed push_log=%s err=%s", push_log_id, e)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core gateway functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def prepare_push_intent(
    req: PushRequest,
    key: IntegrationKey,
    db: AsyncSession,
    idempotency_key: Optional[str] = None,
) -> PushRequestAccepted:
    """Stage 1: validate, idempotency check, preflight, insert push_log row.

    Returns immediately with push_log_id + status=accepted.
    execute_push() is called after this (sync or background).
    """
    customer_id = req.target.customer_id
    supplier_slug = req.source.supplier_slug
    supplier_sku = req.product_ref.supplier_sku

    # ── Resolve customer ──
    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )).scalar_one_or_none()
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Customer {customer_id} not found"
        })

    # ── Resolve supplier + product ──
    supplier = (await db.execute(
        select(Supplier).where(Supplier.slug == supplier_slug)
    )).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Supplier '{supplier_slug}' not found"
        })

    product = (await db.execute(
        select(Product)
        .options(selectinload(Product.variants), selectinload(Product.images))
        .where(Product.supplier_sku == supplier_sku, Product.supplier_id == supplier.id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Product '{supplier_sku}' not found in catalog"
        })

    # ── Build payload + compute hash ──
    builder = _stub_build_push_payload(product, customer, [], [])
    payload_hash = builder.payload_hash()

    # ── Idempotency check ──
    existing = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.key_id == key.id,
            ProductPushLog.idempotency_key == idempotency_key,
        )
    )).scalar_one_or_none() if idempotency_key else None

    if existing:
        if existing.payload_hash == payload_hash:
            # Same key + same body → return existing (idempotent replay)
            return PushRequestAccepted(
                push_log_id=existing.id,
                status=existing.status,
                customer_id=customer_id,
                supplier_slug=supplier_slug,
                supplier_sku=supplier_sku,
                ops_product_id=existing.ops_product_id,
                dry_run=existing.dry_run,
                callback_status=existing.callback_status,
                created_at=existing.pushed_at,
                links=PushRequestLinks(self=f"/api/integrations/v1/push-requests/{existing.id}"),
            )
        else:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "Same Idempotency-Key was used with a different payload"
            })

    # ── Concurrency guard ──
    in_flight = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id == product.id,
            ProductPushLog.status == "processing",
        )
    )).scalar_one_or_none()
    if in_flight:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "IN_FLIGHT",
            "message": "Another push for this product is currently processing"
        })

    # ── Preflight ──
    preflight = await _stub_run_preflight(product, customer, db)
    if preflight.blockers:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
            "code": "PREFLIGHT_BLOCKER",
            "message": f"Preflight failed: {', '.join(preflight.blockers)}",
            "details": {"blockers": preflight.blockers, "warnings": preflight.warnings},
        })

    # ── Insert push_log row ──
    now = datetime.now(timezone.utc)
    push_log = ProductPushLog(
        product_id=product.id,
        customer_id=customer_id,
        status="accepted",
        pushed_at=now,
        key_id=key.id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        supplier_slug=supplier_slug,
        supplier_sku=supplier_sku,
        callback_url=req.callback.url if req.callback else None,
        callback_status="pending" if req.callback else "not_requested",
        dry_run=req.dry_run,
    )
    db.add(push_log)
    await db.commit()
    await db.refresh(push_log)

    return PushRequestAccepted(
        push_log_id=push_log.id,
        status="accepted",
        customer_id=customer_id,
        supplier_slug=supplier_slug,
        supplier_sku=supplier_sku,
        dry_run=req.dry_run,
        callback_status=push_log.callback_status,
        created_at=push_log.pushed_at,
        links=PushRequestLinks(self=f"/api/integrations/v1/push-requests/{push_log.id}"),
    )


async def execute_push(push_log_id: uuid_mod.UUID) -> None:
    """Stage 2: execute mutation plan against OPS (or FakeOpsClient for dry_run).

    Runs synchronously for ≤20 variants, or as a BackgroundTask for >20.
    Uses its own DB session — safe to run detached from the request session.
    """
    async with async_session() as db:
        push_log = await db.get(ProductPushLog, push_log_id)
        if not push_log:
            logger.error("execute_push: push_log %s not found", push_log_id)
            return

        # ── Atomic transition: accepted → processing ──
        result = await db.execute(
            update(ProductPushLog)
            .where(ProductPushLog.id == push_log_id, ProductPushLog.status == "accepted")
            .values(status="processing")
            .returning(ProductPushLog.id)
        )
        if not result.fetchone():
            logger.warning("execute_push: push_log %s not in accepted state", push_log_id)
            return
        await db.commit()

        product = (await db.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.images))
            .where(Product.id == push_log.product_id)
        )).scalar_one_or_none()
        customer = await db.get(Customer, push_log.customer_id)

        # ── Select client ──
        client = _StubFakeOpsClient() if push_log.dry_run else _StubOpsClient()

        # ── Build mutation plan ──
        builder = _stub_build_push_payload(product, customer, [], [])
        plan = builder.mutation_plan()

        step_results: list[dict] = []
        ops_product_id: Optional[str] = None
        final_status = "pushed" if not push_log.dry_run else "dry_run_pushed"
        cleanup_targets: Optional[dict] = None

        # ── Execute plan sequentially ──
        for step in plan:
            mutation = step.get("mutation", "")
            variables = step.get("variables", {})
            t_start = datetime.now(timezone.utc)
            try:
                method = getattr(client, _mutation_to_method(mutation), None)
                if method is None:
                    raise NotImplementedError(f"No client method for {mutation}")
                resp = await method(variables)
                latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
                if "products_id" in resp:
                    ops_product_id = str(resp["products_id"])
                step_results.append({
                    "step": mutation,
                    "ok": True,
                    "ops_id": ops_product_id,
                    "latency_ms": latency,
                    "called_at": t_start.isoformat(),
                })
            except Exception as e:
                latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
                step_results.append({
                    "step": mutation,
                    "ok": False,
                    "error": str(e),
                    "latency_ms": latency,
                    "called_at": t_start.isoformat(),
                })
                cleanup_targets = {"ops_product_id": ops_product_id, "failed_at": mutation}
                final_status = "partial_failure" if ops_product_id else "failed"
                break

        # ── Persist results ──
        push_log.step_results = _redact_auth(step_results)
        push_log.status = final_status
        push_log.cleanup_targets = cleanup_targets
        if ops_product_id and final_status == "pushed":
            push_log.ops_product_id = ops_product_id

        # ── Upsert push_mappings (live push only) ──
        if final_status == "pushed":
            existing_mapping = (await db.execute(
                select(PushMapping).where(
                    PushMapping.source_product_id == push_log.product_id,
                    PushMapping.customer_id == push_log.customer_id,
                )
            )).scalar_one_or_none()
            if existing_mapping:
                existing_mapping.target_ops_product_id = ops_product_id
            else:
                db.add(PushMapping(
                    source_product_id=push_log.product_id,
                    customer_id=push_log.customer_id,
                    target_ops_product_id=ops_product_id,
                ))

            # Update customer-catalog selection
            sel = (await db.execute(
                select(CustomerProductSelection).where(
                    CustomerProductSelection.customer_id == push_log.customer_id,
                    CustomerProductSelection.product_id == push_log.product_id,
                )
            )).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if sel:
                sel.status = "pushed"
                sel.pushed_at = now
            else:
                db.add(CustomerProductSelection(
                    customer_id=push_log.customer_id,
                    product_id=push_log.product_id,
                    status="pushed",
                    added_at=now,
                    pushed_at=now,
                ))

        await db.commit()

        # ── Fire callback ──
        if push_log.callback_url and push_log.callback_status == "pending":
            success = await _fire_callback(
                str(push_log_id),
                push_log.callback_url,
                {
                    "event": "push.completed",
                    "push_log_id": str(push_log_id),
                    "status": final_status,
                    "ops_product_id": ops_product_id,
                    "supplier_sku": push_log.supplier_sku,
                },
            )
            push_log.callback_status = "sent" if success else "failed"
            push_log.callback_attempts = 1
            await db.commit()


def _mutation_to_method(mutation: str) -> str:
    mapping = {
        "setProductCategory": "set_product_category",
        "setProduct": "set_product",
        "setProductSize": "set_product_size",
        "setProductPrice": "set_product_price",
        "setAssignOptions": "set_assign_options",
        "setProductDesign": "set_product_design",
    }
    return mapping.get(mutation, mutation)
