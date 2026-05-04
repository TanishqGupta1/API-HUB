from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "vg_admin"
    customer_id: UUID | None = None


class UserRead(BaseModel):
    id: UUID
    email: str
    role: str
    customer_id: UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class SetupRequest(BaseModel):
    email: str
    password: str
