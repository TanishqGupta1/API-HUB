from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, ENVIRONMENT, async_session, engine, get_db

# Import all models so SQLAlchemy registers them before create_all
import modules.suppliers.models  # noqa: F401
import modules.catalog.models  # noqa: F401
import modules.customers.models  # noqa: F401
import modules.markup.models  # noqa: F401
import modules.push_log.models  # noqa: F401
import modules.sync_jobs.models  # noqa: F401
import modules.master_options.models  # noqa: F401
import modules.push_mappings.models  # noqa: F401

from modules.suppliers.models import Supplier
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.routes import router as suppliers_router
from modules.customers.routes import router as customers_router
from modules.markup.routes import router as markup_router, push_router as markup_push_router
from modules.push_log.routes import router as push_log_router
from modules.catalog.routes import router as catalog_router, categories_router
from modules.catalog.ingest import router as catalog_ingest_router
from modules.master_options.ingest import router as master_options_ingest_router
from modules.master_options.routes import router as master_options_router, product_config_router as master_options_product_config_router
from modules.n8n_proxy.routes import router as n8n_proxy_router
from modules.ps_directory.routes import router as ps_router
from modules.promostandards.routes import router as promostandards_sync_router
from modules.sync_jobs.routes import router as sync_jobs_router
from modules.ops_push.routes import router as ops_push_router
from modules.push_candidates.routes import router as push_candidates_router
from modules.push_mappings.routes import router as push_mappings_router
from modules.suppliers.category_import import router as category_import_router


# Idempotent schema upgrades. `Base.metadata.create_all` creates new tables
# but never alters existing ones, so ADD COLUMN steps ship here. Each statement
# must be idempotent (IF NOT EXISTS) so restarts are safe.
_SCHEMA_UPGRADES: list[str] = [
    "ALTER TABLE product_options ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT false NOT NULL",
    "ALTER TABLE product_options ADD COLUMN IF NOT EXISTS overridden_sort INTEGER",
    "ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT false NOT NULL",
    "ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS price NUMERIC(10,2)",
    "ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS numeric_value NUMERIC(10,2)",
    "ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS overridden_sort INTEGER",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE NULL",
    "CREATE INDEX IF NOT EXISTS idx_products_archived_at ON products(archived_at)",
    "CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_images_product_id ON product_images(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_options_product_id ON product_options(product_id)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    retries = 5
    while retries > 0:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                for stmt in _SCHEMA_UPGRADES:
                    await conn.execute(text(stmt))
            break
        except Exception as e:
            retries -= 1
            if retries == 0:
                raise e
            print(f"Database not ready... retrying in 2s ({retries} retries left)")
            await asyncio.sleep(2)

    if ENVIRONMENT == "development":
        from modules.suppliers.demo_seed import ensure_vg_ops_supplier

        async with async_session() as db:
            await ensure_vg_ops_supplier(db)
    yield
    await engine.dispose()


import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")

app = FastAPI(title="API-HUB", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(suppliers_router)
app.include_router(customers_router)
app.include_router(markup_router)
app.include_router(markup_push_router)
app.include_router(push_log_router)
app.include_router(ps_router)
app.include_router(catalog_router)
app.include_router(categories_router)
app.include_router(catalog_ingest_router)
app.include_router(master_options_ingest_router)
app.include_router(master_options_router)
app.include_router(master_options_product_config_router)
app.include_router(n8n_proxy_router)
app.include_router(sync_jobs_router)
app.include_router(ops_push_router)
app.include_router(push_candidates_router)
app.include_router(push_mappings_router)
app.include_router(category_import_router)
app.include_router(promostandards_sync_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-hub"}


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    suppliers = (await db.execute(select(func.count()).select_from(Supplier))).scalar()
    products = (await db.execute(select(func.count()).select_from(Product))).scalar()
    variants = (await db.execute(select(func.count()).select_from(ProductVariant))).scalar()
    
    return {
        "suppliers": suppliers,
        "products": products,
        "variants": variants,
    }
