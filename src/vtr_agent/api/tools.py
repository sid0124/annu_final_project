"""Tools API: read-only views over the tool registry.

Backed by ``app.core.tool_registry`` (the same in-memory registry served by the
task router's convenience endpoints), exposed under the ``/tools`` prefix the
frontend contract expects.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import get_db
from vtr_agent.core.tool_registry import (
    get_allowed_tools,
    get_tool,
    get_tool_risk_distribution,
    search_tools,
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _tool_dict(tool: Any) -> Dict[str, Any]:
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "version": tool.version,
        "risk_level": tool.risk_level.value,
        "requires_approval": tool.requires_approval,
        "estimated_latency": tool.estimated_latency,
        "supports": tool.supports,
    }


@router.get("/allowed", response_model=Dict)
def list_allowed_tools(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """List tools the current user's role may use (directly or via approval)."""
    allowed = get_allowed_tools(user.role)
    return {
        "user_role": user.role,
        "allowed_tools": {tid: _tool_dict(t) for tid, t in allowed.items()},
    }


@router.get("/risk-distribution", response_model=Dict)
def risk_distribution(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Count of registered tools at each risk level."""
    return {"distribution": {str(k): v for k, v in get_tool_risk_distribution().items()}}


@router.get("/search", response_model=List[Dict])
def search_by_capability(
    capability: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Find tools that declare a given capability."""
    return [_tool_dict(t) for t in search_tools(capability)]


@router.get("/{tool_id}", response_model=Dict)
def get_tool_detail(
    tool_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get metadata for a single tool."""
    tool = get_tool(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return _tool_dict(tool)
