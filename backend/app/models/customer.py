"""
Customer model – represents loan customers with encrypted Aadhaar data.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    phone_number = Column(String(15), nullable=False, index=True)
    address = Column(Text, nullable=True)
    aadhar_hash = Column(String(64), unique=True, nullable=False, index=True)
    aadhar_encrypted = Column(Text, nullable=False)
    aadhar_masked = Column(String(20), nullable=True)
    promissory_note = Column(Text, nullable=True)
    date_of_birth = Column(String(50), nullable=True)
    gender = Column(String(20), nullable=True)
    occupation = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    version_id = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


    # ── Relationships ────────────────────────────────────────────
    creator = relationship("User", back_populates="customers_created", foreign_keys=[created_by])
    documents = relationship("CustomerDocument", back_populates="customer", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="customer")
    notifications = relationship("Notification", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name='{self.name}')>"
