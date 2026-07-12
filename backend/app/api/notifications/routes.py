"""
Notification routes: listing, marking as read, and manual audit trigger.
"""
import logging
from datetime import date
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.notification import Notification
from app.schemas.common import APIResponse
from app.schemas.notification import NotificationResponse
from app.services.scheduler_service import run_daily_overdue_check
from app.services.notification_service import notification_bus

logger = logging.getLogger("sakra.notifications")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]


@router.get("/", response_model=APIResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all notifications for the current user, ordered by newest first.
    """
    stmt = select(Notification).filter(
        Notification.user_id == current_user.id,
    ).order_by(Notification.sent_at.desc())
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    notifications_data = [
        NotificationResponse.model_validate(n).model_dump(mode="json")
        for n in notifications
    ]

    unread_count = sum(1 for n in notifications if not n.is_read)

    return APIResponse(
        success=True,
        message=f"Retrieved {len(notifications_data)} notifications",
        data={
            "notifications": notifications_data,
            "total": len(notifications_data),
            "unread_count": unread_count,
        },
    )


@router.patch("/{notification_id}/read", response_model=APIResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a single notification as read.
    """
    stmt = select(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    notification = result.scalars().first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()

    return APIResponse(
        success=True,
        message="Notification marked as read",
        data=NotificationResponse.model_validate(notification).model_dump(mode="json"),
    )


@router.post("/read-all", response_model=APIResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all notifications for the current user as read.
    """
    stmt = update(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).values(is_read=True)
    res = await db.execute(stmt)
    updated_count = res.rowcount

    await db.commit()

    return APIResponse(
        success=True,
        message=f"Marked {updated_count} notifications as read",
        data={"marked_count": updated_count},
    )


@router.post("/trigger-audit", response_model=APIResponse)
async def trigger_manual_audit(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Manually trigger the daily overdue loan check. Requires ADMIN role.
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result = await run_daily_overdue_check(db, today)

    return APIResponse(
        success=True,
        message=f"Overdue audit completed. {result['total_overdue']} overdue loans found.",
        data=result,
    )


@router.get("/stream")
async def stream_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events (SSE) stream for real-time notification delivery.
    """
    queue = asyncio.Queue()
    notification_bus.register(current_user.id, queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait for next notification (timeout to send keep-alive comment)
                    notif_data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {json.dumps(notif_data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            notification_bus.unregister(current_user.id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
