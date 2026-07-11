"""
User management routes: listing, inviting, and status management.
"""
import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.middleware.auth import PermissionRequirement
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.common import APIResponse
from app.schemas.user import UserInvite, UserUpdate, UserCreate, UserResponse
from app.services.audit import log_audit
from app.services.email_service import send_email
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.users")

router = APIRouter()

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password meeting all strength requirements."""
    # Ensure at least one of each required character type
    password_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()_+-="),
    ]
    # Fill remaining with random characters
    remaining = length - len(password_chars)
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    password_chars.extend(secrets.choice(all_chars) for _ in range(remaining))

    # Shuffle to avoid predictable positions
    result = list(password_chars)
    secrets.SystemRandom().shuffle(result)
    return "".join(result)


@router.get("/", response_model=APIResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    List all users. Requires ADMIN or SUPER_ADMIN role.
    """
    users = await UserRepository.list_all(db)
    users_data = [UserResponse.model_validate(u).model_dump(mode="json") for u in users]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(users_data)} users",
        data=users_data,
    )


@router.post("/invite", response_model=APIResponse)
async def invite_user(
    invite: UserInvite,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Invite a new user by email. Generates a random secure password and sends
    an invitation email. Cannot invite SUPER_ADMIN users.
    """
    # Check if email already exists
    existing = await UserRepository.get_by_email(db, invite.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Generate username from email prefix
    username = invite.email.split("@")[0].lower().replace(".", "_")

    # Check for username collision and add suffix if needed
    base_username = username
    counter = 1
    while await UserRepository.get_by_username(db, username):
        username = f"{base_username}_{counter}"
        counter += 1

    # Generate secure random password
    temp_password = generate_secure_password()

    # Create user via schema
    user_schema = UserCreate(
        username=username,
        email=invite.email,
        password=temp_password,
        role=invite.role,
    )

    user = await UserRepository.create(db, user_schema, status="active")

    # Send invitation email
    email_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
        <div style="background-color: #050816; padding: 24px; text-align: center;">
            <img src="http://localhost:5173/logo.png" alt="SAKRA FINANCE" style="height: 40px; width: auto; display: inline-block;" />
        </div>
        <div style="padding: 32px; color: #0f172a; line-height: 1.6;">
            <h2 style="margin-top: 0; font-size: 20px; font-weight: 700; color: #0f172a;">Welcome to SAKRA FINANCE</h2>
            <p style="font-size: 14px; color: #475569;">You've been invited to join the SAKRA FINANCE secure operating network as <strong>{invite.role}</strong>.</p>
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 6px; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; font-size: 13px; color: #64748b;"><strong>Username:</strong> <code style="font-family: monospace; font-size: 14px; color: #0f172a;">{username}</code></p>
                <p style="margin: 0; font-size: 13px; color: #64748b;"><strong>Temporary Password:</strong> <code style="font-family: monospace; font-size: 14px; color: #0f172a;">{temp_password}</code></p>
            </div>
            <p style="color: #ef4444; font-size: 12px; font-weight: 600; margin: 24px 0;">⚠️ Please change your temporary credentials immediately upon your first login check.</p>
            <p style="font-size: 13px; color: #475569; margin: 0;">Best regards,<br>SAKRA FINANCE Team</p>
        </div>
        <div style="background-color: #f8fafc; border-t: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
            Secure Network Invitation · Server Mumbai Gateway
        </div>
    </div>
    """

    _, _ = send_email(
        to_email=invite.email,
        subject="You've been invited to Sakra Finance",
        body_html=email_html,
    )

    # Audit log
    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="INVITE_USER",
        table_name="users",
        record_id=user.id,
        new_values={"email": invite.email, "role": invite.role, "username": username},
        request=request,
    )
    await db.commit()

    user_data = UserResponse.model_validate(user)

    return APIResponse(
        success=True,
        message=f"User invited successfully. Invitation sent to {invite.email}",
        data=user_data.model_dump(mode="json"),
    )


@router.patch("/{user_id}/status", response_model=APIResponse)
async def update_user_status(
    user_id: int,
    update: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement(ADMIN_ROLES)),
):
    """
    Update a user's role or status. SUPER_ADMIN required for modifying admin users.
    """
    target_user = await UserRepository.get_by_id(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Only SUPER_ADMIN can modify ADMIN or SUPER_ADMIN users
    if target_user.role in ADMIN_ROLES and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SUPER_ADMIN can modify admin users",
        )

    # Cannot modify yourself
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account through this endpoint",
        )

    old_values = {"role": target_user.role, "status": target_user.status}

    updated_user = await UserRepository.update(db, target_user, update)

    new_values = {"role": updated_user.role, "status": updated_user.status}

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_USER",
        table_name="users",
        record_id=user_id,
        old_values=old_values,
        new_values=new_values,
        request=request,
    )
    await db.commit()

    # Clear user profiles and permissions cache
    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:user:{user_id}")
        await cache.invalidate_pattern(f"auth:permission:{user_id}:*")

    user_data = UserResponse.model_validate(updated_user)

    return APIResponse(
        success=True,
        message="User updated successfully",
        data=user_data.model_dump(mode="json"),
    )
