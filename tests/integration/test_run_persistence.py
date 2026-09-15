"""BUG-05 tests: run/approval/evidence/claim persistence across a restart.

The first test drives the orchestrator against a *file-backed* SQLite database,
closes the engine to simulate a process restart, reopens it, and verifies that
runs, steps, approvals, evidence, claims and the report all survived. The
second block covers the DB-backed /tasks endpoints through the API.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vtr_agent.auth.security import get_password_hash
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import Base
from vtr_agent.core.run_orchestrator import (
    create_run,
    decide_approval,
    get_run_by_identifier,
    list_runs_for_user,
    start_or_resume_run,
)
from vtr_agent.utils import new_id


def _seed(db):
    admin = m.User(
        user_id=new_id("USR"),
        username="restart-admin",
        email="restart-admin@vtr.test",
        full_name="Restart Admin",
        password_hash=get_password_hash("Demo@12345"),
        role="admin",
        is_active=True,
        is_demo=True,
    )
    researcher = m.User(
        user_id=new_id("USR"),
        username="restart-researcher",
        email="restart-researcher@vtr.test",
        full_name="Restart Researcher",
        password_hash=get_password_hash("Demo@12345"),
        role="researcher",
        is_active=True,
        is_demo=True,
    )
    project = m.Project(
        project_id=new_id("PROJ"),
        name="Restart Project",
        domain="AI Research",
        description="persistence test project",
        expected_users="researchers",
        status="draft",
    )
    db.add_all([admin, researcher, project])
    db.commit()
    db.refresh(admin)
    db.refresh(researcher)
    db.refresh(project)

    # A document so the retriever step produces persisted evidence.
    document = m.Document(
        document_id=new_id("DOC"),
        project_id=project.id,
        filename="evidence.txt",
        file_type="txt",
        cleaned_text=(
            "Transformer architectures rely on self-attention to model "
            "long-range dependencies between tokens in a sequence."
        ),
        status="approved",
    )
    db.add(document)
    db.commit()
    return admin, researcher, project


def test_run_survives_engine_restart(tmp_path):
    db_path = tmp_path / "restart.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # --- first "process": researcher creates + starts an analysis run -------
    with Session() as db:
        admin, researcher, project = _seed(db)
        run = create_run(
            db, researcher, "Analyse the dataset statistics using python", project.id
        )
        run_id = run.run_id
        # deterministic planner must have proposed a sandbox step
        assert any(
            step["required_tool"] == "python_sandbox" for step in run.plan_json["steps"]
        )

        run = start_or_resume_run(db, researcher, run_id)
        assert run.status == "waiting_approval"
        approval = run.approvals[0]
        approval_id = approval.approval_id
        # the retriever step completed and left persisted evidence before the gate
        assert any(step.status == "completed" for step in run.steps)
        assert len(run.evidence_items) >= 1

        # ids to re-load users in the restarted process (no detached objects)
        researcher_user_id = researcher.user_id
        admin_user_id = admin.user_id

    # --- simulated restart: connection pool and engine are gone -------------
    engine.dispose()

    # --- second "process": everything is still there -------------------------
    engine2 = create_engine(f"sqlite:///{db_path}")
    Session2 = sessionmaker(bind=engine2)
    with Session2() as db:
        researcher2 = db.query(m.User).filter(m.User.user_id == researcher_user_id).first()
        admin2 = db.query(m.User).filter(m.User.user_id == admin_user_id).first()
        assert researcher2 is not None and admin2 is not None

        reloaded = get_run_by_identifier(db, researcher2, run_id)
        assert reloaded is not None
        assert reloaded.status == "waiting_approval"
        assert reloaded.goal == "Analyse the dataset statistics using python"
        assert len(reloaded.steps) == 3
        assert [step.required_tool for step in sorted(reloaded.steps, key=lambda s: s.step_id)] == [
            "retriever",
            "python_sandbox",
            "evidence_tool",
        ]
        pending = [a for a in reloaded.approvals if a.status == "pending"]
        assert len(pending) == 1
        assert pending[0].approval_id == approval_id

        # admin decision persists, then the researcher resumes and completes
        decision = decide_approval(db, admin2, approval_id, "approved", "restart-safe")
        assert decision.status == "approved"
        assert reloaded.status == "policy_check"

        completed = start_or_resume_run(db, researcher2, run_id)
        assert completed.status == "completed"
        assert completed.summary_report
        assert completed.claims, "claims must persist after completion"
        assert completed.evidence_items

        # list_runs_for_user reads from the DB, not process memory
        listed = list_runs_for_user(db, researcher2)
        assert any(item.run_id == run_id for item in listed)

    engine2.dispose()


# --- DB-backed /tasks endpoints through the API ------------------------------


@pytest.fixture
def _run_id(client, auth_headers):
    projects = client.get("/projects", headers=auth_headers).json()
    assert projects, "demo project should exist"
    r = client.post(
        "/tasks",
        headers=auth_headers,
        json={
            "name": "Persisted task",
            "description": "persistence",
            "instructions": "Summarize the project's findings",
            "project_id": projects[0]["project_id"],
            "user_id": 1,
            "priority": "medium",
            "tags": ["persist"],
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["run_id"]


def test_list_tasks_returns_persisted_runs(client, auth_headers, _run_id):
    r = client.get("/tasks", headers=auth_headers)
    assert r.status_code == 200, r.text
    matches = [t for t in r.json() if t["run_id"] == _run_id]
    assert matches, "list_tasks must read runs from the DB"
    assert matches[0]["status"] == "plan_ready"


def test_get_task_by_run_id_and_task_id(client, auth_headers, _run_id):
    r = client.get(f"/tasks/{_run_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == _run_id
    task_id = body["task_id"]

    r = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["run_id"] == _run_id


def test_list_steps_and_stats_are_db_backed(client, auth_headers, _run_id):
    r = client.get(f"/tasks/{_run_id}/steps", headers=auth_headers)
    assert r.status_code == 200, r.text
    steps = r.json()
    assert len(steps) >= 2
    assert {step["required_tool"] for step in steps} >= {"retriever", "evidence_tool"}

    r = client.get(f"/tasks/{_run_id}/stats", headers=auth_headers)
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["total_steps"] == len(steps)
    assert stats["plan_status"] == "plan_ready"
    assert "global_stats" in stats


def test_update_task_status_validates_transition(client, auth_headers, _run_id):
    # plan_ready -> policy_check is a valid transition
    r = client.post(
        f"/tasks/{_run_id}/status",
        headers=auth_headers,
        json={"task_id": _run_id, "status": "policy_check"},
    )
    assert r.status_code == 200, r.text

    # policy_check -> planning is NOT a valid transition
    r = client.post(
        f"/tasks/{_run_id}/status",
        headers=auth_headers,
        json={"task_id": _run_id, "status": "planning"},
    )
    assert r.status_code == 400, r.text


def test_add_step_rejects_unknown_tool(client, auth_headers, _run_id):
    r = client.post(
        f"/tasks/{_run_id}/steps",
        headers=auth_headers,
        json={
            "step_id": "SX",
            "description": "bad tool",
            "required_tool": "nuclear_launch",
            "risk_level": 1,
            "requires_approval": False,
        },
    )
    assert r.status_code == 400, r.text


def test_unauthorized_user_cannot_read_run(client, _run_id):
    r = client.post(
        "/auth/login", json={"username": "enduser", "password": "Demo@12345"}
    )
    assert r.status_code == 200, r.text
    other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/tasks/{_run_id}", headers=other_headers)
    assert r.status_code == 404, r.text
