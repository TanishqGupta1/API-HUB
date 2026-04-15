from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, engine, get_db
from modules.catalog.models import Product, ProductVariant
from modules.catalog.routes import router as catalog_router
from modules.ps_directory.routes import router as ps_router
from modules.suppliers.models import Supplier
from modules.suppliers.routes import router as suppliers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="API-HUB", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suppliers_router)
app.include_router(ps_router)
app.include_router(catalog_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-hub"}


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    suppliers = (await db.execute(select(func.count()).select_from(Supplier))).scalar()
    products = (await db.execute(select(func.count()).select_from(Product))).scalar()
    variants = (await db.execute(select(func.count()).select_from(ProductVariant))).scalar()
    return {"suppliers": suppliers, "products": products, "variants": variants}
