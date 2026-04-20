"""Seed sync jobs and products for UI verification."""

import asyncio
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import uuid

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from database import Base, async_session, engine
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

# Ensure models are registered
import modules.suppliers.models
import modules.catalog.models
import modules.sync_jobs.models

async def seed():
    print("Connecting to database...")
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        from sqlalchemy import select, delete

        print("Setting up suppliers...")
        # 1. Setup Suppliers
        SUPS = [
            {"name": "SanMar", "slug": "sanmar", "protocol": "soap", "promostandards_code": "SANMAR"},
            {"name": "S&S Activewear", "slug": "ss-activewear", "protocol": "rest", "promostandards_code": "SSACT"},
        ]
        
        supplier_map = {}
        for s_data in SUPS:
            res = await db.execute(select(Supplier).where(Supplier.slug == s_data["slug"]))
            existing = res.scalar_one_or_none()
            if not existing:
                s = Supplier(**s_data, base_url="https://api.demo.com", auth_config={})
                db.add(s)
                await db.flush()
                supplier_map[s_data["slug"]] = s
                print(f"  Added supplier: {s.name}")
            else:
                supplier_map[s_data["slug"]] = existing
                print(f"  Supplier found: {existing.name}")

        await db.commit()

        # 2. Add some Products if they don't exist
        print("Seeding dummy products...")
        PRODS = [
            {"sku": "PC61", "name": "Essential Tee", "brand": "Port & Company", "type": "Apparel", "sup": "sanmar"},
            {"sku": "LST640", "name": "Ladies Tee", "brand": "Sport-Tek", "type": "Apparel", "sup": "sanmar"},
        ]

        for p_data in PRODS:
            sup = supplier_map[p_data["sup"]]
            res = await db.execute(select(Product).where(Product.supplier_sku == p_data["sku"]))
            if not res.scalar_one_or_none():
                p = Product(
                    supplier_id=sup.id,
                    supplier_sku=p_data["sku"],
                    product_name=p_data["name"],
                    brand=p_data["brand"],
                    product_type=p_data["type"],
                    description="A high-quality demo product."
                )
                db.add(p)
                await db.flush()
                print(f"  Added product: {p.product_name}")

        await db.commit()

        # 3. Add Sync Jobs
        print("Adding sync history...")
        # Clear old jobs to keep it fresh
        await db.execute(delete(SyncJob))
        
        JOBS = [
            {
                "sup_slug": "sanmar",
                "type": "full_sync",
                "status": "completed",
                "records": 1250,
                "offset": -60 # 1 hour ago
            },
            {
                "sup_slug": "ss-activewear",
                "type": "inventory",
                "status": "completed",
                "records": 8201,
                "offset": -15 # 15 mins ago
            },
            {
                "sup_slug": "sanmar",
                "type": "pricing",
                "status": "failed",
                "records": 402,
                "offset": -5,
                "error": "SoapFault: Authentication failed (Invalid credentials)"
            },
            {
                "sup_slug": "ss-activewear",
                "type": "delta",
                "status": "running",
                "records": 45,
                "offset": -1
            }
        ]

        for j_data in JOBS:
            sup = supplier_map[j_data["sup_slug"]]
            start = datetime.now(timezone.utc) + timedelta(minutes=j_data["offset"])
            finish = start + timedelta(minutes=2) if j_data["status"] == "completed" else None
            
            job = SyncJob(
                supplier_id=sup.id,
                supplier_name=sup.name,
                job_type=j_data["type"],
                status=j_data["status"],
                records_processed=j_data["records"],
                started_at=start,
                finished_at=finish,
                error_log=j_data.get("error")
            )
            db.add(job)
            print(f"  Added job: {sup.name} {j_data['type']} ({j_data['status']})")

        await db.commit()
        print("\nSeed complete! Check your dashboard.")

if __name__ == "__main__":
    asyncio.run(seed())
