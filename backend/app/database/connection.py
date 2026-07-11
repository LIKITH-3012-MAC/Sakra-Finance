"""
Database engine and declarative base configuration.
Supports both MySQL and SQLite with appropriate connection settings.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings


def _build_engine():
    """
    Build the SQLAlchemy engine with driver-specific settings.

    - MySQL: connection pool with pre-ping, recycling, and overflow.
    - SQLite: single-threaded connect args.
    """
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
        )

    # MySQL / other production databases
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
        echo=settings.DEBUG,
    )


engine = _build_engine()
Base = declarative_base()
