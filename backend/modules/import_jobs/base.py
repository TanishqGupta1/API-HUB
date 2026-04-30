"""BaseAdapter interface and core import types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Optional, List
from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from modules.suppliers.models import Supplier
    from modules.catalog.schemas import ProductIngest


class DiscoveryMode(str, Enum):
    """Modes for discovering products from a supplier."""
    FULL = "full"
    DELTA = "delta"
    FIRST_N = "first_n"
    EXPLICIT_LIST = "explicit_list"


class ProductRef(BaseModel):
    """A reference to a product in the supplier's system."""
    supplier_sku: str
    part_id: Optional[str] = None


class AdapterError(Exception):
    """Base class for adapter-related errors."""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class AuthError(AdapterError):
    """Raised when authentication with the supplier fails."""
    pass


class SupplierError(AdapterError):
    """Raised when the supplier's API returns an error for a specific product."""
    pass


class TransientError(AdapterError):
    """Raised for transient errors (network, timeout, 5xx) that may be retried."""
    pass


class BaseAdapter(ABC):
    """Abstract base class for all supplier adapters."""

    def __init__(self, supplier: Supplier, db: AsyncSession):
        self.supplier = supplier
        self.db = db

    @abstractmethod
    async def discover(self, mode: DiscoveryMode, limit: Optional[int] = None, explicit_list: Optional[List[str]] = None) -> List[ProductRef]:
        """Discover products available for import."""
        pass

    @abstractmethod
    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        """Fetch full product details and normalize to ProductIngest shape."""
        pass

    @abstractmethod
    async def discover_changed(self, since: str) -> List[ProductRef]:
        """Discover products that have changed since a given timestamp/marker."""
        pass
