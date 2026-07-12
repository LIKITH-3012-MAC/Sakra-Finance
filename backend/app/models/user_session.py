"""
UserSession model – handles employee active sessions, devices, and token rotation constraints.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Index
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class UserSession(Base):
    __tablename__ = "user_sessions"

    __table_args__ = (
        Index("idx_sessions_created_at", "created_at"),
        Index("idx_sessions_is_active", "is_active"),
        Index("idx_sessions_user_created_at", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, index=True) # UUID Session ID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_fingerprint = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True) # supports IPv4 and IPv6
    user_agent = Column(String(500), nullable=True)
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_active_at = Column(DateTime, default=now_ist_naive, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    def __repr__(self) -> str:
        return f"<UserSession(id='{self.id}', user_id={self.user_id}, is_active={self.is_active})>"
