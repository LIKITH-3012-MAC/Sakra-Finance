"""
UserPasswordHistory model – records previous password hashes to prevent re-use of historical passwords.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.database.connection import Base

class UserPasswordHistory(Base):
    __tablename__ = "user_password_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UserPasswordHistory(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"
