"""
VTR-Agent: Approval API Endpoints

Human approval gate API endpoints for high-risk operation oversight.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    ApprovalRequest, ApprovalDecision, ApprovalStatus,
    RiskLevel
)
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import User
from vtr_agent.core.approval import (
    request_approval, approve_approval, reject_approval,
    get_pending_approvals, check_approval_required,
    get_approval_gate
)
from vtr_agent.api.auth import get_current_user
from vtr_agent.utils import new_id

router = APIRouter(prefix="/approval", tags=["approval"])


@router.post("/request", response_model=Dict)
def request_approval_endpoint(
    req: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Request human approval for a high-risk operation."""
    # Check if approval is required
    requires_approval = check_approval_required(req.tool_id, user.role)
    
    if not requires_approval:
        return {
            "approval_id": new_id("APPROVAL"),
            "status": "automatic",
            "message": "Tool execution does not require approval",
        }
    
    # Request approval
    approval_id = request_approval(
        tool_id=req.tool_id,
        step_id=req.step_id,
        arguments=req.arguments,
        risk_level=RiskLevel(req.risk_level),
        user_role=user.role,
        project_id=req.project_id or "",
        requested_by=user.user_id,
    )
    
    return {
        "approval_id": approval_id,
        "status": "pending",
        "message": "Approval requested from human operator",
    }


@router.get("/pending", response_model=List[Dict])
def get_pending_approvals_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get pending approvals visible to the current user's role."""
    pending = get_pending_approvals(user.role)
    return pending


@router.post("/{approval_id}/approve", response_model=Dict)
def approve_approval_endpoint(
    approval_id: str,
    reason: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve a pending approval request."""
    result = approve_approval(approval_id, user.user_id, reason)
    return {
        "status": result["status"],
        "approval_id": approval_id,
        "decided_by": result["decided_by"],
        "decided_at": result["decided_at"],
        "reason": result["reason"],
    }


@router.post("/{approval_id}/reject", response_model=Dict)
def reject_approval_endpoint(
    approval_id: str,
    reason: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reject a pending approval request."""
    result = reject_approval(approval_id, user.user_id, reason)
    return {
        "status": result["status"],
        "approval_id": approval_id,
        "decided_by": result["decided_by"],
        "decided_at": result["decided_at"],
        "reason": result["reason"],
    }


@router.get("/require/{tool_id}/{user_role}", response_model=Dict)
def check_approval_requirement(
    tool_id: str,
    user_role: str,
    db: Session = Depends(get_db),
):
    """Check if a tool operation requires approval."""
    requires_approval = check_approval_required(tool_id, user_role)
    return {
        "tool_id": tool_id,
        "user_role": user_role,
        "requires_approval": requires_approval,
    }