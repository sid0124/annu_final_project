"""
VTR-Agent: Task Engine

State machine for research workflow coordination and task management.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Research task lifecycle statuses."""
    CREATED = "created"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    POLICY_CHECK = "policy_check"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    EVIDENCE_COLLECTION = "evidence_collection"
    CLAIM_VERIFICATION = "claim_verification"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class RiskLevel(int, Enum):
    """Risk level classification for tasks and tool usage."""
    LEVEL_0 = 0  # Safe - automatic execution
    LEVEL_1 = 1  # Controlled - policy-supervised
    LEVEL_2 = 2  # High - requires human approval
    LEVEL_3 = 3  # Blocked - always prohibited


class StepStatus(str, Enum):
    """Individual step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """Structured plan step definition."""
    step_id: str
    description: str
    required_tool: str
    risk_level: RiskLevel = RiskLevel.LEVEL_1
    requires_approval: bool = False
    depends_on: Optional[List[str]] = None
    timeout_seconds: Optional[int] = None
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ResearchPlan(BaseModel):
    """Complete research plan with steps and metadata."""
    plan_id: str
    goal: str
    steps: List[PlanStep]
    created_at: str
    created_by: str
    status: TaskStatus = TaskStatus.CREATED
    policy_decisions: Dict[str, Any] = Field(default_factory=dict)
    approval_status: Optional[str] = None
    overall_risk: RiskLevel = RiskLevel.LEVEL_1


class TaskStatusUpdate(BaseModel):
    """Status update for a task."""
    task_id: str
    status: TaskStatus
    message: Optional[str] = None
    progress_percentage: float = 0.0


class StateMachine:
    """Manages research task state transitions."""
    
    # Valid state transitions
    TRANSITIONS = {
        TaskStatus.CREATED: [TaskStatus.PLANNING],
        TaskStatus.PLANNING: [TaskStatus.PLAN_READY, TaskStatus.FAILED],
        TaskStatus.PLAN_READY: [TaskStatus.POLICY_CHECK, TaskStatus.FAILED],
        TaskStatus.POLICY_CHECK: [
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.EXECUTING,
            TaskStatus.FAILED,
        ],
        TaskStatus.WAITING_APPROVAL: [
            TaskStatus.EXECUTING,
            TaskStatus.POLICY_CHECK,
            TaskStatus.CANCELLED,
        ],
        TaskStatus.EXECUTING: [
            TaskStatus.EVIDENCE_COLLECTION,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
        ],
        TaskStatus.EVIDENCE_COLLECTION: [
            TaskStatus.CLAIM_VERIFICATION,
            TaskStatus.FAILED,
        ],
        TaskStatus.CLAIM_VERIFICATION: [
            TaskStatus.REPORT_GENERATION,
            TaskStatus.FAILED,
        ],
        TaskStatus.REPORT_GENERATION: [TaskStatus.COMPLETED, TaskStatus.FAILED],
        TaskStatus.COMPLETED: [],  # Terminal
        TaskStatus.FAILED: [TaskStatus.REPORT_GENERATION],  # Can retry
        TaskStatus.BLOCKED: [TaskStatus.POLICY_CHECK],  # Can unblock
        TaskStatus.CANCELLED: [],  # Terminal
    }
    
    @staticmethod
    def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check if a state transition is valid."""
        allowed = StateMachine.TRANSITIONS.get(from_status, [])
        return to_status in allowed
    
    @staticmethod
    def get_next_states(current: TaskStatus) -> List[TaskStatus]:
        """Get valid next states from current state."""
        return StateMachine.TRANSITIONS.get(current, [])
    
    @staticmethod
    def transition_valid(current: TaskStatus, target: TaskStatus) -> str:
        """Get validation message for transition."""
        if StateMachine.can_transition(current, target):
            return "valid"
        return f"Invalid transition from {current.value} to {target.value}. Allowed: {[t.value for t in StateMachine.get_next_states(current)]}"


class TaskEngine:
    """Core task engine managing research workflow execution."""
    
    def __init__(self):
        self.active_tasks: Dict[str, ResearchPlan] = {}
        self.task_history: Dict[str, ResearchPlan] = {}
    
    def create_task(self, goal: str, user_id: str, project_id: str) -> ResearchPlan:
        """Create a new research task."""
        plan_id = f"plan_{user_id}_{len(self.active_tasks) + 1}_{self._generate_timestamp()}"
        
        plan = ResearchPlan(
            plan_id=plan_id,
            goal=goal,
            steps=[],
            created_at=self._generate_timestamp(),
            created_by=user_id,
        )
        
        self.active_tasks[plan_id] = plan
        self.task_history[plan_id] = plan
        
        return plan
    
    def add_step(self, plan_id: str, step: PlanStep) -> bool:
        """Add a step to a research plan."""
        if plan_id not in self.active_tasks:
            return False
        
        plan = self.active_tasks[plan_id]
        plan.steps.append(step)
        plan.status = TaskStatus.PLANNING
        
        return True
    
    def get_plan(self, plan_id: str) -> Optional[ResearchPlan]:
        """Get a research plan by ID."""
        return self.active_tasks.get(plan_id) or self.task_history.get(plan_id)
    
    def update_step_status(
        self, 
        plan_id: str, 
        step_id: str, 
        status: StepStatus, 
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update a step's execution status."""
        plan = self.get_plan(plan_id)
        if not plan:
            return False
        
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = status
                if result is not None:
                    step.result = result
                if error is not None:
                    step.error = error
                step.completed_at = self._generate_timestamp()
                return True
        
        return False
    
    def update_plan_status(self, plan_id: str, status: TaskStatus) -> bool:
        """Update a research plan's status."""
        plan = self.get_plan(plan_id)
        if not plan:
            return False
        
        plan.status = status
        return True
    
    def _generate_timestamp(self) -> str:
        """Generate ISO format timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%z")
    
    def get_task_stats(self) -> Dict[str, int]:
        """Get task execution statistics."""
        stats = {
            "active": len(self.active_tasks),
            "completed": sum(
                1 for p in self.task_history.values() 
                if p.status == TaskStatus.COMPLETED
            ),
            "failed": sum(
                1 for p in self.task_history.values() 
                if p.status == TaskStatus.FAILED
            ),
            "blocked": sum(
                1 for p in self.task_history.values() 
                if p.status == TaskStatus.BLOCKED
            ),
        }
        return stats


# Global task engine instance
task_engine = TaskEngine()


# Convenience functions
def create_research_task(goal: str, user_id: str, project_id: str) -> ResearchPlan:
    """Create a new research task."""
    return task_engine.create_task(goal, user_id, project_id)


def add_plan_step(plan_id: str, step: PlanStep) -> bool:
    """Add a step to a research plan."""
    return task_engine.add_step(plan_id, step)


def get_plan(plan_id: str) -> Optional[ResearchPlan]:
    """Get a research plan by ID."""
    return task_engine.get_plan(plan_id)


def update_step(
    plan_id: str, 
    step_id: str, 
    status: StepStatus, 
    result: Optional[Dict] = None,
    error: Optional[str] = None
) -> bool:
    """Update a step execution status."""
    return task_engine.update_step_status(plan_id, step_id, status, result, error)


def update_plan(plan_id: str, status: TaskStatus) -> bool:
    """Update a research plan status."""
    return task_engine.update_plan_status(plan_id, status)


def get_task_statistics() -> Dict[str, int]:
    """Get task execution statistics."""
    return task_engine.get_task_stats()