"""
Audit logging service for tracking all data modifications.
"""
import logging
import json
from typing import Optional, Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.audit_log import AuditLog

logger = logging.getLogger("sakra.audit")


def log_audit(
    db: Session,
    actor_id: int,
    action: str,
    table_name: str,
    record_id: Optional[int] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Create an audit log entry for any data modification.

    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action type (e.g., 'CREATE', 'UPDATE', 'DELETE', 'LOGIN')
        table_name: Name of the database table affected
        record_id: ID of the affected record
        old_values: Previous values (for updates)
        new_values: New values (for creates/updates)
        request: Starlette request object for extracting IP and user-agent

    Returns:
        The created AuditLog record
    """
    ip_address = None
    user_agent = None

    if request is not None:
        # Extract IP from x-forwarded-for header (for proxied requests) or client directly
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        elif request.client:
            ip_address = request.client.host

        user_agent = request.headers.get("user-agent")

    # Serialize dict values to JSON strings for storage
    old_values_str = json.dumps(old_values, default=str) if old_values else None
    new_values_str = json.dumps(new_values, default=str) if new_values else None

    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values_str,
        new_values=new_values_str,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(audit_entry)
    db.flush()

    logger.info(
        "audit | actor=%d action=%s table=%s record=%s ip=%s",
        actor_id,
        action,
        table_name,
        record_id,
        ip_address,
    )

    return audit_entry
