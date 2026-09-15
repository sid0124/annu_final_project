"""Planner factory.

Selects a planner from configuration: Groq when ``LLM_PROVIDER == "groq"`` and a
``GROQ_API_KEY`` is present, otherwise the deterministic planner. Any failure to
construct an LLM planner degrades safely to deterministic.
"""
from __future__ import annotations

from typing import Optional

from app.planner.base import Planner, PlannerError
from app.planner.deterministic import DeterministicPlanner
from app.planner.groq_planner import GroqPlanner
from vtr_agent.core.config import get_settings


def get_planner(provider: Optional[str] = None) -> Planner:
    """Return the configured planner, degrading safely to deterministic."""
    settings = get_settings()
    name = (provider or settings.LLM_PROVIDER or "").strip().lower()

    if name == "groq" and settings.GROQ_API_KEY:
        try:
            return GroqPlanner()
        except PlannerError:
            pass

    return DeterministicPlanner()
