"""
Central timezone utility for Sakra Finance.
All datetime generation across the platform must use these helpers
to ensure consistent IST (Asia/Kolkata) timestamps.
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return current time in IST (timezone-aware)."""
    return datetime.now(IST)


def now_ist_naive() -> datetime:
    """
    Return current IST time as a naive datetime.
    Use this for SQLAlchemy DATETIME columns that store without timezone info.
    The raw DB value will read as IST directly.
    """
    return datetime.now(IST).replace(tzinfo=None)


def today_ist() -> date:
    """Return current date in IST."""
    return datetime.now(IST).date()

