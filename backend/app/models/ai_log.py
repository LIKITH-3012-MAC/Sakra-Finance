from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.database.connection import Base
from app.utils.timezone import now_ist_naive

class AIAuditLog(Base):
    __tablename__ = "ai_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    conversation_id = Column(String(100), index=True, nullable=False)
    question = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True)
    tools_used = Column(Text, nullable=True) # Comma-separated or JSON
    response_summary = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=now_ist_naive)
