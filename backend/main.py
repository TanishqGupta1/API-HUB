import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from limiter import limiter

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, DATABASE_URL, ENVIRONMENT, async_session, engine, get_db

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
import modules.alerting.models  # noqa: F401  — registers Notification + SchedulerHeartbeat with Base
import modules.webhooks.models  # noqa: F401
# customer_catalog re-exports CustomerProductSelection from catalog.models
# so no separate import is needed here.

from modules.suppliers.models import Supplier
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.routes import router as suppliers_router
from modules.customers.routes import router as customers_router
from modules.markup.routes import router as markup_router, push_router as markup_push_router
from modules.push_log.routes import router as push_log_router, push_status_router
from modules.integrations.models import IntegrationKey  # noqa: F401 — registers table with Base
from modules.integrations.routes import router as integrations_router, admin_router as integrations_admin_router
from modules.catalog.routes import router as catalog_router, categories_router
from modules.catalog.ingest import router as catalog_ingest_router
from modules.master_options.ingest import router as master_options_ingest_router
from modules.master_options.routes import router as master_options_router, product_config_router as master_options_product_config_router
from modules.ps_directory.routes import router as ps_router
from modules.promostandards.routes import router as promostandards_sync_router
from modules.sync_jobs.routes import router as sync_jobs_router
from modules.ops_push.routes import router as ops_push_router
from modules.push_candidates.routes import router as push_candidates_router
from modules.push_mappings.routes import router as push_mappings_router
from modules.ops_config.routes import router as ops_config_router
from modules.suppliers.category_import import router as category_import_router
from modules.auth.routes import router as auth_router
from modules.auth.dependencies import _require_vg_admin, get_current_user, VGAdmin
from modules.audit_log.routes import router as audit_log_router
from modules.audit_log.middleware import AuditLogMiddleware
from modules.customer_catalog.routes import router as customer_catalog_router
from modules.portal.routes import router as portal_router
from modules.images.routes import router as images_router
from modules.webhooks.routes import router as webhooks_router
from modules.analytics.routes import router as analytics_router
from modules.n8n_proxy.routes import router as n8n_proxy_router

_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
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

import modules.ops_inbound.ops_adapter  # noqa: F401  registers OPSAdapter
import modules.rest_connector.fourover_adapter  # noqa: F401  registers FourOverAdapter
import modules.rest_connector.ss_adapter  # noqa: F401  registers SSAdapter
import modules.promostandards.sanmar_adapter  # noqa: F401  registers SanMarAdapter
import modules.promostandards.alphabroder_adapter  # noqa: F401  registers AlphabroderAdapter
from modules.import_jobs.routes import router as import_jobs_router
from modules.import_jobs.scheduler import start_scheduler, start_inventory_scheduler
from modules.decorations.routes import router as decorations_router
from modules.alerting.routes import router as alerting_router
from modules.alerting.checker import run_checker, run_startup_check
from modules.pricing.routes import router as pricing_router, customer_router as pricing_customer_router


def _run_alembic_upgrade(*, stamp_baseline: bool = False) -> None:
    """Run ``alembic upgrade head`` using the Python API (sync, called via asyncio.to_thread).

    Args:
        stamp_baseline: When True the DB pre-dates Alembic adoption — stamp it
            as 0001_baseline before upgrading so only delta migrations run.
            The caller checks for the alembic_version table using the existing
            async engine (avoids opening a second sync engine here).
    """
    import os as _os
    from alembic.config import Config as _AlembicConfig
    from alembic import command as _alembic_cmd

    _ini = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "alembic.ini")
    cfg = _AlembicConfig(_ini)

    # Override URL — Alembic needs a *sync* driver (psycopg2, not asyncpg).
    _sync_url = DATABASE_URL.replace("+asyncpg", "")
    cfg.set_main_option("sqlalchemy.url", _sync_url)

    if stamp_baseline:
        _alembic_cmd.stamp(cfg, "0001_baseline")

    _alembic_cmd.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _require_prod_env()
    import asyncio
    from cache import init_redis, close_redis

    # Sentry must be initialised inside lifespan so that logging is already
    # configured — initialising at module import time means startup errors can
    # be silently swallowed before the SDK has a chance to flush them.
    _sentry_dsn = os.getenv("SENTRY_DSN", "")
    if _sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            # Env-driven so ops can tune without a code deploy (default 20%)
            traces_sample_rate=min(1.0, max(0.0, float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")))),
            profiles_sample_rate=0.1,
            send_default_pii=False,
        )
        logging.getLogger(__name__).info("Sentry SDK initialised")
    retries = 5
    while retries > 0:
        try:
            # Step 1: create any brand-new tables (idempotent via IF NOT EXISTS).
            # Also check whether alembic_version exists using the async engine
            # so we don't need a second sync engine inside _run_alembic_upgrade.
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                result = await conn.execute(
                    text("SELECT to_regclass('public.alembic_version')")
                )
                _has_alembic_table = result.scalar() is not None

            # Step 2: apply Alembic migrations (column additions, index changes, etc.).
            # Runs in a thread pool since Alembic uses a synchronous SQLAlchemy engine.
            await asyncio.to_thread(
                _run_alembic_upgrade,
                stamp_baseline=not _has_alembic_table,
            )
            break
        except Exception as e:
            retries -= 1
            if retries == 0:
                raise e
            logging.getLogger(__name__).warning(
                "DB startup error (%s: %s) — retrying in 2s (%d retries left)",
                type(e).__name__, e, retries,
            )
            await asyncio.sleep(2)

    # Admin seeding is opt-in via SEED_ADMIN=1. Default flow: deploy with empty
    # DB, then first visitor at /signup creates the bootstrap vg_admin (the
    # /api/auth/register endpoint accepts the first user without auth).
    if os.getenv("SEED_ADMIN", "0") == "1":
        from modules.auth.seed import ensure_default_admin
        async with async_session() as db:
            await ensure_default_admin(db)

    if ENVIRONMENT == "development" and os.getenv("SEED_DEMO_SUPPLIER", "0") == "1":
        from modules.suppliers.demo_seed import ensure_vg_ops_supplier

        async with async_session() as db:
            await ensure_vg_ops_supplier(db)

    # Connect to Redis (optional — falls back gracefully if REDIS_URL is unset)
    await init_redis()

    # Start background tasks
    # Scheduler sleeps first to avoid restart storms (no-op if DISABLE_SCHEDULER=true)
    _scheduler_task = asyncio.create_task(start_scheduler())
    # Inventory-only sync runs every 15 min (INVENTORY_SYNC_INTERVAL_MINUTES)
    _inventory_task = asyncio.create_task(start_inventory_scheduler())
    # Alerting checker runs every 5 min (ALERT_CHECK_INTERVAL_SECONDS)
    _checker_task = asyncio.create_task(run_checker())
    # Run one immediate check on boot to catch anything that failed during downtime.
    # Keep a reference so the task isn't garbage-collected mid-flight.
    _startup_check_task = asyncio.create_task(run_startup_check())

    yield

    # Graceful shutdown: cancel background tasks, close Redis, then DB pool
    for task in (_scheduler_task, _inventory_task, _checker_task, _startup_check_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await close_redis()
    await engine.dispose()


import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")

app = FastAPI(title="GraphX Connect", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
_CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-Ingest-Secret",
    "X-Orchestrator-Key",   # Integration Gateway orchestrator auth
    "Idempotency-Key",      # Gateway idempotent push requests
]

_cors_kwargs: dict = dict(
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=_CORS_METHODS,
    allow_headers=_CORS_HEADERS,
)
if not _IS_PRODUCTION:
    _cors_kwargs["allow_origin_regex"] = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

class _PrivateNetworkAccessMiddleware(BaseHTTPMiddleware):
    """Chrome 98+ sends Access-Control-Request-Private-Network: true on
    localhost-to-localhost preflights. Starlette's CORSMiddleware returns 400
    for these requests because it doesn't recognise the header. We intercept
    them here and return the correct 200 + Access-Control-Allow-Private-Network
    response so Chrome allows the actual request through.
    """
    _ALLOW_HEADERS = (
        "Accept, Accept-Language, Authorization, Content-Language, "
        "Content-Type, Idempotency-Key, X-Ingest-Secret, X-Orchestrator-Key"
    )
    _ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"

    async def dispatch(self, request: StarletteRequest, call_next):
        if (
            request.method == "OPTIONS"
            and request.headers.get("Access-Control-Request-Private-Network") == "true"
        ):
            origin = request.headers.get("Origin", "*")
            return StarletteResponse(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Private-Network": "true",
                    "Access-Control-Allow-Methods": self._ALLOW_METHODS,
                    "Access-Control-Allow-Headers": self._ALLOW_HEADERS,
                    "Access-Control-Max-Age": "600",
                    "Vary": "Origin",
                },
            )
        return await call_next(request)


app.add_middleware(CORSMiddleware, **_cors_kwargs)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(_PrivateNetworkAccessMiddleware)  # outermost — handles Chrome PNA before CORS sees it

# Public routers — no JWT cookie required
app.include_router(auth_router)                # /api/auth/{login,logout,me,setup}
app.include_router(catalog_ingest_router)      # uses X-Ingest-Secret header, not JWT
app.include_router(master_options_ingest_router)

# Admin routers — require valid auth_token cookie
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
app.include_router(sync_jobs_router, dependencies=_auth)
app.include_router(ops_push_router, dependencies=_auth)
app.include_router(push_candidates_router, dependencies=_auth)
app.include_router(push_mappings_router, dependencies=_auth)
app.include_router(ops_config_router, dependencies=_auth)
app.include_router(category_import_router, dependencies=_auth)
app.include_router(promostandards_sync_router, dependencies=_auth)
app.include_router(import_jobs_router, dependencies=_auth)
app.include_router(pricing_router, dependencies=_auth)
app.include_router(pricing_customer_router, dependencies=_auth)
app.include_router(decorations_router, dependencies=_auth)
app.include_router(images_router, dependencies=_auth)
app.include_router(audit_log_router, dependencies=_auth)
app.include_router(alerting_router, dependencies=_auth)
app.include_router(customer_catalog_router, dependencies=_auth)
app.include_router(webhooks_router, dependencies=_auth)
app.include_router(analytics_router, dependencies=_auth)
# n8n proxy exposes internal workflow URLs + can trigger any workflow → vg_admin only.
# Mounting under blanket _auth would let any customer_admin enumerate/trigger flows
# and leak N8N_API_BASE_URL / N8N_API_KEY values. See issue #153 / plan Task 11.
app.include_router(n8n_proxy_router, dependencies=[Depends(_require_vg_admin)])
# Customer self-service portal — requires customer_admin role (enforced inside routes)
app.include_router(portal_router, dependencies=_auth)
# Integration Gateway — X-Orchestrator-Key auth (handled inside routes, not _auth)
app.include_router(integrations_router)
app.include_router(integrations_admin_router, dependencies=_auth)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "graphx-connect"}


@app.get("/api/stats")
async def get_stats(_: VGAdmin, db: AsyncSession = Depends(get_db)):
    suppliers = (await db.execute(select(func.count()).select_from(Supplier))).scalar()
    # Dashboard "total catalog" should reflect live products only — archived
    # rows would inflate the counter and confuse admins about why category
    # imports don't seem to grow it. Total-including-archived is still
    # available via the /products list with explicit filter.
    products = (await db.execute(
        select(func.count())
        .select_from(Product)
        .where(Product.archived_at.is_(None))
    )).scalar()
    variants = (await db.execute(select(func.count()).select_from(ProductVariant))).scalar()
    
    # Calculate health (success rate of jobs in last 24h)
    from datetime import datetime, timedelta, timezone
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    from modules.sync_jobs.models import SyncJob
    jobs_24h = (await db.execute(
        select(SyncJob).where(SyncJob.started_at >= yesterday)
    )).scalars().all()
    
    total_jobs = len(jobs_24h)
    success_jobs = len([j for j in jobs_24h if j.status in ("success", "completed", "partial_success")])
    health = round(success_jobs / total_jobs * 100, 1) if total_jobs > 0 else None

    total_processed = sum(j.records_processed for j in jobs_24h)

    return {
        "suppliers": suppliers,
        "products": products,
        "variants": variants,
        "health": health,
        "total_processed": total_processed,
    }
