"""
AuditLog model – immutable audit trail for all data mutations.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_actor_id", "actor_id"),
        Index("idx_audit_logs_actor_created_at", "actor_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    table_name = Column(String(50), nullable=False, index=True)
    record_id = Column(Integer, nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    actor = relationship("User", back_populates="audit_logs", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', table='{self.table_name}')>"
