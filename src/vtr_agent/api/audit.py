"""
VTR-Agent: Audit API

Audit logging API endpoints for system activity tracking.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import AuditLogResponse, DateRangeFilter
from vtr_agent.auth.security import get_current_user
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import get_db
from vtr_agent.core.utils import new_id
from vtr_agent.utils import get_user_role_display

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    request: Request,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[AuditLogResponse]:
    """Get audit logs with filtering."""
    query = db.query(m.AuditLog)

    # Filter by event type
    if event_type:
        query = query.filter(m.AuditLog.action.ilike(f"%{event_type}%"))

    # Filter by action
    if action:
        query = query.filter(m.AuditLog.action.ilike(f"%{action}%"))

    # Filter by resource type
    if resource_type:
        query = query.filter(
            m.AuditLog.resource_type.ilike(f"%{resource_type}%")
        )

    # Filter by user ID
    if user_id:
        query = query.filter(m.AuditLog.user_id == user_id)

    # Filter by date range
    if start_date:
        query = query.filter(m.AuditLog.created_at >= start_date.isoformat())
    if end_date:
        query = query.filter(m.AuditLog.created_at <= end_date.isoformat())

    # Apply RBAC restrictions
    if not user.is_admin:
        query = query.filter(
            (m.AuditLog.user_id == user.id)
            | (m.AuditLog.project_id.in_(_get_user_projects(db, user)))
        )

    # Pagination
    total = query.count()
    logs = query.order_by(m.AuditLog.created_at.desc()).offset(offset).limit(limit)

    return [_audit_log_to_response(log) for log in logs]


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
) -> AuditLogResponse:
    """Get a specific audit log entry."""
    log = db.query(m.AuditLog).filter(m.AuditLog.event_id == log_id).first()

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    # Check permissions
    if not user.is_admin and log.user_id != user.id:
        if log.project_id and log.project_id not in _get_user_projects(
            db, user
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    return _audit_log_to_response(log)


@router.get("/statistics", response_model=Dict[str, Any])
def get_audit_statistics(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get audit log statistics."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # Total logs
    total_logs = db.query(m.AuditLog).count()

    # Logs by action
    actions = (
        db.query(m.AuditLog.action, func.count(m.AuditLog.id))
        .group_by(m.AuditLog.action)
        .order_by(func.count(m.AuditLog.id).desc())
        .all()
    )

    # Logs by user
    users = (
        db.query(m.User.username, func.count(m.AuditLog.id))
        .join(m.AuditLog, m.AuditLog.user_id == m.User.id)
        .group_by(m.User.username)
        .order_by(func.count(m.AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # Logs by day
    from sqlalchemy import func

    daily_stats = (
        db.query(
            func.date(m.AuditLog.created_at).label("date"),
            func.count(m.AuditLog.id).label("count"),
        )
        .group_by("date")
        .order_by("date")
        .all()
    )

    # Error rate
    error_logs = db.query(m.AuditLog).filter(m.AuditLog.status != "ok").count()
    error_rate = (error_logs / total_logs * 100) if total_logs > 0 else 0

    return {
        "total_logs": total_logs,
        "error_rate": error_rate,
        "actions": [{"action": action, "count": count} for action, count in actions],
        "top_users": [
            {"username": username, "log_count": count}
            for username, count in users
        ],
        "daily_stats": [
            {"date": str(date), "count": count} for date, count in daily_stats
        ],
    }


@router.delete("/logs", response_model=Dict[str, str])
def clear_audit_logs(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
    older_than_days: int = 30,
) -> Dict[str, str]:
    """Clear old audit logs (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    from datetime import datetime, timedelta

    cutoff_date = (
        datetime.utcnow() - timedelta(days=older_than_days)
    ).isoformat()

    deleted_count = (
        db.query(m.AuditLog)
        .filter(m.AuditLog.created_at < cutoff_date)
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "message": f"Deleted {deleted_count} audit logs older than {older_than_days} days"
    }


def _get_user_projects(db: Session, user: m.User) -> List[int]:
    """Get list of project IDs the user has access to."""
    if user.is_admin:
        return []

    member_ids = [
        pm.project_id
        for pm in db.query(m.ProjectMembership)
        .filter(m.ProjectMembership.user_id == user.id)
        .all()
    ]

    return member_ids


def _audit_log_to_response(audit_log: m.AuditLog) -> AuditLogResponse:
    """Convert AuditLog model to response."""
    return AuditLogResponse(
        event_id=audit_log.event_id,
        user_id=audit_log.user_id,
        user_role=audit_log.user_role,
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        project_id=audit_log.project_id,
        before_state=audit_log.before_state,
        after_state=audit_log.after_state,
        status=audit_log.status,
        request_id=audit_log.request_id,
        session_id=audit_log.session_id,
        created_at=audit_log.created_at,
        updated_at=audit_log.updated_at,
    )
