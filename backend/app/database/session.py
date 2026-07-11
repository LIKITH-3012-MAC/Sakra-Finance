"""
Database session management.
Provides a session factory and a FastAPI dependency generator.
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.database.connection import engine

# Async session factory bound to the application engine
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Ensures the session is closed after the request completes.
    """
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
