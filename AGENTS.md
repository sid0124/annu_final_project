# AGENTS.md: VTR-Agent - Verifiable Tool-Using Research Agent

Compact guidance for agents working in this repository.

## Quickstart Commands

### Install & Initialize

```bash
# 1. Create virtual environment (required)
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full test suite
python -m pytest -v

# 4. Launch backend
python -m uvicorn vtr_agent.main:app --app-dir src --reload

# 5. Launch React frontend
cd ui
npm install
npm start
```

### Development Workflow

```bash
# Run linting
python -m ruff check app/ tests/ --fix

# Run type checking
python -m mypy app/ --ignore-missing-imports

# Run specific test categories
pytest tests/unit/ -v        # Unit tests only
pytest tests/integration/ -v  # Integration tests
pytest tests/security/ -v    # Security tests
pytest tests/adversarial/ -v # Adversarial attack tests

# Run all tests with coverage
pytest --cov=app --cov-report=xml

# Check formatting
python -m black --check .
```

## Directory Structure

```
VTR-Agent/
├── app/                    # Main application code
│   ├── api/                # FastAPI route handlers
│   ├── core/               # Core system components
│   │   ├── config/         # Configuration (settings, env vars)
│   │   ├── database/       # SQLAlchemy models & sessions
│   │   ├── logging_conf.py # Structured JSON logging
│   │   └── utils.py        # Utility functions
│   ├── auth/               # Authentication & security
│   ├── models/             # Pydantic schemas / API models
│   └── ...                # Additional modules
├── tests/                  # Test suite
│   ├── unit/               # Unit tests (isolated, no DB)
│   ├── integration/        # Integration tests (DB required)
│   ├── security/           # Security/attack tests
│   ├── adversarial/        # Prompt injection / abuse tests
│   └── evaluation/         # Benchmark / comparison tests
├── scripts/                # Utility scripts
│   ├── initialize_database.py  # DB setup & seeding
│   └── smoke_test_api.py       # API smoke tests
├── docs/                   # Documentation
│   ├── architecture/       # Architecture diagrams
│   ├── threat-model/       # Security threat model
│   ├── research/           # Research methodology
│   └── api/                # API specifications
├── .github/workflows/      # CI/CD pipelines
├── pyproject.toml          # Build system config
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
└── README.md               # Project overview & getting started
```

## Core Framework Conventions

### Architecture

- **FastAPI** for all REST APIs
- **SQLAlchemy 2.0** ORM with SQLite (dev) / PostgreSQL (production)
- **Pydantic v2** for request/response validation
- **State machine** for agent workflow coordination
- **Policy engine** controls ALL tool execution (LLM never directly controls OS)

### Database

- **Important**: `conftest.py` sets an isolated temp DB for tests:
  `DATABASE_URL=sqlite:///tmp/test_session.db`
- All models inherit from `Base` (SQLAlchemy declarative base)
- Relationships defined with proper ForeignKey constraints
- Alembic migrations tracked in `alembic.ini`
- Critical tables: `users`, `projects`, `research_runs`, `evidence_graph`, `audit_logs`

### Authentication

- **JWT tokens** with HS256 algorithm
- Login: `POST /auth/login` with username/email + password
- Token: `Authorization: Bearer <token>` header on all protected routes
- Demo credentials: `admin` / `Demo@12345`
- RBAC roles: `admin`, `researcher`, `reviewer`, `expert`, `end_user`
- Token expires in 3600 seconds (1 hour)

### API Design

- **Base URL**: `/api/v1/...` (all endpoints)
- Responses wrapped in `{"ok": bool, "message": str, "data": ...}` pattern
- Error handler never leaks internals or credentials
- All endpoints return structured error responses
- OpenAPI docs available at `/docs`

### Testing

- **Tests require** database initialization before running
- `conftest.py` creates isolated temp DB per session
- Use `auth_headers` fixture for authenticated tests
- Mark tests with `@pytest.mark.skipif(not condition, reason="...")` for conditional runs
- Security tests test prompt injection, tool abuse, sandbox escapes
- Integration tests require DB: run `python scripts/initialize_database.py --with-sample-data` first

## How to Add New Features

### 1. Define API Schema
Create/extend Pydantic models in `app/api/schemas.py`

### 2. Add Router Endpoint
Add endpoint in appropriate `app/api/*.py` file

### 3. Update Policy Engine
Ensure new tool/operation passes through policy checks in `app/core/policy_engine.py`

### 4. Add Database Model (if needed)
Extend `app/core/database/models.py`

### 5. Update Tests
Add tests in appropriate `tests/` subdirectory

### 6. Run Full Verification
```bash
python -m ruff check app/ tests/
python -m mypy app/ --ignore-missing-imports
pytest -x --tb=short  # Verify no regressions
```

## Common Gotchas

### Authentication Issues

- **401 errors**: Check `Authorization: Bearer <token>` header is present and valid
- **Token expired**: Login again; tokens expire in 1 hour
- **Wrong credentials**: Use demo `admin`/`Demo@12345` or valid user credentials
- **RBAC 403**: User lacks required role for endpoint

### Database Issues

- **Tests fail**: Run `python scripts/initialize_database.py --with-sample-data` first
- **Migration errors**: Ensure Alembic is up to date: `alembic upgrade head`
- **Connection errors**: Verify `DATABASE_URL` in `.env` file
- **Schema mismatches**: Run `python -m ruff check` to detect field issues

### Sandbox Issues

- **Sandbox timeouts**: Default 300s; increase in `config.py` if needed
- **Memory limits**: Default 4096MB; adjust based on available resources
- **Network access**: Blocked by default; enable only for approved tools
- **File system**: Read-only by default; write access requires approval

### CI/CD Issues

- **Tests in CI**: Must run `pytest` successfully on feature branch
- **Docker build**: Requires Dockerfile at root; use `docker build -t vtr-agent .`
- **Security scanning**: `bandit -r app/` and `safety check` run in CI
- **Linting**: `ruff check` must pass before merge

## Investigation Order

When investigating issues, follow this priority:

1. **Check CI logs** - Most recent build failures
2. **Review test output** - `pytest -v --tb=short` for detailed traces
3. **Inspect API responses** - Use `/docs` Swagger UI
4. **Check database** - Run `python scripts/initialize_database.py --with-sample-data`
5. **Review recent git changes** - `git log --oneline -5`
6. **Search for similar issues** - Keywords in code comments and error messages

## Key Files to Know

- `app/api/main.py` - FastAPI application entrypoint, includes all routers
- `app/core/config.py` - Pydantic settings, environment variable loading
- `app/core/database/models.py` - SQLAlchemy ORM models (all tables)
- `app/core/database/session.py` - Session management, `get_db()` dependency
- `app/core/logging_conf.py` - Structured JSON logging configuration
- `app/utils.py` - Utility functions (ID generation, password hashing)
- `app/auth/security.py` - JWT token creation/verification
- `tests/conftest.py` - Test fixtures, isolated temp DB setup
- `.github/workflows/ci.yml` - CI/CD pipeline configuration
- `scripts/initialize_database.py` - Database setup and seeding

## What NOT to Do

- ❌ Never give LLM unrestricted tool access
- ❌ Never bypass policy engine for tool execution
- ❌ Never store API keys in source code or .env (use secrets manager)
- ❌ Never directly execute LLM-generated Python in main process
- ❌ Never expose hidden chain-of-thought in UI
- ❌ Never skip the approval gate for high-risk operations
- ❌ Never ignore evidence provenance requirements
- ❌ Never disable safety controls for "convenience"

## Research Context

This project is a capstone M.Sc. Artificial Intelligence project (Semester III) targeting TRL 5-6. The system demonstrates:

- Human-governed, policy-controlled AI research assistance
- Evidence-verifiable tool use with provenance tracking
- Comprehensive safety and security controls
- Reproducible evaluation framework with baselines
- Ablation studies comparing component impacts

The research contribution focuses on the trade-off between agent autonomy vs. safety vs. verifiability vs. human effort vs. latency.

## Version & Maintenance

- **Current version**: 0.1.0
- **Python**: 3.10 or 3.11
- **License**: MIT
- **Support**: GitHub Issues for bug reports and feature requests
