"""Sandbox API: policy-gated code execution.

Wraps ``app.sandbox.sandbox_manager.execute_code_sandbox`` behind the policy
engine so no code runs without an ALLOW (or pre-approved REQUIRE_APPROVAL)
decision — the "LLM proposes, app executes" boundary.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import get_db
from vtr_agent.core.policy_engine import check_operation
from vtr_agent.core.sandbox.sandbox_manager import execute_code_sandbox

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class SandboxExecuteRequest(BaseModel):
    """Code submission for sandboxed execution."""

    code: str = Field(..., min_length=1)
    timeout: int = Field(default=30, ge=1, le=300)
    memory_limit: int = Field(default=512, ge=64, le=4096)
    filesystem_access: str = Field(default="readonly")
    stdin_input: Optional[str] = None


@router.post("/execute", response_model=Dict)
def execute_code(
    req: SandboxExecuteRequest,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Execute Python code inside the sandbox after a policy check."""
    decision = check_operation(
        "python_sandbox",
        user.role,
        operation="execute",
        context={"endpoint": "/sandbox/execute"},
    )

    if decision.decision == "DENY":
        raise HTTPException(
            status_code=403,
            detail=f"Tool access denied: {decision.reason}",
        )

    if decision.decision == "REQUIRE_APPROVAL":
        raise HTTPException(
            status_code=202,
            detail={
                "status": "approval_required",
                "message": decision.reason,
                "tool_id": "python_sandbox",
                "risk_level": decision.risk_level.value,
            },
        )

    result = execute_code_sandbox(
        code=req.code,
        timeout=req.timeout,
        memory_limit=req.memory_limit,
        filesystem_access=req.filesystem_access,
        stdin_input=req.stdin_input,
    )

    return {
        "execution_id": result.execution_id,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "execution_time": result.execution_time,
        "memory_used": result.memory_used,
        "timed_out": result.timed_out,
        "safety_violation": result.safety_violation,
        "status": "completed" if result.exit_code == 0 else "failed",
    }
