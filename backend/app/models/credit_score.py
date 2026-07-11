"""
CreditScore model – tracks customer credit scores over time.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import relationship

from app.database.connection import Base


class CreditScore(Base):
    __tablename__ = "credit_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    score = Column(Numeric(5, 1), nullable=False)
    previous_score = Column(Numeric(5, 1), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    customer = relationship("Customer")
    loan = relationship("Loan", back_populates="credit_scores")

    def __repr__(self) -> str:
        return f"<CreditScore(id={self.id}, customer_id={self.customer_id}, score={self.score})>"
