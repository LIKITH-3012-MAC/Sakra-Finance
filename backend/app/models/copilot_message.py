from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("copilot_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=now_ist_naive, nullable=False)

    # Relationships
    session = relationship("CopilotSession", back_populates="messages")
