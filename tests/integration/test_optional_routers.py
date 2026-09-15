"""Integration tests for the newly-mounted optional routers.

These exercise the evidence graph, approval gate, and retrieval endpoints
through the real FastAPI app (mounted at both root and /api/v1).
"""
from __future__ import annotations

import uuid

import pytest


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _login(client, username: str = "admin", password: str = "Demo@12345"):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Evidence graph ----------------------------------------------------------


def test_evidence_lifecycle(client, auth_headers):
    r = client.post("/evidence/initialize", headers=auth_headers)
    assert r.status_code == 200, r.text

    ev_id = _unique("EVD")
    claim_id = _unique("CLAIM")
    now = "2026-09-15T00:00:00Z"

    r = client.post("/evidence/evidence", headers=auth_headers, json={
        "evidence_id": ev_id,
        "source_document_id": "DOC-1",
        "chunk_id": "CHUNK-1",
        "text": "Transformers rely entirely on self-attention mechanisms.",
        "page": 1,
        "metadata": {"supports_claim": True},
        "confidence": 0.95,
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "added"

    r = client.post("/evidence/claims", headers=auth_headers, json={
        "claim_id": claim_id,
        "text": "Self-attention is the core mechanism of transformers.",
        "confidence": 0.9,
        "evidence_ids": [ev_id],
        "verification_status": "UNVERIFIED",
        "created_at": now,
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "added"

    r = client.post(f"/evidence/claims/{claim_id}/verify", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "SUPPORTED"

    r = client.get(f"/evidence/claims/{claim_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["claim_id"] == claim_id

    r = client.get("/evidence/graph/stats", headers=auth_headers)
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["total_claims"] >= 1

    r = client.get("/evidence/graph/export", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_evidence_mounted_under_api_v1(client, auth_headers):
    # The frontend contract expects the /api/v1 prefix.
    r = client.post("/api/v1/evidence/initialize", headers=auth_headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/v1/evidence/graph/stats", headers=auth_headers)
    assert r.status_code == 200, r.text


# --- Approval gate -----------------------------------------------------------


def test_approval_request_approve_flow(client, auth_headers):
    # end_user requesting a level-2 tool must go through the approval gate
    enduser_headers = _login(client, "enduser")

    r = client.post("/approval/request", headers=enduser_headers, json={
        "tool_id": "python_sandbox",
        "step_id": "S1",
        "arguments": {"code": "print(1)"},
        "risk_level": 2,
        "requires_approval": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("pending", "automatic")

    if body["status"] == "pending":
        approval_id = body["approval_id"]

        r = client.get("/approval/pending", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert any(a["approval_id"] == approval_id for a in r.json())

        r = client.post(f"/approval/{approval_id}/approve",
                        headers=auth_headers, params={"reason": "looks safe"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"


# --- Retrieval ---------------------------------------------------------------


def test_retrieval_endpoints(client, auth_headers):
    r = client.post("/retrieval/initialize", headers=auth_headers)
    assert r.status_code == 200, r.text

    projects = client.get("/projects", headers=auth_headers).json()
    assert projects, "demo project should exist"
    project_id = projects[0]["project_id"]

    r = client.post("/retrieval/query", headers=auth_headers, json={
        "project_id": project_id,
        "query": "transformer self-attention",
        "top_k": 5,
    })
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    r = client.get("/retrieval/documents/does-not-exist/info", headers=auth_headers)
    assert r.status_code == 404


# --- Tool registry -----------------------------------------------------------


def test_tools_registry_endpoints(client, auth_headers):
    # GET /tools is served by the foundation router (flat dict keyed by tool_id)
    r = client.get("/tools", headers=auth_headers)
    assert r.status_code == 200, r.text
    tools = r.json()
    assert "python_sandbox" in tools
    assert tools["python_sandbox"]["risk_level"] == 2

    r = client.get("/tools/allowed", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["user_role"] == "admin"
    assert "python_sandbox" in r.json()["allowed_tools"]

    r = client.get("/tools/risk-distribution", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "distribution" in r.json()

    r = client.get("/tools/search?capability=math", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert any(t["tool_id"] == "python_sandbox" for t in r.json())

    r = client.get("/tools/calculator", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["tool_id"] == "calculator"

    r = client.get("/tools/does-not-exist", headers=auth_headers)
    assert r.status_code == 404

    # Frontend contract: also reachable under /api/v1
    r = client.get("/api/v1/tools/allowed", headers=auth_headers)
    assert r.status_code == 200, r.text


# --- Sandbox execution -------------------------------------------------------


def test_sandbox_execute_allowed_for_admin(client, auth_headers):
    r = client.post("/sandbox/execute", headers=auth_headers,
                    json={"code": "print(2 + 2)"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert "4" in body["stdout"]


def test_sandbox_execute_denied_for_end_user(client):
    headers = _login(client, "enduser")
    r = client.post("/sandbox/execute", headers=headers, json={"code": "print(1)"})
    assert r.status_code == 403, r.text


def test_sandbox_blocks_unsafe_code(client, auth_headers):
    r = client.post("/sandbox/execute", headers=auth_headers,
                    json={"code": "import subprocess\nsubprocess.run(['ls'])"})
    assert r.status_code == 200, r.text
    assert r.json()["safety_violation"]


# --- End-to-end run orchestration -------------------------------------------


def _demo_project_id(client, headers):
    projects = client.get("/projects", headers=headers).json()
    assert projects, "demo project should exist"
    return projects[0]["project_id"]


def _upload_doc(client, headers, project_id, text):
    r = client.post(
        "/documents/upload", headers=headers,
        files={"file": ("evidence.txt", text.encode(), "text/plain")},
        data={"project_id": str(project_id), "source": "test", "licence": "demo",
              "category": "research"},
    )
    assert r.status_code in (200, 201), r.text


def test_run_lifecycle_completes_for_admin(client, auth_headers):
    project_id = _demo_project_id(client, auth_headers)
    _upload_doc(client, auth_headers, project_id,
                "Transformer architectures rely on self-attention to model long-range "
                "dependencies between tokens in a sequence. Empirical results show they "
                "outperform recurrent networks on many downstream tasks.")

    r = client.post("/tasks", headers=auth_headers, json={
        "name": "Analysis run",
        "description": "dataset analysis",
        "instructions": "Analyse the dataset statistics using python code",
        "project_id": project_id,
        "user_id": 1,
        "priority": "medium",
        "tags": ["test"],
    })
    assert r.status_code in (200, 201), r.text
    run_id = r.json()["run_id"]

    r = client.post(f"/tasks/{run_id}/start", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert r.json()["summary_report"]

    r = client.get(f"/tasks/{run_id}/trace", headers=auth_headers)
    assert r.status_code == 200, r.text
    trace = r.json()
    assert all(s["status"] == "completed" for s in trace["steps"])
    assert trace["evidence"], "retriever should have produced evidence"
    assert trace["claims"], "evidence_tool should have created claims"
    assert any(c["verification_status"] == "SUPPORTED" for c in trace["claims"])


def test_run_lifecycle_approval_loop_for_researcher(client, auth_headers, researcher_headers):
    # Researchers see only projects they are members of; create one to own.
    r = client.post("/projects", headers=researcher_headers, json={
        "name": "Researcher Project",
        "domain": "AI Research",
        "description": "researcher-owned project",
    })
    assert r.status_code == 201, r.text
    project_id = r.json()["project_id"]

    r = client.post("/tasks", headers=researcher_headers, json={
        "name": "Researcher analysis",
        "description": "needs approval",
        "instructions": "Run python analysis on the dataset statistics",
        "project_id": project_id,
        "user_id": 1,
        "priority": "medium",
        "tags": ["test"],
    })
    assert r.status_code in (200, 201), r.text
    run_id = r.json()["run_id"]

    # Researcher must pause at the approval gate (python_sandbox = LEVEL_2)
    r = client.post(f"/tasks/{run_id}/start", headers=researcher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "waiting_approval"

    r = client.get(f"/tasks/{run_id}/trace", headers=researcher_headers)
    pending = [a for a in r.json()["approvals"] if a["status"] == "pending"]
    assert pending, "a persisted approval request should exist"
    approval_id = pending[0]["approval_id"]

    # Only admin/reviewer can decide
    r = client.post(f"/tasks/{run_id}/approvals/{approval_id}/decide",
                    headers=researcher_headers, params={"decision": "approved"})
    assert r.status_code == 403

    r = client.post(f"/tasks/{run_id}/approvals/{approval_id}/decide",
                    headers=auth_headers, params={"decision": "approved", "reason": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # Resuming completes the run
    r = client.post(f"/tasks/{run_id}/start", headers=researcher_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
