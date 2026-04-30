"""Backfill script to ensure all products have polymorphic detail rows."""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from database import async_session, engine
from modules.catalog.models import Product, ApprelDetails, PrintDetails
from sqlalchemy import select


async def backfill():
    async with async_session() as db:
        # 1. Find apparel products without details
        stmt = select(Product).where(Product.product_type == "apparel")
        products = (await db.execute(stmt)).scalars().all()
        
        count = 0
        for p in products:
            # Check if exists
            exists = await db.get(ApprelDetails, p.id)
            if not exists:
                db.add(ApprelDetails(product_id=p.id, pricing_method="tiered_variant"))
                count += 1
        
        # 2. Find print products without details
        stmt = select(Product).where(Product.product_type == "print")
        products = (await db.execute(stmt)).scalars().all()
        
        for p in products:
            exists = await db.get(PrintDetails, p.id)
            if not exists:
                db.add(PrintDetails(product_id=p.id, pricing_method="formula"))
                count += 1
        
        await db.commit()
        print(f"Backfilled {count} products with missing details.")

if __name__ == "__main__":
    asyncio.run(backfill())
