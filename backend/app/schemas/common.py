"""
Standard API response envelope for all Sakra Finance endpoints.
"""
from pydantic import BaseModel, Field, PlainSerializer
from typing import Any, Optional, Annotated
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

IST = ZoneInfo("Asia/Kolkata")

def serialize_ist_datetime(dt: datetime) -> str:
    if dt is None:
        return None
    if dt.tzinfo is None:
        # DB stores naive IST values, so attach IST timezone info for ISO format
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST).isoformat()

# ISTDateTime enforces serialization to Asia/Kolkata ISO format string
ISTDateTime = Annotated[datetime, PlainSerializer(serialize_ist_datetime, when_used="json")]


class ResponseMeta(BaseModel):
    """Metadata included with every API response."""
    timestamp: str = Field(default_factory=lambda: datetime.now(IST).isoformat())
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "v1"


class APIResponse(BaseModel):
    """Standard API response wrapper ensuring consistent response structure."""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[Any] = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
