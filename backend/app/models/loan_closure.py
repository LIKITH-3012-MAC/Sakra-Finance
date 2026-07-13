"""
LoanClosure model – immutable settlement record created when a loan is closed.
Preserves all financial data at the moment of closure for permanent archival.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class LoanClosure(Base):
    __tablename__ = "loan_closures"

    __table_args__ = (
        Index("idx_loan_closures_loan_id", "loan_id"),
        Index("idx_loan_closures_customer_id", "customer_id"),
        Index("idx_loan_closures_closed_at", "closed_at"),
        Index("idx_loan_closures_closed_by", "closed_by"),
        Index("idx_loan_closures_reference", "settlement_reference"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    # ── Financial Snapshot ───────────────────────────────────────
    settlement_amount = Column(Numeric(15, 2), nullable=False)
    remaining_before = Column(Numeric(15, 2), nullable=False)
    remaining_after = Column(Numeric(15, 2), nullable=False, default=0)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_amount = Column(Numeric(15, 2), nullable=False)
    total_repayable = Column(Numeric(15, 2), nullable=False)
    total_collected = Column(Numeric(15, 2), nullable=False)
    daily_installment = Column(Numeric(15, 2), nullable=False)
    equivalent_days = Column(Numeric(10, 2), nullable=False)
    completion_percent = Column(Numeric(5, 2), nullable=False, default=100)

    # ── Credit & Risk Snapshot ───────────────────────────────────
    credit_score = Column(Numeric(5, 1), nullable=True)
    risk_level = Column(String(20), nullable=True)

    # ── Reference & Identity ─────────────────────────────────────
    settlement_reference = Column(String(50), unique=True, nullable=False)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    closed_by_username = Column(String(50), nullable=False)
    closed_by_role = Column(String(20), nullable=False)

    # ── Authorization & Compliance ───────────────────────────────
    authorization_verified = Column(Boolean, default=False, nullable=False)
    is_partial_settlement = Column(Boolean, default=False, nullable=False)
    remarks = Column(Text, nullable=True)

    # ── Client Metadata ──────────────────────────────────────────
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # ── Timestamps ───────────────────────────────────────────────
    closed_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    loan = relationship("Loan", foreign_keys=[loan_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    closer = relationship("User", foreign_keys=[closed_by])

    def __repr__(self) -> str:
        return f"<LoanClosure(id={self.id}, loan_id={self.loan_id}, ref='{self.settlement_reference}')>"
