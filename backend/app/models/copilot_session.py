from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class CopilotSession(Base):
    __tablename__ = "copilot_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)

    # Relationships
    messages = relationship("CopilotMessage", back_populates="session", cascade="all, delete-orphan")
