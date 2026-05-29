import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# Centralized so a future "read_only" or "billing_admin" role can be added in one place.
Role = Literal["vg_admin", "customer_admin"]


def _validate_password_strength(value: str) -> str:
    if value != value.strip() or any(c.isspace() for c in value):
        raise ValueError("Password must not contain whitespace")
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("Password must contain at least one letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit")
    if len(set(value)) < 4:
        raise ValueError("Password must contain at least 4 unique characters")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    # Default to least-privileged role. vg_admin must be explicitly requested.
    role: Role = "customer_admin"
    customer_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)

    @model_validator(mode="after")
    def _scope_consistency(self) -> "UserCreate":
        if self.role == "vg_admin" and self.customer_id is not None:
            raise ValueError("vg_admin role must not be tied to a customer_id")
        if self.role == "customer_admin" and self.customer_id is None:
            raise ValueError("customer_admin role requires customer_id")
        return self


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    customer_id: UUID | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SignupSettings(BaseModel):
    enabled: bool


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
