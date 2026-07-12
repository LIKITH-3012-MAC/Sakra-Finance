"""
UserPermission model – represents custom granular privileges assigned to specific employees.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_name = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<UserPermission(id={self.id}, user_id={self.user_id}, name='{self.permission_name}')>"
