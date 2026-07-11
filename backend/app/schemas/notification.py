"""
Notification-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


from app.schemas.common import ISTDateTime

class NotificationResponse(BaseModel):
    """Schema for notification data in API responses."""
    id: int
    user_id: int
    customer_id: Optional[int] = None
    notification_type: str
    message: str
    is_read: bool = False
    sent_at: ISTDateTime

    model_config = {"from_attributes": True}

