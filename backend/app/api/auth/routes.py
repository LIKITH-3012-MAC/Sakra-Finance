"""
Authentication routes: login, refresh, logout, current user, invitations, account activations, and password OTPs.
"""
import uuid
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from pydantic import BaseModel, EmailStr

from app.core.security import hash_password, verify_password, validate_password_strength
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.user_session import UserSession
from app.models.user_invitation import UserInvitation
from app.models.user_password_history import UserPasswordHistory
from app.models.login_log import LoginLog
from app.models.notification import Notification
from app.repositories.user_repo import UserRepository
from app.schemas.common import APIResponse
from app.schemas.user import UserLogin, UserResponse, TokenResponse
from app.services.audit import log_audit
from app.core.celery_app import send_email_async
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.auth")

router = APIRouter()

# Schema declarations
class AccountActivateRequest(BaseModel):
    token: str
    temporary_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/login", response_model=APIResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user. Creates a database session and returns access + refresh tokens.
    """
    user = await UserRepository.get_by_username(db, credentials.username)

    user_agent = request.headers.get("user-agent", "")
    ip_addr = request.client.host
    browser = "Chrome" if "Chrome" in user_agent else "Safari" if "Safari" in user_agent else "Firefox" if "Firefox" in user_agent else "Edge" if "Edge" in user_agent else "Unknown"
    os_name = "Windows" if "Windows" in user_agent else "Mac" if "Macintosh" in user_agent else "Linux" if "Linux" in user_agent else "Android" if "Android" in user_agent else "iPhone" if "iPhone" in user_agent else "Unknown"

    if not user or not verify_password(credentials.password, user.password_hash):
        # Log failure
        log = LoginLog(
            username=credentials.username,
            success=False,
            ip_address=ip_addr,
            browser=browser,
            os=os_name,
            device_type="Desktop",
            country="India",
            user_agent=user_agent,
            reason="INVALID_PASSWORD"
        )
        db.add(log)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if user.status != "active":
        log = LoginLog(
            username=user.username,
            role=user.role,
            employee_id=user.id,
            success=False,
            ip_address=ip_addr,
            browser=browser,
            os=os_name,
            device_type="Desktop",
            country="India",
            user_agent=user_agent,
            reason=f"ACCOUNT_LOCKED_{user.status.upper()}"
        )
        db.add(log)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status}. Please contact an administrator.",
        )

    # Establish new active database session record
    session_id = str(uuid.uuid4())
    user_session = UserSession(
        id=session_id,
        user_id=user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        browser=browser,
        os=os_name,
        country="India",
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(user_session)

    # Log login success audit details
    log = LoginLog(
        username=user.username,
        role=user.role,
        employee_id=user.id,
        success=True,
        ip_address=ip_addr,
        browser=browser,
        os=os_name,
        device_type="Desktop",
        country="India",
        user_agent=user_agent,
        reason="LOGIN_SUCCESS"
    )
    db.add(log)
    await db.commit()

    # Generate tokens including session ID (`sid`)
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "type": "access", "sid": session_id})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "type": "refresh", "sid": session_id})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    token_data = TokenResponse(access_token=access_token)
    user_data = UserResponse.model_validate(user)

    return APIResponse(
        success=True,
        message="Login successful",
        data={
            "token": token_data.model_dump(),
            "user": user_data.model_dump(mode="json"),
        },
    )


@router.post("/refresh", response_model=APIResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate tokens. Restricts rotation to active session hashes.
    """
    refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    try:
        payload = decode_token(refresh_token_value, is_refresh=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    sid = payload.get("sid")
    if sid:
        stmt = select(UserSession).filter(UserSession.id == sid, UserSession.is_active == True)
        result = await db.execute(stmt)
        active_sess = result.scalars().first()
        if not active_sess:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked or expired",
            )

    user_id = payload.get("sub")
    user = await UserRepository.get_by_id(db, int(user_id))

    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Rotate new access & refresh tokens maintaining active session ID
    new_access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "type": "access", "sid": sid})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "type": "refresh", "sid": sid})

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    token_data = TokenResponse(access_token=new_access_token)

    return APIResponse(
        success=True,
        message="Token refreshed successfully",
        data=token_data.model_dump(),
    )


@router.post("/logout", response_model=APIResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Logout. Invalidates cookie and terminates database session record.
    """
    response.delete_cookie(key="refresh_token", path="/", httponly=True, secure=True, samesite="strict")

    # Invalidate active session ID
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            sid = payload.get("sid")
            if sid:
                stmt = select(UserSession).filter(UserSession.id == sid)
                result = await db.execute(stmt)
                sess = result.scalars().first()
                if sess:
                    sess.is_active = False
                    await db.commit()
                    # Evict session cache
                    if settings.CACHE_ENABLED:
                        await cache.delete(f"auth:session:{sid}")
        except Exception:
            pass

    return APIResponse(success=True, message="Logged out successfully")


@router.get("/invite-validate", response_model=APIResponse)
async def invite_validate(token: str, db: AsyncSession = Depends(get_db)):
    """
    Validates a pending invitation token.
    """
    stmt = select(UserInvitation).filter(UserInvitation.token == token)
    result = await db.execute(stmt)
    invite = result.scalars().first()

    if not invite:
        raise HTTPException(status_code=400, detail="Invalid onboarding token.")
    if invite.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Onboarding token has already been {invite.status.lower()}.")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation has expired.")

    return APIResponse(
        success=True,
        message="Invitation token is valid",
        data={
            "name": invite.name,
            "email": invite.email,
            "role": invite.role,
            "department": invite.department,
            "designation": invite.designation
        }
    )


@router.post("/activate", response_model=APIResponse)
async def activate_account(
    payload: AccountActivateRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Onboard invited employee. Validates temp credentials, checks password policy and history.
    """
    stmt = select(UserInvitation).filter(UserInvitation.token == payload.token)
    result = await db.execute(stmt)
    invite = result.scalars().first()

    if not invite or invite.status != "PENDING" or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired invitation token.")

    # Validate temporary password
    if not verify_password(payload.temporary_password, invite.temp_password_hash):
        raise HTTPException(status_code=400, detail="Incorrect temporary password provided.")

    # Enforce password strength policy checks
    user_details = {"name": invite.name, "email": invite.email, "employee_code": invite.employee_code}
    strength_errors = validate_password_strength(payload.new_password, user_details)
    if strength_errors:
        raise HTTPException(status_code=400, detail="Password rules failed: " + "; ".join(strength_errors))

    # Generate unique username from email
    base_username = invite.email.split("@")[0].lower()
    username = base_username
    counter = 1

    while True:
        stmt = select(User).filter(User.username == username)
        result = await db.execute(stmt)
        if not result.scalars().first():
            break
        username = f"{base_username}{counter}"
        counter += 1

    # Argon2id password hash creation
    new_hash = hash_password(payload.new_password)

    # Check for existing invited user record to update
    stmt = select(User).filter(User.email == invite.email, User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        user = User(
            username=username,
            email=invite.email,
            password_hash=new_hash,
            role=invite.role,
            status="active",
            full_name=invite.name,
            employee_code=invite.employee_code,
            branch=invite.branch,
            department=invite.department,
            designation=invite.designation,
            phone_number=invite.phone_number,
            is_deleted=False
        )
        db.add(user)
    else:
        user.username = username
        user.password_hash = new_hash
        user.role = invite.role
        user.status = "active"
        user.full_name = invite.name
        user.employee_code = invite.employee_code
        user.branch = invite.branch
        user.department = invite.department
        user.designation = invite.designation
        user.phone_number = invite.phone_number

    await db.flush()

    # Commit to password history
    history = UserPasswordHistory(user_id=user.id, password_hash=new_hash)
    db.add(history)

    # Update invite record status
    invite.status = "USED"
    await db.commit()

    # Start login session
    session_id = str(uuid.uuid4())
    user_agent = request.headers.get("user-agent", "")
    browser = "Chrome" if "Chrome" in user_agent else "Safari" if "Safari" in user_agent else "Firefox" if "Firefox" in user_agent else "Edge" if "Edge" in user_agent else "Unknown"
    os_name = "Windows" if "Windows" in user_agent else "Mac" if "Macintosh" in user_agent else "Linux" if "Linux" in user_agent else "Android" if "Android" in user_agent else "iPhone" if "iPhone" in user_agent else "Unknown"

    sess = UserSession(
        id=session_id,
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=user_agent,
        browser=browser,
        os=os_name,
        country="India",
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(sess)

    # Write login logs
    log = LoginLog(
        username=user.username,
        role=user.role,
        employee_id=user.id,
        success=True,
        ip_address=request.client.host,
        browser=browser,
        os=os_name,
        device_type="Desktop",
        country="India",
        user_agent=user_agent,
        reason="ACTIVATION_SUCCESS"
    )
    db.add(log)
    await db.commit()

    # Generate and set cookies
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "type": "access", "sid": session_id})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "type": "refresh", "sid": session_id})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    return APIResponse(
        success=True,
        message="Account onboarded successfully",
        data={
            "token": {"access_token": access_token},
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        }
    )


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordWithTokenRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str

@router.post("/forgot-password", response_model=APIResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate a 6-digit OTP code for password resets, hash it, and dispatch via Resend.
    """
    stmt = select(User).filter(User.email == payload.email, User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        # Prevent username enumeration checks by returning success message anyway
        return APIResponse(success=True, message="If the email exists, a verification code has been dispatched.")

    # Generates secure random 6-digit verification code
    otp = str(secrets.randbelow(900000) + 100000)
    user.reset_otp_hash = hash_password(otp)
    user.reset_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    user.reset_otp_attempts = 0
    await db.commit()

    otp_html = f"""
    <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #1e293b; border-radius: 12px; overflow: hidden; background: #0b0f19; color: #f1f5f9; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
      <h2 style="color: #ffffff; text-align: center; margin-top: 0; font-weight: 800; font-size: 20px;">SAKRA SECURITY</h2>
      <p style="color: #94a3b8; font-size: 13px; text-align: center; margin-top: 12px;">Please verify your identity using the following verification OTP code:</p>
      <div style="background: #1e293b; padding: 20px; text-align: center; border-radius: 8px; margin: 24px 0; border: 1px solid #334155;">
        <span style="font-size: 36px; font-family: monospace; font-weight: bold; color: #3b82f6; letter-spacing: 6px;">{otp}</span>
      </div>
      <p style="color: #64748b; font-size: 11px; text-align: center; line-height: 1.4;">
        This verification OTP code is single-use and expires in 10 minutes. If you did not trigger this request, please contact SAKRA security administrators immediately.
      </p>
    </div>
    """

    send_email_async.delay(
        to_email=user.email,
        subject="SAKRA FINANCE — Verification OTP Code",
        html_content=otp_html,
        template="OTP"
    )

    return APIResponse(success=True, message="If the email exists, a verification code has been dispatched.")


@router.post("/verify-otp", response_model=APIResponse)
async def verify_otp(payload: VerifyOTPRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Verify the 6-digit OTP code. If correct, generate a short-lived reset token and return it.
    """
    stmt = select(User).filter(User.email == payload.email, User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid request parameters.")

    # Account Lockout checks
    if user.reset_otp_attempts >= 3:
        raise HTTPException(status_code=400, detail="Too many attempts. Password reset has been locked.")

    # Expiry validation
    if not user.reset_otp_expires_at or user.reset_otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code has expired.")

    # Validate OTP value
    if not user.reset_otp_hash or not verify_password(payload.otp, user.reset_otp_hash):
        user.reset_otp_attempts += 1
        await db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code.")

    # OTP is valid, generate secure random reset token
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    # Clear OTP fields
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    user.reset_otp_attempts = 0
    
    await log_audit(
        db=db,
        actor_id=user.id,
        action="VERIFY_OTP_SUCCESS",
        table_name="users",
        record_id=user.id,
        request=request
    )
    await db.commit()

    return APIResponse(
        success=True,
        message="Verification successful. Use this token to reset your password.",
        data={"reset_token": reset_token}
    )


@router.post("/reset-password", response_model=APIResponse)
async def reset_password(payload: ResetPasswordWithTokenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Validate the reset token, verify password strength rules, check history, and update password hash.
    """
    stmt = select(User).filter(User.email == payload.email, User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid request parameters.")

    # Validate reset token match and expiry
    if not user.reset_token or user.reset_token != payload.token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
        
    if not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # Enforce password policy strength rules
    user_details = {"name": user.username, "email": user.email}
    strength_errors = validate_password_strength(payload.new_password, user_details)
    if strength_errors:
        raise HTTPException(status_code=400, detail="Password rules failed: " + "; ".join(strength_errors))

    # Password history constraints (last 5 checks)
    stmt = select(UserPasswordHistory).filter(UserPasswordHistory.user_id == user.id).order_by(UserPasswordHistory.created_at.desc()).limit(5)
    result = await db.execute(stmt)
    history_entries = result.scalars().all()

    for row in history_entries:
        if verify_password(payload.new_password, row.password_hash):
            raise HTTPException(status_code=400, detail="You cannot reuse any of your last 5 passwords.")

    # Update passwords
    new_hash = hash_password(payload.new_password)
    user.password_hash = new_hash
    
    # Clear reset states
    user.reset_token = None
    user.reset_token_expires_at = None
    
    # Save history record
    history = UserPasswordHistory(user_id=user.id, password_hash=new_hash)
    db.add(history)

    # Invalidate all active user login sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id)
        .values(is_active=False)
    )

    # Notification
    notif = Notification(
        user_id=user.id,
        notification_type="SECURITY_ALERT",
        message="Your account password was updated successfully. All active sessions have been terminated."
    )
    db.add(notif)

    await log_audit(
        db=db,
        actor_id=user.id,
        action="RESET_PASSWORD_SUCCESS",
        table_name="users",
        record_id=user.id,
        request=request
    )
    await db.commit()

    # Clear auth caches
    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:user:{user.id}")

    return APIResponse(success=True, message="Password updated successfully. Active sessions terminated.")


@router.get("/me", response_model=APIResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get profile.
    """
    user_data = UserResponse.model_validate(current_user)

    return APIResponse(
        success=True,
        message="Current user retrieved",
        data=user_data.model_dump(mode="json"),
    )


@router.get("/me/sessions", response_model=APIResponse)
async def get_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active devices for current employee profile."""
    stmt = select(UserSession).filter(UserSession.user_id == current_user.id, UserSession.is_active == True).order_by(UserSession.last_active_at.desc())
    res = await db.execute(stmt)
    sessions = res.scalars().all()

    out = []
    for s in sessions:
        out.append({
            "session_id": s.id,
            "ip_address": s.ip_address,
            "browser": s.browser,
            "os": s.os,
            "country": s.country,
            "last_active": s.last_active_at.isoformat(),
            "created_at": s.created_at.isoformat()
        })
    return APIResponse(success=True, message="Employee sessions retrieved", data=out)


@router.post("/me/sessions/{session_id}/revoke", response_model=APIResponse)
async def revoke_my_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Logout a specific active device profile."""
    stmt = select(UserSession).filter(UserSession.id == session_id, UserSession.user_id == current_user.id)
    res = await db.execute(stmt)
    sess = res.scalars().first()

    if not sess:
        raise HTTPException(status_code=404, detail="Device session not found.")
    sess.is_active = False
    await db.commit()

    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:session:{session_id}")

    return APIResponse(success=True, message="Device profile logged out successfully")


@router.post("/me/sessions/revoke-all", response_model=APIResponse)
async def revoke_all_other_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Logout all other devices, keeping current session active."""
    auth_header = request.headers.get("Authorization", "")
    current_sid = None
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            current_sid = payload.get("sid")
        except Exception:
            pass

    upd_stmt = update(UserSession).where(
        and_(UserSession.user_id == current_user.id, UserSession.is_active == True)
    )
    if current_sid:
        upd_stmt = upd_stmt.where(UserSession.id != current_sid)

    await db.execute(upd_stmt.values(is_active=False))
    await db.commit()

    # Clear other session caches
    if settings.CACHE_ENABLED:
        # Invalidate pattern is safest
        await cache.invalidate_pattern("auth:session:*")

    return APIResponse(success=True, message="All other device sessions revoked.")


class LanguageUpdateRequest(BaseModel):
    preferred_language: str


@router.patch("/me/language", response_model=APIResponse)
async def update_my_language(
    payload: LanguageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the preferred language of the current user.
    """
    if payload.preferred_language not in ["en", "te"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language code. Supported: 'en', 'te'."
        )
    current_user.preferred_language = payload.preferred_language
    await db.commit()

    # Clear cached user record
    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:user:{current_user.id}")

    return APIResponse(
        success=True,
        message="Language preference updated successfully",
        data={"preferred_language": current_user.preferred_language}
    )
