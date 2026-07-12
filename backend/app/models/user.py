"""
User model – represents application users (admins, agents, etc.).
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Index
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("idx_users_email_status", "email", "status"),
        Index("idx_users_role_status", "role", "status"),
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_updated_at", "updated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    version_id = Column(Integer, default=1, nullable=False)
    preferred_language = Column(String(5), nullable=False, default="en")
    
    
    # Password Reset & OTP flow attributes
    reset_otp_hash = Column(String(255), nullable=True, index=True)
    reset_otp_expires_at = Column(DateTime, nullable=True)
    reset_otp_attempts = Column(Integer, default=0, nullable=False)
    reset_token = Column(String(255), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # Employee profile attributes
    full_name = Column(String(100), nullable=True)
    employee_code = Column(String(50), unique=True, nullable=True)
    branch = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=now_ist_naive, nullable=False)
    updated_at = Column(DateTime, default=now_ist_naive, onupdate=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    customers_created = relationship("Customer", back_populates="creator", foreign_keys="Customer.created_by")
    loans_created = relationship("Loan", back_populates="creator", foreign_keys="Loan.created_by")
    payments_recorded = relationship("Payment", back_populates="recorder", foreign_keys="Payment.recorded_by")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")
    audit_logs = relationship("AuditLog", back_populates="actor", foreign_keys="AuditLog.actor_id")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
