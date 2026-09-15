"""VTR-Agent planner package (BUG-08).

Provider-agnostic planning with an "LLM proposes, app executes" boundary:
``get_planner()`` returns the configured planner (Groq when a key is present,
deterministic otherwise), and every proposal is sanitized by ``validate_plan``
before execution.
"""
from app.planner.base import (
    MAX_PLAN_STEPS,
    Planner,
    PlannerError,
    PlannerPlan,
    PlannerStep,
    plan_to_dict,
    validate_plan,
)
from app.planner.deterministic import DeterministicPlanner
from app.planner.factory import get_planner
from app.planner.groq_planner import GroqPlanner

__all__ = [
    "MAX_PLAN_STEPS",
    "DeterministicPlanner",
    "GroqPlanner",
    "Planner",
    "PlannerError",
    "PlannerPlan",
    "PlannerStep",
    "get_planner",
    "plan_to_dict",
    "validate_plan",
]
