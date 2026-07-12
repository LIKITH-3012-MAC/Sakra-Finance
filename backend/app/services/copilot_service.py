import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.copilot_session import CopilotSession
from app.models.copilot_message import CopilotMessage
from app.utils.timezone import now_ist_naive

logger = logging.getLogger("sakra.copilot_service")

class CopilotService:
    """Service layer to manage AI copilot database persistence for sessions and messages."""

    @staticmethod
    async def get_or_create_session(db: AsyncSession, user_id: int, session_id: str) -> CopilotSession:
        """Fetch or create a copilot session for a given user."""
        stmt = select(CopilotSession).filter(
            CopilotSession.session_id == session_id
        )
        res = await db.execute(stmt)
        session = res.scalars().first()

        if not session:
            session = CopilotSession(
                user_id=user_id,
                session_id=session_id,
                created_at=now_ist_naive()
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            logger.info("Created new copilot session: %s for user %d", session_id, user_id)
        
        return session

    @staticmethod
    async def get_session_history(db: AsyncSession, user_id: int) -> List[CopilotMessage]:
        """Load past messages across all sessions of the given user."""
        # Find user's sessions
        stmt = select(CopilotSession).filter(CopilotSession.user_id == user_id)
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        session_ids = [s.session_id for s in sessions]
        if not session_ids:
            return []

        # Load messages ordered by timestamp
        stmt_msg = select(CopilotMessage).filter(
            CopilotMessage.session_id.in_(session_ids)
        ).order_by(CopilotMessage.timestamp.asc())
        res_msg = await db.execute(stmt_msg)
        return list(res_msg.scalars().all())

    @staticmethod
    async def add_message(db: AsyncSession, session_id: str, role: str, message: str, response: Optional[str] = None) -> CopilotMessage:
        """Store message and response securely in MySQL."""
        msg = CopilotMessage(
            session_id=session_id,
            role=role,
            message=message,
            response=response,
            timestamp=now_ist_naive()
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def clear_history(db: AsyncSession, user_id: int):
        """Delete all copilot sessions and messages for the user."""
        stmt = select(CopilotSession).filter(CopilotSession.user_id == user_id)
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        for s in sessions:
            await db.delete(s)
        await db.commit()
        logger.info("Cleared copilot history for user %d", user_id)
