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
