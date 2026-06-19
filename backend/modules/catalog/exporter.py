"""Supplier catalog handoff — api-hub → graphx.

Builds a normalized payload from one product (incl. options) and pushes batches
to the graphx ingest endpoint over httpx. See
plans/2026-06-17-supplier-catalog-handoff-impl.md.
"""
from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.suppliers.models import Supplier

from .models import Product, ProductOption, ProductVariant


def _graphx_env() -> tuple[str, str]:
    """Return (ingest_url, ingest_secret) for graphx, or raise 503 if unconfigured.

    Uses os.environ.get + an explicit 503 instead of os.environ[...] (which raises
    KeyError → opaque 500) so a missing GRAPHX_INGEST_URL/SECRET surfaces as a
    clean 'service not configured'.
    """
    url = os.environ.get("GRAPHX_INGEST_URL")
    secret = os.environ.get("GRAPHX_INGEST_SECRET")
    if not url or not secret:
        raise HTTPException(
            status_code=503,
            detail="graphx ingest not configured (GRAPHX_INGEST_URL / GRAPHX_INGEST_SECRET unset)",
        )
    return url, secret


async def build_supplier_product(db: AsyncSession, product_id: UUID) -> dict:
    """Serialize one product (variants + prices + images + options) for graphx.

    Mirrors the existing ``GET /{id}/export`` query but always includes options
    — the contract graphx expects.
    """
    res = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants).selectinload(ProductVariant.prices),
            selectinload(Product.images),
            selectinload(Product.sizes),
            selectinload(Product.options).selectinload(ProductOption.attributes),
        )
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")

    return {
        "supplier_sku": p.supplier_sku,
        "name": p.product_name,
        "brand": p.brand,
        "description": p.description,
        "product_type": p.product_type,
        "category": p.category,
        "images": [
            {"url": i.url, "type": i.image_type, "color": i.color}
            for i in (p.images or [])
        ],
        "options": [
            {
                "option_key": o.option_key,
                "title": o.title,
                "attributes": [{"title": a.title} for a in (o.attributes or [])],
            }
            for o in (p.options or [])
        ],
        "variants": [
            {
                "color": v.color,
                "size": v.size,
                "sku": v.sku,
                "prices": [
                    {
                        "price_type": pr.price_type,
                        "quantity_min": pr.quantity_min,
                        "quantity_max": pr.quantity_max,
                        "price": float(pr.price),
                    }
                    for pr in (v.prices or [])
                ],
            }
            for v in (p.variants or [])
        ],
    }


async def _post(
    url: str,
    secret: str,
    supplier_key: str,
    tenant_slug: str,
    products: list[dict],
) -> dict:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            url,
            headers={"x-ingest-secret": secret},
            json={
                "supplier_key": supplier_key,
                "tenant_slug": tenant_slug,
                "products": products,
            },
        )
        body = None
        if r.headers.get("content-type", "").startswith("application/json"):
            try:
                body = r.json()
            except Exception:
                body = None
        # A non-2xx from graphx is a FAILED push, not a successful "sent" — surface
        # it as a 502 instead of silently returning and counting the batch as sent.
        if r.status_code >= 300:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "graphx ingest rejected the batch",
                    "upstream_status": r.status_code,
                    "upstream_body": body,
                },
            )
        return {"status": r.status_code, "body": body}


async def push_products_to_graphx(
    db: AsyncSession,
    supplier_id: Optional[UUID] = None,
    tenant_slug: str = "vg",
    batch: int = 50,
) -> dict:
    """Push products (optionally one supplier's) to graphx in batches.

    Products without any options are skipped — they need ``derive_options``
    to be run first. Env: ``GRAPHX_INGEST_URL`` + ``GRAPHX_INGEST_SECRET``.
    """
    url, secret = _graphx_env()

    sup = await db.get(Supplier, supplier_id) if supplier_id else None

    q = select(Product.id).where(Product.archived_at.is_(None))
    if supplier_id is not None:
        q = q.where(Product.supplier_id == supplier_id)
    ids = (await db.execute(q)).scalars().all()

    sent = 0
    skipped = 0
    batches: list[dict] = []
    buf: list[dict] = []

    for pid in ids:
        prod = await build_supplier_product(db, pid)
        if not prod["options"]:  # needs derive_options first
            skipped += 1
            continue
        buf.append(prod)
        if len(buf) >= batch:
            batches.append(await _post(url, secret, sup.slug if sup else "", tenant_slug, buf))
            sent += len(buf)
            buf = []

    if buf:
        batches.append(await _post(url, secret, sup.slug if sup else "", tenant_slug, buf))
        sent += len(buf)

    return {"sent": sent, "skipped": skipped, "batches": batches}
