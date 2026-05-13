from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


SelectionStatus = Literal["selected", "pushed", "stale", "failed"]


class SelectionBulkCreate(BaseModel):
    product_ids: list[UUID]


class SelectionRead(BaseModel):
    """Selection row + flattened product fields (saves the FE an extra fetch).

    `status` mirrors the stored column on `customer_product_selections`,
    except 'failed' which is layered on at read time when the latest
    push_log entry for this (customer, product) is 'failed'.
    """

    id: UUID
    customer_id: UUID
    product_id: UUID
    status: SelectionStatus
    added_at: datetime
    pushed_at: Optional[datetime] = None

    # Embedded product convenience fields
    supplier_id: UUID
    supplier_sku: str
    product_name: str
    product_type: str
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    last_synced: Optional[datetime] = None

    # Decoration visibility (matches push_candidates payload — admins rely
    # on this on the catalog page).
    supplier_has_decoration_overlay: bool = False
    decoration_ready: bool = False

    model_config = ConfigDict(from_attributes=True)


class SelectionBulkResponse(BaseModel):
    added: int
    already_selected: int
    not_found: int
