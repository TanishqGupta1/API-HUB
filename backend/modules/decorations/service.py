from __future__ import annotations

import uuid as uuid_mod

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.suppliers.models import Supplier


async def decoration_required(product: Product, db: AsyncSession) -> bool:
    """Return True if this product's supplier requires a decoration before push."""
    supplier = await db.get(Supplier, product.supplier_id)
    if supplier is None:
        return False
    return bool(supplier.has_decoration_overlay)


class DecorationMissingError(Exception):
    """Raised when a supplier requires decoration but none is saved."""


async def assert_decoration_ready(
    customer_id: uuid_mod.UUID,
    product: Product,
    db: AsyncSession,
) -> None:
    """Raise DecorationMissingError if decoration is required but absent."""
    from modules.decorations.models import CustomerProductDecoration

    if not await decoration_required(product, db):
        return

    row = await db.get(CustomerProductDecoration, (customer_id, product.id))
    if row is None or not row.decoration_options:
        raise DecorationMissingError(
            f"Product {product.supplier_sku} requires decoration before push "
            f"for customer {customer_id}"
        )
