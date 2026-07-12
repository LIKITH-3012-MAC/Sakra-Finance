"""
LoginLog model – security audit records for tracking sign-in operations.
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    employee_id = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    ip_address = Column(String(45), nullable=True)
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    reason = Column(String(255), nullable=True) # e.g. "INVALID_PASSWORD", "SUCCESS"
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    def __repr__(self) -> str:
        return f"<LoginLog(id={self.id}, username='{self.username}', success={self.success})>"
