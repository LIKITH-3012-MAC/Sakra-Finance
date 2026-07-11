"""
MailLog model – tracks all emails sent from the Sakra Finance subsystem.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database.connection import Base

class MailLog(Base):
    __tablename__ = "mail_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient = Column(String(100), nullable=False, index=True)
    subject = Column(String(200), nullable=False)
    template = Column(String(50), nullable=False) # e.g. "INVITATION", "PASSWORD_RESET"
    status = Column(String(20), nullable=False, index=True) # SENT, FAILED
    provider_message_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<MailLog(id={self.id}, recipient='{self.recipient}', template='{self.template}')>"
