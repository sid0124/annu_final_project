"""DB-backed run orchestration for the VTR-Agent vertical slice."""
from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from vtr_agent.core.database import models as m
from vtr_agent.core.policy_engine import check_operation
from vtr_agent.utils import RiskLevel, new_id


INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"(reveal|show|print|leak|send|exfiltrate)\s+(the\s+)?(api[_\s]?keys?|secrets?|passwords?|tokens?|env)", re.I),
    re.compile(r"(curl|wget)\s+https?://", re.I),
    re.compile(r"import\s+subprocess|os\.system\(", re.I),
]


def create_run(
    db: Session,
    user: m.User,
    task: str,
    project_id: str | int | None = None,
    allowed_tools: list[str] | None = None,
) -> m.ResearchRun:
    """Create a research run with a deterministic structured plan."""
    project = _resolve_project(db, user, project_id)
    run = m.ResearchRun(
        run_id=new_id("RUN"),
        task_id=new_id("TASK"),
        goal=task,
        status="created",
        created_by=user.id,
        project_id=project.id if project else None,
        plan_json={},
    )
    db.add(run)
    db.flush()

    plan_steps = _plan_steps(task, allowed_tools)
    run.plan_json = {
        "task_id": run.task_id,
        "goal": task,
        "planner": "deterministic_phase2_adapter",
        "limitations": [
            "No external LLM planner is enabled yet.",
            "Python analysis uses the current subprocess sandbox, not the final Docker worker.",
        ],
        "steps": plan_steps,
    }
    for step in plan_steps:
        db.add(
            m.PlanStepModel(
                step_id=step["step_id"],
                run_id_ref=run.id,
                description=step["description"],
                required_tool=step["required_tool"],
                risk_level=step["risk_level"],
                requires_approval=step["requires_approval"],
                status="pending",
            )
        )

    _audit(
        db,
        user,
        "RUN_CREATED",
        "research_run",
        run.run_id,
        project_id=run.project_id,
        after={"goal": task, "steps": len(plan_steps)},
    )
    db.commit()
    db.refresh(run)
    return run


def start_or_resume_run(db: Session, user: m.User, run_id: str) -> m.ResearchRun:
    """Execute allowed run steps until completion, failure, block, or approval wait."""
    run = _get_authorized_run(db, user, run_id)
    if run.status in {"completed", "cancelled", "blocked", "failed"}:
        return run

    if _scan_for_injection(run.goal):
        run.status = "blocked"
        run.error_message = "Task text contains prompt-injection or unsafe tool-abuse patterns."
        _audit(db, user, "SAFETY_EVENT", "research_run", run.run_id, project_id=run.project_id, status="blocked", after={"reason": run.error_message})
        db.commit()
        db.refresh(run)
        return run

    run.status = "executing"
    _audit(db, user, "RUN_STARTED", "research_run", run.run_id, project_id=run.project_id)

    for step in sorted(run.steps, key=lambda item: item.step_id):
        if step.status == "completed":
            continue

        decision = check_operation(
            step.required_tool,
            user.role,
            operation="execute",
            context={"run_id": run.run_id, "step_id": step.step_id},
        )
        step.result_json = {**(step.result_json or {}), "policy_decision": decision.model_dump(mode="json")}
        _audit(
            db,
            user,
            "POLICY_DECISION",
            "plan_step",
            step.step_id,
            project_id=run.project_id,
            after=decision.model_dump(mode="json"),
        )

        if decision.decision == "DENY":
            step.status = "blocked"
            step.error = decision.reason
            run.status = "blocked"
            run.error_message = decision.reason
            db.commit()
            db.refresh(run)
            return run

        if decision.decision == "REQUIRE_APPROVAL" and not _step_has_approval(run, step.step_id):
            _ensure_approval_request(db, user, run, step, decision.risk_level)
            step.status = "waiting_approval"
            run.status = "waiting_approval"
            db.commit()
            db.refresh(run)
            return run

        step.status = "running"
        _execute_step(db, user, run, step)
        step.status = "completed"

    _verify_claims(run)
    run.status = "completed"
    run.summary_report = _build_report(run)
    _audit(db, user, "RUN_COMPLETED", "research_run", run.run_id, project_id=run.project_id, after={"claims": len(run.claims), "evidence": len(run.evidence_items)})
    db.commit()
    db.refresh(run)
    return run


def decide_approval(
    db: Session,
    user: m.User,
    approval_id: str,
    decision: str,
    reason: str,
) -> m.ApprovalRequestModel:
    """Approve or reject a persisted approval request."""
    approval = (
        db.query(m.ApprovalRequestModel)
        .filter(m.ApprovalRequestModel.approval_id == approval_id)
        .first()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not user.is_admin and not user.is_reviewer:
        raise HTTPException(status_code=403, detail="User cannot decide approvals")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")

    approval.status = decision
    approval.decision = decision
    approval.decided_by = user.user_id
    approval.decision_reason = reason
    if approval.run:
        if decision == "approved":
            approval.run.status = "plan_ready"
            for step in approval.run.steps:
                if step.step_id == approval.step_id and step.status == "waiting_approval":
                    step.status = "pending"
        else:
            approval.run.status = "cancelled"
            approval.run.error_message = f"Approval rejected for {approval.tool_id}: {reason}"
    _audit(
        db,
        user,
        "APPROVAL_DECISION",
        "approval_request",
        approval.approval_id,
        project_id=approval.run.project_id if approval.run else None,
        after={"decision": decision, "reason": reason},
    )
    db.commit()
    db.refresh(approval)
    return approval


def run_to_dict(run: m.ResearchRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "task_id": run.task_id,
        "goal": run.goal,
        "status": run.status,
        "project_id": run.project.project_id if run.project else None,
        "plan": run.plan_json,
        "summary_report": run.summary_report,
        "error_message": run.error_message,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def trace_for_run(run: m.ResearchRun) -> dict[str, Any]:
    return {
        **run_to_dict(run),
        "steps": [
            {
                "step_id": step.step_id,
                "description": step.description,
                "required_tool": step.required_tool,
                "risk_level": step.risk_level,
                "requires_approval": step.requires_approval,
                "status": step.status,
                "result": step.result_json,
                "error": step.error,
            }
            for step in sorted(run.steps, key=lambda item: item.step_id)
        ],
        "approvals": [approval_to_dict(item) for item in run.approvals],
        "evidence": [evidence_to_dict(item) for item in run.evidence_items],
        "claims": [claim_to_dict(item) for item in run.claims],
    }


def approval_to_dict(approval: m.ApprovalRequestModel) -> dict[str, Any]:
    return {
        "approval_id": approval.approval_id,
        "run_id": approval.run.run_id if approval.run else None,
        "tool_id": approval.tool_id,
        "step_id": approval.step_id,
        "arguments": approval.arguments_json,
        "risk_level": approval.risk_level,
        "status": approval.status,
        "requested_by": approval.requested_by,
        "decided_by": approval.decided_by,
        "decision": approval.decision,
        "decision_reason": approval.decision_reason,
        "created_at": approval.created_at,
        "updated_at": approval.updated_at,
    }


def evidence_to_dict(evidence: m.EvidenceModel) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "source_type": evidence.source_type,
        "source_url_or_id": evidence.source_url_or_id,
        "content": evidence.content,
        "metadata": evidence.metadata_json,
        "created_at": evidence.created_at,
    }


def claim_to_dict(claim: m.ClaimModel) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "text": claim.text,
        "verification_status": claim.verification_status,
        "confidence": claim.confidence,
        "evidence_ids": claim.evidence_ids_json,
        "created_at": claim.created_at,
    }


def _plan_steps(task: str, allowed_tools: list[str] | None) -> list[dict[str, Any]]:
    allowed = set(allowed_tools or [])
    needs_analysis = bool(re.search(r"\b(analy[sz]e|dataset|statistics|python|code|chart|plot)\b", task, re.I))
    steps = [
        {
            "step_id": "S1",
            "description": "Retrieve approved project evidence relevant to the task.",
            "required_tool": "retriever",
            "risk_level": RiskLevel.LEVEL_1.value,
            "requires_approval": False,
        },
        {
            "step_id": "S2",
            "description": "Create provenance-linked evidence and preliminary claims.",
            "required_tool": "evidence_tool",
            "risk_level": RiskLevel.LEVEL_1.value,
            "requires_approval": False,
        },
    ]
    if needs_analysis or "python_sandbox" in allowed:
        steps.insert(
            1,
            {
                "step_id": "S1A",
                "description": "Run approved bounded analysis in the sandbox.",
                "required_tool": "python_sandbox",
                "risk_level": RiskLevel.LEVEL_2.value,
                "requires_approval": True,
            },
        )
    return steps


def _execute_step(db: Session, user: m.User, run: m.ResearchRun, step: m.PlanStepModel) -> None:
    if step.required_tool == "retriever":
        documents = (
            db.query(m.Document)
            .filter(m.Document.project_id == run.project_id)
            .order_by(m.Document.id.asc())
            .limit(5)
            .all()
        )
        for document in documents:
            content = (document.cleaned_text or document.text_preview or "").strip()
            if not content:
                continue
            if _scan_for_injection(content):
                _audit(db, user, "SAFETY_EVENT", "document", document.document_id, project_id=run.project_id, status="blocked", after={"reason": "Indirect prompt-injection pattern detected"})
                content = "[UNTRUSTED_CONTENT_REDACTED]"
            db.add(
                m.EvidenceModel(
                    evidence_id=new_id("EVD"),
                    run_id_ref=run.id,
                    source_type="document",
                    source_url_or_id=document.document_id,
                    content=content[:1200],
                    metadata_json={"filename": document.filename, "tool": "retriever"},
                )
            )
        step.result_json = {"retrieved_documents": len(documents)}
        _audit(db, user, "TOOL_EXECUTION", "tool", "retriever", project_id=run.project_id, after=step.result_json)
    elif step.required_tool == "python_sandbox":
        from app.sandbox.sandbox_manager import execute_code_sandbox

        result = execute_code_sandbox(
            "values = [1, 2, 3, 4]\nprint({'count': len(values), 'mean': sum(values) / len(values)})",
            timeout=10,
            memory_limit=256,
            filesystem_access="sandbox_only",
        )
        step.result_json = {
            "execution_id": result.execution_id,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "safety_violation": result.safety_violation,
            "sandbox_limitation": "Current implementation uses subprocess isolation; Docker worker remains required for final system.",
        }
        db.add(
            m.EvidenceModel(
                evidence_id=new_id("EVD"),
                run_id_ref=run.id,
                source_type="sandbox_result",
                source_url_or_id=result.execution_id,
                content=f"Approved sandbox analysis result: {result.stdout or result.stderr}",
                metadata_json={"tool": "python_sandbox", "exit_code": result.exit_code},
            )
        )
        _audit(db, user, "SANDBOX_EXECUTION", "tool", "python_sandbox", project_id=run.project_id, after=step.result_json, status="ok" if result.exit_code == 0 else "error")
    elif step.required_tool == "evidence_tool":
        _create_claims_from_evidence(db, run)
        step.result_json = {"claims_created": len(run.claims)}
        _audit(db, user, "CLAIMS_GENERATED", "research_run", run.run_id, project_id=run.project_id, after=step.result_json)
    else:
        step.result_json = {"message": f"No executor registered for {step.required_tool}"}


def _create_claims_from_evidence(db: Session, run: m.ResearchRun) -> None:
    if run.claims:
        return
    evidence_items = list(run.evidence_items)
    if not evidence_items:
        db.add(
            m.ClaimModel(
                claim_id=new_id("CLM"),
                run_id_ref=run.id,
                text="No approved evidence was available for this run.",
                verification_status="UNSUPPORTED",
                confidence=0.0,
                evidence_ids_json=[],
            )
        )
        return
    for evidence in evidence_items[:3]:
        sentence = _first_sentence(evidence.content)
        db.add(
            m.ClaimModel(
                claim_id=new_id("CLM"),
                run_id_ref=run.id,
                text=sentence,
                verification_status="UNVERIFIED",
                confidence=0.7,
                evidence_ids_json=[evidence.evidence_id],
            )
        )
    db.flush()


def _verify_claims(run: m.ResearchRun) -> None:
    evidence_by_id = {item.evidence_id: item for item in run.evidence_items}
    for claim in run.claims:
        if not claim.evidence_ids_json:
            claim.verification_status = "UNSUPPORTED"
            claim.confidence = 0.0
            continue
        support = 0
        for evidence_id in claim.evidence_ids_json:
            evidence = evidence_by_id.get(evidence_id)
            if evidence and _token_overlap(claim.text, evidence.content) >= 0.35:
                support += 1
        claim.verification_status = "SUPPORTED" if support else "UNSUPPORTED"
        claim.confidence = 0.85 if support else 0.2


def _build_report(run: m.ResearchRun) -> str:
    supported = [claim for claim in run.claims if claim.verification_status == "SUPPORTED"]
    unsupported = [claim for claim in run.claims if claim.verification_status != "SUPPORTED"]
    lines = [
        f"# VTR-Agent Run Report: {run.run_id}",
        "",
        f"Goal: {run.goal}",
        f"Status: {run.status}",
        "",
        "## Verified Claims",
    ]
    lines.extend(f"- {claim.text} (evidence: {', '.join(claim.evidence_ids_json)})" for claim in supported)
    if not supported:
        lines.append("- No supported claims were produced.")
    lines.append("")
    lines.append("## Unsupported or Unverified Claims")
    lines.extend(f"- {claim.text} [{claim.verification_status}]" for claim in unsupported)
    if not unsupported:
        lines.append("- None.")
    lines.append("")
    lines.append("## Limitations")
    lines.append("- Planner is deterministic until an LLM provider is configured.")
    lines.append("- Docker sandbox isolation is still required for the final security target.")
    return "\n".join(lines)


def _resolve_project(db: Session, user: m.User, project_id: str | int | None) -> m.Project | None:
    if project_id is None:
        return db.query(m.Project).order_by(m.Project.id.asc()).first()
    return (
        db.query(m.Project)
        .filter((m.Project.project_id == str(project_id)) | (m.Project.id == _as_int(project_id)))
        .first()
    )


def _get_authorized_run(db: Session, user: m.User, run_id: str) -> m.ResearchRun:
    run = db.query(m.ResearchRun).filter(m.ResearchRun.run_id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not user.is_admin and run.created_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return run


def _ensure_approval_request(db: Session, user: m.User, run: m.ResearchRun, step: m.PlanStepModel, risk_level: Any) -> None:
    existing = next((item for item in run.approvals if item.step_id == step.step_id and item.status == "pending"), None)
    if existing:
        return
    approval = m.ApprovalRequestModel(
        approval_id=new_id("APR"),
        run_id_ref=run.id,
        tool_id=step.required_tool,
        step_id=step.step_id,
        arguments_json={"description": step.description},
        risk_level=int(risk_level),
        status="pending",
        requested_by=user.user_id,
    )
    db.add(approval)
    _audit(db, user, "APPROVAL_REQUESTED", "approval_request", approval.approval_id, project_id=run.project_id, after={"tool_id": step.required_tool, "step_id": step.step_id})


def _step_has_approval(run: m.ResearchRun, step_id: str) -> bool:
    return any(item.step_id == step_id and item.status == "approved" for item in run.approvals)


def _audit(
    db: Session,
    user: m.User,
    action: str,
    resource_type: str,
    resource_id: str,
    project_id: int | None = None,
    status: str = "ok",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        m.AuditLog(
            event_id=new_id("AUD"),
            user_id=user.id,
            user_role=user.role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            project_id=project_id,
            before_state=json.dumps(before) if before else None,
            after_state=json.dumps(after) if after else None,
            status=status,
        )
    )


def _scan_for_injection(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in INJECTION_PATTERNS)


def _first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "No textual evidence content was available."
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return parts[0][:500]


def _token_overlap(a: str, b: str) -> float:
    a_tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9]{3,}", a)}
    b_tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9]{3,}", b)}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
