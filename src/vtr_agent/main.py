"""
VTR-Agent: Core Application Entry Point

This module provides the FastAPI application entrypoint for the VTR-Agent system,
including lifespan hooks, middleware configuration, and API route registrations.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vtr_agent.core.config import settings
from vtr_agent.core.database.session import init_db
from vtr_agent.core.logging_conf import setup_logging
from vtr_agent.core.utils import new_id

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    init_db()
    yield


app = FastAPI(
    title="VTR-Agent API",
    description=(
        "VTR-Agent — Verifiable Tool-Using Research Agent with "
        "Planning, Sandboxing and Safety Policies. "
        "Enables policy-controlled tool use with evidence verification "
        "for safe, traceable research assistance."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Core API Routers --------------------------------------------------------
# Only import routers that are fully implemented; guard future ones.
from vtr_agent.api import auth as auth_api
from vtr_agent.api import tasks as tasks_api
from vtr_agent.api import audit as audit_api
from vtr_agent.api import foundation as foundation_api

app.include_router(auth_api.router)
app.include_router(tasks_api.router)
app.include_router(audit_api.router)
app.include_router(foundation_api.router)

app.include_router(auth_api.router, prefix="/api/v1")
app.include_router(tasks_api.router, prefix="/api/v1")
app.include_router(audit_api.router, prefix="/api/v1")
app.include_router(foundation_api.router, prefix="/api/v1")

# Phase 2+ routers — imported lazily so the app starts even when modules are absent
_OPTIONAL_ROUTERS = [
    ("vtr_agent.api.projects", "projects"),
    ("vtr_agent.api.tools", "tools"),
    ("vtr_agent.api.retrieval", "retrieval"),
    ("vtr_agent.api.evidence", "evidence"),
    ("vtr_agent.api.approval", "approval"),
    ("vtr_agent.api.sandbox", "sandbox"),
    ("vtr_agent.api.safety", "safety"),
    ("vtr_agent.api.verification", "verification"),
    ("vtr_agent.api.observability", "observability"),
]

import importlib as _importlib
for _mod_path, _tag in _OPTIONAL_ROUTERS:
    try:
        _mod = _importlib.import_module(_mod_path)
        app.include_router(_mod.router)
    except (ImportError, ModuleNotFoundError):
        pass  # Module not yet implemented — skip until built in later phase


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Safe error messages never leak internals or credentials."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "message": str(exc.detail),
            "request_id": request.headers.get("x-request-id", new_id("REQ")),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Generic 500 handler with request_id for correlation with logs."""
    request_id = request.headers.get("x-request-id", new_id("REQ"))
    import logging

    logging.getLogger("vtr_agent").exception(
        "Unhandled error", extra={"request_id": request_id}
    )
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "message": "An internal error occurred.",
            "request_id": request_id,
        },
    )


@app.get("/", tags=["meta"])
def root():
    """API metadata endpoint."""
    return {
        "app": "VTR-Agent",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "demo_mode": settings.DEMO_MODE,
    }


@app.get("/health", tags=["health"])
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": new_id("REQ"),
        "version": settings.APP_VERSION,
    }
