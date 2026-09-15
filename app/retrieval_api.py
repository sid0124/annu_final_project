"""
VTR-Agent: Retrieval API Endpoints

RAG retrieval API endpoints for document search and evidence management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    RetrievalQuery, RetrievalResult, DocumentResponse,
    EvidenceRecord, ClaimRecord, GraphStatistics
)
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import Document, Project
from vtr_agent.retrieval import init_retrieval, retrieve, ingest, get_retrieved_chunks, get_document_info
from vtr_agent.evidence import (
    add_claim, add_evidence, link_claim_evidence, verify_claim,
    get_claim, get_unsupported_claims, get_verified_claims,
    get_graph_stats, export_graph
)
from vtr_agent.api.auth import get_current_user
from vtr_agent.core.database import models as m

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/initialize", response_model=Dict)
def retrieval_initialize(
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Initialize the retrieval system."""
    init_retrieval()
    return {"status": "initialized", "message": "Retrieval system ready"}


@router.post("/ingest", response_model=Dict)
def ingest_document(
    document: Document,
    project_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Ingest a document into the retrieval system."""
    # Verify project exists
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Ingest document
    result = ingest(document, project, chunking_strategy="fixed_size")
    
    return {
        "status": "success",
        "chunks": result.get("chunks", 0),
        "document_id": result.get("document_id"),
    }


@router.post("/query", response_model=List[RetrievalResult])
def retrieve_documents(
    query: RetrievalQuery,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Retrieve documents matching a query."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    results = retrieve(
        query=query.query,
        project_id=query.project_id,
        top_k=query.top_k,
        filters=query.filters,
    )
    
    return results


@router.get("/documents/{document_id}/chunks", response_model=List[Dict])
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get all chunks for a document."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    chunks = get_retrieved_chunks(document_id)
    return chunks


@router.get("/documents/{document_id}/info", response_model=Dict)
def get_document_info(
    document_id: str,
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    """Get document information."""
    # Check permissions
    if not user.is_admin and user.role not in ("researcher", "expert", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    info = get_document_info(document_id)
    if not info:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return info


@router.post("/evidence", response_model=EvidenceRecord)
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


@router.post("/claims", response_model=ClaimRecord)
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


@router.get("/graph/stats", response_model=GraphStatistics)
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