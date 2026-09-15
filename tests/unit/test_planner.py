"""Unit tests for the VTR-Agent planner package (BUG-08).

Covers the deterministic planner, the "LLM proposes, app executes" validation
boundary, the Groq adapter (with httpx stubbed out), and the factory.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.planner import (
    MAX_PLAN_STEPS,
    DeterministicPlanner,
    GroqPlanner,
    PlannerError,
    get_planner,
    validate_plan,
)
from app.planner.base import PlannerPlan, PlannerStep
from vtr_agent.utils import RiskLevel


# --- Deterministic planner ---------------------------------------------------


def test_deterministic_planner_basic_two_steps():
    plan = DeterministicPlanner().plan("Summarize the project's findings")
    assert plan.planner == "deterministic"
    assert [step.required_tool for step in plan.steps] == ["retriever", "evidence_tool"]
    assert all(step.requires_approval is False for step in plan.steps)
    assert plan.steps[0].step_id == "S1"
    assert plan.steps[1].step_id == "S2"


def test_deterministic_planner_inserts_sandbox_for_analysis():
    plan = DeterministicPlanner().plan("Analyse the dataset statistics using python")
    tools = [step.required_tool for step in plan.steps]
    assert tools == ["retriever", "python_sandbox", "evidence_tool"]
    sandbox = plan.steps[1]
    assert sandbox.risk_level == RiskLevel.LEVEL_2.value
    assert sandbox.requires_approval is True
    # dependency points at the (renumbered) retriever step
    assert sandbox.depends_on == ["S1"]


def test_deterministic_planner_sandbox_when_explicitly_allowed():
    plan = DeterministicPlanner().plan("plain task", allowed_tools=["python_sandbox"])
    assert any(step.required_tool == "python_sandbox" for step in plan.steps)


# --- Validation boundary -----------------------------------------------------


def test_validate_plan_drops_unknown_tools():
    plan = PlannerPlan(
        planner="test",
        goal="g",
        steps=[
            PlannerStep(step_id="X1", description="d", required_tool="retriever"),
            PlannerStep(step_id="X2", description="d", required_tool="nuclear_launch"),
        ],
    )
    validated = validate_plan(plan)
    assert [step.step_id for step in validated.steps] == ["S1"]
    assert validated.steps[0].required_tool == "retriever"
    assert any("unregistered tool" in note for note in validated.notes)


def test_validate_plan_forces_approval_for_high_risk():
    plan = PlannerPlan(
        planner="test",
        goal="g",
        steps=[
            PlannerStep(
                step_id="X1",
                description="d",
                required_tool="python_sandbox",
                risk_level=0,
                requires_approval=False,
            ),
        ],
    )
    validated = validate_plan(plan)
    step = validated.steps[0]
    assert step.requires_approval is True
    assert step.risk_level == RiskLevel.LEVEL_2.value
    assert any("forced requires_approval" in note for note in validated.notes)


def test_validate_plan_renumbers_and_remaps_dependencies():
    plan = PlannerPlan(
        planner="test",
        goal="g",
        steps=[
            PlannerStep(step_id="B", description="d", required_tool="retriever"),
            PlannerStep(
                step_id="A",
                description="d",
                required_tool="evidence_tool",
                depends_on=["B"],
            ),
        ],
    )
    validated = validate_plan(plan)
    assert [step.step_id for step in validated.steps] == ["S1", "S2"]
    assert validated.steps[1].depends_on == ["S1"]


def test_validate_plan_caps_step_count():
    steps = [
        PlannerStep(step_id=f"X{i}", description="d", required_tool="calculator")
        for i in range(MAX_PLAN_STEPS + 5)
    ]
    validated = validate_plan(PlannerPlan(planner="test", goal="g", steps=steps))
    assert len(validated.steps) == MAX_PLAN_STEPS


def test_validate_plan_falls_back_when_no_usable_steps():
    plan = PlannerPlan(
        planner="test",
        goal="g",
        steps=[PlannerStep(step_id="X1", description="d", required_tool="nope")],
    )
    validated = validate_plan(plan)
    assert [step.required_tool for step in validated.steps] == ["retriever", "evidence_tool"]
    assert validated.planner == "fallback"


# --- Groq adapter (httpx stubbed) -------------------------------------------


def _stub_groq_client(monkeypatch, content=None, error=None):
    from app.planner import groq_planner

    class _Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": content}}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            if error is not None:
                raise error
            return _Response()

    monkeypatch.setattr(groq_planner.httpx, "Client", _Client)


def test_groq_planner_parses_and_validates(monkeypatch):
    payload = {
        "steps": [
            {
                "step_id": "A1",
                "description": "Find sources",
                "required_tool": "retriever",
                "risk_level": 1,
                "requires_approval": False,
                "depends_on": [],
            },
            {
                "step_id": "A2",
                "description": "Compute statistics",
                "required_tool": "python_sandbox",
                "risk_level": 0,  # LLM tries to downgrade the gate
                "requires_approval": False,
                "depends_on": ["A1"],
            },
            {
                "step_id": "A3",
                "description": "Bogus",
                "required_tool": "not_a_real_tool",
                "risk_level": 1,
                "requires_approval": False,
                "depends_on": [],
            },
        ]
    }
    _stub_groq_client(monkeypatch, content=json.dumps(payload))

    plan = GroqPlanner(api_key="fake-key").plan("Compute dataset statistics")
    assert plan.planner == "groq"
    # unknown tool dropped; remaining steps renumbered
    assert [step.step_id for step in plan.steps] == ["S1", "S2"]
    assert [step.required_tool for step in plan.steps] == ["retriever", "python_sandbox"]
    # approval gate restored despite the LLM's downgrade attempt
    sandbox = plan.steps[1]
    assert sandbox.requires_approval is True
    assert sandbox.risk_level == RiskLevel.LEVEL_2.value
    assert sandbox.depends_on == ["S1"]
    assert any("validated against" in note for note in plan.notes)


def test_groq_planner_handles_fenced_json(monkeypatch):
    content = '```json\n{"steps":[{"step_id":"Q1","description":"d","required_tool":"calculator","risk_level":0,"requires_approval":false,"depends_on":[]}]}\n```'
    _stub_groq_client(monkeypatch, content=content)
    plan = GroqPlanner(api_key="fake-key").plan("Add numbers")
    assert [step.required_tool for step in plan.steps] == ["calculator"]


def test_groq_planner_raises_on_empty_response(monkeypatch):
    _stub_groq_client(monkeypatch, content="sorry, I cannot help with that")
    with pytest.raises(PlannerError):
        GroqPlanner(api_key="fake-key").plan("Do something")


def test_groq_planner_raises_on_http_error(monkeypatch):
    _stub_groq_client(monkeypatch, error=httpx.ConnectError("network down"))
    with pytest.raises(PlannerError):
        GroqPlanner(api_key="fake-key").plan("Do something")


def test_groq_planner_requires_api_key():
    with pytest.raises(PlannerError):
        GroqPlanner(api_key="")


# --- Factory -----------------------------------------------------------------


def _fake_settings(monkeypatch, **overrides):
    import vtr_agent.core.config as config

    values = {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": None,
        "LLM_MODEL": "llama-3.3-70b-versatile",
        "LLM_TEMPERATURE": 0.2,
        "LLM_MAX_TOKENS": 128,
    }
    values.update(overrides)
    monkeypatch.setattr(config, "_settings", SimpleNamespace(**values))


def test_factory_defaults_to_deterministic_without_key(monkeypatch):
    _fake_settings(monkeypatch)
    assert isinstance(get_planner(), DeterministicPlanner)


def test_factory_returns_groq_with_key(monkeypatch):
    _fake_settings(monkeypatch, GROQ_API_KEY="fake-key")
    assert isinstance(get_planner(), GroqPlanner)


def test_factory_degrades_unsupported_provider(monkeypatch):
    _fake_settings(monkeypatch, LLM_PROVIDER="openai", GROQ_API_KEY="fake-key")
    assert isinstance(get_planner(), DeterministicPlanner)
