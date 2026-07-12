import asyncio
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger("sakra.notifications")

class NotificationBus:
    """In-memory notification bus for Server-Sent Events (SSE) broadcasting."""
    def __init__(self):
        self.listeners = {}

    def register(self, user_id: int, queue: asyncio.Queue):
        if user_id not in self.listeners:
            self.listeners[user_id] = []
        self.listeners[user_id].append(queue)
        logger.debug(f"User {user_id} registered to notification stream.")

    def unregister(self, user_id: int, queue: asyncio.Queue):
        if user_id in self.listeners:
            if queue in self.listeners[user_id]:
                self.listeners[user_id].remove(queue)
            if not self.listeners[user_id]:
                del self.listeners[user_id]
            logger.debug(f"User {user_id} unregistered from notification stream.")

    def broadcast(self, user_id: int, event_data: dict):
        if user_id in self.listeners:
            for queue in self.listeners[user_id]:
                queue.put_nowait(event_data)

notification_bus = NotificationBus()

async def create_system_notification(
    db: AsyncSession,
    notification_type: str,
    message: str,
    customer_id: int = None
) -> list[Notification]:
    """
    Creates Notification entries in the database for all active users.
    Returns a list of created Notification models (which should be committed by the caller).
    """
    try:
        stmt = select(User).filter(User.is_deleted == False)
        res = await db.execute(stmt)
        users = res.scalars().all()
    except Exception as e:
        logger.error(f"Failed to fetch users for notifications: {e}")
        return []

    created_notifs = []
    for u in users:
        notif = Notification(
            user_id=u.id,
            customer_id=customer_id,
            notification_type=notification_type,
            message=message
        )
        db.add(notif)
        created_notifs.append(notif)
        
    return created_notifs

def push_realtime_notifications(notifications: list[Notification]):
    """
    Pushes committed notifications to the in-memory bus for real-time SSE streaming.
    Should be called after committing the database transaction.
    """
    from app.schemas.notification import NotificationResponse
    for n in notifications:
        try:
            data = NotificationResponse.model_validate(n).model_dump(mode="json")
            notification_bus.broadcast(n.user_id, data)
        except Exception as e:
            logger.error(f"Failed to broadcast real-time notification to user {n.user_id}: {e}")
