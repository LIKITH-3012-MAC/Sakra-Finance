"""
Customer-related Pydantic schemas with Aadhaar and phone validation.
"""
import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    """Schema for creating a new customer."""
    name: str = Field(..., min_length=1, max_length=255)
    phone_number: str = Field(..., min_length=10, max_length=15)
    address: Optional[str] = None
    aadhar_number: str = Field(..., min_length=12, max_length=12)
    promissory_note: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-+]", "", v)
        if not re.match(r"^\d{10,15}$", cleaned):
            raise ValueError("Phone number must contain 10-15 digits")
        return v

    @field_validator("aadhar_number")
    @classmethod
    def validate_aadhar_number(cls, v: str) -> str:
        if not re.match(r"^\d{12}$", v):
            raise ValueError("Aadhaar number must be exactly 12 digits")
        return v


class CustomerUpdate(BaseModel):
    """Schema for updating customer data with optimistic locking."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=15)
    address: Optional[str] = None
    promissory_note: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    remarks: Optional[str] = None
    version_id: int = Field(..., description="Required for optimistic locking")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = re.sub(r"[\s\-+]", "", v)
            if not re.match(r"^\d{10,15}$", cleaned):
                raise ValueError("Phone number must contain 10-15 digits")
        return v


from app.schemas.common import ISTDateTime

class CustomerResponse(BaseModel):
    """Schema for customer data in API responses."""
    id: int
    name: str
    phone_number: str
    address: Optional[str] = None
    aadhar_masked: Optional[str] = None
    promissory_note: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[int] = None
    version_id: int
    created_at: ISTDateTime
    updated_at: Optional[ISTDateTime] = None

    # Dynamic document presence properties
    has_profile_photo: bool = False
    has_aadhaar: bool = False
    has_promissory_note: bool = False

    # Dynamic collection intelligence fields
    pending_installments_count: Optional[int] = 0
    oldest_pending_date: Optional[str] = None
    latest_pending_date: Optional[str] = None
    pending_amount: Optional[float] = 0.0
    pending_dates: Optional[list[dict]] = []

    model_config = {"from_attributes": True}
