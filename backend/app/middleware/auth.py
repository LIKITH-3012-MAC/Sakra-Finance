"""
Authentication middleware with JWT-based user validation and role-based access control.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.jwt import decode_token
from app.database.session import get_db
from app.models.user import User

logger = logging.getLogger("sakra.auth")

# HTTPBearer with auto_error=False allows us to handle missing tokens gracefully
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that extracts and validates the JWT access token,
    then returns the authenticated User object.

    Raises:
        HTTPException 401: If token is missing, invalid, or expired
        HTTPException 403: If user is deleted or inactive
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

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
        from app.models.user_session import UserSession
        active_sess = db.query(UserSession).filter(
            UserSession.id == sid,
            UserSession.is_active == True
        ).first()
        if not active_sess:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked or expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user = db.query(User).filter(User.id == int(user_id), User.is_deleted == False).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        db: Session = Depends(get_db),
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

        # 2. Check for database-driven explicit custom permission overrides
        has_permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.permission_name == self.required
        ).first()

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

