"""
VTR-Agent: Task API Endpoints

Task management API endpoints for research workflow coordination.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    TaskCreate, TaskUpdate, TaskResponse, PlanStep,
    TaskStatusUpdate, RiskLevel, TaskStatus
)
from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import User, Project, ResearchRun, PlanStepModel, EvidenceModel, ClaimModel
from vtr_agent.core.task_engine import (
    create_research_task, add_plan_step, get_plan,
    update_step, update_plan, get_task_statistics, StepStatus
)
from vtr_agent.core.policy_engine import check_operation, policy_engine, check_tool_permission
from vtr_agent.core.sandbox.sandbox_manager import execute_code_sandbox
from vtr_agent.core.run_orchestrator import create_run, start_or_resume_run, trace_for_run, run_to_dict
from vtr_agent.core.tool_registry import get_allowed_tools, get_tool, get_all_tools
from vtr_agent.utils import new_id

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
    
    # Check user has permission to create tasks in this project
    user_role = user.role
    allowed = get_allowed_tools(user_role)
    if "tasks" not in [t.lower() for t in allowed.keys()]:
        # More specific check
        perms = allowed.get(user_role, {})
        if not perms.get("create_task", False) and not user.is_admin:
            raise HTTPException(status_code=403, detail="User cannot create tasks")
    
    # Create database-backed research run with run_id
    run = create_run(db, user, task.instructions, project.id)
    
    # Add initial plan step if instructions provided
    if task.instructions:
        step = PlanStep(
            step_id="S1",
            description=task.instructions,
            required_tool="retriever",
            risk_level=RiskLevel.LEVEL_1,
            requires_approval=False,
        )
        add_plan_step(run.task_id, step)
    
    return TaskResponse(
        task_id=run.task_id,
        name=task.name or "Research Task",
        description=task.description or "",
        instructions=task.instructions or "",
        project_id=project.project_id,
        user_id=user.user_id,
        status=run.status.value,
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
    """List all tasks for the user's projects."""
    # Get user's projects
    if user.is_admin:
        projects = db.query(Project).all()
    else:
        # Get projects user is member of
        from vtr_agent.core.database.models import ProjectMembership
        memberships = db.query(ProjectMembership).filter(
            ProjectMembership.user_id == user.id
        ).all()
        project_ids = [pm.project_id for pm in memberships]
        projects = db.query(Project).filter(Project.id.in_(project_ids)).all()
    
    # Build task list from active plans
    tasks = []
    for project in projects:
        # Look for active plans (simplified - in production would query DB)
        # For now, return empty list as plans are in-memory
        pass
    
    return tasks


@router.get("/{plan_id}", response_model=TaskResponse)
def get_task(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific research plan."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check permissions
    if not user.is_admin and plan.created_by != user.user_id:
        # Check if user has access to the project
        from vtr_agent.core.database.models import ProjectMembership
        has_access = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == plan.plan_id,
            ProjectMembership.user_id == user.id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this plan")
    
    return TaskResponse(
        task_id=plan.plan_id,
        name=plan.goal[:50] if len(plan.goal) > 50 else plan.goal,
        description=plan.goal,
        instructions=plan.goal,
        project_id="",  # Will be set from project association
        user_id=plan.created_by,
        status=plan.status.value,
        priority="medium",
        tags=[],
        created_at=plan.created_at,
        updated_at=plan.created_at,
    )


@router.post("/{plan_id}/steps", response_model=PlanStep)
def add_task_step(
    plan_id: str,
    step: PlanStep,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a step to a research plan."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check permissions
    if not user.is_admin and plan.created_by != user.user_id:
        from vtr_agent.core.database.models import ProjectMembership
        has_access = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == plan.plan_id,
            ProjectMembership.user_id == user.id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    success = add_plan_step(plan_id, step)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add step to plan")
    
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
    """Update research task status."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check permissions
    if not user.is_admin and plan.created_by != user.user_id:
        from vtr_agent.core.database.models import ProjectMembership
        has_access = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == plan.plan_id,
            ProjectMembership.user_id == user.id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate state transition
    from vtr_agent.core.task_engine import StateMachine
    valid = StateMachine.can_transition(plan.status, status_update.status)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: {StateMachine.transition_valid(plan.status, status_update.status)}"
        )
    
    # Update plan status
    update_plan(plan_id, status_update.status)
    
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
    """List all steps in a research plan."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check permissions
    if not user.is_admin and plan.created_by != user.user_id:
        from vtr_agent.core.database.models import ProjectMembership
        has_access = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == plan.plan_id,
            ProjectMembership.user_id == user.id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return plan.steps


@router.get("/{plan_id}/stats", response_model=Dict)
def get_task_stats(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get task execution statistics."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check permissions
    if not user.is_admin and plan.created_by != user.user_id:
        from vtr_agent.core.database.models import ProjectMembership
        has_access = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == plan.plan_id,
            ProjectMembership.user_id == user.id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")
    
    stats = get_task_statistics()
    return {
        "plan_id": plan_id,
        "plan_status": plan.status.value,
        "total_steps": len(plan.steps),
        "completed_steps": sum(
            1 for s in plan.steps if s.status.value == "completed"
        ),
        "failed_steps": sum(
            1 for s in plan.steps if s.status.value == "failed"
        ),
        "overall_risk": plan.overall_risk.value,
        "global_stats": stats,
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


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
