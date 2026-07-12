"""
IAM Admin Control panel routes: employee invitations, session monitoring, mail logging, and employee directory management.
"""
import uuid
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from app.utils.timezone import now_ist_naive, now_ist
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from pydantic import BaseModel, EmailStr

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.user_invitation import UserInvitation
from app.models.user_session import UserSession
from app.models.mail_log import MailLog
from app.models.login_log import LoginLog
from app.models.notification import Notification
from app.core.security import hash_password
from app.services.email_service import send_email
from app.services.audit import log_audit
from app.schemas.common import APIResponse
from app.services.cache import cache
from app.core.config import settings

logger = logging.getLogger("sakra.iam")

router = APIRouter()

# Schema for incoming invites
class EmployeeInviteRequest(BaseModel):
    name: str
    email: EmailStr
    employee_code: str
    department: str
    designation: str
    branch: str
    phone_number: str
    role: str
    notes: Optional[str] = None
    expiration_hours: float


class EmployeeUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


@router.post("/invite", response_model=APIResponse)
async def invite_employee(
    payload: EmployeeInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """
    Invite a new employee, generating a secure token and temp password,
    then dispatching a Resend invite email.
    """
    # Check if email is already in use
    stmt = select(User).filter(User.email == payload.email, User.is_deleted == False)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An active employee account with this email already exists.")

    # Check if active invite is pending
    stmt_invite = select(UserInvitation).filter(
        UserInvitation.email == payload.email,
        UserInvitation.status == "PENDING",
        UserInvitation.expires_at > now_ist_naive()
    )
    result_invite = await db.execute(stmt_invite)
    existing_invite = result_invite.scalars().first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="A pending invitation has already been sent to this email.")

    # Generate invite token & temp password
    invite_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    temp_password = "SakraTemp@" + secrets.token_hex(4) + "!"
    temp_password_hash = hash_password(temp_password)

    # Expiry calculation
    expires_at = now_ist_naive() + timedelta(hours=payload.expiration_hours)

    # Create temporary Username
    base_username = payload.email.split("@")[0].lower().replace(".", "_")
    username = base_username
    counter = 1
    while True:
        stmt_chk = select(User).filter(User.username == username)
        res_chk = await db.execute(stmt_chk)
        if not res_chk.scalars().first():
            break
        username = f"{base_username}_{counter}"
        counter += 1

    # Insert employee into database with status INVITED
    new_emp = User(
        username=username,
        email=payload.email,
        password_hash=temp_password_hash,
        role=payload.role,
        status="INVITED",
        full_name=payload.name,
        employee_code=payload.employee_code,
        branch=payload.branch,
        department=payload.department,
        designation=payload.designation,
        phone_number=payload.phone_number,
        is_deleted=False
    )
    db.add(new_emp)
    await db.flush()

    invite = UserInvitation(
        id=invite_id,
        name=payload.name,
        email=payload.email,
        employee_code=payload.employee_code,
        department=payload.department,
        designation=payload.designation,
        branch=payload.branch,
        phone_number=payload.phone_number,
        role=payload.role,
        temp_password_hash=temp_password_hash,
        token=token,
        expires_at=expires_at,
        status="PENDING",
        created_by=current_user.id
    )
    db.add(invite)
    await db.flush()

    # expires_at is already in IST (naive), attach IST tzinfo for display formatting
    from zoneinfo import ZoneInfo
    expires_at_ist = expires_at.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    activation_link = f"http://localhost:5173/activate.html?token={token}"
    email_html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #1e293b; border-radius: 12px; overflow: hidden; background: #0f172a; color: #f1f5f9;">
      <div style="background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 32px 24px; text-align: center;">
        <h2 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px; font-weight: 800;">SAKRA FINANCE</h2>
        <span style="color: #93c5fd; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 2px; display: block; margin-top: 6px;">Enterprise OS Onboarding</span>
      </div>
      <div style="padding: 32px; background: #0b0f19; line-height: 1.6;">
        <h3 style="color: #ffffff; margin-top: 0; font-size: 16px; font-weight: 700;">Dear {payload.name},</h3>
        <p style="color: #94a3b8; font-size: 13px;">You have been invited to join the <strong>SAKRA FINANCE</strong> operating system.</p>
        
        <div style="margin: 24px 0; background: #1e293b/50; border-radius: 8px; padding: 20px; border: 1px solid #1e293b;">
          <table style="width: 100%; border-collapse: collapse; font-size: 12px; color: #cbd5e1;">
            <tr><td style="padding: 6px 0; color: #64748b;">Department:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #ffffff;">{payload.department}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">Designation:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #ffffff;">{payload.designation}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">Role:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #3b82f6;">{payload.role}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">One-time Temporary Password:</td><td style="padding: 6px 0; font-family: monospace; font-weight: bold; text-align: right; color: #f43f5e; font-size: 13px;">{temp_password}</td></tr>
          </table>
        </div>

        <div style="text-align: center; margin: 36px 0;">
          <a href="{activation_link}" style="background: #2563eb; color: #ffffff; text-decoration: none; padding: 14px 30px; font-size: 12px; font-weight: bold; border-radius: 6px; text-transform: uppercase; letter-spacing: 1.5px; display: inline-block; box-shadow: 0 4px 12px rgba(37,99,235,0.25);">
            Activate Enterprise Account
          </a>
        </div>

        <p style="color: #64748b; font-size: 11px; margin-top: 32px; border-top: 1px solid #1e293b; padding-top: 20px;">
          <strong>Security Notice:</strong> This activation token is valid until <strong>{expires_at_ist.strftime('%d %B %Y %I:%M %p IST')}</strong>. You must customize your credentials and replace this temporary password during onboarding.
        </p>
      </div>
      <div style="background: #090d16; padding: 20px; text-align: center; font-size: 10px; color: #475569; border-top: 1px solid #1e293b;">
        Sakra Vision HQ • Secure IAM Subsystem • support@sakra.finance
      </div>
    </div>
    """

    mail_entry = MailLog(
        recipient=payload.email,
        subject="SAKRA FINANCE — Invitation to Join OS Platform",
        template="INVITATION",
        status="PENDING",
        provider_message_id=None
    )
    db.add(mail_entry)
    await db.flush()

    success, msg_id = send_email(payload.email, "SAKRA FINANCE — Invitation to Join OS Platform", email_html)
    
    if success:
        mail_entry.status = "SENT"
        mail_entry.provider_message_id = msg_id
        invite.status = "PENDING"
    else:
        mail_entry.status = "FAILED"
        invite.status = "EMAIL_FAILED"
        new_emp.status = "suspended"

    # Audit log
    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_INVITATION",
        table_name="user_invitations",
        record_id=invite.id,
        new_values={"email": payload.email, "role": payload.role, "status": invite.status},
        request=request
    )

    # System Notification
    notif = Notification(
        user_id=current_user.id,
        notification_type="SYSTEM_ALERT",
        message=f"Invitation sent to {payload.name} ({payload.email}). Status: {invite.status}"
    )
    db.add(notif)
    await db.commit()

    return APIResponse(
        success=success,
        message="Employee invited successfully." if success else "Employee registered, but email delivery failed.",
        data={"invite_id": invite_id, "status": invite.status, "expires_at": expires_at.isoformat()}
    )


@router.get("/invitations", response_model=APIResponse)
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List all sent employee invites."""
    stmt = select(UserInvitation).order_by(UserInvitation.created_at.desc())
    res = await db.execute(stmt)
    invites = res.scalars().all()
    out = []
    for i in invites:
        out.append({
            "id": i.id,
            "name": i.name,
            "email": i.email,
            "employee_code": i.employee_code,
            "department": i.department,
            "designation": i.designation,
            "role": i.role,
            "status": i.status,
            "expires_at": i.expires_at.isoformat(),
            "created_at": i.created_at.isoformat(),
        })
    return APIResponse(success=True, message="Invitations retrieved", data=out)


@router.post("/invitations/{invite_id}/resend", response_model=APIResponse)
async def resend_invitation(
    invite_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Resend a pending or failed employee invitation."""
    stmt = select(UserInvitation).filter(UserInvitation.id == invite_id)
    res = await db.execute(stmt)
    invite = res.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    stmt_emp = select(User).filter(User.email == invite.email, User.is_deleted == False)
    res_emp = await db.execute(stmt_emp)
    emp = res_emp.scalars().first()

    # Regenerate credentials
    token = secrets.token_urlsafe(32)
    temp_password = "SakraTemp@" + secrets.token_hex(4) + "!"
    temp_password_hash = hash_password(temp_password)
    expires_at = now_ist_naive() + timedelta(hours=24)

    invite.token = token
    invite.temp_password_hash = temp_password_hash
    invite.expires_at = expires_at
    invite.status = "PENDING"

    if emp:
        emp.password_hash = temp_password_hash
        emp.status = "INVITED"

    # expires_at is already in IST (naive), attach IST tzinfo for display formatting
    from zoneinfo import ZoneInfo
    expires_at_ist = expires_at.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    activation_link = f"http://localhost:5173/activate.html?token={token}"
    email_html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #1e293b; border-radius: 12px; overflow: hidden; background: #0f172a; color: #f1f5f9;">
      <div style="background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 32px 24px; text-align: center;">
        <h2 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px; font-weight: 800;">SAKRA FINANCE</h2>
        <span style="color: #93c5fd; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 2px; display: block; margin-top: 6px;">Enterprise OS Onboarding (Resend)</span>
      </div>
      <div style="padding: 32px; background: #0b0f19; line-height: 1.6;">
        <h3 style="color: #ffffff; margin-top: 0; font-size: 16px; font-weight: 700;">Dear {invite.name},</h3>
        <p style="color: #94a3b8; font-size: 13px;">This is a follow-up invitation to join the <strong>SAKRA FINANCE</strong> operating system.</p>
        
        <div style="margin: 24px 0; background: #1e293b/50; border-radius: 8px; padding: 20px; border: 1px solid #1e293b;">
          <table style="width: 100%; border-collapse: collapse; font-size: 12px; color: #cbd5e1;">
            <tr><td style="padding: 6px 0; color: #64748b;">Department:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #ffffff;">{invite.department}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">Designation:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #ffffff;">{invite.designation}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">Role:</td><td style="padding: 6px 0; font-weight: bold; text-align: right; color: #3b82f6;">{invite.role}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;">One-time Temporary Password:</td><td style="padding: 6px 0; font-family: monospace; font-weight: bold; text-align: right; color: #f43f5e; font-size: 13px;">{temp_password}</td></tr>
          </table>
        </div>

        <div style="text-align: center; margin: 36px 0;">
          <a href="{activation_link}" style="background: #2563eb; color: #ffffff; text-decoration: none; padding: 14px 30px; font-size: 12px; font-weight: bold; border-radius: 6px; text-transform: uppercase; letter-spacing: 1.5px; display: inline-block; box-shadow: 0 4px 12px rgba(37,99,235,0.25);">
            Activate Enterprise Account
          </a>
        </div>

        <p style="color: #64748b; font-size: 11px; margin-top: 32px; border-top: 1px solid #1e293b; padding-top: 20px;">
          <strong>Security Notice:</strong> This activation token is valid until <strong>{expires_at_ist.strftime('%d %B %Y %I:%M %p IST')}</strong>.
        </p>
      </div>
    </div>
    """

    mail_entry = MailLog(
        recipient=invite.email,
        subject="SAKRA FINANCE — Invitation to Join OS Platform",
        template="INVITATION_RESEND",
        status="PENDING",
        provider_message_id=None
    )
    db.add(mail_entry)
    await db.flush()

    success, msg_id = send_email(invite.email, "SAKRA FINANCE — Invitation to Join OS Platform", email_html)
    
    if success:
        mail_entry.status = "SENT"
        mail_entry.provider_message_id = msg_id
        invite.status = "PENDING"
    else:
        mail_entry.status = "FAILED"
        invite.status = "EMAIL_FAILED"

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="RESEND_INVITATION",
        table_name="user_invitations",
        record_id=invite.id,
        new_values={"email": invite.email, "status": invite.status},
        request=request
    )
    await db.commit()

    return APIResponse(
        success=success,
        message="Invitation resent successfully." if success else "Resend failed. Email delivery unavailable.",
        data={"status": invite.status}
    )


@router.post("/invitations/{invite_id}/revoke", response_model=APIResponse)
async def revoke_invitation(
    invite_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a pending employee invite and disable their invited user account."""
    stmt = select(UserInvitation).filter(UserInvitation.id == invite_id)
    res = await db.execute(stmt)
    invite = res.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    invite.status = "REVOKED"
    
    stmt_emp = select(User).filter(User.email == invite.email, User.is_deleted == False)
    res_emp = await db.execute(stmt_emp)
    emp = res_emp.scalars().first()
    if emp:
        emp.status = "inactive"

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="REVOKE_INVITATION",
        table_name="user_invitations",
        record_id=invite.id,
        new_values={"email": invite.email, "status": "REVOKED"},
        request=request
    )
    await db.commit()

    # Clear cached state
    if settings.CACHE_ENABLED and emp:
        await cache.delete(f"auth:user:{emp.id}")

    return APIResponse(success=True, message="Invitation revoked successfully")


@router.delete("/invitations/{invite_id}", response_model=APIResponse)
async def delete_invitation(
    invite_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Delete invitation record completely and soft-delete user."""
    stmt = select(UserInvitation).filter(UserInvitation.id == invite_id)
    res = await db.execute(stmt)
    invite = res.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    stmt_emp = select(User).filter(User.email == invite.email)
    res_emp = await db.execute(stmt_emp)
    emp = res_emp.scalars().first()
    if emp:
        emp.is_deleted = True
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == emp.id)
            .values(is_active=False)
        )

    await db.delete(invite)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="DELETE_INVITATION",
        table_name="user_invitations",
        record_id=invite_id,
        request=request
    )
    await db.commit()

    if settings.CACHE_ENABLED and emp:
        await cache.delete(f"auth:user:{emp.id}")

    return APIResponse(success=True, message="Invitation deleted successfully")


@router.get("/employees", response_model=APIResponse)
async def list_employees(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List all active and invited employees with profiles."""
    query = select(User).filter(User.is_deleted == False)

    if search:
        query = query.filter(
            (User.username.like(f"%{search}%")) |
            (User.email.like(f"%{search}%")) |
            (User.full_name.like(f"%{search}%")) |
            (User.employee_code.like(f"%{search}%")) |
            (User.department.like(f"%{search}%")) |
            (User.branch.like(f"%{search}%"))
        )

    if role:
        query = query.filter(User.role == role)

    if status_filter:
        query = query.filter(User.status == status_filter)

    res = await db.execute(query.order_by(User.created_at.desc()))
    employees = res.scalars().all()
    
    out = []
    for e in employees:
        out.append({
            "id": e.id,
            "username": e.username,
            "email": e.email,
            "role": e.role,
            "status": e.status,
            "full_name": e.full_name,
            "employee_code": e.employee_code,
            "branch": e.branch,
            "department": e.department,
            "designation": e.designation,
            "phone_number": e.phone_number,
            "created_at": e.created_at.isoformat()
        })
    return APIResponse(success=True, message="Employees list retrieved", data=out)


@router.get("/employees/{emp_id}", response_model=APIResponse)
async def get_employee(
    emp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Retrieve details of a single employee."""
    stmt = select(User).filter(User.id == emp_id, User.is_deleted == False)
    res = await db.execute(stmt)
    emp = res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return APIResponse(
        success=True,
        message="Employee retrieved",
        data={
            "id": emp.id,
            "username": emp.username,
            "email": emp.email,
            "role": emp.role,
            "status": emp.status,
            "full_name": emp.full_name,
            "employee_code": emp.employee_code,
            "branch": emp.branch,
            "department": emp.department,
            "designation": emp.designation,
            "phone_number": emp.phone_number,
            "created_at": emp.created_at.isoformat()
        }
    )


@router.put("/employees/{emp_id}", response_model=APIResponse)
async def update_employee(
    emp_id: int,
    payload: EmployeeUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Update employee details, role, or status."""
    stmt = select(User).filter(User.id == emp_id, User.is_deleted == False)
    res = await db.execute(stmt)
    emp = res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if emp.role == "SUPER_ADMIN" and current_user.id != emp.id:
         raise HTTPException(status_code=403, detail="Cannot modify other SUPER_ADMIN accounts.")

    old_values = {
        "full_name": emp.full_name,
        "branch": emp.branch,
        "department": emp.department,
        "designation": emp.designation,
        "phone_number": emp.phone_number,
        "role": emp.role,
        "status": emp.status
    }

    if payload.full_name is not None: emp.full_name = payload.full_name
    if payload.branch is not None: emp.branch = payload.branch
    if payload.department is not None: emp.department = payload.department
    if payload.designation is not None: emp.designation = payload.designation
    if payload.phone_number is not None: emp.phone_number = payload.phone_number
    if payload.role is not None: emp.role = payload.role
    if payload.status is not None: emp.status = payload.status

    # If deactivating, revoke active sessions
    if payload.status in ["inactive", "suspended", "locked"]:
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == emp.id)
            .values(is_active=False)
        )

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_EMPLOYEE",
        table_name="users",
        record_id=emp.id,
        old_values=old_values,
        new_values=payload.model_dump(exclude_unset=True),
        request=request
    )
    # Create notifications
    from app.services.notification_service import create_system_notification, push_realtime_notifications
    notifs = []
    if payload.status is not None and payload.status != old_values["status"]:
        if payload.status in ["inactive", "suspended", "locked"]:
            notifs.extend(await create_system_notification(
                db,
                "SECURITY_USER_DISABLED",
                f"Employee account deactivated: {emp.username} (status: {payload.status}) by {current_user.username}"
            ))
    elif payload.role is not None and payload.role != old_values["role"]:
        notifs.extend(await create_system_notification(
            db,
            "SECURITY_PRIVILEGES_CHANGED",
            f"Employee privileges changed: {emp.username} (role changed from {old_values['role']} to {payload.role}) by {current_user.username}"
        ))
    else:
        notifs.extend(await create_system_notification(
            db,
            "SECURITY_PRIVILEGES_CHANGED",
            f"Employee details updated: {emp.username} by {current_user.username}"
        ))

    await db.commit()

    # Push real-time notifications
    push_realtime_notifications(notifs)

    # Clear cached user and permissions
    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:user:{emp.id}")
        await cache.invalidate_pattern(f"auth:permission:{emp.id}:*")

    return APIResponse(success=True, message="Employee updated successfully")


@router.delete("/employees/{emp_id}", response_model=APIResponse)
async def delete_employee(
    emp_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Soft-delete an employee and terminate all active sessions."""
    stmt = select(User).filter(User.id == emp_id, User.is_deleted == False)
    res = await db.execute(stmt)
    emp = res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if emp.role == "SUPER_ADMIN":
         raise HTTPException(status_code=403, detail="Cannot delete SUPER_ADMIN accounts.")

    emp.is_deleted = True
    
    # Revoke sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == emp.id)
        .values(is_active=False)
    )

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="DELETE_EMPLOYEE",
        table_name="users",
        record_id=emp.id,
        request=request
    )
    # Create notifications
    from app.services.notification_service import create_system_notification, push_realtime_notifications
    notifs = await create_system_notification(
        db,
        "SECURITY_USER_DISABLED",
        f"Employee account deleted: {emp.username} by {current_user.username}"
    )

    await db.commit()

    # Push real-time notifications
    push_realtime_notifications(notifs)

    # Clear cached user and permissions
    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:user:{emp_id}")
        await cache.invalidate_pattern(f"auth:permission:{emp_id}:*")

    return APIResponse(success=True, message="Employee account soft-deleted successfully")


@router.get("/sessions", response_model=APIResponse)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List active user login sessions."""
    stmt = select(UserSession).filter(UserSession.is_active == True).order_by(UserSession.last_active_at.desc())
    res = await db.execute(stmt)
    sessions = res.scalars().all()
    out = []
    for s in sessions:
        stmt_user = select(User).filter(User.id == s.user_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalars().first()
        out.append({
            "session_id": s.id,
            "username": user.username if user else "Unknown",
            "email": user.email if user else "—",
            "ip_address": s.ip_address,
            "browser": s.browser,
            "os": s.os,
            "country": s.country,
            "last_active": s.last_active_at.isoformat(),
            "created_at": s.created_at.isoformat()
        })
    return APIResponse(success=True, message="Active sessions retrieved", data=out)


@router.post("/sessions/{session_id}/revoke", response_model=APIResponse)
async def revoke_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a specific active session."""
    stmt = select(UserSession).filter(UserSession.id == session_id)
    res = await db.execute(stmt)
    s = res.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")

    s.is_active = False
    
    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="TERMINATE_SESSION",
        table_name="user_sessions",
        record_id=0,
        new_values={"session_id": session_id},
        request=request
    )
    await db.commit()

    if settings.CACHE_ENABLED:
        await cache.delete(f"auth:session:{session_id}")

    return APIResponse(success=True, message="Session terminated successfully")


@router.post("/sessions/terminate-all", response_model=APIResponse)
async def terminate_all_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Force logout all device sessions except current user's active session."""
    # Find current request's active session ID from authorization header
    auth_header = request.headers.get("Authorization", "")
    current_sid = None
    if auth_header.startswith("Bearer "):
        try:
            from app.core.jwt import decode_token
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            current_sid = payload.get("sid")
        except Exception:
            pass

    upd_stmt = update(UserSession).where(UserSession.is_active == True)
    if current_sid:
        upd_stmt = upd_stmt.where(UserSession.id != current_sid)

    res = await db.execute(upd_stmt.values(is_active=False))
    count = res.rowcount

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="TERMINATE_ALL_SESSIONS",
        table_name="user_sessions",
        record_id=0,
        new_values={"count": count},
        request=request
    )
    await db.commit()

    # Clear cached session states
    if settings.CACHE_ENABLED:
        await cache.invalidate_pattern("auth:session:*")

    return APIResponse(success=True, message=f"Successfully terminated {count} device sessions.")


@router.delete("/sessions/terminate-all", response_model=APIResponse)
async def delete_all_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Force logout all device sessions (DELETE verb fallback)."""
    return await terminate_all_sessions(request=request, db=db, current_user=current_user)


@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a specific session (DELETE verb fallback)."""
    return await revoke_session(session_id=session_id, request=request, db=db, current_user=current_user)


@router.get("/mail-logs", response_model=APIResponse)
async def list_mail_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List and audit all outgoing Resend emails."""
    stmt = select(MailLog).order_by(MailLog.created_at.desc()).limit(100)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    out = []
    for l in logs:
        out.append({
            "id": l.id,
            "recipient": l.recipient,
            "subject": l.subject,
            "template": l.template,
            "status": l.status,
            "provider_message_id": l.provider_message_id,
            "created_at": l.created_at.isoformat()
        })
    return APIResponse(success=True, message="Mail logs retrieved", data=out)


@router.get("/security-metrics", response_model=APIResponse)
async def get_security_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Gather aggregates for the Admin Security Dashboard."""
    # Build select statements
    active_threshold = now_ist_naive() - timedelta(minutes=15)
    
    total_users_stmt = select(func.count(User.id)).filter(User.is_deleted == False)
    active_sessions_stmt = select(func.count(UserSession.id)).filter(UserSession.is_active == True)
    failed_logins_stmt = select(func.count(LoginLog.id)).filter(LoginLog.success == False)
    expired_invites_stmt = select(func.count(UserInvitation.id)).filter(
        UserInvitation.status == "PENDING",
        UserInvitation.expires_at < now_ist_naive()
    )
    accepted_invites_stmt = select(func.count(UserInvitation.id)).filter(UserInvitation.status == "USED")
    revoked_invites_stmt = select(func.count(UserInvitation.id)).filter(UserInvitation.status == "REVOKED")
    pending_invites_stmt = select(func.count(UserInvitation.id)).filter(
        UserInvitation.status == "PENDING",
        UserInvitation.expires_at >= now_ist_naive()
    )
    locked_accounts_stmt = select(func.count(User.id)).filter(User.status == "locked", User.is_deleted == False)
    online_count_stmt = select(func.count(UserSession.user_id.distinct())).filter(
        UserSession.is_active == True,
        UserSession.last_active_at >= active_threshold
    )

    ist_now = now_ist()
    ist_midnight = ist_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_midnight = ist_midnight.replace(tzinfo=None)

    today_logins_stmt = select(func.count(LoginLog.id)).filter(LoginLog.created_at >= today_midnight)
    today_invites_stmt = select(func.count(UserInvitation.id)).filter(UserInvitation.created_at >= today_midnight)
    otp_requests_stmt = select(func.count(MailLog.id)).filter(MailLog.template == "OTP", MailLog.created_at >= today_midnight)
    email_failures_stmt = select(func.count(MailLog.id)).filter(MailLog.status == "FAILED")

    # Run queries in parallel
    results = await asyncio.gather(
        db.execute(total_users_stmt),
        db.execute(active_sessions_stmt),
        db.execute(failed_logins_stmt),
        db.execute(expired_invites_stmt),
        db.execute(accepted_invites_stmt),
        db.execute(revoked_invites_stmt),
        db.execute(pending_invites_stmt),
        db.execute(locked_accounts_stmt),
        db.execute(online_count_stmt),
        db.execute(today_logins_stmt),
        db.execute(today_invites_stmt),
        db.execute(otp_requests_stmt),
        db.execute(email_failures_stmt)
    )

    total_users = results[0].scalar() or 0
    active_sessions = results[1].scalar() or 0
    failed_logins = results[2].scalar() or 0
    expired_invites = results[3].scalar() or 0
    accepted_invites = results[4].scalar() or 0
    revoked_invites = results[5].scalar() or 0
    pending_invites = results[6].scalar() or 0
    locked_accounts = results[7].scalar() or 0
    online_count = results[8].scalar() or 0
    offline_count = max(0, total_users - online_count)
    today_logins = results[9].scalar() or 0
    today_invites = results[10].scalar() or 0
    otp_requests = results[11].scalar() or 0
    email_failures = results[12].scalar() or 0

    return APIResponse(
        success=True,
        message="Security metrics computed",
        data={
            "total_users": total_users,
            "active_sessions": active_sessions,
            "failed_logins": failed_logins,
            "expired_invitations": expired_invites,
            "locked_accounts": locked_accounts,
            "online_employees": online_count,
            "offline_employees": offline_count,
            "accepted_invitations": accepted_invites,
            "revoked_invitations": revoked_invites,
            "pending_invitations": pending_invites,
            "today_logins": today_logins,
            "today_invitations": today_invites,
            "otp_requests": otp_requests,
            "email_failures": email_failures
        }
    )


@router.get("/permissions", response_model=APIResponse)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Get role default permissions template map."""
    role_defaults = {
        "SUPER_ADMIN": ["admin_control", "audit_logs", "dashboard", "customers", "customer_edit", "daily_payments", "loan_creation", "analytics", "reports", "settings", "copilot"],
        "ADMIN": ["dashboard", "customers", "customer_edit", "daily_payments", "loan_creation", "analytics", "reports", "audit_logs", "settings", "copilot"],
        "FINANCE_MANAGER": ["dashboard", "customers", "daily_payments", "analytics", "reports"],
        "COLLECTION_OFFICER": ["dashboard", "customers", "daily_payments"],
        "AUDITOR": ["dashboard", "analytics", "reports", "audit_logs"],
        "DATA_ENTRY": ["dashboard", "customers", "daily_payments"],
        "VIEWER": ["dashboard"]
    }
    return APIResponse(success=True, message="Permissions template retrieved", data=role_defaults)
