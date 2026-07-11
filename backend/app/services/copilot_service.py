import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.copilot_session import CopilotSession
from app.models.copilot_message import CopilotMessage

logger = logging.getLogger("sakra.copilot_service")

class CopilotService:
    """Service layer to manage AI copilot database persistence for sessions and messages."""

    @staticmethod
    def get_or_create_session(db: Session, user_id: int, session_id: str) -> CopilotSession:
        """Fetch or create a copilot session for a given user."""
        session = db.query(CopilotSession).filter(
            CopilotSession.session_id == session_id
        ).first()

        if not session:
            session = CopilotSession(
                user_id=user_id,
                session_id=session_id,
                created_at=datetime.utcnow()
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info("Created new copilot session: %s for user %d", session_id, user_id)
        
        return session

    @staticmethod
    def get_session_history(db: Session, user_id: int) -> List[CopilotMessage]:
        """Load past messages across all sessions of the given user."""
        # Find user's sessions
        sessions = db.query(CopilotSession).filter(CopilotSession.user_id == user_id).all()
        session_ids = [s.session_id for s in sessions]
        if not session_ids:
            return []

        # Load messages ordered by timestamp
        return db.query(CopilotMessage).filter(
            CopilotMessage.session_id.in_(session_ids)
        ).order_by(CopilotMessage.timestamp.asc()).all()

    @staticmethod
    def add_message(db: Session, session_id: str, role: str, message: str, response: Optional[str] = None) -> CopilotMessage:
        """Store message and response securely in MySQL."""
        msg = CopilotMessage(
            session_id=session_id,
            role=role,
            message=message,
            response=response,
            timestamp=datetime.utcnow()
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def clear_history(db: Session, user_id: int):
        """Delete all copilot sessions and messages for the user."""
        sessions = db.query(CopilotSession).filter(CopilotSession.user_id == user_id).all()
        for s in sessions:
            db.delete(s)
        db.commit()
        logger.info("Cleared copilot history for user %d", user_id)
