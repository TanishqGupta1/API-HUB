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
