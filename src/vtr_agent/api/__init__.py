"""
VTR-Agent: API Router Initialization

Central API router that includes all sub-routers.
Only implemented routers are imported directly; Phase 2+ routers are guarded
with try/except so the package remains importable even before they exist.
"""
from __future__ import annotations

import importlib

from fastapi import APIRouter

from vtr_agent.api import auth as auth_api
from vtr_agent.api import tasks as tasks_api
from vtr_agent.api import audit as audit_api

router = APIRouter()

# Always-present routers
router.include_router(auth_api.router)
router.include_router(tasks_api.router)
router.include_router(audit_api.router)

# Phase 2+ routers — guarded until implemented
_OPTIONAL_ROUTERS = [
    "vtr_agent.api.projects",
    "vtr_agent.api.tools",
    "vtr_agent.api.retrieval",
    "vtr_agent.api.evidence",
    "vtr_agent.api.approval",
    "vtr_agent.api.sandbox",
    "vtr_agent.api.safety",
    "vtr_agent.api.verification",
    "vtr_agent.api.observability",
    "vtr_agent.api.chat",
    "vtr_agent.api.datasets",
    "vtr_agent.api.documents",
    "vtr_agent.api.mlops",
    "vtr_agent.api.ops",
]

for _mod_path in _OPTIONAL_ROUTERS:
    try:
        _mod = importlib.import_module(_mod_path)
        router.include_router(_mod.router)
    except (ImportError, ModuleNotFoundError):
        pass  # Not yet implemented
