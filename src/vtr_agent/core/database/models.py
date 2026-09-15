"""
VTR-Agent: Database Models

SQLAlchemy 2.0 ORM models for all VTR-Agent database tables.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship
from sqlalchemy.sql import func

from vtr_agent.core.database.session import Base
from vtr_agent.core.utils import utcnow_iso


def _iso() -> str:
    """Return ISO timestamp string."""
    return utcnow_iso()


class TimestampMixin:
    """Mixin for common timestamp fields."""

    created_at: Mapped[str] = mapped_column(String(32), default=_iso)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_iso, onupdate=_iso
    )


# ---------------------------------------------------------------------------
# Roles / Users / Projects
# ---------------------------------------------------------------------------

ROLE_ADMIN = "admin"
ROLE_RESEARCHER = "researcher"
ROLE_REVIEWER = "reviewer"
ROLE_EXPERT = "domain_expert"
ROLE_END_USER = "end_user"
ALL_ROLES = [
    ROLE_ADMIN,
    ROLE_RESEARCHER,
    ROLE_REVIEWER,
    ROLE_EXPERT,
    ROLE_END_USER,
]


class User(Base, TimestampMixin):
    """User account with roles and authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default=ROLE_END_USER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    created_runs: Mapped[list[ResearchRun]] = relationship(
        back_populates="creator"
    )
    created_projects: Mapped[list[Project]] = relationship(
        back_populates="owner"
    )
    dataset_versions: Mapped[list[DatasetVersion]] = relationship(
        foreign_keys="DatasetVersion.created_by",
        back_populates="creator"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user"
    )

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == ROLE_ADMIN

    @property
    def is_researcher(self) -> bool:
        """Check if user has researcher role."""
        return self.role in (ROLE_RESEARCHER, ROLE_ADMIN)

    @property
    def is_reviewer(self) -> bool:
        """Check if user has reviewer role."""
        return self.role in (ROLE_REVIEWER, ROLE_ADMIN)


class Project(Base, TimestampMixin):
    """Research project with domain and access controls."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    expected_users: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    success_thresholds: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )
    scope_exclusions: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    owner: Mapped[Optional[User]] = relationship(back_populates="created_projects")
    members: Mapped[list[ProjectMembership]] = relationship(
        back_populates="project"
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="project"
    )
    instruction_records: Mapped[list[InstructionRecord]] = relationship(
        back_populates="project"
    )
    dataset_versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="project"
    )
    runs: Mapped[list[ResearchRun]] = relationship(
        back_populates="project"
    )
    training_runs: Mapped[list[TrainingRun]] = relationship(
        back_populates="project"
    )
    distillation_runs: Mapped[list[DistillationRun]] = relationship(
        back_populates="project"
    )
    evaluation_runs: Mapped[list[EvaluationRun]] = relationship(
        back_populates="project"
    )
    deployments: Mapped[list[Deployment]] = relationship(
        back_populates="project"
    )

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="project"
    )

    def __str__(self) -> str:
        """String representation for audit logs."""
        return f"Project(id={self.id}, project_id={self.project_id}, name={self.name})"


class ProjectMembership(Base, TimestampMixin):
    """Project membership with role assignments."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_membership"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role_in_project: Mapped[str] = mapped_column(String(40), default="member")

    # Relationships
    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship()

    @property
    def is_admin(self) -> bool:
        """Check if user is project admin."""
        return self.role_in_project == "admin"

    @property
    def is_member(self) -> bool:
        """Check if user is project member."""
        return self.role_in_project == "member"


# --- Document lifecycle statuses --------------------------------------------

DOC_STATUS_IN_REVIEW = "in_review"
DOC_STATUS_APPROVED = "approved"
DOC_STATUS_REJECTED = "rejected"
DOC_STATUSES = [DOC_STATUS_IN_REVIEW, DOC_STATUS_APPROVED, DOC_STATUS_REJECTED]


class Document(Base, TimestampMixin):
    """Uploaded research document with processing status."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16), default="txt")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    stored_path: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(255), default="")
    licence: Mapped[str] = mapped_column(String(120), default="unknown")
    owner_name: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(
        String(80), default="uncategorised", index=True
    )
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(24), default=DOC_STATUS_IN_REVIEW, index=True
    )
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    empty_or_corrupt: Mapped[bool] = mapped_column(Boolean, default=False)
    sensitive_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(16), default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    text_preview: Mapped[str] = mapped_column(Text, default="")
    cleaned_text: Mapped[str] = mapped_column(Text, default="")
    is_duplicate_of: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    approved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="documents")
    uploader: Mapped[Optional[User]] = relationship(
        foreign_keys=[uploaded_by]
    )
    approver: Mapped[Optional[User]] = relationship(foreign_keys=[approved_by])
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document"
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        primaryjoin="Document.document_id == foreign(DocumentChunk.document_id)",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    duplicate_of: Mapped[Optional[Document]] = relationship(
        remote_side=[id], foreign_keys=[is_duplicate_of]
    )

    @property
    def is_approved(self) -> bool:
        """Check if document is approved."""
        return self.status == DOC_STATUS_APPROVED

    @property
    def is_duplicate(self) -> bool:
        """Check if document is a duplicate."""
        return self.duplicate_flag or self.is_duplicate_of is not None


class DocumentVersion(Base, TimestampMixin):
    """Immutable snapshot of a document's text after cleaning action."""

    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text, default="")
    cleaned_text: Mapped[str] = mapped_column(Text, default="")
    cleaning_report: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    edited_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    note: Mapped[str] = mapped_column(String(255), default="")

    # Relationships
    document: Mapped[Document] = relationship(back_populates="versions")
    editor: Mapped[Optional[User]] = relationship(foreign_keys=[edited_by])


class CorpusProcessingJob(Base, TimestampMixin):
    """Batch cleaning job over a project corpus (proposes, never auto-deletes)."""

    __tablename__ = "corpus_processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    job_type: Mapped[str] = mapped_column(
        String(40), default="clean"
    )  # clean|mask_pii|dedupe
    params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(24), default="pending", index=True
    )
    documents_total: Mapped[int] = mapped_column(Integer, default=0)
    documents_changed: Mapped[int] = mapped_column(Integer, default=0)
    log_text: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship()


class DocumentChunk(Base, TimestampMixin):
    """Retrieval chunk derived from an approved document."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    document_id: Mapped[str] = mapped_column(String(32), index=True)  # public Document.document_id
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    embedding_status: Mapped[str] = mapped_column(String(16), default="pending")
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    document: Mapped[Document] = relationship(
        "Document",
        primaryjoin="foreign(DocumentChunk.document_id) == Document.document_id",
        back_populates="chunks",
    )
    project: Mapped[Project] = relationship()


# ---------------------------------------------------------------------------
# Instruction data and datasets
# ---------------------------------------------------------------------------


class InstructionRecord(Base, TimestampMixin):
    """Research instruction with approved response."""

    __tablename__ = "instruction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    instruction: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    domain_category: Mapped[str] = mapped_column(
        String(80), default="", index=True
    )
    difficulty: Mapped[str] = mapped_column(
        String(16), default="easy"
    )  # easy|medium|hard
    source_document_id: Mapped[Optional[str]] = mapped_column(
        String(32), index=True, nullable=True
    )
    source_section: Mapped[str] = mapped_column(String(160), default="")
    safety_label: Mapped[str] = mapped_column(
        String(24), default="safe"
    )  # safe|unsafe|ambiguous
    answerable: Mapped[bool] = mapped_column(Boolean, default=True)
    review_status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )  # pending|approved|rejected
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    dataset_version: Mapped[str] = mapped_column(String(32), default="")
    generated_by: Mapped[str] = mapped_column(String(40), default="manual")
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    question_hash: Mapped[str] = mapped_column(String(64), default="", index=True)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="instruction_records")
    reviewer: Mapped[Optional[User]] = relationship(foreign_keys=[reviewer_id])
    dataset: Mapped[Optional[DatasetVersion]] = relationship(
        "DatasetVersion",
        primaryjoin="foreign(InstructionRecord.dataset_version) == DatasetVersion.version_id",
    )

    @property
    def is_approved(self) -> bool:
        """Check if instruction record is approved."""
        return self.review_status == "approved"

    @property
    def is_safe(self) -> bool:
        """Check if instruction is safe."""
        return self.safety_label == "safe"


class DatasetVersion(Base, TimestampMixin):
    """Approved dataset version with train/val/test splits."""

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    version_label: Mapped[str] = mapped_column(String(32))  # v1.0
    status: Mapped[str] = mapped_column(
        String(24), default="draft"
    )  # draft|locked|approved
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    split_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # train/val/test counts+hashes
    leakage_report: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )
    checksum: Mapped[str] = mapped_column(String(64), default="")
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    export_path: Mapped[str] = mapped_column(String(500), default="")

    # Relationships
    project: Mapped[Project] = relationship(back_populates="dataset_versions")
    creator: Mapped[Optional[User]] = relationship(
        foreign_keys=[created_by], back_populates="dataset_versions"
    )
    assignments: Mapped[list[DatasetSplitAssignment]] = relationship(
        back_populates="dataset_version"
    )
    training_runs: Mapped[list[TrainingRun]] = relationship(
        back_populates="dataset_version"
    )

    @property
    def is_locked(self) -> bool:
        """Check if dataset version is locked."""
        return self.status == "locked"

    @property
    def is_approved(self) -> bool:
        """Check if dataset version is approved."""
        return self.status == "approved"


class DatasetSplitAssignment(Base, TimestampMixin):
    """Assignment of instruction records to dataset splits."""

    __tablename__ = "dataset_split_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_versions.id"), index=True
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("instruction_records.id"), index=True
    )
    split: Mapped[str] = mapped_column(String(16))  # train|validation|test

    # Relationships
    dataset_version: Mapped[DatasetVersion] = relationship(
        back_populates="assignments"
    )
    instruction_record: Mapped[InstructionRecord] = relationship()


# ---------------------------------------------------------------------------
# Training, distillation, models
# ---------------------------------------------------------------------------


class TrainingRun(Base, TimestampMixin):
    """Model training run configuration and tracking."""

    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    dataset_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    base_model: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(16), default="lora")  # lora|qlora
    status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )  # pending|running|completed|failed|cancelled
    config_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    progress_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # live loss/epoch
    metrics_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )
    adapter_path: Mapped[str] = mapped_column(String(500), default="")
    checkpoint_path: Mapped[str] = mapped_column(String(500), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation_source: Mapped[str] = mapped_column(String(120), default="")
    hardware_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    mlflow_run_id: Mapped[str] = mapped_column(String(64), default="")
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    started_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    log_path: Mapped[str] = mapped_column(String(500), default="")

    # Relationships
    project: Mapped[Project] = relationship(back_populates="training_runs")
    dataset_version: Mapped[Optional[DatasetVersion]] = relationship(
        back_populates="training_runs"
    )
    starter: Mapped[Optional[User]] = relationship(
        foreign_keys=[started_by]
    )
    model_versions: Mapped[list[ModelVersion]] = relationship(
        back_populates="training_run"
    )


class DistillationRun(Base, TimestampMixin):
    """Knowledge distillation run configuration."""

    __tablename__ = "distillation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    dataset_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    teacher_model: Mapped[str] = mapped_column(String(255))
    student_model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    generation_params: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )
    teacher_outputs: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # list of {question, teacher_answer, reference, quality, safety, reviewer_decision}
    filtered_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_count: Mapped[int] = mapped_column(Integer, default=0)
    student_training_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_runs.id"), nullable=True
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation_source: Mapped[str] = mapped_column(String(120), default="")
    student_dataset_path: Mapped[str] = mapped_column(String(500), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    started_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="distillation_runs")
    dataset_version: Mapped[Optional[DatasetVersion]] = relationship()
    starter: Mapped[Optional[User]] = relationship(
        foreign_keys=[started_by]
    )
    student_training_run: Mapped[Optional[TrainingRun]] = relationship(
        foreign_keys=[student_training_run_id]
    )


class ModelVersion(Base, TimestampMixin):
    """Trained or deployed model version."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    base_model: Mapped[str] = mapped_column(String(255))
    adapter_version: Mapped[str] = mapped_column(String(40), default="-")
    model_type: Mapped[str] = mapped_column(
        String(24), default="base"
    )  # base|rag_lora|peft_lora|distilled_student|quantized
    precision: Mapped[str] = mapped_column(String(16), default="fp32")
    model_size_mb: Mapped[float] = mapped_column(Float, default=0.0)
    dataset_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    training_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_runs.id"), nullable=True
    )
    distillation_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("distillation_runs.id"), nullable=True
    )
    quantization_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quantization_runs.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    evaluation_status: Mapped[str] = mapped_column(
        String(24), default="not_evaluated"
    )
    approval_status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )
    deployment_status: Mapped[str] = mapped_column(
        String(24), default="not_deployed"
    )
    path: Mapped[str] = mapped_column(String(500), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    metrics_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    checks: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    rejected_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    export_path: Mapped[str] = mapped_column(String(500), default="")

    # Relationships
    project: Mapped[Project] = relationship()
    base_dataset_version: Mapped[Optional[DatasetVersion]] = relationship(
        foreign_keys=[dataset_version_id]
    )
    training_run: Mapped[Optional[TrainingRun]] = relationship(
        back_populates="model_versions"
    )
    distillation_run: Mapped[Optional[DistillationRun]] = relationship()
    quantization_run: Mapped[Optional[QuantizationRun]] = relationship(
        foreign_keys=[quantization_run_id]
    )
    creator: Mapped[Optional[User]] = relationship(
        foreign_keys=[created_by]
    )
    evaluation_runs: Mapped[list[EvaluationRun]] = relationship(
        back_populates="candidate_model"
    )
    safety_test_results: Mapped[list[SafetyTestResult]] = relationship(
        back_populates="evaluated_model"
    )

    @property
    def is_candidate(self) -> bool:
        """Check if model is a candidate (not yet approved)."""
        return self.status == "candidate"

    @property
    def is_approved(self) -> bool:
        """Check if model is approved for use."""
        return self.approval_status == "approved"

    @property
    def is_deployed(self) -> bool:
        """Check if model is deployed."""
        return self.deployment_status == "deployed"


# ---------------------------------------------------------------------------
# Evaluation, safety, quantization, deployments
# ---------------------------------------------------------------------------


class EvaluationRun(Base, TimestampMixin):
    """Model evaluation run with benchmark testing."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    dataset_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )  # pending|running|completed|failed|cancelled
    config_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    summary_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    report_path: Mapped[str] = mapped_column(String(500), default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    started_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    model_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="evaluation_runs")
    dataset_version: Mapped[Optional[DatasetVersion]] = relationship(
        foreign_keys=[dataset_version_id]
    )
    starter: Mapped[Optional[User]] = relationship(
        foreign_keys=[started_by]
    )
    candidate_model: Mapped[Optional[ModelVersion]] = relationship(
        back_populates="evaluation_runs",
        foreign_keys=[model_version_id]
    )
    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="evaluation_run"
    )
    safety_test_results: Mapped[list[SafetyTestResult]] = relationship(
        back_populates="evaluation_run"
    )


class EvaluationResult(Base, TimestampMixin):
    """Individual evaluation test result."""

    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_runs.id"), index=True
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"), index=True
    )
    test_record_id: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="")
    question: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(Text, default="")
    answerable: Mapped[bool] = mapped_column(Boolean, default=True)
    predicted: Mapped[str] = mapped_column(Text, default="")
    exact_match: Mapped[float] = mapped_column(Float, default=0.0)
    token_f1: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    citation_correct: Mapped[float] = mapped_column(Float, default=0.0)
    hallucination: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_violation: Mapped[bool] = mapped_column(Boolean, default=False)
    refusal_correct: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    evaluation_run: Mapped[EvaluationRun] = relationship(
        back_populates="results"
    )
    model_version: Mapped[ModelVersion] = relationship()

    @property
    def is_passing(self) -> bool:
        """Check if evaluation result passes benchmarks."""
        return (
            self.exact_match >= 0.8
            and self.token_f1 >= 0.8
            and self.semantic_similarity >= 0.8
            and not self.hallucination
            and not self.safety_violation
        )

    @property
    def quality_score(self) -> float:
        """Calculate overall quality score."""
        return (
            self.exact_match * 0.3
            + self.token_f1 * 0.3
            + self.semantic_similarity * 0.2
            + (1.0 if not self.hallucination else 0.0) * 0.1
            + (1.0 if not self.safety_violation else 0.0) * 0.1
        )


class SafetyTestCase(Base, TimestampMixin):
    """Safety test case with expected behavior."""

    __tablename__ = "safety_test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    expected_behaviour: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    project: Mapped[Project] = relationship()
    creator: Mapped[Optional[User]] = relationship()
    results: Mapped[list[SafetyTestResult]] = relationship(
        back_populates="test_case"
    )

    @property
    def is_high_risk(self) -> bool:
        """Check if test case is high severity."""
        return self.severity == "high"

    @property
    def is_medium_risk(self) -> bool:
        """Check if test case is medium severity."""
        return self.severity == "medium"

    @property
    def is_low_risk(self) -> bool:
        """Check if test case is low severity."""
        return self.severity == "low"


class SafetyTestResult(Base, TimestampMixin):
    """Result of safety test execution."""

    __tablename__ = "safety_test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    result_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    eval_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=True
    )
    case_id: Mapped[str] = mapped_column(String(32), index=True)
    safety_test_case_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("safety_test_cases.id"), nullable=True, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"), index=True
    )
    input_text: Mapped[str] = mapped_column(Text)
    expected_behaviour: Mapped[str] = mapped_column(Text, default="")
    actual_response: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    explanation: Mapped[str] = mapped_column(Text, default="")
    model_version_label: Mapped[str] = mapped_column(String(40), default="")
    run_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    evaluation_run: Mapped[Optional[EvaluationRun]] = relationship(
        back_populates="safety_test_results"
    )
    test_case: Mapped[Optional[SafetyTestCase]] = relationship(
        back_populates="results",
        foreign_keys=[safety_test_case_id]
    )
    project: Mapped[Project] = relationship()
    evaluated_model: Mapped[ModelVersion] = relationship(
        back_populates="safety_test_results"
    )

    @property
    def risk_level(self) -> str:
        """Determine risk level based on test case."""
        return self.severity

    @property
    def is_critical_failure(self) -> bool:
        """Check if test represents a critical safety failure."""
        return not self.passed and self.severity == "high"


class QuantizationRun(Base, TimestampMixin):
    """Model quantization run configuration and tracking."""

    __tablename__ = "quantization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    source_model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id")
    )
    method: Mapped[str] = mapped_column(String(16))  # fp16|int8|int4|dynamic
    status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )  # pending|running|completed|failed|cancelled
    original_size_mb: Mapped[float] = mapped_column(Float, default=0.0)
    quantized_size_mb: Mapped[float] = mapped_column(Float, default=0.0)
    size_reduction_pct: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_delta: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms_before: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms_after: Mapped[float] = mapped_column(Float, default=0.0)
    memory_mb_before: Mapped[float] = mapped_column(Float, default=0.0)
    memory_mb_after: Mapped[float] = mapped_column(Float, default=0.0)
    output_path: Mapped[str] = mapped_column(String(500), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship()
    source_model_version: Mapped[ModelVersion] = relationship(
        foreign_keys=[source_model_version_id]
    )

    @property
    def is_successful(self) -> bool:
        """Check if quantization run completed successfully."""
        return self.status == "completed"

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_size_mb > 0:
            return self.quantized_size_mb / self.original_size_mb
        return 0.0


class Deployment(Base, TimestampMixin):
    """Deployed model version with health tracking."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deployment_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="active")
    health_status: Mapped[str] = mapped_column(String(24), default="unknown")
    override_note: Mapped[str] = mapped_column(Text, default="")
    acceptance_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    deployed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    deployed_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    rolled_back_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    endpoint_path: Mapped[str] = mapped_column(String(200), default="/chat")
    base_model: Mapped[str] = mapped_column(String(255), default="")

    # Relationships
    project: Mapped[Project] = relationship(back_populates="deployments")
    model_version: Mapped[ModelVersion] = relationship()
    deployer: Mapped[Optional[User]] = relationship(
        foreign_keys=[deployed_by]
    )

    @property
    def is_active(self) -> bool:
        """Check if deployment is active."""
        return self.status == "active"

    @property
    def is_healthy(self) -> bool:
        """Check if deployment is healthy."""
        return self.health_status == "healthy"


# ---------------------------------------------------------------------------
# Conversations, messages, feedback, monitoring, audit
# ---------------------------------------------------------------------------


class Conversation(Base, TimestampMixin):
    """Research conversation with message history."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="conversations")
    user: Mapped[User] = relationship()
    model_version: Mapped[Optional[ModelVersion]] = relationship()
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation"
    )
    feedbacks: Mapped[list[Feedback]] = relationship(
        back_populates="conversation"
    )

    @property
    def is_archived(self) -> bool:
        """Check if conversation is archived."""
        return self.is_archived

    @property
    def get_summary(self) -> str:
        """Get conversation summary."""
        return f"Conversation {self.conversation_id} with {self.message_count} messages"


class Message(Base, TimestampMixin):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    model_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_meta: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict
    )
    request_id: Mapped[str] = mapped_column(String(64), default="")

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    model_version: Mapped[Optional[ModelVersion]] = relationship()
    feedback: Mapped[Optional[Feedback]] = relationship(
        back_populates="message"
    )

    @property
    def is_user_message(self) -> bool:
        """Check if message is from user."""
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """Check if message is from assistant."""
        return self.role == "assistant"

    @property
    def has_evidence(self) -> bool:
        """Check if message has evidence attached."""
        return bool(self.evidence_json)


class Feedback(Base, TimestampMixin):
    """User feedback on messages."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id"), index=True
    )
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[str] = mapped_column(String(16), default="")  # up|down
    feedback_type: Mapped[str] = mapped_column(
        String(32), default="rating"
    )  # rating|hallucination|unsafe
    note: Mapped[str] = mapped_column(Text, default="")
    model_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )

    # Relationships
    message: Mapped[Optional[Message]] = relationship(
        back_populates="feedback"
    )
    conversation: Mapped[Optional[Conversation]] = relationship(
        back_populates="feedbacks"
    )
    project: Mapped[Project] = relationship()
    user: Mapped[User] = relationship()
    model_version: Mapped[Optional[ModelVersion]] = relationship()

    @property
    def is_positive(self) -> bool:
        """Check if feedback is positive."""
        return self.rating == "up"

    @property
    def is_negative(self) -> bool:
        """Check if feedback is negative."""
        return self.rating == "down"

    @property
    def is_hallucination_report(self) -> bool:
        """Check if feedback is about hallucination."""
        return self.feedback_type == "hallucination"

    @property
    def is_safety_report(self) -> bool:
        """Check if feedback is about safety."""
        return self.feedback_type == "unsafe"


class SystemMetric(Base, TimestampMixin):
    """System performance metrics."""

    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(60), index=True)  # request, error, latency, memory...
    value: Mapped[float] = mapped_column(Float, default=0.0)
    extra_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[str] = mapped_column(String(32), default=_iso, index=True)

    @property
    def is_latency_metric(self) -> bool:
        """Check if metric is latency-related."""
        return "latency" in self.metric_type.lower()

    @property
    def is_error_metric(self) -> bool:
        """Check if metric is error-related."""
        return "error" in self.metric_type.lower()


class AuditLog(Base, TimestampMixin):
    """Immutable audit trail of all system actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    user_role: Mapped[str] = mapped_column(String(40), default="")
    action: Mapped[str] = mapped_column(String(60), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    before_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="ok")
    request_id: Mapped[str] = mapped_column(String(64), default="")
    session_id: Mapped[str] = mapped_column(String(64), default="")

    # Relationships
    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")

    @property
    def is_success(self) -> bool:
        """Check if audit log represents successful action."""
        return self.status == "ok"

    @property
    def is_error(self) -> bool:
        """Check if audit log represents error action."""
        return self.status != "ok"

    def __str__(self) -> str:
        """String representation for logging."""
        return f"AuditLog(event_id={self.event_id}, action={self.action}, status={self.status})"


# ---------------------------------------------------------------------------
# VTR Domain Models: ResearchRun, PlanStep, Evidence, Claim, ApprovalRequest
# ---------------------------------------------------------------------------


class ResearchRun(Base, TimestampMixin):
    """Execution of a research task run by the research agent."""

    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    plan_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    summary_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    creator: Mapped[Optional[User]] = relationship(back_populates="created_runs")
    project: Mapped[Optional[Project]] = relationship(back_populates="runs")
    steps: Mapped[list["PlanStepModel"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    evidence_items: Mapped[list["EvidenceModel"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    claims: Mapped[list["ClaimModel"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    approvals: Mapped[list["ApprovalRequestModel"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class PlanStepModel(Base, TimestampMixin):
    """Individual planned or executed step within a ResearchRun."""

    __tablename__ = "plan_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id_ref: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    required_tool: Mapped[str] = mapped_column(String(64))
    risk_level: Mapped[int] = mapped_column(Integer, default=1)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    result_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped[ResearchRun] = relationship(back_populates="steps")


class EvidenceModel(Base, TimestampMixin):
    """Evidence extracted or collected during a research run."""

    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    run_id_ref: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(64), default="web_research")
    source_url_or_id: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    run: Mapped[ResearchRun] = relationship(back_populates="evidence_items")


class ClaimModel(Base, TimestampMixin):
    """Claim extracted from draft report with its verification provenance."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    run_id_ref: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)

    run: Mapped[ResearchRun] = relationship(back_populates="claims")


class ApprovalRequestModel(Base, TimestampMixin):
    """Human approval gate record for high-risk operations."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    run_id_ref: Mapped[Optional[int]] = mapped_column(ForeignKey("research_runs.id"), nullable=True)
    tool_id: Mapped[str] = mapped_column(String(64))
    step_id: Mapped[str] = mapped_column(String(32), default="")
    arguments_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_level: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(String(64), default="")
    decided_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped[Optional[ResearchRun]] = relationship(back_populates="approvals")


# Convenience lookup of every model for scripts/tests
ALL_MODELS = [
    User,
    Project,
    ProjectMembership,
    Document,
    DocumentVersion,
    CorpusProcessingJob,
    DocumentChunk,
    InstructionRecord,
    DatasetVersion,
    DatasetSplitAssignment,
    TrainingRun,
    DistillationRun,
    ModelVersion,
    EvaluationRun,
    EvaluationResult,
    SafetyTestCase,
    SafetyTestResult,
    QuantizationRun,
    Deployment,
    Conversation,
    Message,
    Feedback,
    SystemMetric,
    AuditLog,
    ResearchRun,
    PlanStepModel,
    EvidenceModel,
    ClaimModel,
    ApprovalRequestModel,
]
