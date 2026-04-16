from typing import Optional
from pydantic import BaseModel


class PSCompany(BaseModel):
    Code: str
    Name: str
    Type: str


class PSEndpoint(BaseModel):
    Name: Optional[str] = None
    ServiceType: Optional[str] = None
    Version: Optional[str] = None
    Status: Optional[str] = None
    ProductionURL: Optional[str] = None
    TestURL: Optional[str] = None
