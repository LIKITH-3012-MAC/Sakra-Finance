"""
User-related Pydantic schemas for authentication, creation, and management.
"""
import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

VALID_ROLES = ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "AUDITOR", "DATA_ENTRY", "VIEWER"]
INVITABLE_ROLES = ["ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "AUDITOR", "DATA_ENTRY", "VIEWER"]


class UserLogin(BaseModel):
    """Schema for user login requests."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """Schema for creating a new user with full validation."""
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    role: str = Field(...)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(VALID_ROLES)}")
        return v


class UserInvite(BaseModel):
    """Schema for inviting a new user via email. Cannot invite SUPER_ADMIN."""
    email: EmailStr
    role: str = Field(...)

    @field_validator("role")
    @classmethod
    def validate_invitable_role(cls, v: str) -> str:
        if v not in INVITABLE_ROLES:
            raise ValueError(f"Cannot invite with role '{v}'. Allowed roles: {', '.join(INVITABLE_ROLES)}")
        return v


class UserUpdate(BaseModel):
    """Schema for updating user properties."""
    role: Optional[str] = None
    status: Optional[str] = None
    full_name: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_language: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(VALID_ROLES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        valid_statuses = ["active", "inactive", "suspended", "locked", "INVITED"]
        if v is not None and v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


from app.schemas.common import ISTDateTime

class UserResponse(BaseModel):
    """Schema for user data in API responses."""
    id: int
    username: str
    email: str
    role: str
    status: str
    full_name: Optional[str] = None
    employee_code: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_language: Optional[str] = "en"
    created_at: ISTDateTime
    updated_at: Optional[ISTDateTime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for JWT token response after authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900
