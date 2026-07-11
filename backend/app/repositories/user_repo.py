"""
User repository with static methods for CRUD operations.
All queries automatically filter out soft-deleted users.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import hash_password
from app.schemas.user import UserCreate, UserUpdate


class UserRepository:
    """Repository for User model database operations."""

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by their ID, excluding soft-deleted users."""
        stmt = select(User).filter(
            User.id == user_id,
            User.is_deleted == False,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get a user by their username, excluding soft-deleted users."""
        stmt = select(User).filter(
            User.username == username,
            User.is_deleted == False,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by their email, excluding soft-deleted users."""
        stmt = select(User).filter(
            User.email == email,
            User.is_deleted == False,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, schema: UserCreate, status: str = "active") -> User:
        """
        Create a new user with hashed password.

        Args:
            db: Database session
            schema: UserCreate schema with user data
            status: Initial user status (default: 'active')

        Returns:
            The created User object
        """
        user = User(
            username=schema.username,
            email=schema.email,
            password_hash=hash_password(schema.password),
            role=schema.role,
            status=status,
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def update(db: AsyncSession, user: User, schema: UserUpdate) -> User:
        """
        Update user fields from schema, only updating provided fields.

        Args:
            db: Database session
            user: Existing User object to update
            schema: UserUpdate schema with optional fields

        Returns:
            The updated User object
        """
        update_data = schema.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        await db.flush()
        return user

    @staticmethod
    async def list_all(db: AsyncSession) -> list[User]:
        """Get all non-deleted users, ordered by creation date descending."""
        stmt = select(User).filter(
            User.is_deleted == False,
        ).order_by(User.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def soft_delete(db: AsyncSession, user: User) -> User:
        """Soft delete a user by setting is_deleted flag."""
        user.is_deleted = True
        user.status = "inactive"
        await db.flush()
        return user
