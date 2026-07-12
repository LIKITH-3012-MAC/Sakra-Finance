"""
Payment model – records individual payments made against a loan.
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        UniqueConstraint("customer_id", "payment_date", "loan_id", name="uq_customer_payment_date_loan"),
        Index("idx_payments_created_at", "created_at"),
        Index("idx_payments_customer_payment_date", "customer_id", "payment_date"),
        Index("idx_payments_loan_created_at", "loan_id", "created_at"),
        Index("idx_payments_customer_created_at", "customer_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    expected_amount = Column(Numeric(15, 2), nullable=False)
    amount_paid = Column(Numeric(15, 2), nullable=False)
    remaining_amount = Column(Numeric(15, 2), nullable=False)
    payment_mode = Column(String(20), default="CASH", nullable=False)
    payment_status = Column(String(20), nullable=False, index=True)
    remarks = Column(Text, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version_id = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)
    updated_at = Column(DateTime, default=now_ist_naive, onupdate=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    loan = relationship("Loan", back_populates="payments")
    customer = relationship("Customer")
    recorder = relationship("User", back_populates="payments_recorded", foreign_keys=[recorded_by])
    adjustments = relationship("PaymentAdjustment", back_populates="payment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, loan_id={self.loan_id}, amount={self.amount_paid})>"
