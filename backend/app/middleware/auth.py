"""
Authentication middleware with JWT-based user validation and role-based access control.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.jwt import decode_token
from app.database.session import get_db
from app.models.user import User
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.auth")

# HTTPBearer with auto_error=False allows us to handle missing tokens gracefully
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that extracts and validates the JWT access token,
    then returns the authenticated User object.
    Caches user/session information in Redis to avoid unnecessary database lookups.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif request:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
    except Exception as e:
        logger.warning("Token decode failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure this is an access token, not a refresh token
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session activity status
    sid = payload.get("sid")
    if sid:
        session_cache_key = f"auth:session:{sid}"
        session_active = None
        if settings.CACHE_ENABLED:
            session_active = await cache.get(session_cache_key)

        if session_active is None:
            from app.models.user_session import UserSession
            stmt = select(UserSession).filter(
                UserSession.id == sid,
                UserSession.is_active == True
            )
            result = await db.execute(stmt)
            active_sess = result.scalars().first()
            if not active_sess:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked or expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if settings.CACHE_ENABLED:
                await cache.set(session_cache_key, True, expire_seconds=300)
        elif not session_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked or expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Check user cache
    user_cache_key = f"auth:user:{user_id}"
    cached_user = None
    if settings.CACHE_ENABLED:
        cached_user_dict = await cache.get(user_cache_key)
        if cached_user_dict:
            from datetime import datetime
            for date_field in ["reset_otp_expires_at", "reset_token_expires_at", "created_at", "updated_at"]:
                val = cached_user_dict.get(date_field)
                if val:
                    cached_user_dict[date_field] = datetime.fromisoformat(val)
            cached_user = User(**cached_user_dict)

    if not cached_user:
        stmt = select(User).filter(User.id == int(user_id), User.is_deleted == False)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or has been deleted",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if settings.CACHE_ENABLED:
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "password_hash": user.password_hash,
                "role": user.role,
                "status": user.status,
                "is_deleted": user.is_deleted,
                "version_id": user.version_id,
                "preferred_language": user.preferred_language,
                "reset_otp_hash": user.reset_otp_hash,
                "reset_otp_expires_at": user.reset_otp_expires_at.isoformat() if user.reset_otp_expires_at else None,
                "reset_otp_attempts": user.reset_otp_attempts,
                "reset_token": user.reset_token,
                "reset_token_expires_at": user.reset_token_expires_at.isoformat() if user.reset_token_expires_at else None,
                "full_name": user.full_name,
                "employee_code": user.employee_code,
                "branch": user.branch,
                "department": user.department,
                "designation": user.designation,
                "phone_number": user.phone_number,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            }
            await cache.set(user_cache_key, user_dict, expire_seconds=300)
    else:
        user = cached_user

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status}",
        )

    return user


class PermissionRequirement:
    """
    Dependency class for granular database-driven permission verification with legacy roles support.
    """

    def __init__(self, required: str | list[str]):
        self.required = required

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Legacy role check fallback if passed a list
        if isinstance(self.required, list):
            if current_user.role not in self.required:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{current_user.role}' does not have permission. Required one of: {', '.join(self.required)}",
                )
            return current_user

        from app.models.user_permission import UserPermission

        # 1. SUPER_ADMIN bypasses all security checks
        if current_user.role == "SUPER_ADMIN":
            return current_user

        # 2. Check for database-driven explicit custom permission overrides with caching
        perm_cache_key = f"auth:permission:{current_user.id}:{self.required}"
        has_permission = None
        if settings.CACHE_ENABLED:
            has_permission = await cache.get(perm_cache_key)

        if has_permission is None:
            stmt = select(UserPermission).filter(
                UserPermission.user_id == current_user.id,
                UserPermission.permission_name == self.required
            )
            result = await db.execute(stmt)
            perm_record = result.scalars().first()
            has_permission = perm_record is not None
            if settings.CACHE_ENABLED:
                await cache.set(perm_cache_key, has_permission, expire_seconds=300)

        if has_permission:
            return current_user

        # 3. Check for role-based default permissions fallback
        role_defaults = {
            "ADMIN": [
                "dashboard", "customers", "customer_edit", "daily_payments", 
                "loan_creation", "analytics", "reports", "audit_logs", 
                "settings", "copilot", "finance_ledger", "cash_book"
            ],
            "FINANCE_MANAGER": [
                "dashboard", "customers", "daily_payments", "analytics", 
                "reports", "finance_ledger", "cash_book"
            ],
            "COLLECTION_OFFICER": [
                "dashboard", "customers", "daily_payments"
            ],
            "AUDITOR": [
                "dashboard", "analytics", "reports", "audit_logs"
            ],
            "DATA_ENTRY": [
                "dashboard", "customers", "daily_payments"
            ],
            "VIEWER": [
                "dashboard"
            ]
        }

        user_allowed = role_defaults.get(current_user.role, [])
        if self.required in user_allowed:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{current_user.username}' does not have the required permission: '{self.required}'",
        )
