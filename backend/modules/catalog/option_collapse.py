"""Derive selectable Color/Size options from a product's stored variant matrix.

Read-only over product_variants; never mutates variants. Idempotent full-replace
of the two derived ProductOptions (option_key 'color', 'size'). No product_sizes
written. See plans/2026-06-16-variant-option-collapse.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .ingest import _upsert_options
from .models import Product, ProductOption, ProductVariant
from .schemas import OptionAttributeIngest, OptionIngest

DERIVED_OPTION_KEYS = ("color", "size")

# Canonical apparel size order; lower = earlier. Unknown sizes sort after, alpha.
_SIZE_ORDER = {
    "XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4,
    "2XL": 5, "XXL": 5, "3XL": 6, "XXXL": 6,
    "4XL": 7, "5XL": 8, "6XL": 9,
}


@dataclass
class CollapseResult:
    colors: int        # 1 if a color option was written, else 0
    sizes: int         # 1 if a size option was written, else 0
    color_attrs: int   # distinct color count
    size_attrs: int    # distinct size count


def _norm(value: str) -> str:
    """Trim + collapse internal whitespace. Preserves display casing."""
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _norm(value).casefold()).strip("-")
    return s or "x"


def _size_sort_key(title: str):
    key = _norm(title).upper()
    return (_SIZE_ORDER.get(key, 999), key)


def _distinct(
    values: Iterable[Optional[str]],
    sort_key: Optional[Callable[[str], object]] = None,
) -> list[str]:
    """Ordered distinct, dedup on casefold key; first display form wins."""
    seen: dict[str, str] = {}
    for v in values:
        if v is None:
            continue
        disp = _norm(v)
        if not disp:
            continue
        k = disp.casefold()
        if k not in seen:
            seen[k] = disp
    items = list(seen.values())
    items.sort(key=sort_key if sort_key else (lambda s: s.casefold()))
    return items


def _build_option(
    option_key: str,
    title: str,
    options_type: str,
    raw_titles: Iterable[Optional[str]],
    sort_order: int,
    sort_key: Optional[Callable[[str], object]] = None,
) -> tuple[OptionIngest, int]:
    distinct = _distinct(raw_titles, sort_key=sort_key)
    attrs = [
        OptionAttributeIngest(title=t, attribute_key=_slug(t), sort_order=i)
        for i, t in enumerate(distinct)
    ]
    opt = OptionIngest(
        option_key=option_key,
        title=title,
        options_type=options_type,
        sort_order=sort_order,
        required=bool(distinct),
        enabled=True,
        attributes=attrs,
    )
    return opt, len(distinct)


async def derive_options(db: AsyncSession, product_id: UUID) -> CollapseResult:
    """Read variants, (re)build Color/Size options, prune emptied axes. Commits."""
    rows = (
        await db.execute(
            select(ProductVariant.color, ProductVariant.size)
            .where(ProductVariant.product_id == product_id)
        )
    ).all()

    color_opt, n_colors = _build_option(
        "color", "Color", "swatch", (r.color for r in rows), sort_order=0
    )
    size_opt, n_sizes = _build_option(
        "size", "Size", "dropdown", (r.size for r in rows),
        sort_order=1, sort_key=_size_sort_key,
    )

    payload: list[OptionIngest] = []
    built: set[str] = set()
    if n_colors:
        payload.append(color_opt)
        built.add("color")
    if n_sizes:
        payload.append(size_opt)
        built.add("size")

    if payload:
        await _upsert_options(db, product_id, payload)

    stale = [k for k in DERIVED_OPTION_KEYS if k not in built]
    if stale:
        await db.execute(
            delete(ProductOption).where(
                ProductOption.product_id == product_id,
                ProductOption.option_key.in_(stale),
            )
        )

    await db.commit()
    return CollapseResult(
        colors=1 if n_colors else 0,
        sizes=1 if n_sizes else 0,
        color_attrs=n_colors,
        size_attrs=n_sizes,
    )


async def derive_options_bulk(
    db: AsyncSession, supplier_id: Optional[UUID] = None
) -> dict:
    """Re-derive options for every product (optionally one supplier). Commits per
    product so one bad product does not roll back the whole run."""
    q = select(Product.id)
    if supplier_id is not None:
        q = q.where(Product.supplier_id == supplier_id)
    ids = (await db.execute(q)).scalars().all()

    totals = {"products": 0, "color_options": 0, "size_options": 0}
    for pid in ids:
        res = await derive_options(db, pid)
        totals["products"] += 1
        totals["color_options"] += res.colors
        totals["size_options"] += res.sizes
    return totals
