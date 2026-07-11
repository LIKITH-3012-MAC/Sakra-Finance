"""
UserSession model – handles employee active sessions, devices, and token rotation constraints.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from app.database.connection import Base

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, index=True) # UUID Session ID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_fingerprint = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True) # supports IPv4 and IPv6
    user_agent = Column(String(500), nullable=True)
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UserSession(id='{self.id}', user_id={self.user_id}, is_active={self.is_active})>"
