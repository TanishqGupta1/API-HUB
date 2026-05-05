from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "vg_admin"
    customer_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    customer_id: UUID | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SetupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()
