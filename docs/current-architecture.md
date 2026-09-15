# Current Architecture Audit — VTR-Agent

Date: 2026-09-15
Auditor: Cline (automated architecture review)
Scope: Backend + Frontend + Database + Tests + Config + CI

> Phase 1 update: the backend now mounts the existing core routers and a new foundation router at both root paths and `/api/v1`. The React SPA is the canonical UI for this repo; `ui/dashboard.py` is not present. Authentication, project listing/creation, document upload registration, tool listing, metrics, basic safety/evidence placeholders, approval listing, sandbox status, and the protected training guard are now available through FastAPI.

---

## 1. Existing Architecture (as implemented)

The system is split into two parallel Python packages:

### `src/vtr_agent/` — intended "main" package:
- `src/vtr_agent/main.py` — FastAPI entrypoint, lifespan hook, CORS, error handlers, root + health endpoints.
- `src/vtr_agent/api/` — implemented routers: `auth`, `tasks`, `audit`. Plus a lazy import list for many optional routers that **do not exist**.
- `src/vtr_agent/auth/security.py` — JWT creation/decode, password hashing (bcrypt via passlib), `get_current_user`, `require_role`.
- `src/vtr_agent/core/config.py` — Pydantic-settings `Settings`.
- `src/vtr_agent/core/database/` — SQLAlchemy 2.0 `Base`, `SessionLocal`, `get_db()`, `init_db()`.
- `src/vtr_agent/core/database/models.py` — full ORM schema, **but missing `ResearchRun`**.
- `src/vtr_agent/core/task_engine.py` — re-export shim → `app.core.task_engine`.
- `src/vtr_agent/core/policy_engine.py` — re-export shim → `app.core.policy_engine`.
- `src/vtr_agent/core/tool_registry.py` — re-export shim → `app.core.tool_registry`.
- `src/vtr_agent/core/utils.py` — re-export shim → `vtr_agent.utils`.
- `src/vtr_agent/utils.py` — `RiskLevel`, password hashing, `new_id`, `get_role_permissions`.
- `src/vtr_agent/core/logging_conf.py` — structured JSON logging.

### `app/` — "Phase 1" real implementations the shims point at:
- `app/core/task_engine.py`, `app/core/policy_engine.py`, `app/core/tool_registry.py` — in-memory engines + Pydantic schemas.
- `app/retrieval.py`, `app/evidence.py`, `app/approval.py`, `app/sandbox/sandbox_manager.py`, `app/evaluation.py` — in-memory modules.

---

## 2. Existing Modules

### Backend (real, importable today)
- FastAPI with CORS, structured logging, global exception handlers.
- Auth: JWT login/logout/refresh/me, RBAC roles (`admin`, `researcher`, `reviewer`, `expert`, `end_user`).
- Task API: create/list/get task, plan steps, task stats, `/tasks/tools/allowed`, `/tasks/tools/all`.
- Audit API: `/audit/logs`, `/audit/logs/{id}`, `/audit/statistics`, `/audit/logs` (clear).
- Task/policy/tool engines (in-memory, Pydantic models).
- Sandbox manager (subprocess, timeouts, violation detection).
- Retrieval system (mock embeddings/index).
- Evidence graph (in-memory claims/evidence/verification).
- Approval gate (in-memory pending approvals).
- Evaluation framework with simulated baselines.

### Frontend (real, buildable today)
- React SPA with auth context, centralized store, sidebar navigation, Framer Motion animations, prebuilt bundle.
- Pages: Overview, Research runs, Evidence graph, Approvals, Tool registry, Settings.
- API client hardcoded to `/api/v1`.

### Not implemented / absent
- No LLM provider integration anywhere (`.env.example` references `LLM_PROVIDER` but no module consumes it).
- No planner module.
- No `/api/v1` prefix on backend routes (frontend expects it).
- No persistent run orchestration connecting tasks → policy → approval → tools → evidence → claims → report → audit.
- No Streamlit dashboard (`ui/dashboard.py` referenced in docs does not exist). The actual UI is a React SPA.
- Optional backend routers referenced in `main.py` do not exist.

---

## 3. Current Data Flow (as implemented)

```
User → FastAPI (/auth login) → JWT
User → FastAPI (/tasks) → TaskEngine.create_task (in-memory) → Plan stored in memory
User → FastAPI (/tasks/{id}/steps) → reads in-memory plan steps
User → FastAPI (/tasks/tools/all) → ToolRegistry.get_all_tools() (in-memory)
User → FastAPI (/audit/...) → queries AuditLog table in DB
```

There is **no orchestrated end-to-end flow**. There is:
- No "submit task → planner → plan → policy → approval → tool → evidence → claim verification → report" pipeline reachable through the API.
- The in-memory engines (task, policy, sandbox, retrieval, evidence, approval) are siloed and never linked by run_id in a persisted way.
- Approvals live only in process memory — they disappear on restart and are not associated with a DB-backed run or audit log.

---

## 4. Current State Flow

`app.core.task_engine.StateMachine` defines a rich state machine:
`CREATED → PLANNING → PLAN_READY → POLICY_CHECK → WAITING_APPROVAL / EXECUTING → EVIDENCE_COLLECTION → CLAIM_VERIFICATION → REPORT_GENERATION → COMPLETED`
with failure branches `FAILED`, `BLOCKED`, `CANCELLED`.

But:
- The only persisted state is the **Pydantic plan in memory** inside `TaskEngine.active_tasks`.
- The Task API currently calls `task_engine.create_research_task(...)`, which returns a Pydantic `ResearchPlan` that is not saved to the `ResearchRun` DB table (because that table does not exist).
- So "run state" is not actually persisted; on restart all in-flight runs vanish.

---

## 5. Existing APIs

### Implemented (mounted in `main.py`):
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/refresh`
- `POST /tasks/`, `GET /tasks/`, `GET /tasks/{plan_id}`, `POST /tasks/{plan_id}/steps`
- `PATCH /tasks/{plan_id}/steps/{step_id}`, `PATCH /tasks/{plan_id}`
- `GET /tasks/{plan_id}/stats`, `GET /tasks/tools/allowed`, `GET /tasks/tools/all`
- `GET /audit/logs`, `GET /audit/logs/{log_id}`, `GET /audit/statistics`, `DELETE /audit/logs`
- `GET /`, `GET /health`

### Referenced but **not mounted** (lazy imports silently skip them because the modules don't exist under `src/vtr_agent.api`):
- `/projects`, `/tools`, `/retrieval`, `/evidence`, `/approval`, `/sandbox`, `/safety`, `/verification`, `/observability`

**Important**: the frontend assumes paths like `/api/v1/auth/login`, `/api/v1/tasks`, `/api/v1/retrieval/...`, `/api/v1/evidence/...`, `/api/v1/approval/...`. Those do not currently exist.

---

## 6. Existing Database Entities (ORM)

From `src/vtr_agent/core/database/models.py`:
- `User`, `Project`, `ProjectMembership`
- `Document`, `DocumentChunk`
- `DatasetVersion`, `DatasetSplitAssignment`
- `TrainingRun`, `DistillationRun`, `QuantizationRun`
- `ModelVersion`
- `EvaluationRun`, `EvaluationResult`
- `SafetyTestCase`, `SafetyTestResult`
- `Deployment`
- `Conversation`, `Message`, `Feedback`
- `SystemMetric`
- `AuditLog`

**Missing / broken**:
- `ResearchRun` is **referenced by name** in `User.created_runs` and `Project.runs` but the class is never defined → SQLAlchemy mapper error on `Base.metadata.create_all()`.

---

## 7. Existing Tools

From `app.core.policy_engine` default registrations + `app.core.tool_registry`:

- `retriever` — Research Retrieval, LEVEL_1, no approval, readonly FS.
- `python_sandbox` — Python Sandbox, LEVEL_2, requires approval, sandbox-only FS.
- `calculator` — Math calculator, LEVEL_0, no approval.
- `visualizer` — Data Visualization, LEVEL_1, no approval, sandbox-only FS.
- `evidence_tool` — Evidence Manager, LEVEL_1.
- (plus some policy-engine tooling around `notes_analyzer`, `llm_interface` etc.)

Tool metadata (latency estimate, capabilities) lives in `app.core.tool_registry.ToolRegistry`.

---

## 8. Existing Security Controls

- JWT authentication + RBAC.
- Structured audit logging (AuditLog table).
- Policy engine with ALLOW / REQUIRE_APPROVAL / DENY decisions.
- Approval gate for high-risk tools.
- Sandbox with timeout, memory heuristic, FS access modes, violation detection heuristics, network pattern checks.
- Retrieval treats chunks as untrusted data in principle, but there is **no implemented injection detector** in the pipeline.
- CORS restricted by `ALLOWED_ORIGINS`.
- Global exception handler that hides internals.

**Gaps**:
- No LLM provider / no prompt-injection detector integrated.
- No real separation between "LLM proposes" and "app executes" — there is no LLM at all yet.
- Approval state is ephemeral (in-memory), not tied to a persisted run or audit log in a queryable way.
- `ApprovalStatus` schema missing, so the approval router imports don't resolve in some contexts.

---

## 9. Broken Components

1. **`ResearchRun` missing** — `User.created_runs` and `Project.runs` reference a class that does not exist. This causes the pytest integration error: `sqlalchemy.exc.InvalidRequestError: ... 'ResearchRun' failed to locate a name ...`
2. **Optional API routers not mounted** — `main.py` tries to import `vtr_agent.api.approval`, `.retrieval`, `.evidence`, `.tools`, etc., but those modules don't exist. They are silently skipped.
3. **Schema/contract gaps** — `src/vtr_agent.api.schemas` is missing `ApprovalStatus`, `GraphStatistics`, `ClaimRecord`, `ClaimStatus`, and a unified `EvidenceRecord` that matches what the UI and routers expect.
4. **Import path mismatch for `app.*` vs `src/vtr_agent.*`** — some files import from `vtr_agent.evidence`, some from `app.evidence`. The shim arrangement works only because `src/vtr_agent.core.*` re-export `app.*`. This is fragile.
5. **In-memory state** — task engine, policy engine, tool registry, retrieval, evidence graph, approval gate are all process-local singletons. Run state not persisted.
6. **API prefix mismatch** — backend serves at root, frontend calls `/api/v1/...`.
7. **No Streamlit dashboard** — docs/AGENTS.md tell users to run `streamlit run ui/dashboard.py`, but that file does not exist. The actual UI is a React SPA.
8. **Tests fail** — `tests/integration/test_basic.py::test_database_initialized` errors because of the `ResearchRun` issue.

---

## 10. Incorrect Dependencies

- `app.core.policy_engine.py` imports from `vtr_agent.core.config` and `vtr_agent.utils` (reverse of what you'd expect).
- `app.core.tool_registry.py` imports from `vtr_agent.core.policy_engine` and calls `policy_engine._init_default_tools()` — couples tool registry to policy engine internals.
- `app.evaluation.py` imports from `vtr_agent.core.*` and `vtr_agent.sandbox.sandbox_manager`, `vtr_agent.evidence`, `vtr_agent.retrieval` — mixed namespace usage.
- `app/retrieval_api.py` and `app/evidence_api.py` import `vtr_agent.evidence`, `vtr_agent.retrieval` but live under `app/` and are never mounted.
- Frontend `api.ts` uses `import.meta.env.VITE_API_BASE` (Vite convention) while `App.tsx` uses `process.env.REACT_APP_API_URL` (CRA convention). Mixed env patterns.

---

## 11. Missing Components

- `ResearchRun` ORM model + DB-backed run lifecycle.
- Planner / LLM integration (no model, no tool-calling loop).
- Mounted optional routers: `tools`, `retrieval`, `evidence`, `approval`, `verification`, `observability`, `sandbox`, `safety`, `projects` (under `src/vtr_agent.api` and ideally under `/api/v1`).
- DB-backed approval persistence + audit linkage.
- Evidence/claim persistence against DB.
- End-to-end run orchestrator service that ties task → plan → policy → approval → tool result → evidence → claim verification → report → audit.
- Real prompt-injection detection for retrieved/untrusted content.
- `ui/dashboard.py` if Streamlit is desired (or update docs to match React SPA reality).

---

## 12. Duplicate Components

- **Two task/policy/tool/evidence/retrieval/approval implementations in two namespaces**: `app.*` (real logic) and `src/vtr_agent.core.*` (shims that re-export `app.*`). Parallel import paths; fragile.
- **Two evidence APIs** conceptually: `app/retrieval_api.py` and `app/evidence_api.py` both include evidence endpoints. Neither mounted.
- **Two auth password-hash implementations**: `vtr_agent.utils.pwd_context` (pbkdf2_sha256) vs `vtr_agent.auth.security.pwd_context` (bcrypt). Tests use bcrypt (seeded passwords are bcrypt), but utils also defines pbkdf2 — unused/inconsistent.

---

## 13. Recommended Changes (prioritized)

### P0 — security / architecture-breaking
1. Add the missing `ResearchRun` ORM model and wire it into `User` and `Project` relationships so the DB can map and tests can run.
2. Add the missing schema types (`ApprovalStatus`, `GraphStatistics`, `ClaimRecord`, `ClaimStatus`, unified `EvidenceRecord`) so optional routers can be mounted without import errors.
3. Mount the optional API routers under `src/vtr_agent.api` (at least `tools`, `retrieval`, `evidence`, `approval`, `verification`, `observability`) with proper auth and the `/api/v1` prefix, so the frontend contract is real.
4. Make in-memory engines persist run state and approvals against the DB (at least `ResearchRun` status + audit events + approvals + evidence/claims) so the system is replayable and restart-safe.

### P1 — major workflow
5. Add a run orchestrator service implementing the required flow: task created → plan generated → plan validated → policy check → approval gate if required → tool execution → result → evidence → claim verification → report → audit → COMPLETED.
6. Add a (mock) planner interface so the architecture has a defined "LLM proposes, app executes" boundary even before a real LLM provider is wired.
7. Add injection-safety handling for retrieved/untrusted content (classification + safe handling) so retrieved documents are not treated as system instructions.

### P2 — functional issues
8. Decide UI strategy: either add a real Streamlit dashboard, or update docs/AGENTS to match the existing React SPA and fix the SPA's API base/path and schema references. For this task, keep the React SPA as canonical UI and add the backend `/api/v1` contract it expects.
9. Fix import/namespace consistency (reduce shim fragility; make `src/vtr_agent.api.*` the single mounted API surface).
10. Fix sandbox to only execute after policy+approval in the orchestrated flow, not as an open convenience function.

### P3 — UI / optimization / docs
11. Build a professional, animated React frontend theme (enterprise research-agent look) that consumes the real `/api/v1` contract, with dashboard metrics from real DB/audit data, animated run timeline, evidence graph, approvals, tool registry, settings.
12. Update README/AGENTS/docs to match the actual stack and startup commands.

---

## Appendix A — Required vs Current Flow Comparison

### Required (from spec):
```
USER → TASK → RUN_ID → PLANNER → STRUCTURED PLAN → PLAN VALIDATION →
POLICY ENGINE → ALLOW/APPROVAL/DENY → HUMAN APPROVAL WHEN REQUIRED →
TOOL REGISTRY → CONTROLLED TOOL EXECUTION →
RETRIEVAL/SANDBOX/ANALYSIS → RESULT VALIDATION → EVIDENCE →
EVIDENCE GRAPH → CLAIM EXTRACTION → CLAIM VERIFICATION →
REPORT GENERATION → FINAL ANSWER → AUDIT LOG → METRICS → RUN REPLAY
```

### Current (actual):
```
USER → /auth/login (JWT)
USER → /tasks/ (creates in-memory ResearchPlan, no ResearchRun DB row)
USER → /tasks/{id}/steps (reads/writes in-memory steps)
   (no planner, no policy-driven step flow, no run persisted)
USER → /audit/logs (reads AuditLog table — works)
   (no evidence/claim/report/approval flow reachable via API)
```

So the gap is large at the orchestration layer, even though many individual components exist.

---

## Appendix B — Critical Bugs (for fixing)

- **BUG-01**: `ResearchRun` class missing → DB mapper error → tests fail.
- **BUG-02**: Optional routers referenced in `main.py` don't exist → not mounted.
- **BUG-03**: `src/vtr_agent.api.schemas` missing `ApprovalStatus`, `GraphStatistics`, `ClaimRecord`, `ClaimStatus`, unified `EvidenceRecord`.
- **BUG-04**: Frontend API base path mismatch (`/api/v1` vs root) + missing response shapes.
- **BUG-05**: No run persistence → in-memory engines lose state on restart; not replayable.
- **BUG-06**: Approvals not linked to a persisted run/audit in a queryable way.
- **BUG-07**: Two password-hash implementations (pbkdf2 in utils, bcrypt in security) — inconsistency risk.
- **BUG-08**: No LLM/planner → "planning" state exists in StateMachine but nothing produces a plan.

---

*End of audit.*
