from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncJobRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    job_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_products: int = 0
    success_count: int = 0
    failed_count: int = 0
    records_processed: int = 0
    error_log: Optional[str] = None
    errors: Optional[list] = None
    discovery_mode: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SyncJobCreate(BaseModel):
    supplier_id: UUID
    supplier_name: str
    job_type: str
