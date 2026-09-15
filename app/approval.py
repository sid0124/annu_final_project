"""
VTR-Agent: Human Approval Workflow

Human oversight gate for high-risk tool executions and research operations.
Every high-risk action must pass through this gate before execution.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    ApprovalRequest, ApprovalDecision, ApprovalStatus,
    TaskStatus,
)
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import User, Project, AuditLog
from vtr_agent.core.policy_engine import policy_engine, PolicyDecision
from vtr_agent.core.task_engine import task_engine, StateMachine, PlanStep
from vtr_agent.utils import new_id, RiskLevel


router = APIRouter(prefix="/approval", tags=["approval"])


class ApprovalGate:
    """Manages human approval workflow for high-risk operations."""
    
    def __init__(self):
        self.pending_approvals: Dict[str, Dict] = {}
        self.approval_history: List[Dict] = []
    
    def request_approval(
        self, 
        tool_id: str, 
        step_id: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel,
        user_role: str,
        project_id: str,
        requested_by: str,
    ) -> str:
        """Request human approval for a high-risk operation."""
        approval_id = new_id("APPROVAL")
        
        approval = {
            "approval_id": approval_id,
            "tool_id": tool_id,
            "step_id": step_id,
            "arguments": arguments,
            "risk_level": risk_level.value,
            "user_role": user_role,
            "project_id": project_id,
            "requested_by": requested_by,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "decision": None,
            "decided_by": None,
            "decided_at": None,
            "reason": None,
        }
        
        self.pending_approvals[approval_id] = approval
        
        # Log the approval request
        print(f"Approval requested: {approval_id} for tool {tool_id} by {user_role}")
        
        return approval_id
    
    def approve(self, approval_id: str, approver: str, reason: str = "") -> Dict:
        """Approve a pending approval request."""
        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval ID {approval_id} not found")
        
        approval = self.pending_approvals[approval_id]
        approval["status"] = "approved"
        approval["decision"] = "approved"
        approval["decided_by"] = approver
        approval["decided_at"] = datetime.now(timezone.utc).isoformat()
        approval["reason"] = reason
        
        # Log the approval
        self._log_approval(approval)
        
        return approval
    
    def reject(self, approval_id: str, rejector: str, reason: str) -> Dict:
        """Reject a pending approval request."""
        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval ID {approval_id} not found")
        
        approval = self.pending_approvals[approval_id]
        approval["status"] = "rejected"
        approval["decision"] = "rejected"
        approval["decided_by"] = rejector
        approval["decided_at"] = datetime.now(timezone.utc).isoformat()
        approval["reason"] = reason
        
        # Log the rejection
        self._log_approval(approval)
        
        return approval
    
    def get_pending(self, user_role: str) -> List[Dict]:
        """Get pending approvals for a user role."""
        pending = []
        for approval_id, approval in self.pending_approvals.items():
            # Users can only see approvals they requested or that their role allows
            if approval["requested_by"] == "current_user" or user_role == "admin":
                pending.append(approval)
        return pending
    
    def _log_approval(self, approval: Dict) -> None:
        """Log approval decision to audit trail."""
        self.approval_history.append({
            "approval_id": approval["approval_id"],
            "decision": approval["decision"],
            "approved_by": approval["decided_by"],
            "timestamp": approval["decided_at"],
            "tool_id": approval["tool_id"],
            "risk_level": approval["risk_level"],
            "reason": approval["reason"],
        })
    
    def check_approval_required(self, tool_id: str, user_role: str) -> bool:
        """Check if an operation requires approval."""
        # Check policy engine
        decision = policy_engine.check_tool_permission(tool_id, user_role)
        
        requires_approval = decision.requires_approval or (
            decision.risk_level.value >= 2  # Level 2+ requires approval
        )
        
        return requires_approval


# Global approval gate instance
approval_gate = ApprovalGate()


# Convenience functions
def request_approval(
    tool_id: str, 
    step_id: str,
    arguments: Dict[str, Any],
    risk_level: RiskLevel,
    user_role: str,
    project_id: str,
    requested_by: str,
) -> str:
    """Request human approval for a high-risk operation."""
    return approval_gate.request_approval(
        tool_id, step_id, arguments, risk_level, user_role, project_id, requested_by
    )


def approve_approval(approval_id: str, approver: str, reason: str = "") -> Dict:
    """Approve a pending approval request."""
    return approval_gate.approve(approval_id, approver, reason)


def reject_approval(approval_id: str, rejector: str, reason: str) -> Dict:
    """Reject a pending approval request."""
    return approval_gate.reject(approval_id, rejector, reason)


def get_pending_approvals(user_role: str) -> List[Dict]:
    """Get pending approvals for a user role."""
    return approval_gate.get_pending(user_role)


def check_approval_required(tool_id: str, user_role: str) -> bool:
    """Check if an operation requires approval."""
    return approval_gate.check_approval_required(tool_id, user_role)


def get_approval_gate() -> ApprovalGate:
    """Get the approval gate instance."""
    return approval_gate