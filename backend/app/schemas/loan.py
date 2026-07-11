"""
Loan-related Pydantic schemas with interest formula validation.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
import logging

logger = logging.getLogger("sakra.schemas.loan")
VALID_INTEREST_FORMULAS = ["FLAT", "REDUCING", "MONTHLY", "DAILY", "COMPOUND"]


class LoanCreate(BaseModel):
    """Schema for creating a new loan."""
    customer_id: int = Field(..., gt=0)
    principal_amount: Decimal = Field(..., gt=0, description="Loan principal amount, must be positive")
    interest_formula: str = Field(..., description="Interest calculation formula")
    interest_rate: Decimal = Field(..., ge=0, le=100, max_digits=8, decimal_places=4, description="Interest rate percentage")
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
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100, max_digits=8, decimal_places=4)
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

    # New fields
    interest_amount: Decimal
    total_repayable_amount: Decimal
    daily_installment: Decimal
    remaining_balance: Decimal

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def resolve_computed_fields(cls, data: Any) -> Any:
        if hasattr(data, "principal_amount"):
            # ORM object
            res = {}
            for col in data.__table__.columns:
                res[col.name] = getattr(data, col.name)
            
            res["created_at"] = data.created_at
            res["updated_at"] = data.updated_at
            
            if res.get("interest_amount") is None:
                res["interest_amount"] = data.computed_interest_amount
            if res.get("total_repayable_amount") is None:
                res["total_repayable_amount"] = data.computed_total_repayable_amount
            if res.get("daily_installment") is None:
                res["daily_installment"] = data.computed_daily_installment
            if res.get("remaining_balance") is None:
                res["remaining_balance"] = data.computed_remaining_balance
            
            return res
        elif isinstance(data, dict):
            # Dictionary
            if data.get("interest_amount") is None:
                from app.services.interest import calculate_interest
                principal = Decimal(str(data["principal_amount"]))
                rate = Decimal(str(data["interest_rate"]))
                formula = data["interest_formula"]
                duration = int(data["duration_days"])
                interest = calculate_interest(principal, rate, formula, duration)
                data["interest_amount"] = interest
            if data.get("total_repayable_amount") is None:
                data["total_repayable_amount"] = Decimal(str(data["principal_amount"])) + Decimal(str(data["interest_amount"]))
            if data.get("daily_installment") is None:
                data["daily_installment"] = (Decimal(str(data["total_repayable_amount"])) / Decimal(str(data["duration_days"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if data.get("remaining_balance") is None:
                data["remaining_balance"] = data["total_repayable_amount"]
        return data
