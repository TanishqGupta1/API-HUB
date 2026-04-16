from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyncJobRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    job_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    records_processed: int
    error_log: str | None

    model_config = {"from_attributes": True}


class SyncJobCreate(BaseModel):
    supplier_id: UUID
    supplier_name: str
    job_type: str
