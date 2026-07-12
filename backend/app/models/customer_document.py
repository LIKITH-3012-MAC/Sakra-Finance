"""
CustomerDocument model – stores document blobs and metadata for customer KYC files.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.timezone import now_ist_naive


class CustomerDocument(Base):
    __tablename__ = "customer_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(50), nullable=False) # e.g. "PROFILE_PHOTO", "AADHAAR", "PROMISSORY_NOTE"
    file_blob = Column(LONGBLOB, nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # ── Relationships ────────────────────────────────────────────
    customer = relationship("Customer", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<CustomerDocument(id={self.id}, type='{self.document_type}', filename='{self.filename}')>"
