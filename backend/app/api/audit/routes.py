import logging
import asyncio
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
    limit: int = Query(25, ge=1, le=1000),  # Max limit up to 1000 records
    action_filter: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve security audit logs (immutability logs).
    Super Admin role clearance only.
    """
    # Enforce maximum pagination limit check
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum allowed limit is 1000 records per request"
        )

    if current_user.role != "SUPER_ADMIN":
        return APIResponse(
            success=False,
            message="ACCESS DENIED: Role 'SUPER_ADMIN' required to view security audit trail.",
            errors={"detail": "Unauthorized"},
        )

    # Base query specifying only required columns (avoiding SELECT *)
    stmt = select(
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

    # Count query
    count_stmt = select(func.count(AuditLog.id))

    # Apply filters
    if action_filter:
        stmt = stmt.filter(AuditLog.action.like(f"%{action_filter}%"))
        count_stmt = count_stmt.filter(AuditLog.action.like(f"%{action_filter}%"))

    # Pagination calculation
    skip = (page - 1) * limit
    
    # Run queries in parallel
    res_task = db.execute(stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    count_task = db.execute(count_stmt)

    res, count_res = await asyncio.gather(res_task, count_task)
    logs_result = res.all()
    total = count_res.scalar() or 0

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
