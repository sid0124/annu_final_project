"""Foundation API routes for Phase 1.

These endpoints keep the application usable while the fuller run orchestrator
and module-specific APIs are built out.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from vtr_agent.auth.security import get_current_user
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import get_db
from vtr_agent.core.tool_registry import get_all_tools
from vtr_agent.utils import new_id, sanitize_filename, sha256_text

router = APIRouter(tags=["foundation"])


class ProjectCreateRequest(BaseModel):
    """Minimal project creation request accepted by the current UI/tests."""

    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(default="General", max_length=120)
    description: str = Field(default="", max_length=1000)
    expected_users: str = Field(default="", max_length=500)
    success_thresholds: dict[str, float] = Field(default_factory=dict)
    scope_exclusions: str = ""
    risks: str = ""


def _project_response(project: m.Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "project_id": project.project_id,
        "name": project.name,
        "domain": project.domain,
        "description": project.description,
        "expected_users": project.expected_users,
        "status": project.status,
        "success_thresholds": project.success_thresholds,
        "scope_exclusions": project.scope_exclusions,
        "risks": project.risks,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _ensure_demo_project(db: Session, user: m.User) -> m.Project:
    project = db.query(m.Project).order_by(m.Project.id.asc()).first()
    if project is not None:
        return project

    project = m.Project(
        project_id=new_id("PRJ"),
        name="Demo Research Project",
        domain="AI Research",
        description="Default project for local development and tests.",
        expected_users="Postgraduate researchers and reviewers",
        status="draft",
        owner_id=user.id,
        success_thresholds={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """List projects visible to the current user."""
    if user.is_admin:
        _ensure_demo_project(db, user)
        projects = db.query(m.Project).order_by(m.Project.id.asc()).all()
    else:
        memberships = (
            db.query(m.ProjectMembership)
            .filter(m.ProjectMembership.user_id == user.id)
            .all()
        )
        project_ids = [membership.project_id for membership in memberships]
        projects = (
            db.query(m.Project)
            .filter(m.Project.id.in_(project_ids))
            .order_by(m.Project.id.asc())
            .all()
            if project_ids
            else []
        )
    return [_project_response(project) for project in projects]


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Create a project owned by the current user."""
    if not user.is_admin and not user.is_researcher:
        raise HTTPException(status_code=403, detail="User cannot create projects")

    project = m.Project(
        project_id=new_id("PRJ"),
        name=body.name,
        domain=body.domain,
        description=body.description,
        expected_users=body.expected_users,
        status="draft",
        success_thresholds=body.success_thresholds,
        scope_exclusions=body.scope_exclusions,
        risks=body.risks,
        owner_id=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_response(project)


@router.post("/documents/upload", status_code=201)
async def upload_document(
    project_id: str = Form(...),
    source: str = Form(default=""),
    licence: str = Form(default="unknown"),
    category: str = Form(default="general"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Register an uploaded document and store its text preview in the DB."""
    if not user.is_admin and not user.is_researcher:
        raise HTTPException(status_code=403, detail="User cannot upload documents")

    project = (
        db.query(m.Project)
        .filter((m.Project.project_id == project_id) | (m.Project.id == _as_int(project_id)))
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    filename = sanitize_filename(file.filename or "uploaded.txt")
    document = m.Document(
        document_id=new_id("DOC"),
        project_id=project.id,
        filename=filename,
        file_type=filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt",
        size_bytes=len(content),
        sha256=sha256_text(text),
        stored_path="",
        source=source,
        licence=licence,
        category=category,
        uploaded_by=user.id,
        status=m.DOC_STATUS_APPROVED,
        word_count=len(text.split()),
        text_preview=text[:500],
        cleaned_text=text,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {
        "document_id": document.document_id,
        "project_id": project.project_id,
        "filename": document.filename,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "status": document.status,
    }


@router.get("/tools")
def list_tools(user: m.User = Depends(get_current_user)):
    """List registered tool metadata."""
    tools = get_all_tools()
    return {
        tool_id: {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
            "risk_level": int(tool.risk_level),
            "requires_approval": tool.requires_approval,
            "supports": tool.supports,
        }
        for tool_id, tool in tools.items()
    }


@router.get("/metrics")
def metrics():
    """Lightweight health metrics endpoint."""
    return {
        "status": "ok",
        "metrics": {
            "task_success_rate": 0.0,
            "unsupported_claim_rate": 0.0,
            "unsafe_action_block_rate": 0.0,
        },
    }


@router.post("/training/start")
def start_training(
    body: dict[str, Any],
    user: m.User = Depends(get_current_user),
):
    """Admin-only placeholder for protected training operations."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Training requires admin role")
    return {"ok": True, "message": "Training start accepted", "request": body}


@router.get("/safety/events")
def safety_events(user: m.User = Depends(get_current_user)):
    return []


@router.get("/evidence/graph")
def evidence_graph(user: m.User = Depends(get_current_user)):
    return {"nodes": [], "edges": []}


@router.get("/claims/verify")
def verify_claims(user: m.User = Depends(get_current_user)):
    return {"verified": 0, "unsupported": 0, "claims": []}


@router.get("/sandbox/status")
def sandbox_status(user: m.User = Depends(get_current_user)):
    return {"status": "available", "mode": "phase1-placeholder"}


@router.get("/approval/requests")
def approval_requests(user: m.User = Depends(get_current_user)):
    return []


def _as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
