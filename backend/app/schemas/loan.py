"""
Loan-related Pydantic schemas with interest formula validation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal
from datetime import date, datetime

VALID_INTEREST_FORMULAS = ["FLAT", "REDUCING", "COMPOUND"]


class LoanCreate(BaseModel):
    """Schema for creating a new loan."""
    customer_id: int = Field(..., gt=0)
    principal_amount: Decimal = Field(..., gt=0, description="Loan principal amount, must be positive")
    interest_formula: str = Field(..., description="Interest calculation formula")
    interest_rate: Decimal = Field(..., ge=0, description="Interest rate percentage")
    loan_start_date: date
    duration_days: int = Field(default=100, gt=0, description="Loan duration in days")

    @field_validator("interest_formula")
    @classmethod
    def validate_interest_formula(cls, v: str) -> str:
        upper_v = v.upper()
        if upper_v not in VALID_INTEREST_FORMULAS:
            raise ValueError(f"Interest formula must be one of: {', '.join(VALID_INTEREST_FORMULAS)}")
        return upper_v


class LoanUpdate(BaseModel):
    """Schema for updating loan data with optimistic locking."""
    principal_amount: Optional[Decimal] = Field(None, gt=0)
    interest_formula: Optional[str] = None
    interest_rate: Optional[Decimal] = Field(None, ge=0)
    loan_start_date: Optional[date] = None
    duration_days: Optional[int] = Field(None, gt=0)
    version_id: int = Field(..., description="Required for optimistic locking")

    @field_validator("interest_formula")
    @classmethod
    def validate_interest_formula(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            upper_v = v.upper()
            if upper_v not in VALID_INTEREST_FORMULAS:
                raise ValueError(f"Interest formula must be one of: {', '.join(VALID_INTEREST_FORMULAS)}")
            return upper_v
        return v


from app.schemas.common import ISTDateTime

class LoanResponse(BaseModel):
    """Schema for loan data in API responses."""
    id: int
    customer_id: int
    principal_amount: Decimal
    interest_formula: str
    interest_rate: Decimal
    loan_start_date: date
    loan_end_date: Optional[date] = None
    duration_days: int
    status: str
    version_id: int
    created_at: ISTDateTime
    updated_at: Optional[ISTDateTime] = None

    model_config = {"from_attributes": True}
