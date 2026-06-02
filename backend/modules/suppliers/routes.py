import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import Category, Product, ProductImage, ProductVariant
from modules.common.sanitize import sanitize_error
from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.resolver import resolve_wsdl_url
from modules.ps_directory.client import get_ps_endpoints
from modules.sync_jobs.models import SyncJob

from .models import Supplier
from .schemas import SupplierCreate, SupplierRead
from .service import get_cached_endpoints

log = logging.getLogger(__name__)

_PROBE_TIMEOUT_SECONDS = 20
_AUTH_ERROR_HINTS = ("auth", "unauthorized", "credential", "id and password", "invalid id")

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.created_at.desc()))
    suppliers = result.scalars().all()
    out = []
    for s in suppliers:
        count = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.supplier_id == s.id)
            )
        ).scalar() or 0
        data = SupplierRead.model_validate(s)
        data.product_count = count
        data.has_credentials = bool(s.auth_config)
        out.append(data)
    return out


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    payload = body.model_dump()

    existing = (
        await db.execute(select(Supplier).where(Supplier.slug == payload["slug"]))
    ).scalar_one_or_none()

    # "Activate" flow is idempotent in the UI: if the supplier already exists,
    # update credentials/config instead of failing with a unique constraint 500.
    if existing:
        for key, val in payload.items():
            setattr(existing, key, val)
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        data = SupplierRead.model_validate(existing)
        data.product_count = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.supplier_id == existing.id)
            )
        ).scalar() or 0
        data.has_credentials = bool(existing.auth_config)
        return data

    supplier = Supplier(**payload)
    db.add(supplier)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Supplier with this slug already exists")
    await db.refresh(supplier)
    data = SupplierRead.model_validate(supplier)
    data.product_count = 0
    data.has_credentials = bool(supplier.auth_config)
    return data


async def get_supplier_by_id_or_slug(db: AsyncSession, id_or_slug: str) -> Supplier:
    # Try UUID first
    supplier = None
    try:
        uid = UUID(id_or_slug)
        result = await db.execute(select(Supplier).where(Supplier.id == uid))
        supplier = result.scalar_one_or_none()
    except ValueError:
        # Not a UUID, try slug
        result = await db.execute(select(Supplier).where(Supplier.slug == id_or_slug))
        supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(404, "Supplier not found")
    return supplier


@router.get("/{supplier_id_or_slug}", response_model=SupplierRead)
async def get_supplier(supplier_id_or_slug: str, db: AsyncSession = Depends(get_db)):
    supplier = await get_supplier_by_id_or_slug(db, supplier_id_or_slug)
    
    count = (
        await db.execute(
            select(func.count()).select_from(Product).where(Product.supplier_id == supplier.id)
        )
    ).scalar() or 0
    data = SupplierRead.model_validate(supplier)
    data.product_count = count
    data.has_credentials = bool(supplier.auth_config)
    return data


_SUPPLIER_PATCHABLE = {
    "name", "protocol", "promostandards_code", "base_url", "adapter_class",
    "auth_config", "field_mappings", "is_active", "protocol_config",
}


@router.patch("/{supplier_id_or_slug}", response_model=SupplierRead)
async def patch_supplier(
    supplier_id_or_slug: str, body: dict, db: AsyncSession = Depends(get_db)
):
    supplier = await get_supplier_by_id_or_slug(db, supplier_id_or_slug)

    for key, val in body.items():
        if key in _SUPPLIER_PATCHABLE:
            setattr(supplier, key, val)
            
    await db.commit()
    await db.refresh(supplier)
    
    count = (
        await db.execute(
            select(func.count()).select_from(Product).where(Product.supplier_id == supplier.id)
        )
    ).scalar() or 0
    data = SupplierRead.model_validate(supplier)
    data.product_count = count
    data.has_credentials = bool(supplier.auth_config)
    return data


@router.delete("/{supplier_id_or_slug}")
async def delete_supplier(supplier_id_or_slug: str, db: AsyncSession = Depends(get_db)):
    supplier = await get_supplier_by_id_or_slug(db, supplier_id_or_slug)

    product_ids = (
        await db.execute(select(Product.id).where(Product.supplier_id == supplier.id))
    ).scalars().all()
    if product_ids:
        await db.execute(delete(ProductVariant).where(ProductVariant.product_id.in_(product_ids)))
        await db.execute(delete(ProductImage).where(ProductImage.product_id.in_(product_ids)))
    await db.execute(delete(Product).where(Product.supplier_id == supplier.id))
    await db.execute(delete(Category).where(Category.supplier_id == supplier.id))
    await db.execute(delete(SyncJob).where(SyncJob.supplier_id == supplier.id))

    await db.delete(supplier)
    await db.commit()
    return {"deleted": True}


@router.get("/{supplier_id_or_slug}/endpoints")
async def get_supplier_endpoints(supplier_id_or_slug: str, db: AsyncSession = Depends(get_db)):
    supplier = await get_supplier_by_id_or_slug(db, supplier_id_or_slug)
    return await get_cached_endpoints(db, supplier.id)


@router.put("/{supplier_id_or_slug}/mappings")
async def save_supplier_mappings(
    supplier_id_or_slug: str, body: dict, db: AsyncSession = Depends(get_db)
):
    supplier = await get_supplier_by_id_or_slug(db, supplier_id_or_slug)
    supplier.field_mappings = body
    await db.commit()
    return {"saved": True, "supplier_id": str(supplier.id), "mappings": body}
async def _probe_promostandards(code: str | None, auth_config: dict) -> dict:
    """Real SOAP probe: resolve the supplier's Product Data WSDL via the PS
    directory, then call getProductSellable with the provided credentials. A
    successful response proves both connectivity and auth — the same path the
    nightly import will take. Replaces the prior fake directory-only check.
    """
    if not code:
        return {"ok": False, "error": "Missing PromoStandards code"}

    user_id = (auth_config or {}).get("id")
    password = (auth_config or {}).get("password")
    if not user_id or not password:
        return {"ok": False, "error": "Missing supplier id or password credentials"}

    try:
        endpoints = await get_ps_endpoints(code)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {
                "ok": False,
                "error": (
                    f"Supplier code '{code}' not found in PromoStandards directory. "
                    "Verify the code (usually lowercase) is correct."
                ),
            }
        return {"ok": False, "error": f"PromoStandards directory returned {e.response.status_code}"}
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        log.warning("PS directory unreachable for %s: %s", code, sanitize_error(e))
        return {"ok": False, "error": "Cannot reach PromoStandards directory — check network/DNS."}
    except Exception as e:  # noqa: BLE001 — directory edge cases shouldn't 500 the probe
        log.warning("PS directory lookup for %s failed: %s", code, sanitize_error(e))
        return {"ok": False, "error": "Directory check failed — see server logs for details."}

    wsdl_url = resolve_wsdl_url(endpoints, "product_data")
    if not wsdl_url:
        return {
            "ok": False,
            "error": (
                f"No Product Data endpoint published in the PromoStandards directory for '{code}'. "
                "Supplier must publish a productdata WSDL before catalog sync can run."
            ),
        }

    soap_client = PromoStandardsClient(wsdl_url, {"id": user_id, "password": password})
    try:
        product_ids = await asyncio.wait_for(
            soap_client.get_sellable_product_ids(), timeout=_PROBE_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": f"SOAP probe to {wsdl_url} timed out after {_PROBE_TIMEOUT_SECONDS}s",
        }
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        lowered = msg.lower()
        logger.warning("SOAP probe failed wsdl=%s error=%s", wsdl_url, msg[:500])
        if any(hint in lowered for hint in _AUTH_ERROR_HINTS):
            return {"ok": False, "error": "Authentication failed — check credentials."}
        return {"ok": False, "error": f"SOAP probe to {wsdl_url} failed — check WSDL URL and network."}

    return {
        "ok": True,
        "message": f"Connected to {code}: {len(product_ids)} sellable products visible",
        "wsdl_url": wsdl_url,
        "product_count": len(product_ids),
    }


@router.post("/test")
async def test_supplier_connection(body: dict):
    """Test connection to a supplier before adding it.

    PromoStandards (SanMar, S&S, etc.) → real SOAP probe via getProductSellable.
    REST/HMAC → credential-shape sanity check (real ping deferred until
    per-protocol adapters expose one).
    """
    protocol = body.get("protocol")

    if protocol == "promostandards":
        return await _probe_promostandards(
            code=body.get("promostandards_code"),
            auth_config=body.get("auth_config") or {},
        )

    # REST/HMAC fallback — shape-only check until per-protocol probes land.
    auth_config = body.get("auth_config") or {}
    if auth_config.get("id") and auth_config.get("password"):
        return {"ok": True, "message": "Credentials format valid"}
    return {"ok": False, "error": "Invalid configuration or missing credentials"}
