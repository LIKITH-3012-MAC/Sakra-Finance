"""
IAM Admin Control panel routes: employee invitations, session monitoring, mail logging, and employee directory management.
"""
import uuid
import secrets
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database.session import get_db
from app.middleware.auth import get_current_user, PermissionRequirement
from app.models.user import User
from app.models.user_invitation import UserInvitation
from app.models.user_session import UserSession
from app.models.mail_log import MailLog
from app.models.login_log import LoginLog
from app.models.user_permission import UserPermission
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.core.security import hash_password
from app.services.email_service import send_email
from app.services.audit import log_audit
from app.schemas.common import APIResponse

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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """
    Invite a new employee, generating a secure token and temp password,
    then dispatching a Resend invite email.
    """
    # Check if email is already in use
    existing_user = db.query(User).filter(User.email == payload.email, User.is_deleted == False).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An active employee account with this email already exists.")

    # Check if active invite is pending
    existing_invite = db.query(UserInvitation).filter(
        UserInvitation.email == payload.email,
        UserInvitation.status == "PENDING",
        UserInvitation.expires_at > datetime.utcnow()
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="A pending invitation has already been sent to this email.")

    # Generate invite token & temp password
    invite_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    temp_password = "SakraTemp@" + secrets.token_hex(4) + "!"
    temp_password_hash = hash_password(temp_password)

    # Expiry calculation
    expires_at = datetime.utcnow() + timedelta(hours=payload.expiration_hours)

    # Create temporary Username
    base_username = payload.email.split("@")[0].lower().replace(".", "_")
    username = base_username
    counter = 1
    while db.query(User).filter(User.username == username).first():
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
    db.flush()

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
    db.flush()

    # Compose template
    from zoneinfo import ZoneInfo
    expires_at_ist = expires_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
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

    # Dispatch email synchronously or eager celery to get Resend message ID immediately
    mail_entry = MailLog(
        recipient=payload.email,
        subject="SAKRA FINANCE — Invitation to Join OS Platform",
        template="INVITATION",
        status="PENDING",
        provider_message_id=None
    )
    db.add(mail_entry)
    db.flush()

    success, msg_id = send_email(payload.email, "SAKRA FINANCE — Invitation to Join OS Platform", email_html)
    
    if success:
        mail_entry.status = "SENT"
        mail_entry.provider_message_id = msg_id
        invite.status = "PENDING"
    else:
        mail_entry.status = "FAILED"
        invite.status = "EMAIL_FAILED"
        new_emp.status = "suspended" # lock until retry/resend

    # Audit log
    log_audit(
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
    db.commit()

    return APIResponse(
        success=success,
        message="Employee invited successfully." if success else "Employee registered, but email delivery failed.",
        data={"invite_id": invite_id, "status": invite.status, "expires_at": expires_at.isoformat()}
    )


@router.get("/invitations", response_model=APIResponse)
async def list_invitations(
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List all sent employee invites."""
    invites = db.query(UserInvitation).order_by(UserInvitation.created_at.desc()).all()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Resend a pending or failed employee invitation."""
    invite = db.query(UserInvitation).filter(UserInvitation.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    emp = db.query(User).filter(User.email == invite.email, User.is_deleted == False).first()

    # Regenerate credentials
    token = secrets.token_urlsafe(32)
    temp_password = "SakraTemp@" + secrets.token_hex(4) + "!"
    temp_password_hash = hash_password(temp_password)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    invite.token = token
    invite.temp_password_hash = temp_password_hash
    invite.expires_at = expires_at
    invite.status = "PENDING"

    if emp:
        emp.password_hash = temp_password_hash
        emp.status = "INVITED"

    # Compose template
    from zoneinfo import ZoneInfo
    expires_at_ist = expires_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
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
    db.flush()

    success, msg_id = send_email(invite.email, "SAKRA FINANCE — Invitation to Join OS Platform", email_html)
    
    if success:
        mail_entry.status = "SENT"
        mail_entry.provider_message_id = msg_id
        invite.status = "PENDING"
    else:
        mail_entry.status = "FAILED"
        invite.status = "EMAIL_FAILED"

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="RESEND_INVITATION",
        table_name="user_invitations",
        record_id=invite.id,
        new_values={"email": invite.email, "status": invite.status},
        request=request
    )
    db.commit()

    return APIResponse(
        success=success,
        message="Invitation resent successfully." if success else "Resend failed. Email delivery unavailable.",
        data={"status": invite.status}
    )


@router.post("/invitations/{invite_id}/revoke", response_model=APIResponse)
async def revoke_invitation(
    invite_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a pending employee invite and disable their invited user account."""
    invite = db.query(UserInvitation).filter(UserInvitation.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    invite.status = "REVOKED"
    
    emp = db.query(User).filter(User.email == invite.email, User.is_deleted == False).first()
    if emp:
        emp.status = "inactive"

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REVOKE_INVITATION",
        table_name="user_invitations",
        record_id=invite.id,
        new_values={"email": invite.email, "status": "REVOKED"},
        request=request
    )
    db.commit()

    return APIResponse(success=True, message="Invitation revoked successfully")


@router.delete("/invitations/{invite_id}", response_model=APIResponse)
async def delete_invitation(
    invite_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Delete invitation record completely and soft-delete user."""
    invite = db.query(UserInvitation).filter(UserInvitation.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    emp = db.query(User).filter(User.email == invite.email).first()
    if emp:
        emp.is_deleted = True
        # Terminate active sessions
        db.query(UserSession).filter(UserSession.user_id == emp.id).update({UserSession.is_active: False})

    db.delete(invite)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="DELETE_INVITATION",
        table_name="user_invitations",
        record_id=invite_id,
        request=request
    )
    db.commit()

    return APIResponse(success=True, message="Invitation deleted successfully")


@router.get("/employees", response_model=APIResponse)
async def list_employees(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List all active and invited employees with profiles."""
    query = db.query(User).filter(User.is_deleted == False)

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

    employees = query.order_by(User.created_at.desc()).all()
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Retrieve details of a single employee."""
    emp = db.query(User).filter(User.id == emp_id, User.is_deleted == False).first()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Update employee details, role, or status status."""
    emp = db.query(User).filter(User.id == emp_id, User.is_deleted == False).first()
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
        db.query(UserSession).filter(UserSession.user_id == emp.id).update({UserSession.is_active: False})

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_EMPLOYEE",
        table_name="users",
        record_id=emp.id,
        old_values=old_values,
        new_values=payload.model_dump(exclude_unset=True),
        request=request
    )
    db.commit()

    return APIResponse(success=True, message="Employee updated successfully")


@router.delete("/employees/{emp_id}", response_model=APIResponse)
async def delete_employee(
    emp_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Soft-delete an employee and terminate all active sessions."""
    emp = db.query(User).filter(User.id == emp_id, User.is_deleted == False).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if emp.role == "SUPER_ADMIN":
         raise HTTPException(status_code=403, detail="Cannot delete SUPER_ADMIN accounts.")

    emp.is_deleted = True
    
    # Revoke sessions
    db.query(UserSession).filter(UserSession.user_id == emp.id).update({UserSession.is_active: False})

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="DELETE_EMPLOYEE",
        table_name="users",
        record_id=emp.id,
        request=request
    )
    db.commit()

    return APIResponse(success=True, message="Employee account soft-deleted successfully")


@router.get("/sessions", response_model=APIResponse)
async def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List active user login sessions."""
    sessions = db.query(UserSession).filter(UserSession.is_active == True).order_by(UserSession.last_active_at.desc()).all()
    out = []
    for s in sessions:
        user = db.query(User).filter(User.id == s.user_id).first()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a specific active session."""
    s = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found.")

    s.is_active = False
    
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="TERMINATE_SESSION",
        table_name="user_sessions",
        record_id=0,
        new_values={"session_id": session_id},
        request=request
    )
    db.commit()

    return APIResponse(success=True, message="Session terminated successfully")


@router.post("/sessions/terminate-all", response_model=APIResponse)
async def terminate_all_sessions(
    request: Request,
    db: Session = Depends(get_db),
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

    query = db.query(UserSession).filter(UserSession.is_active == True)
    if current_sid:
        query = query.filter(UserSession.id != current_sid)

    count = query.update({UserSession.is_active: False}, synchronize_session=False)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="TERMINATE_ALL_SESSIONS",
        table_name="user_sessions",
        record_id=0,
        new_values={"count": count},
        request=request
    )
    db.commit()

    return APIResponse(success=True, message=f"Successfully terminated {count} device sessions.")


@router.delete("/sessions/terminate-all", response_model=APIResponse)
async def delete_all_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Force logout all device sessions (DELETE verb fallback)."""
    return await terminate_all_sessions(request=request, db=db, current_user=current_user)


@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Revoke a specific session (DELETE verb fallback)."""
    return await revoke_session(session_id=session_id, request=request, db=db, current_user=current_user)


@router.get("/mail-logs", response_model=APIResponse)
async def list_mail_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """List and audit all outgoing Resend emails."""
    logs = db.query(MailLog).order_by(MailLog.created_at.desc()).limit(100).all()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionRequirement("admin_control")),
):
    """Gather aggregates for the Admin Security Dashboard."""
    total_users = db.query(User).filter(User.is_deleted == False).count()
    active_sessions = db.query(UserSession).filter(UserSession.is_active == True).count()
    failed_logins = db.query(LoginLog).filter(LoginLog.success == False).count()
    expired_invites = db.query(UserInvitation).filter(
        UserInvitation.status == "PENDING",
        UserInvitation.expires_at < datetime.utcnow()
    ).count()

    # Active/Used count
    accepted_invites = db.query(UserInvitation).filter(UserInvitation.status == "USED").count()
    revoked_invites = db.query(UserInvitation).filter(UserInvitation.status == "REVOKED").count()
    pending_invites = db.query(UserInvitation).filter(UserInvitation.status == "PENDING", UserInvitation.expires_at >= datetime.utcnow()).count()

    # Locked/Inactive users count
    locked_accounts = db.query(User).filter(User.status == "locked", User.is_deleted == False).count()

    # Online / Offline count
    active_threshold = datetime.utcnow() - timedelta(minutes=15)
    online_count = db.query(UserSession.user_id).filter(
        UserSession.is_active == True,
        UserSession.last_active_at >= active_threshold
    ).distinct().count()
    
    offline_count = max(0, total_users - online_count)

    # Today's logs (midnight calculated in IST, converted to UTC for database query)
    from zoneinfo import ZoneInfo
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    ist_midnight = ist_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_midnight = ist_midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    
    today_logins = db.query(LoginLog).filter(LoginLog.created_at >= today_midnight).count()
    today_invites = db.query(UserInvitation).filter(UserInvitation.created_at >= today_midnight).count()

    # Reset OTP counters
    otp_requests = db.query(MailLog).filter(MailLog.template == "OTP", MailLog.created_at >= today_midnight).count()
    email_failures = db.query(MailLog).filter(MailLog.status == "FAILED").count()

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
    db: Session = Depends(get_db),
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
