import logging
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Any

from app.database.session import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.common import APIResponse

logger = logging.getLogger("sakra.api.audit")

router = APIRouter()

@router.get("/", response_model=APIResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    action_filter: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve security audit logs (immutability logs).
    Super Admin role clearance only.
    """
    if current_user.role != "SUPER_ADMIN":
        return APIResponse(
            success=False,
            message="ACCESS DENIED: Role 'SUPER_ADMIN' required to view security audit trail.",
            errors={"detail": "Unauthorized"},
        )

    # Base Query
    query = db.query(
        AuditLog.id,
        AuditLog.action,
        AuditLog.table_name,
        AuditLog.record_id,
        AuditLog.old_values,
        AuditLog.new_values,
        AuditLog.ip_address,
        AuditLog.user_agent,
        AuditLog.created_at,
        User.username.label("actor_username")
    ).outerjoin(User, AuditLog.actor_id == User.id)

    # Filter
    if action_filter:
        query = query.filter(AuditLog.action.like(f"%{action_filter}%"))

    # Total Count
    total = query.count()

    # Pagination
    skip = (page - 1) * limit
    logs_result = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    # Convert row objects to dictionaries
    logs_data = []
    for row in logs_result:
        logs_data.append({
            "id": row.id,
            "action": row.action,
            "table_name": row.table_name,
            "record_id": row.record_id,
            "old_values": row.old_values,
            "new_values": row.new_values,
            "ip_address": row.ip_address,
            "user_agent": row.user_agent,
            "created_at": row.created_at.isoformat(),
            "actor_username": row.actor_username or "SYSTEM"
        })

    return APIResponse(
        success=True,
        message="Audit logs retrieved successfully",
        data={
            "logs": logs_data,
            "total": total
        }
    )
