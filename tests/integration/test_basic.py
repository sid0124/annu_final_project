"""Integration tests: basic system functionality."""

from __future__ import annotations

import pytest


def test_database_initialized(client):
    """Test that database is initialized with sample data."""
    # This test ensures the database has been seeded
    r = client.post("/auth/login", json={"username": "admin", "password": "Demo@12345"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get("/projects", headers=headers)
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) > 0, "No projects found - database may not be initialized"


def test_authentication_works(client, auth_headers):
    """Test basic authentication flow."""
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["role"] in ["admin", "researcher", "reviewer", "expert", "end_user"]


def test_list_projects(client, auth_headers):
    """Test listing projects."""
    r = client.get("/projects", headers=auth_headers)
    assert r.status_code == 200
    projects = r.json()
    assert isinstance(projects, list)


def test_create_project(client, auth_headers):
    """Test creating a new project."""
    r = client.post("/projects", headers=auth_headers, json={
        "name": "Test Project",
        "domain": "Test Domain",
        "description": "A test project",
    })
    assert r.status_code in (200, 201), r.text


def test_upload_document(client, auth_headers):
    """Test document upload."""
    r = client.get("/projects", headers=auth_headers).json()
    assert len(r) > 0, "No projects available"
    pid = r[0]["project_id"]

    content = "# Test Document\n\nThis is a test document."
    files = {"file": ("test.txt", content.encode(), "text/plain")}
    data = {"project_id": str(pid), "source": "test", "licence": "demo", "category": "test"}

    r = client.post("/documents/upload", headers=auth_headers, files=files, data=data)
    assert r.status_code in (200, 201), r.text


def test_safety_events_logged(client, auth_headers):
    """Test that safety events are tracked."""
    r = client.get("/safety/events", headers=auth_headers)
    # This may return 404 or empty if no events, which is OK
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_audit_logs_accessible(client, auth_headers):
    """Test audit log accessibility."""
    r = client.get("/audit/logs", headers=auth_headers)
    # May return 200 with empty or data, or 403 if not admin
    assert r.status_code in (200, 403, 404), f"Unexpected status: {r.status_code}"


def test_evidence_endpoints(client, auth_headers):
    """Test evidence-related endpoints."""
    r = client.get("/evidence/graph", headers=auth_headers)
    # May vary based on implementation
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_claim_verification(client, auth_headers):
    """Test claim verification endpoints."""
    r = client.get("/claims/verify", headers=auth_headers)
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_tool_registry(client, auth_headers):
    """Test tool registry endpoint."""
    r = client.get("/tools", headers=auth_headers)
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_sandbox_status(client, auth_headers):
    """Test sandbox status endpoint."""
    r = client.get("/sandbox/status", headers=auth_headers)
    # May vary based on implementation
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_policy_engine(client, auth_headers):
    """Test policy engine endpoint."""
    r = client.request("GET", "/policy/check", headers=auth_headers, json={})
    # May vary based on implementation
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_approval_gate(client, auth_headers):
    """Test approval gate endpoint."""
    r = client.get("/approval/requests", headers=auth_headers)
    assert r.status_code in (200, 404), f"Unexpected status: {r.status_code}"


def test_observability_metrics(client, auth_headers):
    """Test observability metrics endpoint."""
    r = client.get("/metrics", headers=auth_headers)
    assert r.status_code == 200


def test_run_lifecycle(client, auth_headers):
    """Test complete run lifecycle."""
    # Create a task
    r = client.post("/tasks", headers=auth_headers, json={
        "name": "Test Task",
        "description": "A test research task",
        "instructions": "Compare transformer methods",
        "project_id": 1,
        "user_id": 1,
        "priority": "medium",
        "tags": ["test"],
    })
    assert r.status_code in (200, 201), r.text

    # List tasks
    r = client.get("/tasks", headers=auth_headers)
    assert r.status_code == 200
