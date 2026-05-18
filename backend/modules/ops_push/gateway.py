"""Integration Gateway core — prepare_push_intent() + execute_push()."""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
from modules.ops_client.client import OpsAuth, OpsGraphQLClient
from modules.ops_push.payload_builder import build_push_payload, compute_payload_hash, _request_fingerprint
from modules.ops_push.preflight import run_preflight
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping
from modules.suppliers.models import Supplier

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Real OPS client — wraps OpsGraphQLClient with the stub method interface
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RealOpsClient:
    """Calls live OPS GraphQL mutations. Variables are pre-resolved dicts."""

    _QUERIES: dict[str, tuple[str, str]] = {
        "set_product_category": (
            "mutation SetProductCategory($input: setProductCategory_input!) {"
            " setProductCategory(input: $input) { category_id } }",
            "setProductCategory",
        ),
        "set_product": (
            "mutation SetProduct($input: setProduct_input!) {"
            " setProduct(input: $input) { products_id } }",
            "setProduct",
        ),
        "set_product_size": (
            "mutation SetProductSize($input: setProductSize_input!) {"
            " setProductSize(input: $input) { size_id } }",
            "setProductSize",
        ),
        "set_product_price": (
            "mutation SetProductPrice($input: setProductPrice_input!) {"
            " setProductPrice(input: $input) { product_price_id } }",
            "setProductPrice",
        ),
        "set_assign_options": (
            "mutation SetAssignOptions($input: setAssignOptions_input!) {"
            " setAssignOptions(input: $input) { products_id } }",
            "setAssignOptions",
        ),
        "set_additional_option": (
            "mutation SetAdditionalOption($input: setAdditionalOption_input!) {"
            " setAdditionalOption(input: $input) { options_id } }",
            "setAdditionalOption",
        ),
        "set_additional_option_attributes": (
            "mutation SetAdditionalOptionAttributes($input: setAdditionalOptionAttributes_input!) {"
            " setAdditionalOptionAttributes(input: $input) { options_values_id } }",
            "setAdditionalOptionAttributes",
        ),
        "update_product_stock": (
            "mutation UpdateProductStock($input: updateProductStock_input!) {"
            " updateProductStock(input: $input) { products_id } }",
            "updateProductStock",
        ),
        "set_product_design": (
            "mutation SetProductDesign($input: setProductDesign_input!) {"
            " setProductDesign(input: $input) { products_id } }",
            "setProductDesign",
        ),
    }

    def __init__(self, gql: OpsGraphQLClient) -> None:
        self._gql = gql

    async def aclose(self) -> None:
        await self._gql.aclose()

    async def _call(self, method_name: str, variables: dict) -> dict:
        entry = self._QUERIES.get(method_name)
        if entry is None:
            raise NotImplementedError(f"No query registered for '{method_name}'")
        query, data_key = entry
        result = await self._gql.execute(query, variables=variables)
        if not result.ok:
            raise RuntimeError(
                f"OPS {method_name} failed: [{result.ops_error_code}] {result.ops_error_message}"
            )
        return (result.data or {}).get(data_key) or {}

    async def set_product_category(self, variables: dict) -> dict:
        return await self._call("set_product_category", variables)

    async def set_product(self, variables: dict) -> dict:
        return await self._call("set_product", variables)

    async def set_product_size(self, variables: dict) -> dict:
        return await self._call("set_product_size", variables)

    async def set_product_price(self, variables: dict) -> dict:
        return await self._call("set_product_price", variables)

    async def set_assign_options(self, variables: dict) -> dict:
        return await self._call("set_assign_options", variables)

    async def set_additional_option(self, variables: dict) -> dict:
        return await self._call("set_additional_option", variables)

    async def set_additional_option_attributes(self, variables: dict) -> dict:
        return await self._call("set_additional_option_attributes", variables)

    async def update_product_stock(self, variables: dict) -> dict:
        return await self._call("update_product_stock", variables)

    async def set_product_design(self, variables: dict) -> dict:
        return await self._call("set_product_design", variables)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fake OPS client — used for dry_run pushes; records calls without HTTP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FakeOpsClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._counter = 10000

    async def aclose(self) -> None:
        pass

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    async def set_product_category(self, variables: dict) -> dict:
        r = {"category_id": self._next_id()}
        self.calls.append({"method": "set_product_category", "variables": variables, "response": r})
        return r

    async def set_product(self, variables: dict) -> dict:
        r = {"products_id": self._next_id()}
        self.calls.append({"method": "set_product", "variables": variables, "response": r})
        return r

    async def set_product_size(self, variables: dict) -> dict:
        r = {"size_id": self._next_id()}
        self.calls.append({"method": "set_product_size", "variables": variables, "response": r})
        return r

    async def set_product_price(self, variables: dict) -> dict:
        r = {"product_price_id": self._next_id()}
        self.calls.append({"method": "set_product_price", "variables": variables, "response": r})
        return r

    async def set_assign_options(self, variables: dict) -> dict:
        r = {"products_id": self._counter}
        self.calls.append({"method": "set_assign_options", "variables": variables, "response": r})
        return r

    async def set_additional_option(self, variables: dict) -> dict:
        r = {"options_id": self._next_id()}
        self.calls.append({"method": "set_additional_option", "variables": variables, "response": r})
        return r

    async def set_additional_option_attributes(self, variables: dict) -> dict:
        r = {"options_values_id": self._next_id()}
        self.calls.append({"method": "set_additional_option_attributes", "variables": variables, "response": r})
        return r

    async def update_product_stock(self, variables: dict) -> dict:
        r = {"products_id": self._counter}
        self.calls.append({"method": "update_product_stock", "variables": variables, "response": r})
        return r

    async def set_product_design(self, variables: dict) -> dict:
        r = {"products_id": self._counter}
        self.calls.append({"method": "set_product_design", "variables": variables, "response": r})
        return r


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_STEP_REF_RE = re.compile(r'^\$step(\d+)\.(\w+)$')


def _resolve_step_refs(value: Any, step_responses: dict[int, dict]) -> Any:
    """Recursively replace '$stepN.field' placeholders with resolved values."""
    if isinstance(value, str):
        m = _STEP_REF_RE.match(value)
        if m:
            step_num, field = int(m.group(1)), m.group(2)
            return step_responses.get(step_num, {}).get(field, value)
    if isinstance(value, dict):
        return {k: _resolve_step_refs(v, step_responses) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_step_refs(v, step_responses) for v in value]
    return value


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
    pref = req.product_ref

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

    # product_ref accepts product_id (UUID) OR supplier_sku — exactly one path
    # must resolve a row. We don't enforce "both unset" at the Pydantic layer so
    # error shape stays consistent with the gateway envelope.
    if pref.product_id is None and not pref.supplier_sku:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
            "code": "INVALID_REF",
            "message": "product_ref must include product_id or supplier_sku",
        })

    product_query = select(Product).options(
        selectinload(Product.variants), selectinload(Product.images)
    )
    if pref.product_id is not None:
        product_query = product_query.where(Product.id == pref.product_id)
    else:
        product_query = product_query.where(
            Product.supplier_sku == pref.supplier_sku,
            Product.supplier_id == supplier.id,
        )
    product = (await db.execute(product_query)).scalar_one_or_none()
    if not product:
        identifier = str(pref.product_id) if pref.product_id else pref.supplier_sku
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Product '{identifier}' not found in catalog"
        })

    # Cross-check: if resolved by product_id, the product must belong to the
    # supplier the orchestrator named. Stops a key scoped to "sanmar" from
    # nominating a 4Over product simply by knowing its UUID.
    if pref.product_id is not None and product.supplier_id != supplier.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "SUPPLIER_MISMATCH",
            "message": (
                f"Product {product.id} belongs to a different supplier than "
                f"'{supplier_slug}'"
            ),
        })

    supplier_sku = product.supplier_sku

    # ── Compute payload hash over the canonical request body (Rev 1, RFC 8785) ──
    # Task 6: real RFC 8785 JCS hash over the inbound request, not a stub on (product_id, customer_id).
    payload_hash = compute_payload_hash(req.model_dump(mode="json"))

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

    # ── Preflight (Task 7: 8 real checks + token cache) ──
    preflight = await run_preflight(db, customer_id, product.id)
    if not preflight.ok:
        # Use Task 7's spec-shaped error envelope (status/code/message/details/trace_id).
        envelope = preflight.to_error_envelope()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=envelope)

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
        if push_log.dry_run:
            client: Any = FakeOpsClient()
        else:
            if not customer or not customer.ops_base_url:
                logger.error("execute_push: customer %s has no OPS credentials", push_log.customer_id)
                push_log.status = "failed"
                push_log.step_results = [{"error": "Customer has no OPS credentials configured"}]
                await db.commit()
                return
            auth = OpsAuth(
                base_url=customer.ops_base_url,
                token_url=customer.ops_token_url or "",
                client_id=customer.ops_client_id or "",
                client_secret=(customer.ops_auth_config or {}).get("client_secret", ""),
            )
            client = RealOpsClient(OpsGraphQLClient(auth))

        try:
            # ── Build mutation plan (Task 6: real builder with markup + RFC 8785) ──
            payload = await build_push_payload(db, push_log.customer_id, push_log.product_id)
            plan = [step.model_dump(mode="json") for step in payload.plan]

            step_results: list[dict] = []
            step_responses: dict[int, dict] = {}  # step_num → OPS response dict for placeholder resolution
            ops_product_id: Optional[str] = None
            final_status = "pushed" if not push_log.dry_run else "dry_run_pushed"
            cleanup_targets: Optional[dict] = None

            # ── Execute plan sequentially ──
            for step in plan:
                step_num = step.get("step", 0)
                mutation = step.get("mutation", "")
                raw_variables = step.get("variables", {})
                variables = _resolve_step_refs(raw_variables, step_responses)
                t_start = datetime.now(timezone.utc)
                try:
                    method = getattr(client, _mutation_to_method(mutation), None)
                    if method is None:
                        raise NotImplementedError(f"No client method for {mutation}")
                    resp = await method(variables)
                    step_responses[step_num] = resp
                    latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
                    if "products_id" in resp:
                        ops_product_id = str(resp["products_id"])
                    step_results.append({
                        "step": step_num,
                        "source_key": step.get("source_key", ""),
                        "mutation": mutation,
                        "request_fingerprint": _request_fingerprint(variables),
                        "ops_ids": resp,
                        "attempted_at": t_start.isoformat(),
                        "status": "ok",
                        "latency_ms": latency,
                    })
                except Exception as e:
                    latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
                    step_results.append({
                        "step": step_num,
                        "source_key": step.get("source_key", ""),
                        "mutation": mutation,
                        "request_fingerprint": _request_fingerprint(variables),
                        "ops_ids": {},
                        "attempted_at": t_start.isoformat(),
                        "status": "failed",
                        "error": str(e),
                        "latency_ms": latency,
                    })
                    cleanup_targets = {"ops_product_id": ops_product_id, "failed_at": mutation}
                    final_status = "partial_failure" if ops_product_id else "failed"
                    break

            # ── Persist results ──
            push_log.step_results = _redact_auth(step_results)
            push_log.status = final_status
            push_log.cleanup_targets = cleanup_targets
            if final_status in ("failed", "partial_failure"):
                failed_step = next((s for s in step_results if s.get("status") == "failed"), None)
                if failed_step:
                    push_log.error = f"{failed_step['mutation']}: {failed_step.get('error', 'unknown error')}"
            if ops_product_id and final_status == "pushed":
                push_log.ops_product_id = ops_product_id

            # ── Upsert push_mappings (live push only) ──
            # target_ops_product_id is an INTEGER column; the mutation responses
            # carry it as int but step_results stringifies for JSON serialization.
            # Coerce back to int here and skip the mapping write if the OPS id
            # isn't numeric (e.g. early-failure cases where ops_product_id is None).
            if final_status == "pushed" and ops_product_id is not None:
                try:
                    target_int = int(ops_product_id)
                except (TypeError, ValueError):
                    target_int = None
                if target_int is not None:
                    existing_mapping = (await db.execute(
                        select(PushMapping).where(
                            PushMapping.source_product_id == push_log.product_id,
                            PushMapping.customer_id == push_log.customer_id,
                        )
                    )).scalar_one_or_none()
                    now_mapping = datetime.now(timezone.utc)
                    if existing_mapping:
                        existing_mapping.target_ops_product_id = target_int
                        existing_mapping.updated_at = now_mapping
                    else:
                        db.add(PushMapping(
                            source_system="api-hub",
                            source_product_id=push_log.product_id,
                            source_supplier_sku=push_log.supplier_sku,
                            customer_id=push_log.customer_id,
                            target_ops_base_url=(customer.ops_base_url if customer else ""),
                            target_ops_product_id=target_int,
                            pushed_at=now_mapping,
                            updated_at=now_mapping,
                            status="active",
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
        finally:
            await client.aclose()


def _mutation_to_method(mutation: str) -> str:
    mapping = {
        "setProductCategory": "set_product_category",
        "setProduct": "set_product",
        "setProductSize": "set_product_size",
        "setProductPrice": "set_product_price",
        "setAssignOptions": "set_assign_options",
        "setAdditionalOption": "set_additional_option",
        "setAdditionalOptionAttributes": "set_additional_option_attributes",
        "updateProductStock": "update_product_stock",
        "setProductDesign": "set_product_design",
    }
    return mapping.get(mutation, mutation)
