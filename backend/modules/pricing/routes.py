"""Pricing API routes — POST /api/pricing/quote and customer quote."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
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
        raise HTTPException(status_code=404, detail=str(exc))


@customer_router.post("/{customer_id}/pricing/quote", response_model=CustomerQuoteResult)
async def customer_quote(
    customer_id: UUID,
    req: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> CustomerQuoteResult:
    try:
        return await resolve_customer_quote(req, customer_id, db)
    except BoundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except MissingPricingDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
