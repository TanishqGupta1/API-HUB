import os
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
import modules.ops_config.models  # noqa: F401
import modules.decorations.models  # noqa: F401

from modules.suppliers.models import Supplier
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.routes import router as suppliers_router
from modules.customers.routes import router as customers_router
from modules.markup.routes import router as markup_router, push_router as markup_push_router
from modules.push_log.routes import router as push_log_router, push_status_router
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
from modules.ops_config.routes import router as ops_config_router
from modules.suppliers.category_import import router as category_import_router

_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
    "N8N_WEBHOOK_BASE_URL",
    "API_BASE_URL",
)


def _require_prod_env() -> None:
    """Refuse to boot in production if required env vars are missing.

    Called at the top of the lifespan handler. In development the check is
    a no-op so local dev still works without a full prod env.
    """
    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        return
    missing = [v for v in _PROD_REQUIRED_ENV_VARS if not os.getenv(v, "").strip()]
    if missing:
        raise RuntimeError(
            "Production startup blocked. Missing required env vars: "
            + ", ".join(missing)
            + ". Set them in the task definition / ECS secrets / Secrets Manager."
        )
from modules.pricing.routes import router as pricing_router, customer_router as pricing_customer_router

import modules.ops_inbound.ops_adapter  # noqa: F401  registers OPSAdapter
import modules.rest_connector.fourover_adapter  # noqa: F401  registers FourOverAdapter
import modules.rest_connector.ss_adapter  # noqa: F401  registers SSAdapter
import modules.promostandards.sanmar_adapter  # noqa: F401  registers SanMarAdapter
import modules.promostandards.alphabroder_adapter  # noqa: F401  registers AlphabroderAdapter
from modules.import_jobs.routes import router as import_jobs_router
from modules.import_jobs.scheduler import start_scheduler
from modules.decorations.routes import router as decorations_router


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
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS adapter_class VARCHAR(64)",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_full_sync TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_delta_sync TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS errors JSONB",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS protocol_config JSONB",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS discovery_mode VARCHAR(32)",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS total_products INTEGER DEFAULT 0",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS push_name_prefix VARCHAR(32)",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS failed_count INTEGER DEFAULT 0",
    "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE",
    "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sync_jobs' AND column_name='finished_at') THEN UPDATE sync_jobs SET completed_at = finished_at WHERE completed_at IS NULL AND finished_at IS NOT NULL; ALTER TABLE sync_jobs DROP COLUMN finished_at; END IF; END $$",
    "UPDATE sync_jobs SET status = 'pending' WHERE status = 'queued'",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS has_decoration_overlay BOOLEAN NOT NULL DEFAULT FALSE",
    """CREATE TABLE IF NOT EXISTS customer_product_decorations (
        customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
        product_id  UUID NOT NULL REFERENCES products(id)  ON DELETE CASCADE,
        decoration_options JSONB NOT NULL DEFAULT '[]',
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (customer_id, product_id)
    )""",
    # Fix SanMar MultipleResultsFound: old (product_id, color, size) constraint breaks with NULL values.
    # Drop it and add a clean (product_id, sku) unique constraint instead.
    "ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS uq_variant_product_color_size",
    # Inline dedup before adding unique constraint (Blocker 3)
    """DO $$ BEGIN
    DELETE FROM product_variants
    WHERE id IN (
        SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY product_id, sku ORDER BY id) as rn
            FROM product_variants
            WHERE sku IS NOT NULL
        ) sub
        WHERE rn > 1
    );
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_product_variants_product_sku') THEN
        ALTER TABLE product_variants ADD CONSTRAINT uq_product_variants_product_sku UNIQUE (product_id, sku);
    END IF;
    END $$""",
    "ALTER TABLE product_images ADD COLUMN IF NOT EXISTS supplier_image_url TEXT",
    "ALTER TABLE product_images ADD COLUMN IF NOT EXISTS checksum VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS idx_product_images_checksum ON product_images(checksum)",
    # New image tracking columns (Blocker 2 & 6)
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS last_image_fetch_at TIMESTAMP WITH TIME ZONE NULL",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS last_image_fetch_attempt_at TIMESTAMP WITH TIME ZONE NULL",
    # Fix ProductImage upsert key (Moderate 7)
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_product_images_supplier_url') THEN ALTER TABLE product_images ADD CONSTRAINT uq_product_images_supplier_url UNIQUE (product_id, supplier_image_url); END IF; END $$",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    _require_prod_env()
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

    # Start the background scheduler (sleeps first; no-op if DISABLE_SCHEDULER=true)
    _scheduler_task = asyncio.create_task(start_scheduler(interval_hours=24))

    yield

    # Graceful shutdown: cancel scheduler before closing DB pool
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    from modules.n8n_proxy import routes as _n8n_proxy
    if _n8n_proxy._http_client is not None:
        await _n8n_proxy._http_client.aclose()


import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")

app = FastAPI(title="API-HUB", version="0.1.0", lifespan=lifespan)

_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
_CORS_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = ["Authorization", "Content-Type", "X-Ingest-Secret"]

_cors_kwargs: dict = dict(
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=_CORS_METHODS,
    allow_headers=_CORS_HEADERS,
)
if not _IS_PRODUCTION:
    _cors_kwargs["allow_origin_regex"] = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Routers
app.include_router(suppliers_router)
app.include_router(customers_router)
app.include_router(markup_router)
app.include_router(markup_push_router)
app.include_router(push_log_router)
app.include_router(push_status_router)
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
app.include_router(ops_config_router)
app.include_router(category_import_router)
app.include_router(promostandards_sync_router)
app.include_router(import_jobs_router)
app.include_router(pricing_router)
app.include_router(pricing_customer_router)
app.include_router(decorations_router)


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
