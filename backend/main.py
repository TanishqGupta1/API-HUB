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
import modules.auth.models  # noqa: F401
import modules.audit_log.models  # noqa: F401

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
from modules.ops_push.routes import router as ops_push_router, push_action_router as ops_push_action_router
from modules.push_candidates.routes import router as push_candidates_router
from modules.push_mappings.routes import router as push_mappings_router
from modules.ops_config.routes import router as ops_config_router
from modules.suppliers.category_import import router as category_import_router
from modules.pricing.routes import router as pricing_router, customer_router as pricing_customer_router

import modules.ops_inbound.ops_adapter  # noqa: F401  registers OPSAdapter
import modules.rest_connector.fourover_adapter  # noqa: F401  registers FourOverAdapter
import modules.rest_connector.ss_adapter  # noqa: F401  registers SSAdapter
import modules.promostandards.sanmar_adapter  # noqa: F401  registers SanMarAdapter
import modules.promostandards.alphabroder_adapter  # noqa: F401  registers AlphabroderAdapter
from modules.import_jobs.routes import router as import_jobs_router
from modules.import_jobs.scheduler import start_scheduler
from modules.decorations.routes import router as decorations_router
from modules.auth.routes import router as auth_router
from modules.auth.dependencies import get_current_user
from modules.audit_log.routes import router as audit_log_router
from modules.audit_log.middleware import AuditLogMiddleware


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
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS last_image_fetch_at TIMESTAMP WITH TIME ZONE NULL",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS last_image_fetch_attempt_at TIMESTAMP WITH TIME ZONE NULL",
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_product_images_supplier_url') THEN ALTER TABLE product_images ADD CONSTRAINT uq_product_images_supplier_url UNIQUE (product_id, supplier_image_url); END IF; END $$",
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS push_name_prefix VARCHAR(32)",
    """CREATE TABLE IF NOT EXISTS customer_product_selections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
        product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL DEFAULT 'selected',
        added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        pushed_at TIMESTAMPTZ,
        CONSTRAINT uq_customer_product_selection UNIQUE (customer_id, product_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_customer_product_selections_customer ON customer_product_selections(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_customer_product_selections_product ON customer_product_selections(product_id)",
    """CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_email VARCHAR(255),
        user_id VARCHAR(36),
        method VARCHAR(10) NOT NULL,
        path TEXT NOT NULL,
        status_code INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_email ON audit_logs(user_email)",
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
        from modules.auth.seed import ensure_default_admin

        async with async_session() as db:
            await ensure_vg_ops_supplier(db)
            await ensure_default_admin(db)

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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="API-HUB", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth — no token required on these routes
app.include_router(auth_router)
# Ingest — uses INGEST_SHARED_SECRET, not JWT
app.include_router(catalog_ingest_router)
app.include_router(master_options_ingest_router)

# All admin-facing routers require a valid JWT
_auth = [Depends(get_current_user)]
app.include_router(suppliers_router, dependencies=_auth)
app.include_router(customers_router, dependencies=_auth)
app.include_router(markup_router, dependencies=_auth)
app.include_router(markup_push_router, dependencies=_auth)
app.include_router(push_log_router, dependencies=_auth)
app.include_router(push_status_router, dependencies=_auth)
app.include_router(ps_router, dependencies=_auth)
app.include_router(catalog_router, dependencies=_auth)
app.include_router(categories_router, dependencies=_auth)
app.include_router(master_options_router, dependencies=_auth)
app.include_router(master_options_product_config_router, dependencies=_auth)
app.include_router(n8n_proxy_router, dependencies=_auth)
app.include_router(sync_jobs_router, dependencies=_auth)
app.include_router(ops_push_router, dependencies=_auth)
app.include_router(ops_push_action_router, dependencies=_auth)
app.include_router(push_candidates_router, dependencies=_auth)
app.include_router(push_mappings_router, dependencies=_auth)
app.include_router(ops_config_router, dependencies=_auth)
app.include_router(category_import_router, dependencies=_auth)
app.include_router(promostandards_sync_router, dependencies=_auth)
app.include_router(import_jobs_router, dependencies=_auth)
app.include_router(pricing_router, dependencies=_auth)
app.include_router(pricing_customer_router, dependencies=_auth)
app.include_router(decorations_router, dependencies=_auth)
app.include_router(audit_log_router, dependencies=_auth)


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
