from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine

# Import all models so SQLAlchemy registers them before create_all
import modules.suppliers.models  # noqa: F401
import modules.catalog.models  # noqa: F401
import modules.customers.models  # noqa: F401
import modules.markup.models  # noqa: F401
import modules.push_log.models  # noqa: F401

from modules.suppliers.routes import router as suppliers_router
from modules.customers.routes import router as customers_router
from modules.markup.routes import router as markup_router
from modules.push_log.routes import router as push_log_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up on shutdown
    await engine.dispose()


app = FastAPI(
    title="VG Integration Hub",
    description="Middleware platform connecting wholesale supplier APIs to OnPrintShop storefronts.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow local frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(suppliers_router)
app.include_router(customers_router)
app.include_router(markup_router)
app.include_router(push_log_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "vg-integration-hub"}
