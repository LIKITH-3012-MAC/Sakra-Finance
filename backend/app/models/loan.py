"""
Loan model – represents a loan issued to a customer.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_formula = Column(String(50), nullable=False)
    interest_rate = Column(Numeric(8, 4), nullable=False)
    loan_start_date = Column(Date, nullable=False, index=True)
    loan_end_date = Column(Date, nullable=False, index=True)
    duration_days = Column(Integer, default=100, nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version_id = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── New calculated columns ───────────────────────────────────
    interest_amount = Column(Numeric(15, 2), nullable=True)
    total_repayable_amount = Column(Numeric(15, 2), nullable=True)
    daily_installment = Column(Numeric(15, 2), nullable=True)
    remaining_balance = Column(Numeric(15, 2), nullable=True)

    # ── Relationships ────────────────────────────────────────────
    customer = relationship("Customer", back_populates="loans")
    creator = relationship("User", back_populates="loans_created", foreign_keys=[created_by])
    schedules = relationship("LoanSchedule", back_populates="loan", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="loan")
    credit_scores = relationship("CreditScore", back_populates="loan")

    @property
    def computed_interest_amount(self):
        if self.interest_amount is not None:
            return self.interest_amount
        from app.services.interest import calculate_interest
        return calculate_interest(self.principal_amount, self.interest_rate, self.interest_formula, self.duration_days)

    @property
    def computed_total_repayable_amount(self):
        if self.total_repayable_amount is not None:
            return self.total_repayable_amount
        return self.principal_amount + self.computed_interest_amount

    @property
    def computed_daily_installment(self):
        if self.daily_installment is not None:
            return self.daily_installment
        from decimal import Decimal, ROUND_HALF_UP
        return (self.computed_total_repayable_amount / Decimal(str(self.duration_days))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def computed_remaining_balance(self):
        if self.remaining_balance is not None:
            return self.remaining_balance
        from decimal import Decimal
        total_paid = sum((p.amount_paid for p in self.payments), Decimal("0"))
        return max(self.computed_total_repayable_amount - total_paid, Decimal("0"))

    def __repr__(self) -> str:
        return f"<Loan(id={self.id}, customer_id={self.customer_id}, status='{self.status}')>"
