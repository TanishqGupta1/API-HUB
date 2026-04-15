from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .models import MarkupRule
from .schemas import MarkupRuleCreate, MarkupRuleRead

router = APIRouter(prefix="/api/markup-rules", tags=["markup"])


@router.get("/{customer_id}", response_model=list[MarkupRuleRead])
async def list_markup_rules(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MarkupRule)
        .where(MarkupRule.customer_id == customer_id)
        .order_by(MarkupRule.priority.desc())
    )
    return result.scalars().all()


@router.post("", response_model=MarkupRuleRead, status_code=201)
async def create_markup_rule(body: MarkupRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = MarkupRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_markup_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MarkupRule).where(MarkupRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Markup rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True}
