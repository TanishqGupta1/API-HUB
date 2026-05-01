"""Pricing API routes — POST /api/pricing/quote and customer quote.

Auth boundary
-------------
GET/POST /api/pricing/quote          — public (no auth). Returns base cost
                                       with no markup. Safe to expose because
                                       it contains no business pricing rules.

POST /api/customers/{id}/pricing/quote — INTERNAL ONLY. Returns marked-up
                                         price including storefront overrides
                                         and markup percentages. Gated by the
                                         same X-Ingest-Secret header used on
                                         all n8n → FastAPI internal calls.
                                         Do NOT expose this endpoint on a
                                         public surface.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from modules.catalog.ingest import require_ingest_secret
from sqlalchemy.ext.asyncio import AsyncSession

from .customer_quote import resolve_customer_quote
from .errors import BoundsError, MissingPricingDataError
from .resolvers import resolve_quote
from .schemas import CustomerQuoteResult, QuoteRequest, QuoteResult

router = APIRouter(prefix="/api/pricing", tags=["pricing"])
customer_router = APIRouter(prefix="/api/customers", tags=["pricing"])


@router.post("/quote", response_model=QuoteResult)
async def quote(req: QuoteRequest, db: AsyncSession = Depends(get_db)) -> QuoteResult:
    try:
        return await resolve_quote(req, db)
    except BoundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except MissingPricingDataError as exc:
        # 404 only when the product itself is missing; variant/data gaps are 422.
        detail = str(exc)
        status = 404 if "not found" in detail.lower() and "variant" not in detail.lower() else 422
        raise HTTPException(status_code=status, detail=detail)


@customer_router.post(
    "/{customer_id}/pricing/quote",
    response_model=CustomerQuoteResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def customer_quote(
    customer_id: UUID,
    req: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> CustomerQuoteResult:
    """Internal-only endpoint — requires X-Ingest-Secret header.

    Returns base price + markup rules + storefront overrides for a specific
    customer. Only n8n workflows should call this. Never expose to a public
    storefront without re-evaluating the auth boundary.
    """
    try:
        return await resolve_customer_quote(req, customer_id, db)
    except BoundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except MissingPricingDataError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() and "variant" not in detail.lower() else 422
        raise HTTPException(status_code=status, detail=detail)
