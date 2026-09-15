"""
VTR-Agent: Task API Endpoints

Task management API endpoints for research workflow coordination.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    TaskCreate, TaskResponse, PlanStep,
    TaskStatusUpdate, TaskStatus
)
from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import (
    User, Project, ResearchRun, PlanStepModel, EvidenceModel,
)
from app.core.task_engine import StateMachine
from vtr_agent.core.policy_engine import check_operation
from vtr_agent.core.sandbox.sandbox_manager import execute_code_sandbox
from vtr_agent.core.run_orchestrator import (
    create_run, start_or_resume_run, trace_for_run, run_to_dict,
    decide_approval, approval_to_dict, get_run_by_identifier,
    list_runs_for_user, run_status_counts,
)
from vtr_agent.core.tool_registry import get_allowed_tools, get_tool, get_all_tools
from vtr_agent.utils import new_id

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _run_to_task_response(run: ResearchRun) -> TaskResponse:
    """Render a persisted ResearchRun as a TaskResponse (BUG-05: DB is source of truth)."""
    return TaskResponse(
        task_id=run.task_id,
        name=(run.goal[:80] or "Research Task"),
        description=run.goal,
        instructions=run.goal,
        project_id=run.project.project_id if run.project else "",
        user_id=run.creator.user_id if run.creator else "",
        status=run.status,
        priority="medium",
        tags=[],
        created_at=run.created_at,
        updated_at=run.updated_at,
        run_id=run.run_id,
    )


@router.post("/", response_model=TaskResponse)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new research task."""
    # Verify project exists and user has access
    project = (
        db.query(Project)
        .filter((Project.project_id == str(task.project_id)) | (Project.id == _as_int(task.project_id)))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Researchers (and admins) may create research tasks
    if not user.is_researcher:
        raise HTTPException(status_code=403, detail="User cannot create tasks")

    # Create database-backed research run with run_id. The planner-generated
    # plan is persisted as ResearchRun.plan_json + PlanStepModel rows, so the
    # task/plan survives a restart (BUG-05).
    run = create_run(db, user, task.instructions, project.id)

    return TaskResponse(
        task_id=run.task_id,
        name=task.name or "Research Task",
        description=task.description or "",
        instructions=task.instructions or "",
        project_id=project.project_id,
        user_id=user.user_id,
        status=run.status,
        priority=task.priority or "medium",
        tags=task.tags or [],
        created_at=run.created_at,
        updated_at=run.updated_at,
        run_id=run.run_id,  # Propagate run_id
    )


@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[TaskStatus] = None,
):
    """List tasks for the user, read from persisted research runs (BUG-05)."""
    runs = list_runs_for_user(db, user)
    if status is not None:
        runs = [run for run in runs if run.status == status.value]
    return [_run_to_task_response(run) for run in runs]


@router.get("/{plan_id}", response_model=TaskResponse)
def get_task(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific research task by run_id or task_id (persisted)."""
    run = get_run_by_identifier(db, user, plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _run_to_task_response(run)


@router.post("/{plan_id}/steps", response_model=PlanStep)
def add_task_step(
    plan_id: str,
    step: PlanStep,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Append a step to a persisted research plan (BUG-05)."""
    run = get_run_by_identifier(db, user, plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # The tool must exist in the registry; the app never executes an unknown tool.
    if get_tool(step.required_tool) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool '{step.required_tool}' in step",
        )

    existing = (
        db.query(PlanStepModel)
        .filter(PlanStepModel.run_id_ref == run.id, PlanStepModel.step_id == step.step_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Step '{step.step_id}' already exists")

    db.add(
        PlanStepModel(
            step_id=step.step_id,
            run_id_ref=run.id,
            description=step.description,
            required_tool=step.required_tool,
            risk_level=step.risk_level.value if hasattr(step.risk_level, "value") else int(step.risk_level),
            requires_approval=step.requires_approval,
            status="pending",
        )
    )
    db.commit()
    return step


@router.post("/{run_id}/steps/{step_id}/execute", response_model=Dict)
def execute_step(
    run_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute a research plan step."""
    # Get the research run from database
    run = db.query(ResearchRun).filter(ResearchRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if not user.is_admin and run.created_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this run")
    
    # Find the step in the run's plan
    step_found = None
    for step in run.plan_json.get("steps", []) if run.plan_json else []:
        if step.get("step_id") == step_id:
            step_found = step
            break
    
    if not step_found:
        raise HTTPException(status_code=404, detail="Step not found in run plan")
    
    # Check tool permissions with full operation context
    # Use check_operation with run_id and step_id context for full policy evaluation
    tool_id = step_found.get("required_tool")
    decision = check_operation(
        tool_id,
        user.role,
        operation="execute",
        context={"run_id": run_id, "step_id": step_id},
    )
    
    if decision.decision == "DENY":
        raise HTTPException(
            status_code=403,
            detail=f"Tool access denied: {decision.reason}"
        )
    
    if decision.decision == "REQUIRE_APPROVAL":
        # Check if approval already exists and is approved
        from vtr_agent.core.run_orchestrator import _step_has_approval
        if _step_has_approval(run, step_id):
            # Approval already granted, proceed with execution
            pass
        else:
            # Require approval - return approval_required
            raise HTTPException(
                status_code=202,
                detail={
                    "status": "approval_required",
                    "message": decision.reason,
                    "tool_id": tool_id,
                    "risk_level": decision.risk_level.value
                }
            )
    
    # Update step status to running
    # Find and update the corresponding PlanStepModel
    plan_step = (
        db.query(PlanStepModel)
        .filter(PlanStepModel.run_id_ref == run.id, PlanStepModel.step_id == step_id)
        .first()
    )
    
    if plan_step:
        plan_step.status = "running"
        db.flush()
    
    # Execute tool in sandbox
    tool = get_tool(step_found.get("required_tool"))
    filesystem_access = tool.filesystem_access if tool else "readonly"
    
    # Prepare code to execute based on tool type
    if step_found.get("required_tool") == "python_sandbox":
        # Execute Python code - need to generate code from step description
        code = f"# Step {step_id} execution\nresult = {step_found.get('description', '')}\nprint(result)"
        execution_result = execute_code_sandbox(
            code=code,
            timeout=30,
            memory_limit=512,
            filesystem_access=filesystem_access,
        )
        result = {
            "step_id": step_id,
            "tool": tool_id,
            "status": "completed" if execution_result.exit_code == 0 else "failed",
            "output": execution_result.stdout[-500:] if execution_result.stdout else "",
            "error": execution_result.stderr[-500:] if execution_result.stderr else "",
            "execution_time": execution_result.execution_time,
        }
        if execution_result.safety_violation:
            result["safety_violation"] = execution_result.safety_violation
            result["status"] = "blocked"
    else:
        # For other tools, execute with sandbox
        code = f"print('Tool execution: {step_found.get('description', '')}')"
        execution_result = execute_code_sandbox(
            code=code,
            timeout=30,
            memory_limit=512,
            filesystem_access=filesystem_access,
        )
        result = {
            "step_id": step_id,
            "tool": tool_id,
            "status": "completed" if execution_result.exit_code == 0 else "failed",
            "output": execution_result.stdout[-500:] if execution_result.stdout else "",
            "error": execution_result.stderr[-500:] if execution_result.stderr else "",
            "execution_time": execution_result.execution_time,
        }
        if execution_result.safety_violation:
            result["safety_violation"] = execution_result.safety_violation
            result["status"] = "blocked"
    
    # Update step status and persist evidence
    if plan_step:
        plan_step.status = "completed" if result["status"] != "blocked" else "blocked"
        plan_step.result_json = result
        if result.get("safety_violation"):
            plan_step.error = result["safety_violation"]
        else:
            plan_step.error = result.get("error")
        
        # Persist evidence to database if tool produced output
        if result.get("output") and result["status"] == "completed":
            # Add evidence to run for claim creation
            db.add(
                EvidenceModel(
                    evidence_id=new_id("EVD"),
                    run_id_ref=run.id,
                    source_type="tool_execution",
                    source_url_or_id=step_id,
                    content=result.get("output", "")[:1200],
                    metadata_json={
                        "tool": tool_id,
                        "step_id": step_id,
                        "execution_time": result.get("execution_time", 0),
                        "risk_level": step_found.get("risk_level", 1),
                    },
                )
            )
            db.flush()
            # Create claims from the newly added evidence
            _create_claims_from_evidence(db, run)
    
    # Audit the execution
    from vtr_agent.core.run_orchestrator import _audit
    _audit(
        db,
        user,
        "TOOL_EXECUTION",
        "plan_step",
        step_id,
        project_id=run.project_id,
        after={
            "status": result["status"],
            "tool": tool_id,
            "execution_time": result.get("execution_time", 0),
        },
    )
    
    return {
        "run_id": run_id,
        "plan_id": run.task_id,
        "step_id": step_id,
        "status": result["status"],
        "output": result.get("output"),
        "error": result.get("error"),
        "execution_time": result.get("execution_time"),
        "decision": decision.decision,
        "reason": decision.reason,
    }


@router.post("/{plan_id}/status", response_model=TaskStatusUpdate)
def update_task_status(
    plan_id: str,
    status_update: TaskStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update research task status, validated against the state machine (BUG-05)."""
    run = get_run_by_identifier(db, user, plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Validate the transition against the canonical state machine.
    try:
        current = TaskStatus(run.status)
    except ValueError:
        current = None

    if current is not None and not StateMachine.can_transition(current, status_update.status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: {StateMachine.transition_valid(current, status_update.status)}",
        )

    run.status = status_update.status.value
    db.commit()

    return TaskStatusUpdate(
        task_id=plan_id,
        status=status_update.status,
        message=status_update.message,
        progress_percentage=status_update.progress_percentage,
    )


@router.get("/{plan_id}/steps", response_model=List[PlanStep])
def list_steps(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all steps in a persisted research plan (BUG-05)."""
    run = get_run_by_identifier(db, user, plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    steps = (
        db.query(PlanStepModel)
        .filter(PlanStepModel.run_id_ref == run.id)
        .order_by(PlanStepModel.step_id.asc())
        .all()
    )
    return [
        PlanStep(
            step_id=step.step_id,
            description=step.description,
            required_tool=step.required_tool,
            risk_level=step.risk_level,
            requires_approval=step.requires_approval,
            status=step.status,
            result=step.result_json or None,
            error=step.error,
        )
        for step in steps
    ]


@router.get("/{plan_id}/stats", response_model=Dict)
def get_task_stats(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get execution statistics for a persisted research run (BUG-05)."""
    run = get_run_by_identifier(db, user, plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    steps = (
        db.query(PlanStepModel)
        .filter(PlanStepModel.run_id_ref == run.id)
        .all()
    )
    return {
        "plan_id": plan_id,
        "run_id": run.run_id,
        "plan_status": run.status,
        "total_steps": len(steps),
        "completed_steps": sum(1 for s in steps if s.status == "completed"),
        "failed_steps": sum(1 for s in steps if s.status == "failed"),
        "blocked_steps": sum(1 for s in steps if s.status == "blocked"),
        "waiting_approval_steps": sum(1 for s in steps if s.status == "waiting_approval"),
        "global_stats": run_status_counts(db, user),
    }


@router.get("/tools/allowed", response_model=Dict)
def get_allowed_tools_endpoint(
    user_role: str = Depends(lambda: get_current_user(db=None).role if True else "researcher"),
    db: Session = Depends(get_db),
):
    """Get tools allowed for user role."""
    # Get current user role
    current_user = get_current_user(db=None) if False else get_current_user(db)
    allowed = get_allowed_tools(current_user.role)
    return {
        "user_role": current_user.role,
        "allowed_tools": {
            tool_id: {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": tool.requires_approval,
            }
            for tool_id, tool in allowed.items()
        }
    }


@router.get("/tools/all", response_model=Dict)
def get_all_tools_endpoint():
    """Get all registered tools."""
    all_tools = get_all_tools()
    return {
        "tools": {
            tool_id: {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": tool.requires_approval,
                "supports": tool.supports,
            }
            for tool_id, tool in all_tools.items()
        }
    }


@router.post("/{run_id}/start", response_model=Dict)
def start_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start (or resume) the orchestrated run lifecycle.

    Drives the persisted state machine: plan -> policy check -> approval gate
    (pausing at WAITING_APPROVAL if required) -> tool execution -> evidence ->
    claim verification -> report. Re-invoking after an approval resumes the run.
    """
    run = start_or_resume_run(db, user, run_id)
    return run_to_dict(run)


@router.post("/{run_id}/approvals/{approval_id}/decide", response_model=Dict)
def decide_run_approval(
    run_id: str,
    approval_id: str,
    decision: str = Query(..., pattern="^(approved|rejected)$"),
    reason: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or reject a persisted approval request for a run step.

    After approval, re-invoking ``/{run_id}/start`` resumes execution.
    """
    approval = decide_approval(db, user, approval_id, decision, reason)
    return approval_to_dict(approval)


@router.get("/{run_id}/trace", response_model=Dict)
def get_run_trace(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get execution trace for a research run."""
    # Get the research run from database
    run = db.query(ResearchRun).filter(ResearchRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if not user.is_admin and run.created_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this run")
    
    # Get trace data
    trace = trace_for_run(run)
    return trace


@router.get("/{run_id}/audit", response_model=Dict)
def get_run_audit(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get audit trail for a research run."""
    # Get the research run from database
    run = db.query(ResearchRun).filter(ResearchRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if not user.is_admin and run.created_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this run")
    
    # Get audit logs for this run
    from vtr_agent.core.database.models import AuditLog
    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.project_id == run.project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    
    logs = []
    for log in audit_logs:
        logs.append({
            "event_id": log.event_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "status": log.status,
            "created_at": log.created_at,
        })
    
    return {
        "run_id": run_id,
        "project_id": run.project_id,
        "audit_logs": logs,
        "total_logs": len(logs),
    }


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
