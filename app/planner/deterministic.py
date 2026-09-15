"""Deterministic (rule-based) planner.

Used when no LLM provider is configured, and as the automatic fallback when an
LLM planner is unavailable or its output is unusable. Requires no API key.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from app.planner.base import Planner, PlannerPlan, PlannerStep, validate_plan
from vtr_agent.utils import RiskLevel

_ANALYSIS_RE = re.compile(
    r"\b(analy[sz]e|dataset|statistics|python|code|chart|plot)\b", re.I
)


class DeterministicPlanner(Planner):
    """Rule-based planner producing a fixed, safe retrieve -> evidence pipeline.

    Adds a sandboxed analysis step when the task text implies computation, or
    when ``python_sandbox`` is explicitly among the allowed tools.
    """

    name = "deterministic"

    def plan(self, task: str, allowed_tools: Optional[Iterable[str]] = None) -> PlannerPlan:
        allowed = set(allowed_tools or [])
        steps = [
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
        ]
        if _ANALYSIS_RE.search(task) or "python_sandbox" in allowed:
            steps.insert(
                1,
                PlannerStep(
                    step_id="S1A",
                    description="Run approved bounded analysis in the sandbox.",
                    required_tool="python_sandbox",
                    risk_level=RiskLevel.LEVEL_2.value,
                    requires_approval=True,
                    depends_on=["S1"],
                ),
            )

        return validate_plan(
            PlannerPlan(
                planner=self.name,
                goal=task,
                steps=steps,
                notes=["No external LLM planner is enabled; using the deterministic planner."],
            )
        )
