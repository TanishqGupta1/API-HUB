"""Maps Supplier.adapter_class string -> BaseAdapter subclass.

Adapter modules self-register at import time. main.py imports each adapter
module so the registry is populated by the time routes mount.
"""
from __future__ import annotations

from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from modules.import_jobs.base import BaseAdapter


class AdapterNotConfiguredError(Exception):
    """supplier.adapter_class is NULL — operator must set one before importing."""


class AdapterNotRegisteredError(Exception):
    """supplier.adapter_class points at a name nobody has registered."""


ADAPTERS: dict[str, Type[BaseAdapter]] = {}


def register_adapter(name: str, cls: Type[BaseAdapter]) -> None:
    if not issubclass(cls, BaseAdapter):
        raise TypeError(f"{cls!r} is not a BaseAdapter subclass")
    ADAPTERS[name] = cls


def get_adapter(supplier, db: AsyncSession) -> BaseAdapter:
    adapter_key = getattr(supplier, "adapter_class", None)
    if not adapter_key:
        raise AdapterNotConfiguredError(
            f"Supplier {getattr(supplier, 'name', '?')} has no adapter_class set"
        )
    cls = ADAPTERS.get(adapter_key)
    if cls is None:
        raise AdapterNotRegisteredError(
            f"adapter_class {adapter_key!r} not registered. "
            f"Known: {sorted(ADAPTERS)}"
        )
    return cls(supplier=supplier, db=db)
