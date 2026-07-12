"""
LoanSchedule model – represents individual installment entries for a loan.
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class LoanSchedule(Base):
    __tablename__ = "loan_schedules"

    __table_args__ = (
        UniqueConstraint("loan_id", "installment_number", name="uq_loan_installment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False, index=True)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    expected_amount = Column(Numeric(15, 2), nullable=False)
    paid_amount = Column(Numeric(15, 2), default=0, nullable=False)
    remaining_amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)
    updated_at = Column(DateTime, default=now_ist_naive, onupdate=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    loan = relationship("Loan", back_populates="schedules")

    def __repr__(self) -> str:
        return f"<LoanSchedule(id={self.id}, loan_id={self.loan_id}, installment={self.installment_number})>"
