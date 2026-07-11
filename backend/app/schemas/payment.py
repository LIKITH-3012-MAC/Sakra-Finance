"""
Payment-related Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import date, datetime

VALID_PAYMENT_MODES = ["CASH", "UPI", "BANK_TRANSFER", "CHEQUE", "OTHER"]


class PaymentCreate(BaseModel):
    """Schema for recording a new payment."""
    loan_id: int = Field(..., gt=0)
    payment_date: date
    amount_paid: Decimal = Field(..., gt=0, description="Payment amount, must be positive")
    payment_mode: str = Field(default="CASH")
    remarks: Optional[str] = None


class PaymentUpdate(BaseModel):
    """Schema for modifying an existing payment with optimistic locking."""
    amount_paid: Decimal = Field(..., gt=0, description="Updated payment amount, must be positive")
    version_id: int = Field(..., description="Required for optimistic locking")


from app.schemas.common import ISTDateTime

class PaymentResponse(BaseModel):
    """Schema for payment data in API responses."""
    id: Optional[int] = None
    loan_id: int
    customer_id: int
    payment_date: date
    amount_paid: Decimal
    payment_mode: Optional[str] = None
    remarks: Optional[str] = None
    recorded_by: Optional[int] = None
    version_id: Optional[int] = None
    created_at: Optional[ISTDateTime] = None
    updated_at: Optional[ISTDateTime] = None

    # Dynamic fields for merged schedule payments
    expected_amount: Optional[Decimal] = None
    payment_status: Optional[str] = None
    recorded_by_name: Optional[str] = None

    model_config = {"from_attributes": True}

