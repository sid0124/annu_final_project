"""
VTR-Agent: Schemas

Pydantic request/response models for API validation.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator
from pydantic.types import SecretStr

from vtr_agent.utils import RiskLevel
from vtr_agent.evidence import ClaimStatus, ClaimRecord  # canonical definitions

# Role enums
class Role(str, Enum):
    """User roles."""

    ADMIN = "admin"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"
    EXPERT = "domain_expert"
    END_USER = "end_user"

    def __str__(self) -> str:
        return self.value


class Status(str, Enum):
    """Project statuses."""

    DRAFT = "draft"
    CORPUS_COLLECTION = "corpus_collection"
    DATA_REVIEW = "data_review"
    DATASET_READY = "dataset_ready"
    TRAINING = "training"
    EVALUATION = "evaluation"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value


# Base models
class TimestampModel(BaseModel):
    """Base model with timestamps."""

    created_at: str
    updated_at: str


class UserSummary(BaseModel):
    """User summary for API responses."""

    user_id: str
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    is_demo: bool


# Authentication schemas
class LoginRequest(BaseModel):
    """Login request model."""

    username: str = Field(..., description="Username or email")
    password: SecretStr = Field(..., description="User password")

    @validator("username")
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Username cannot be empty")
        return v.strip()

    @validator("password")
    def validate_password(cls, v: SecretStr) -> SecretStr:
        """Validate password format."""
        if not v or len(str(v)) == 0:
            raise ValueError("Password cannot be empty")
        return v


class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenPayload(BaseModel):
    """Token payload model."""

    sub: str
    role: Role
    iat: int
    exp: int


# User schemas
class UserCreate(BaseModel):
    """User creation model."""

    username: str = Field(..., min_length=3, max_length=80)
    email: str = Field(..., min_length=5, max_length=255)
    full_name: str = Field(..., max_length=200)
    password: SecretStr = Field(..., min_length=8)
    role: Role = Role.END_USER
    is_active: bool = True
    is_demo: bool = False

    @validator("email")
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @validator("password")
    def validate_password(cls, v: SecretStr) -> SecretStr:
        """Validate password strength."""
        password = str(v)
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseModel):
    """User update model."""

    username: Optional[str] = Field(None, min_length=3, max_length=80)
    email: Optional[str] = Field(None, min_length=5, max_length=255)
    full_name: Optional[str] = Field(None, max_length=200)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


# Project schemas
class ProjectCreate(BaseModel):
    """Project creation model."""

    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., max_length=120)
    description: str = Field(..., max_length=1000)
    expected_users: str = Field(..., max_length=500)
    success_thresholds: Dict[str, float] = Field(default={})
    scope_exclusions: str = Field(default="")
    risks: str = Field(default="")


class ProjectPatch(BaseModel):
    """Project patch model (partial update)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    domain: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    expected_users: Optional[str] = Field(None, max_length=500)
    success_thresholds: Optional[Dict[str, float]] = None
    scope_exclusions: Optional[str] = Field(None, max_length=500)
    risks: Optional[str] = Field(None, max_length=500)
    status: Optional[Status] = None


class ProjectResponse(BaseModel):
    """Project response model."""

    project_id: str
    name: str
    domain: str
    description: str
    expected_users: str
    status: Status
    success_thresholds: Dict[str, float]
    scope_exclusions: str
    risks: str
    owner_id: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProjectMembershipCreate(BaseModel):
    """Project membership creation model."""

    user_id: str = Field(..., description="User ID to add")
    role_in_project: str = Field(default="member", max_length=40)


class ProjectMembershipResponse(BaseModel):
    """Project membership response model."""

    project_id: int
    user_id: int
    username: str
    role: str
    role_in_project: str


# Document schemas
class DocumentCreate(BaseModel):
    """Document creation model."""

    project_id: str
    filename: str = Field(..., max_length=255)
    file_type: str = Field(default="txt", max_length=16)
    metadata: Dict[str, Any] = Field(default={})


class DocumentResponse(BaseModel):
    """Document response model."""

    document_id: str
    project_id: str
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DocumentProcessRequest(BaseModel):
    """Document processing request model."""

    document_id: str
    processing_options: Dict[str, Any] = Field(default={})


class DocumentProcessResponse(BaseModel):
    """Document processing response model."""

    document_id: str
    chunks: int
    processing_time: float
    status: str


# Tool schemas
class ToolMetadata(BaseModel):
    """Tool metadata model."""

    tool_id: str
    name: str
    description: str
    version: str
    risk_level: int
    permissions: List[str]
    requires_approval: bool
    network_access: bool
    filesystem_access: str
    schema_: Dict[str, Any] = Field(default_factory=dict, alias="schema")

    class Config:
        populate_by_name = True


class ToolExecutionRequest(BaseModel):
    """Tool execution request model."""

    tool_id: str
    arguments: Dict[str, Any] = Field(default={})
    sandbox_config: Optional[Dict[str, Any]] = None


class ToolExecutionResponse(BaseModel):
    """Tool execution response model."""

    execution_id: str
    tool_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float
    sandbox_logs: Optional[List[str]] = None


# Evidence schemas
class EvidenceRecord(BaseModel):
    """Evidence record model."""

    evidence_id: str
    claim_id: str
    source_id: str
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    text: str
    metadata: Dict[str, Any] = Field(default={})
    confidence: float = Field(default=1.0)
    created_at: str


class EvidenceGraph(BaseModel):
    """Evidence graph model."""

    graph_id: str
    run_id: str
    claims: List[EvidenceRecord]
    created_at: str
    updated_at: str


class GraphStatistics(BaseModel):
    """Aggregate statistics over the evidence graph."""

    total_claims: int = 0
    total_evidence: int = 0
    status_distribution: Dict[str, Any] = Field(default_factory=dict)
    support_rate: float = 0.0
    unsupported_rate: float = 0.0


# Approval schemas
class ApprovalStatus(str, Enum):
    """Approval lifecycle status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class ApprovalRequest(BaseModel):
    """Approval request body for a high-risk tool operation."""

    tool_id: str
    step_id: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: int = Field(default=1, ge=0, le=3)
    project_id: Optional[str] = None
    requested_by: Optional[str] = None
    requires_approval: bool = True


class ApprovalDecision(BaseModel):
    """Approval decision model."""

    request_id: str
    decision: str  # "approve", "reject", "defer"
    approver_id: str
    reason: str
    conditions: Optional[Dict[str, Any]] = None
    decided_at: str


# Task schemas
class TaskCreate(BaseModel):
    """Task creation model."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    instructions: str = Field(..., min_length=1)
    project_id: str | int
    user_id: str | int
    priority: str = Field(default="medium")
    tags: List[str] = Field(default=[])


class TaskUpdate(BaseModel):
    """Task update model."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    instructions: Optional[str] = Field(None, min_length=1)
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None


class TaskResponse(BaseModel):
    """Task response model."""

    task_id: str
    name: str
    description: str
    instructions: str
    project_id: str
    user_id: str
    status: str
    priority: str
    tags: List[str]
    created_at: str
    updated_at: str
    run_id: Optional[str] = None

    class Config:
        from_attributes = True


class TaskStatus(str, Enum):
    """Research task lifecycle statuses."""

    CREATED = "created"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    POLICY_CHECK = "policy_check"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    EVIDENCE_COLLECTION = "evidence_collection"
    CLAIM_VERIFICATION = "claim_verification"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """Structured plan step definition."""

    step_id: str
    description: str
    required_tool: str
    risk_level: RiskLevel = RiskLevel.LEVEL_1
    requires_approval: bool = False
    depends_on: Optional[List[str]] = None
    timeout_seconds: Optional[int] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskStatusUpdate(BaseModel):
    """Status update for a task."""

    task_id: str
    status: TaskStatus
    message: Optional[str] = None
    progress_percentage: float = 0.0


class DateRangeFilter(BaseModel):
    """Date range filter for audit query helpers."""

    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Audit log entry response model."""

    event_id: str
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    project_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    status: str = "ok"
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: str
    updated_at: str


# Retrieval schemas
class RetrievalQuery(BaseModel):
    """Retrieval query model."""

    project_id: str
    query: str
    filters: Dict[str, Any] = Field(default={})
    top_k: int = Field(default=5)
    score_threshold: float = Field(default=0.0)


class RetrievalResult(BaseModel):
    """Retrieval result model."""

    document_id: str
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = Field(default={})
    score: float
    source: str
    page: Optional[int] = None


# Safety schemas
class SafetyTestRequest(BaseModel):
    """Safety test request model."""

    test_case_id: str
    input_text: str
    project_id: str
    model_version_id: Optional[str] = None


class SafetyTestResult(BaseModel):
    """Safety test result model."""

    test_case_id: str
    passed: bool
    explanation: str
    severity: str
    detected_issues: List[str] = Field(default=[])


# Evaluation schemas
class EvaluationRunRequest(BaseModel):
    """Evaluation run request model."""

    project_id: str
    candidate_name: str
    candidate_type: str
    dataset_version_id: Optional[str] = None
    notes: str = Field(default="")
    config: Dict[str, Any] = Field(default={})


class EvaluationRunResponse(BaseModel):
    """Evaluation run response model."""

    run_id: str
    project_id: str
    candidate_name: str
    candidate_type: str
    status: str
    started_at: str
    finished_at: Optional[str] = None


# Sandbox schemas
class SandboxConfig(BaseModel):
    """Sandbox configuration model."""

    timeout: int = Field(default=300)
    memory_limit: int = Field(default=4096)
    cpu_limit: float = Field(default=2.0)
    network_access: bool = Field(default=False)
    filesystem_access: str = Field(default="readonly")
    environment: Dict[str, str] = Field(default={})


class SandboxExecutionRequest(BaseModel):
    """Sandbox execution request model."""

    code: str
    language: str = Field(default="python")
    config: SandboxConfig = Field(default_factory=SandboxConfig)
    inputs: Dict[str, Any] = Field(default={})


class SandboxExecutionResponse(BaseModel):
    """Sandbox execution response model."""

    execution_id: str
    status: str
    output: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = Field(default=[])
    execution_time: float
    memory_used: int


# API Response base models
class APIResponse(BaseModel):
    """Base API response model."""

    success: bool
    message: str
    data: Any = None
    errors: List[str] = Field(default=[])


class PaginatedResponse(BaseModel):
    """Paginated response model."""

    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


# Validation utilities
class ValidationError(BaseModel):
    """Validation error model."""

    field: str
    message: str
    code: str
    value: Any = None


class ValidationResult(BaseModel):
    """Validation result model."""

    valid: bool
    errors: List[ValidationError] = Field(default=[])
