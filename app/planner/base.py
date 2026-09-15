"""Planner interface for VTR-Agent (BUG-08).

Defines the ``LLM proposes, app executes`` boundary. A planner only *proposes*
a structured plan; :func:`validate_plan` sanitizes that proposal against the
authoritative tool registry before the application executes anything. No
planner (LLM or otherwise) can introduce an unregistered tool or downgrade a
tool's registered risk / approval requirement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from vtr_agent.core.tool_registry import get_all_tools
from vtr_agent.utils import RiskLevel

#: Hard cap on the number of steps a planner may propose.
MAX_PLAN_STEPS = 10


class PlannerError(RuntimeError):
    """Raised when a planner fails to produce a usable plan."""


class PlannerStep(BaseModel):
    """One proposed step of a research plan."""

    step_id: str
    description: str
    required_tool: str
    risk_level: int = RiskLevel.LEVEL_1.value
    requires_approval: bool = False
    depends_on: List[str] = Field(default_factory=list)


class PlannerPlan(BaseModel):
    """A full structured plan produced by a planner."""

    planner: str
    goal: str
    steps: List[PlannerStep] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class Planner(ABC):
    """Provider-agnostic planner interface."""

    name: str = "base"

    @abstractmethod
    def plan(self, task: str, allowed_tools: Optional[Iterable[str]] = None) -> PlannerPlan:
        """Produce a structured plan for ``task`` using only ``allowed_tools``."""


def _fallback_plan(goal: str, reason: str) -> PlannerPlan:
    return PlannerPlan(
        planner="fallback",
        goal=goal,
        steps=[
            PlannerStep(
                step_id="S1",
                description="Retrieve approved project evidence relevant to the task.",
                required_tool="retriever",
                risk_level=RiskLevel.LEVEL_1.value,
                requires_approval=False,
            ),
            PlannerStep(
                step_id="S2",
                description="Create provenance-linked evidence and preliminary claims.",
                required_tool="evidence_tool",
                risk_level=RiskLevel.LEVEL_1.value,
                requires_approval=False,
                depends_on=["S1"],
            ),
        ],
        notes=[reason],
    )


def validate_plan(plan: PlannerPlan) -> PlannerPlan:
    """Sanitize a planner proposal against the authoritative tool registry.

    This is the application-side gate between "proposed" and "executable":
      * steps referencing unregistered tools are dropped (an LLM cannot
        introduce a tool the system does not know about);
      * ``risk_level`` is clamped to each tool's *registered* risk level;
      * ``requires_approval`` is forced True for LEVEL_2+ tools or tools flagged
        as needing human approval (an LLM cannot downgrade a gate);
      * step ids are renumbered deterministically and ``depends_on`` rewritten;
      * the plan length is capped.
    """
    registry = get_all_tools()
    notes: List[str] = list(plan.notes)
    cleaned: List[PlannerStep] = []

    for step in plan.steps[:MAX_PLAN_STEPS]:
        tool = registry.get(step.required_tool)
        if tool is None:
            notes.append(
                f"Dropped step '{step.step_id}': unregistered tool "
                f"'{step.required_tool}' (planner cannot introduce tools)."
            )
            continue

        registered_risk = tool.risk_level.value
        must_approve = bool(tool.requires_approval) or registered_risk >= RiskLevel.LEVEL_2.value
        if must_approve and not step.requires_approval:
            notes.append(
                f"Step '{step.step_id}': forced requires_approval=True for "
                f"LEVEL_{registered_risk} tool '{step.required_tool}'."
            )

        cleaned.append(
            step.model_copy(
                update={
                    "risk_level": registered_risk,
                    "requires_approval": must_approve,
                }
            )
        )

    if not cleaned:
        return _fallback_plan(
            plan.goal,
            "Planner produced no usable steps; applied the safe retrieval+evidence fallback plan.",
        )

    remap = {old: f"S{index + 1}" for index, old in enumerate(item.step_id for item in cleaned)}
    finalized: List[PlannerStep] = []
    for index, step in enumerate(cleaned):
        new_id = f"S{index + 1}"
        depends_on = [
            remap[dep] for dep in step.depends_on if dep in remap and remap[dep] != new_id
        ]
        finalized.append(step.model_copy(update={"step_id": new_id, "depends_on": depends_on}))

    return PlannerPlan(
        planner=plan.planner,
        goal=plan.goal,
        steps=finalized,
        notes=notes,
    )


def plan_to_dict(plan: PlannerPlan) -> Dict[str, Any]:
    """Serialize a plan for persistence in ``ResearchRun.plan_json``."""
    return {
        "planner": plan.planner,
        "goal": plan.goal,
        "steps": [step.model_dump(mode="json") for step in plan.steps],
        "notes": list(plan.notes),
    }
