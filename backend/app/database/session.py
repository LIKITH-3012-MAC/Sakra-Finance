"""
Database session management.
Provides a session factory and a FastAPI dependency generator.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import engine

# Session factory bound to the application engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Ensures the session is closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
