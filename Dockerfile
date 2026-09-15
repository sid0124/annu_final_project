# VTR-Agent Docker Configuration

## Dockerfile

```dockerfile
# Stage 1: Build Python application
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY scripts/ scripts/
COPY docs/ docs/

# Stage 2: Runtime
FROM python:3.11-slim

# Create app user (non-root)
RUN useradd -m vtruser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# Copy application code
COPY --from=builder /app/app/ app/
COPY --from=builder /app/scripts/ scripts/
COPY --from=builder /app/docs/ docs/

# Set permissions
RUN chown -R vtruser:vtruser /app

# Switch to non-root user
USER vtruser

# Expose ports
EXPOSE 8000 8501

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Startup command
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## docker-compose.yml

```yaml
version: "3.8"

services:
  # Backend API
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://vtruser:vtrpass@db/vtr_agent
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENVIRONMENT=production
    depends_on:
      - db
      - redis

  # Database
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=vtr_agent
      - POSTGRES_USER=vtruser
      - POSTGRES_PASSWORD=vtrpass
    volumes:
      - db_data:/var/lib/postgresql/data

  # Redis (for rate limiting)
  redis:
    image: redis:7
    ports:
      - "6379:6379"

  # Frontend
  frontend:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DATABASE_URL=postgresql://vtruser:vtrpass@db/vtr_agent
      - ENVIRONMENT=production
    depends_on:
      - backend

  # Monitoring (optional)
  # prometheus:
  #   image: prom/prometheus
  #   ports:
  #     - "9090:9090"
  #   volumes:
  #     - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  # grafana:
  #   image: grafana/grafana
  #   ports:
  #     - "3000:3000"
  
volumes:
  db_data:
```

## Environment Configuration

### .env.example

```env
# Database
DATABASE_URL=sqlite:////tmp/vtr_agent.db

# Security
JWT_SECRET_KEY=change-this-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES=3600

# Redis (for rate limiting and caching)
REDIS_URL=redis://localhost:6379/0

# Server
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:8501

# Sandbox
SANDBOX_TIMEOUT=300
SANDBOX_MEMORY_LIMIT=4096
SANDBOX_CPU_LIMIT=2.0

# ML Model
MODEL_PATH=/app/models
MODEL_MAX_LENGTH=2048
MODEL_BATCH_SIZE=8

# Retrieval
RETRIEVAL_TOP_K=5
RETRIEVAL_CHUNK_SIZE=800
RETRIEVAL_OVERLAP=100

# Evidence
EVIDENCE_MAX_CLAIMS=100
EVIDENCE_MAX_SOURCES=50

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=vtr_agent.log

# Monitoring
OTEL_SERVICE_NAME=vtr-agent
OTEL_SERVICE_VERSION=0.1.0

# File upload
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.txt,.pdf,.md,.csv,.docx

# Approval workflows
APPROVAL_REQUIRED_RISK_LEVELS=1,2
APPROVAL_TIMEOUT=3600
```

## CI/CD Pipeline (GitHub Actions)

The CI/CD pipeline is defined in `.github/workflows/ci.yml` and includes:

1. **Test**: Install dependencies, run linting, type checks, unit tests, integration tests
2. **Security Scan**: Run bandit and safety scans
3. **Docker Build**: Build and push Docker image
4. **Quality Gate**: Ensure all tests pass before merge

## Deployment Checklist

### Pre-Deployment
- [ ] Set up PostgreSQL database
- [ ] Configure Redis for rate limiting
- [ ] Generate JWT secret key
- [ ] Set up environment variables
- [ ] Test database migrations: `alembic upgrade head`
- [ ] Verify sandbox Docker availability
- [ ] Test with demo credentials: `admin`/`Demo@12345`

### Post-Deployment
- [ ] Access API at `http://localhost:8000/docs`
- [ ] Access Streamlit UI at `http://localhost:8501`
- [ ] Login with demo credentials
- [ ] Run initial test: `pytest -x --tb=short`
- [ ] Verify audit logging is working
- [ ] Check sandbox execution with test cases
- [ ] Verify evidence graph is populated

### Production Considerations
- **Database**: Use PostgreSQL with regular backups
- **Secrets**: Use Kubernetes secrets or Docker secrets for JWT_KEY
- **Rate Limiting**: Configure Redis connection and rate limits
- **Monitoring**: Set up OpenTelemetry collector and Grafana
- **Backup**: Regular database snapshots
- **Scaling**: Multiple backend instances behind load balancer
- **CDN**: Static asset serving for frontend

## MLOps Integration

### Model Tracking with MLflow

The system integrates with MLflow for experiment tracking:

```bash
# Start MLflow tracking server
mlflow server --host 0.0.0.0 --port 5000

# Log experiments
export MLFLOW_TRACKING_URI=http://localhost:5000

# In your research runs:
import mlflow
mlflow.start_run()
# ... run research ...
mlflow.end_run()
```

### Experiment Configuration

 experiments are configured with:

```yaml
experiment:
  name: full_system_v1
  seed: 42
  
retrieval:
  top_k: 5
  chunk_size: 800
  
evaluation:
  repetitions: 5
  
safety:
  timeout: 300
  memory_limit: 4096
```

## Monitoring & Observability

### OpenTelemetry Setup

```bash
# Install OpenTelemetry
pip install opentelemetry-api opentelemetry-sdk

# Configure instrumentation
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider

# Set up resource attributes
resource = Resource.create({
    "service.name": "vtr-agent",
    "service.version": "0.1.0",
    "deployment.environment": "production"
})

# Configure tracer provider
trace.set_tracer_provider(TracerProvider(resource=resource))
meter_provider = MeterProvider(resource=resource)
metrics.set_meter_provider(meter_provider)

# Instrument the application
# import vtr_agent.core.logging_conf  # This sets up structured logging
```

### Prometheus Metrics

Key metrics to expose:

```
vtr_agent_task_success_total{baseline="simple_llm"} 1
vtr_agent_task_success_total{baseline="basic_rag"} 1
vtr_agent_task_success_total{baseline="vtr-agent"} 1

vtr_agent_unsupported_claim_rate{baseline="simple_llm"} 0.4
vtr_agent_unsupported_claim_rate{baseline="basic_rag"} 0.2
vtr_agent_unsupported_claim_rate{baseline="vtr-agent"} 0.08

vtr_agent_unsafe_action_block_rate{baseline="basic_rag"} 0.2
vtr_agent_unsafe_action_block_rate{baseline="vtr-agent"} 0.95

vtr_agent_human_effort{baseline="simple_llm"} 0.0
vtr_agent_human_effort{baseline="basic_rag"} 0.5
vtr_agent_human_effort{baseline="vtr-agent"} 0.3

vtr_agent_latency_ms{baseline="simple_llm"} 500
vtr_agent_latency_ms{baseline="basic_rag"} 1000
vtr_agent_latency_ms{baseline="vtr-agent"} 2000
```
Now let me create the Dockerfile and docker-compose.yml for deployment:
<tool_call>
<function=write>
<parameter=content>
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY scripts/ scripts/
COPY docs/ docs/

EXPOSE 8000 8501

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]