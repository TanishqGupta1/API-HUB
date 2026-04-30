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
    finished_at: Optional[datetime]
    records_processed: int
    error_log: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class SyncJobCreate(BaseModel):
    supplier_id: UUID
    supplier_name: str
    job_type: str
