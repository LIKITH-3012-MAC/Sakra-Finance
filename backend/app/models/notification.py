"""
Notification model – stores user/customer notifications.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        Index("idx_notifications_sent_at", "sent_at"),
        Index("idx_notifications_user_is_read_sent_at", "user_id", "is_read", "sent_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    notification_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])
    customer = relationship("Customer", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type='{self.notification_type}', is_read={self.is_read})>"
