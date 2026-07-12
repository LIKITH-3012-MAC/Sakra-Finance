"""
PaymentAdjustment model – records corrections/adjustments to payments.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class PaymentAdjustment(Base):
    __tablename__ = "payment_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    old_amount = Column(Numeric(15, 2), nullable=False)
    new_amount = Column(Numeric(15, 2), nullable=False)
    reason = Column(Text, nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    payment = relationship("Payment", back_populates="adjustments")
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self) -> str:
        return f"<PaymentAdjustment(id={self.id}, payment_id={self.payment_id})>"
