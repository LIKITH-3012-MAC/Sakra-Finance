"""
Database engine and declarative base configuration.
Supports both MySQL and SQLite with appropriate connection settings.
"""

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings


def _build_engine():
    """
    Build the SQLAlchemy AsyncEngine with driver-specific settings.

    - MySQL: connection pool with pre-ping, recycling, and overflow.
    - SQLite: single-threaded connect args.
    """
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        # Convert sqlite to sqlite+aiosqlite for async compatibility
        if not url.startswith("sqlite+aiosqlite"):
            url = url.replace("sqlite", "sqlite+aiosqlite")
        return create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
        )

    # Convert mysql+pymysql to mysql+aiomysql for async compatibility
    if url.startswith("mysql+pymysql"):
        url = url.replace("mysql+pymysql", "mysql+aiomysql")
    elif url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+aiomysql://")

    # MySQL / other production databases with production-grade pooling
    return create_async_engine(
        url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=1800,
        pool_pre_ping=False,
        echo=settings.DEBUG,
    )


engine = _build_engine()
Base = declarative_base()
