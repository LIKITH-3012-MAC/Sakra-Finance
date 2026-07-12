"""
JWT token utilities for access and refresh tokens.
Uses PyJWT with HS256 algorithm.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import jwt

from app.core.config import settings


from app.utils.timezone import now_ist

ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    """
    Create a short-lived JWT access token.
    """
    now = now_ist()
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = data.copy()
    payload.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),
    })

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a long-lived JWT refresh token.
    """
    now = now_ist()
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload = data.copy()
    payload.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),
    })

    return jwt.encode(payload, settings.JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)



def decode_token(token: str, is_refresh: bool = False) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token string to decode.
        is_refresh: If True, use the refresh secret key; otherwise use the access secret key.

    Returns:
        The decoded token payload as a dictionary.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
    """
    secret = settings.JWT_REFRESH_SECRET_KEY if is_refresh else settings.JWT_SECRET_KEY

    return jwt.decode(token, secret, algorithms=[ALGORITHM])
