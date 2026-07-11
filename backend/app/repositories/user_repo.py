"""
User repository with static methods for CRUD operations.
All queries automatically filter out soft-deleted users.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password
from app.schemas.user import UserCreate, UserUpdate


class UserRepository:
    """Repository for User model database operations."""

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get a user by their ID, excluding soft-deleted users."""
        return db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False,
        ).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        """Get a user by their username, excluding soft-deleted users."""
        return db.query(User).filter(
            User.username == username,
            User.is_deleted == False,
        ).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """Get a user by their email, excluding soft-deleted users."""
        return db.query(User).filter(
            User.email == email,
            User.is_deleted == False,
        ).first()

    @staticmethod
    def create(db: Session, schema: UserCreate, status: str = "active") -> User:
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
        db.flush()
        return user

    @staticmethod
    def update(db: Session, user: User, schema: UserUpdate) -> User:
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
        db.flush()
        return user

    @staticmethod
    def list_all(db: Session) -> list[User]:
        """Get all non-deleted users, ordered by creation date descending."""
        return db.query(User).filter(
            User.is_deleted == False,
        ).order_by(User.created_at.desc()).all()

    @staticmethod
    def soft_delete(db: Session, user: User) -> User:
        """Soft delete a user by setting is_deleted flag."""
        user.is_deleted = True
        user.status = "inactive"
        db.flush()
        return user
