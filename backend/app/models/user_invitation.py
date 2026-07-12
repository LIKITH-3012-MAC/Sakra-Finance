"""
UserInvitation model – represents employee invitations with token validation and expiration.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(String(36), primary_key=True, index=True) # UUID
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=False)
    designation = Column(String(100), nullable=False)
    branch = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    role = Column(String(20), nullable=False)
    permission_template = Column(String(50), nullable=True) # e.g. "DEFAULT"
    temp_password_hash = Column(String(255), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, USED, REVOKED
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)
    updated_at = Column(DateTime, default=now_ist_naive, onupdate=now_ist_naive, nullable=False)

    def __repr__(self) -> str:
        return f"<UserInvitation(id='{self.id}', email='{self.email}', status='{self.status}')>"
