"""
VTR-Agent: Evidence Graph

Provenance tracking system that maps claims to their supporting evidence,
source documents, and verification status.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

# neo4j is optional — falls back to in-memory graph
try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    GraphDatabase = None  # type: ignore

from vtr_agent.core.config import get_settings


class ClaimStatus(str, Enum):
    """Claim verification statuses."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class EvidenceRecord(BaseModel):
    """Record of evidence supporting a claim."""
    evidence_id: str
    source_document_id: str
    chunk_id: str
    text: str
    page: Optional[int]
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClaimRecord(BaseModel):
    """Record of a research claim with provenance."""
    claim_id: str
    text: str
    confidence: float
    evidence_ids: List[str]
    verification_status: ClaimStatus
    derived_from: Optional[str] = None  # ID of claim or calculation that derived this
    created_at: str
    verified_at: Optional[str] = None
    verified_by: Optional[str] = None


class EvidenceGraph:
    """Evidence graph tracking claim-provenance relationships."""
    
    def __init__(self, use_neo4j: bool = False, neo4j_uri: str = "bolt://localhost:7687"):
        self.use_neo4j = use_neo4j
        self.neo4j_uri = neo4j_uri
        self.claims: Dict[str, ClaimRecord] = {}
        self.evidence: Dict[str, EvidenceRecord] = {}
        self.graph_edges: Dict[str, List[str]] = {}  # claim_id -> [evidence_id, ...]
        self._initialized = False
        
        if use_neo4j:
            try:
                self.driver = GraphDatabase.driver(neo4j_uri)
                self._initialize_neo4j()
            except Exception:
                print("Neo4j not available, using in-memory graph")
                use_neo4j = False
    
    def _initialize_neo4j(self) -> None:
        """Initialize Neo4j connection."""
        if not self.use_neo4j:
            return
        try:
            with self.driver.session() as session:
                # Ensure constraints exist
                session.run("""
                    CREATE (c:Claim {claim_id: string})
                    CREATE (e:Evidence {evidence_id: string})
                    MATCH (c)-[r:SUPPORTS]->(e)
                    RETURN count(c), count(e)
                """)
            print("Neo4j evidence graph initialized")
        except Exception as e:
            print(f"Neo4j initialization failed: {e}")
            self.use_neo4j = False
    
    def _get_driver(self):
        """Get Neo4j driver if available."""
        if self.use_neo4j and hasattr(self, 'driver'):
            return self.driver
        return None
    
    def initialize(self) -> None:
        """Initialize the evidence graph."""
        if self._initialized:
            return
        
        # If Neo4j not available, use in-memory graph
        if not self.use_neo4j:
            self._initialized = True
            print("Evidence graph initialized (in-memory mode)")
        else:
            self._initialized = True
            print("Evidence graph initialized (Neo4j mode)")
    
    def add_claim(self, claim: ClaimRecord) -> str:
        """Add a claim to the evidence graph."""
        if not self._initialized:
            self.initialize()
        
        self.claims[claim.claim_id] = claim
        self.graph_edges[claim.claim_id] = claim.evidence_ids or []
        
        # Also store evidence records
        for evidence_id in claim.evidence_ids or []:
            if evidence_id not in self.evidence:
                # Extract evidence ID from format "E1", "E2", etc.
                ev_id = evidence_id.replace("E", "ev_")
                # Try to find existing evidence
                pass
        
        return claim.claim_id
    
    def add_evidence(self, evidence: EvidenceRecord) -> str:
        """Add evidence to the evidence graph."""
        if not self._initialized:
            self.initialize()
        
        self.evidence[evidence.evidence_id] = evidence
        return evidence.evidence_id
    
    def link_claim_evidence(
        self, 
        claim_id: str, 
        evidence_id: str,
        relationship: str = "SUPPORTS",
    ) -> bool:
        """Link a claim to its evidence."""
        if claim_id not in self.claims:
            print(f"Warning: Claim {claim_id} not found")
            return False
        
        if evidence_id not in self.evidence and not evidence_id.startswith("E"):
            print(f"Warning: Evidence {evidence_id} not found")
            return False
        
        # Add to graph edges
        if claim_id in self.graph_edges:
            if evidence_id not in self.graph_edges[claim_id]:
                self.graph_edges[claim_id].append(evidence_id)
        else:
            self.graph_edges[claim_id] = [evidence_id]
        
        # Update claim's evidence_ids
        if claim_id in self.claims:
            if evidence_id not in self.claims[claim_id].evidence_ids:
                self.claims[claim_id].evidence_ids.append(evidence_id)
        
        # Update evidence's claim relationship (Neo4j would handle this)
        # In in-memory mode, just track the link
        
        return True
    
    def update_claim_verification(
        self, 
        claim_id: str, 
        status: ClaimStatus,
        verified_by: Optional[str] = None,
    ) -> Optional[ClaimRecord]:
        """Update claim verification status."""
        if claim_id not in self.claims:
            return None
        
        claim = self.claims[claim_id]
        claim.verification_status = status
        claim.verified_at = __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc
        ).isoformat()
        claim.verified_by = verified_by or "system"
        
        return claim
    
    def verify_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Verify a claim against its evidence."""
        if claim_id not in self.claims:
            return None
        
        claim = self.claims[claim_id]
        evidence_ids = claim.evidence_ids or []
        
        # If no evidence, mark as unverified
        if not evidence_ids:
            return self.update_claim_verification(claim_id, ClaimStatus.UNVERIFIED)
        
        # Gather evidence support/contradiction
        support_count = 0
        contradiction_count = 0
        total_verified = 0
        
        for evidence_id in evidence_ids:
            evidence = self.evidence.get(evidence_id)
            if evidence is None:
                continue
            
            total_verified += 1
            
            # Check if evidence supports or contradicts claim
            # In production, would use NLP/NLI to determine this
            # For now, use stored metadata
            if evidence.metadata.get("supports_claim", False):
                support_count += 1
            if evidence.metadata.get("contradicts_claim", False):
                contradiction_count += 1
        
        # Determine verification status
        if total_verified == 0:
            status = ClaimStatus.UNVERIFIED
        elif support_count > 0 and contradiction_count == 0:
            status = ClaimStatus.SUPPORTED
        elif support_count > 0 and contradiction_count > 0:
            status = ClaimStatus.PARTIALLY_SUPPORTED
        elif contradiction_count > 0 and support_count == 0:
            status = ClaimStatus.CONTRADICTED
        else:
            status = ClaimStatus.UNSUPPORTED
        
        return self.update_claim_verification(claim_id, status)
    
    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Get a claim by ID."""
        return self.claims.get(claim_id)
    
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """Get evidence by ID."""
        return self.evidence.get(evidence_id)
    
    def get_claim_by_evidence(self, evidence_id: str) -> List[ClaimRecord]:
        """Get all claims linked to a piece of evidence."""
        claims = []
        for claim_id, claim in self.claims.items():
            if evidence_id in claim.evidence_ids:
                claims.append(claim)
        return claims
    
    def get_unsupported_claims(self) -> List[ClaimRecord]:
        """Get all claims that are unsupported or contradicted."""
        unsupported = []
        for claim in self.claims.values():
            if claim.verification_status in (
                ClaimStatus.UNSUPPORTED,
                ClaimStatus.CONTRADICTED,
                ClaimStatus.PARTIALLY_SUPPORTED,
            ):
                unsupported.append(claim)
        return unsupported
    
    def get_verified_claims(self) -> List[ClaimRecord]:
        """Get all verified claims."""
        verified = []
        for claim in self.claims.values():
            if claim.verification_status == ClaimStatus.SUPPORTED:
                verified.append(claim)
        return verified
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get evidence graph statistics."""
        total_claims = len(self.claims)
        total_evidence = len(self.evidence)
        
        status_counts = {}
        for status in ClaimStatus:
            status_counts[status.value] = sum(
                1 for c in self.claims.values() 
                if c.verification_status == status
            )
        
        supported = status_counts.get(ClaimStatus.SUPPORTED.value, 0)
        unsupported = sum(
            status_counts.get(s.value, 0) 
            for s in [ClaimStatus.UNSUPPORTED, ClaimStatus.CONTRADICTED, ClaimStatus.PARTIALLY_SUPPORTED]
        )
        
        return {
            "total_claims": total_claims,
            "total_evidence": total_evidence,
            "status_distribution": status_counts,
            "support_rate": round(supported / total_claims * 100, 2) if total_claims > 0 else 0,
            "unsupported_rate": round(unsupported / total_claims * 100, 2) if total_claims > 0 else 0,
        }
    
    def export_for_export(self) -> Dict[str, Any]:
        """Export graph data for serialization."""
        return {
            "claims": {
                claim_id: {
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "confidence": claim.confidence,
                    "evidence_ids": claim.evidence_ids,
                    "verification_status": claim.verification_status,
                }
                for claim_id, claim in self.claims.items()
            },
            "evidence": {
                evidence_id: {
                    "evidence_id": evidence.evidence_id,
                    "source_document_id": evidence.source_document_id,
                    "text": evidence.text,
                    "confidence": evidence.confidence,
                }
                for evidence_id, evidence in self.evidence.items()
            },
            "edges": self.graph_edges,
        }


# Global evidence graph instance
evidence_graph = EvidenceGraph()


# Convenience functions
def add_claim(claim: ClaimRecord) -> str:
    """Add a claim to the evidence graph."""
    return evidence_graph.add_claim(claim)


def add_evidence(evidence: EvidenceRecord) -> str:
    """Add evidence to the evidence graph."""
    return evidence_graph.add_evidence(evidence)


def link_claim_evidence(
    claim_id: str, 
    evidence_id: str,
    relationship: str = "SUPPORTS",
) -> bool:
    """Link a claim to its evidence."""
    return evidence_graph.link_claim_evidence(claim_id, evidence_id, relationship)


def verify_claim(claim_id: str) -> Optional[ClaimRecord]:
    """Verify a claim against its evidence."""
    return evidence_graph.verify_claim(claim_id)


def get_claim(claim_id: str) -> Optional[ClaimRecord]:
    """Get a claim by ID."""
    return evidence_graph.get_claim(claim_id)


def get_unsupported_claims() -> List[ClaimRecord]:
    """Get all unsupported or contradicted claims."""
    return evidence_graph.unsupported_claims()


def get_verified_claims() -> List[ClaimRecord]:
    """Get all verified (supported) claims."""
    return evidence_graph.verified_claims()


def get_graph_stats() -> Dict[str, Any]:
    """Get evidence graph statistics."""
    return evidence_graph.get_graph_statistics()


def export_graph() -> Dict[str, Any]:
    """Export evidence graph data."""
    return evidence_graph.export_for_export()