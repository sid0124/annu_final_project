"""
VTR-Agent: Evidence API Endpoints

Evidence graph and claim verification API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    ClaimRecord, ClaimStatus, GraphStatistics
)
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import Document, Project
from vtr_agent.evidence import (
    EvidenceRecord,
    add_claim, add_evidence, link_claim_evidence, verify_claim,
    get_claim, get_unsupported_claims, get_verified_claims,
    get_graph_stats, export_graph, evidence_graph
)
from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database import models as m

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("/initialize", response_model=Dict)
def evidence_initialize(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Initialize the evidence graph."""
    evidence_graph.initialize()
    return {"status": "initialized", "message": "Evidence graph ready"}


@router.post("/evidence", response_model=Dict)
def add_evidence_endpoint(
    evidence: EvidenceRecord,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Add evidence to the evidence graph."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    evidence_id = add_evidence(evidence)
    return {"evidence_id": evidence_id, "status": "added"}


@router.post("/claims", response_model=Dict)
def add_claim_endpoint(
    claim: ClaimRecord,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Add a claim to the evidence graph."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    claim_id = add_claim(claim)
    return {"claim_id": claim_id, "status": "added"}


@router.post("/claims/{claim_id}/verify", response_model=ClaimRecord)
def verify_claim_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Verify a claim against its evidence."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    claim = verify_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    return claim


@router.get("/claims/{claim_id}", response_model=ClaimRecord)
def get_claim_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get a claim by ID."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    claim = get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    return claim


@router.get("/claims/unsupported", response_model=List[ClaimRecord])
def get_unsupported_claims_endpoint(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get all unsupported or contradicted claims."""
    # Check permissions - only admin can view all
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    claims = get_unsupported_claims()
    return claims


@router.get("/claims/verified", response_model=List[ClaimRecord])
def get_verified_claims_endpoint(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get all verified claims."""
    claims = get_verified_claims()
    return claims


@router.get("/graph/stats", response_model=Dict)
def get_graph_statistics(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get evidence graph statistics."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    stats = get_graph_stats()
    return stats


@router.get("/graph/export", response_model=Dict)
def export_graph_endpoint(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Export evidence graph data."""
    # Check permissions - only admin
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    graph_data = export_graph()
    return {"graph_data": graph_data}


@router.post("/claims/{claim_id}/link-evidence", response_model=Dict)
def link_claim_evidence_endpoint(
    claim_id: str,
    evidence_id: str,
    relationship: str = "SUPPORTS",
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Link a claim to its evidence."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    success = link_claim_evidence(claim_id, evidence_id, relationship)
    if not success:
        raise HTTPException(status_code=404, detail="Claim or evidence not found")
    
    return {"status": "linked", "claim_id": claim_id, "evidence_id": evidence_id, "relationship": relationship}