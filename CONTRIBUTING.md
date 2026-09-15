# VTR-Agent

> **Verifiable Tool-Using Research Agent**
>
> Human-Governed, Policy-Controlled, Evidence-Verifiable Research Assistant

VTR-Agent is a research-grade AI system that combines advanced language models with controlled tool execution, human oversight, and evidence verification to produce verifiable research outputs.

## Project Overview

VTR-Agent is designed for postgraduate researchers who need:

- **Rigor**: Evidence-backed research claims
- **Safety**: Protection against prompt injection and tool abuse
- **Transparency**: Complete traceability of reasoning process
- **Collaboration**: Human-AI cooperation with clear oversight

## Key Features

### Core System Components
1. **Task Engine**: State machine for research workflow management
2. **LLM Interface**: Structured output generation with controlled tools
3. **Policy Engine**: Permission-based tool access control
4. **Approval Gates**: Human oversight for high-risk operations
5. **Evidence Graph**: Provenance tracking and claim verification
6. **Sandbox Execution**: Isolated code execution environments
7. **Safety Layer**: Prompt injection detection and prevention

### User Interface
- **Streamlit Dashboard**: Research task management and monitoring
- **Evidence Inspector**: Visual evidence graph exploration
- **Approval Interface**: Tool execution review and approval
- **Execution Trace**: Complete reasoning process visualization

### Research Integrity
- **Provenance Tracking**: Every claim linked to source evidence
- **Claim Verification**: Unsupported claims detected and blocked
- **Reproducibility**: Full experiment documentation and replay
- **Ablation Framework**: Component-by-component performance analysis

## System Architecture

```mermaid
graph TD
    subgraph UI_Layer [Streamlit Operations Interface]
        P1[1. Login / RBAC] --> P2[2. Overview Dashboard]
        P3[3. Domain Projects] --> P4[4. Task Creation]
        P5[5. Plan Review] --> P6[6. Evidence Inspection]
        P7[7. Approval Center] --> P8[8. Execution Trace]
        P9[9. Report Generation] --> P10[10. Run Replay]
    end

    subgraph API_Layer [FastAPI REST Application]
        AuthRouter[/auth]
        ProjectsRouter[/projects]
        TasksRouter[/tasks]
        ToolsRouter[/tools]
        EvidenceRouter[/evidence]
        ApprovalRouter[/approval]
        SandboxRouter[/sandbox]
    end

    subgraph Core_Layer [Application Services]
        TaskEngine[Task Engine]
        PolicyEngine[Policy Engine]
        EvidenceGraph[Evidence Graph]
        SandboxManager[Sandbox Manager]
        RetrievalService[Retrieval Service]
        SafetyEngine[Safety Engine]
    end

    UI_Layer -->|HTTP REST + Bearer JWT| API_Layer
    API_Layer --> Core_Layer
    Core_Layer --> DB[(PostgreSQL)]
```

## Getting Started

### Prerequisites

- Python 3.10 or 3.11
- PostgreSQL database
- Docker (optional, for sandboxing)

### Installation

```bash
# Clone repository
git clone https://github.com/domainforge/vtr-agent.git
cd vtr-agent

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/initialize_database.py --with-sample-data

# Run tests
pytest -v
```

### Quick Start

1. **Launch the system**:
   ```powershell
   # Terminal 1: Backend
   uvicorn app.api.main:app --reload
   
   # Terminal 2: Frontend
   streamlit run ui/dashboard.py
   ```

2. **Login** with demo credentials:
   - Username: `admin`
   - Password: `Demo@12345`

3. **Create a research task**:
   - Enter research question
   - Select allowed tools
   - Review generated plan

4. **Execute the task**:
   - Approve tool requests as needed
   - Monitor execution in real-time
   - Review evidence and claims

## Usage Examples

### Example Research Task
```
Research Question: "Compare transformer-based academic paper classification methods"

Expected Agent Actions:
1. Search research literature
2. Extract comparative evidence
3. Execute analysis on dataset
4. Generate evidence-backed claims
5. Produce verification report
```

### Approval Workflow
```
1. Task created → Planner generates structured plan
2. Plan → Policy Engine for risk assessment
3. High-risk tools → Approval gate
4. User reviews → Approve/Reject
5. Approved tools → Sandbox execution
6. Results → Evidence graph update
7. Claims → Verification against evidence
8. Report → Generation with provenance
```

### Execution Trace
```
Run #2026-00123
├── Task: Compare transformer classifiers
├── Plan:
│   ├── Step 1: Retrieve literature (risk: low)
│   ├── Step 2: Extract evidence (risk: low)
│   ├── Step 3: Run analysis (risk: medium, approval: YES)
│   └── Step 4: Generate claims (risk: low)
├── Tool Executions:
│   ├── retriever: search succeeded
│   ├── python_sandbox: analysis completed
│   └── calculator: statistical results
├── Evidence Generated:
│   ├── Paper A: transformer performance (42 pages)
│   ├── Paper B: comparison benchmark (28 pages)
│   └── Dataset: experimental results (analysis completed)
├── Claims Verified:
│   ├── SUPPORTED: Transformer X best for domain Y
│   ├── SUPPORTED: Method Z improves accuracy 15%
│   └── UNVERIFIED: Claim about method W
└── Final Report: 12 claims, 10 supported, 2 unsupported
```

## Configuration

### Environment Variables
```env
# Database
DATABASE_URL=postgresql://user:password@localhost/vtr_agent

# Security
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES=3600

# Redis (for rate limiting)
REDIS_URL=redis://localhost:6379

# ML Model
MODEL_PATH=/path/to/model

# Sandbox Configuration
SANDBOX_TIMEOUT=300
SANDBOX_MEMORY_LIMIT=4096
SANDBOX_CPU_LIMIT=2.0

# File Upload
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.txt,.pdf,.md,.csv

# Rate Limiting
RATE_LIMIT=100/minute
```

### Configuration Files

The system uses Pydantic settings with environment variable support:

- `app/core/config/settings.py`: Application configuration
- `app/core/config/auth.py`: Authentication settings
- `app/core/config/security.py`: Security policies
- `app/core/config/sandbox.py`: Sandbox execution settings

## Evaluation & Metrics

### Key Performance Indicators

#### Research Effectiveness
- **Task Success Rate**: Percentage of research tasks completed successfully
- **Unsupported Claim Rate**: Unsupported claims / total verifiable claims
- **Evidence Coverage**: Evidence supporting generated claims

#### Safety & Security
- **Prompt Injection Detection**: Direct and indirect attack prevention rate
- **Tool Abuse Prevention**: Unauthorized tool access blocking rate
- **Data Protection**: Sensitive information redaction effectiveness

#### Operational Efficiency
- **Human Approval Rate**: Percentage of tool requests requiring human approval
- **Average Latency**: Task completion time in seconds
- **Resource Utilization**: CPU and memory usage efficiency

### Baseline Comparison

The system evaluates against three baselines:

| **Baseline** | **Description** | **Safety** | **Evidence** | **Latency** |
|--------------|----------------|------------|--------------|-------------|
| **Simple LLM** | Direct LLM responses | ❌ Low | ❌ None | ✅ Fast |
| **Basic RAG** | Retrieved evidence + LLM | ⚠️ Medium | ✅ Partial | ⚠️ Medium |
| **VTR-Agent** | Full controls + evidence | ✅ High | ✅ Complete | ⚠️ High |

### Expected Research Outcomes

Based on preliminary analysis, the VTR-Agent system should:

1. **Reduce unsafe actions by >80%** compared to simple LLM
2. **Reduce unsupported claims by >70%** compared to basic RAG
3. **Add 15-30 seconds average latency** per task
4. **Require 15-20% human approval** for tool execution
5. **Maintain >90% reproducibility** across runs

## System Development Roadmap

### Phase 1: Foundation (Weeks 1-4)
- ✅ Repository setup and documentation
- ✅ Core project structure
- ✅ Basic authentication system
- ✅ Database schema and models
- ✅ CI/CD pipeline

### Phase 2: Core Components (Weeks 5-8)
- 🔄 Task Engine implementation
- 🔄 Policy Engine development
- 🔄 Tool Registry creation
- 🔄 Approval Gate system
- 🔄 Baseline systems (Simple LLM, Basic RAG)

### Phase 3: Safety & Evidence (Weeks 9-12)
- Sandbox implementation
- Evidence graph construction
- Safety controls
- Claim verification
- Human approval workflows

### Phase 4: Integration & Testing (Weeks 13-16)
- System integration
- Comprehensive testing
- Evaluation framework
- User interface development
- Documentation completion

### Phase 5: Final Deployment (Weeks 17-20)
- Docker deployment
- Production monitoring
- User training materials
- Research paper preparation
- Final system demonstration

## Testing Strategy

### Test Coverage
- **Unit Tests**: Core component testing
- **Integration Tests**: System workflow testing
- **Security Tests**: Attack scenario simulation
- **Adversarial Tests**: Prompt injection and abuse attempts
- **Evaluation Tests**: Baseline comparison and metrics

### Test Command
```bash
# Run all tests
pytest -v --tb=short

# Run unit tests only
pytest tests/unit/ -v

# Run security tests
pytest tests/security/ -v

# Run evaluation tests
pytest tests/evaluation/ -v
```

### Key Test Scenarios

#### Security Tests
1. **Prompt Injection Attack**: Block malicious instruction attempts
2. **Tool Abuse**: Prevent unauthorized tool access
3. **Data Leakage**: Test PII protection
4. **Sandbox Escapes**: Verify isolation effectiveness
5. **Authentication Bypass**: Test login security

#### Functional Tests
1. **Task Planning**: Verify structured plan generation
2. **Tool Execution**: Test policy-controlled tool use
3. **Evidence Management**: Verify provenance tracking
4. **Approval Workflow**: Test human oversight
5. **Claim Verification**: Validate evidence matching

#### Performance Tests
1. **Latency Measurement**: Track task completion times
2. **Resource Usage**: Monitor CPU and memory consumption
3. **Scalability**: Test concurrent user capacity
4. **Reliability**: Verify system availability under load

## Security & Compliance

### Threat Model Coverage

| Threat | Attack Vector | Impact | Mitigation |
|--------|---------------|--------|------------|
| **T1** Prompt Injection | Direct user input | System compromise | Policy engine + LLM filtering |
| **T2** Indirect Injection | Retrieved document content | Tool execution | Retrieval sanitization |
| **T3** Tool Abuse | Excessive permissions | Data/system damage | Permission boundaries |
| **T4** Data Leakage | Unauthenticated access | Sensitive data exposure | RBAC + encryption |
| **T5** Sandbox Escapes | Container exploit | Host compromise | Security isolation |
| **T6** Unsupported Claims | Hallucination | Research integrity | Evidence verification |

### Compliance Features

- **GDPR Compliance**: Personal data protection
- **Research Ethics**: IRB guidelines support
- **Academic Integrity**: Reproducible research practices
- **Security Standards**: Defense-in-depth architecture

### Security Controls

#### Defense in Depth
1. **Network Security**: HTTPS, rate limiting, DDoS protection
2. **Application Security**: Input validation, output encoding
3. **Authentication Security**: JWT, multi-factor auth
4. **Authorization Security**: RBAC, permission tiers
5. **Data Security**: Encryption, PII redaction
6. **Infrastructure Security**: Container isolation, network segmentation

#### Safety Controls
1. **Prompt Injection Detection**: Pattern-based and ML-based detection
2. **Tool Abuse Prevention**: Permission-based access control
3. **Sensitive Data Protection**: Regex-based PII identification
4. **Sandbox Security**: Resource limits, process isolation
5. **Audit Logging**: Immutable, tamper-evident logs

## Evaluation & Research

### Primary Research Questions

1. **RQ1**: Does policy-controlled tool execution reduce unsafe actions?
2. **RQ2**: Does evidence-graph verification reduce unsupported claims?
3. **RQ3**: What are the latency and human-effort overheads introduced by safety controls?
4. **RQ4**: Does sandboxing improve security without making legitimate research unusably slow?
5. **RQ5**: How does the proposed system perform under prompt injection and tool-abuse scenarios?

### Expected Research Contributions

1. **Novel Architecture**: First system to integrate all safety controls
2. **Evidence Graph**: Comprehensive provenance tracking
3. **Human-Loop Integration**: Measurable human-AI collaboration
4. **Ablation Framework**: Component-by-component performance analysis

### Key Metrics to Collect

#### System Metrics
- **Task Success Rate**: 85%+
- **Unsupported Claim Rate**: < 10%
- **Unsafe Action Block Rate**: 98%+
- **Human Approval Rate**: 15-20%
- **Reproducibility Score**: 90%+

#### Safety Metrics
- **Prompt Injection Detection**: 100%
- **Tool Abuse Prevention**: 99%+
- **Data Protection**: 100%
- **Sandbox Security**: 99%+

#### Performance Metrics
- **Total Latency**: < 5 minutes per task
- **Planning Latency**: < 30 seconds
- **Tool Execution Latency**: < 300 seconds
- **Resource Utilization**: < 80% CPU/Memory

## Contributing

### Development Guidelines

- **Code Quality**: Follow PEP 8, write comprehensive docstrings
- **Testing**: 90%+ test coverage, write integration and security tests
- **Documentation**: Complete docstrings, user guides, API documentation
- **Security**: Regular security reviews, dependency scanning
- **Performance**: Optimize for latency and resource usage

### Code Review Process

1. **Initial Review**: Check functionality and test coverage
2. **Security Review**: Validate security controls
3. **Performance Review**: Assess impact on system performance
4. **Documentation Review**: Ensure clear user documentation
5. **Integration Review**: Verify system compatibility

### Development Workflow

1. **Fork Repository**: Create your branch
2. **Create Feature Branch**: `git checkout -b feature/name`
3. **Implement Changes**: Write code and tests
4. **Run Tests**: Ensure all tests pass
5. **Code Review**: Get feedback from maintainers
6. **Merge**: Once approved, merge to main

## Support & Resources

### Getting Help

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Complete technical and user guides
- **Community**: Discussion forums and Slack
- **Support**: Professional support available for enterprise use

### Resources

- **API Documentation**: Full OpenAPI specification
- **Architecture Diagrams**: System design and component relationships
- **Evaluation Framework**: Benchmarks and comparison methodologies
- **Example Projects**: Sample research tasks and workflows

## Future Enhancements

### Phase 2 Roadmap

1. **Advanced ML Integration**: Fine-tuned models for specific domains
2. **Multi-Modal Support**: Image and structured data processing
3. **Cloud Deployment**: Kubernetes and serverless deployment
4. **Advanced Analytics**: Performance monitoring and optimization
5. **User Customization**: Personalized tool sets and approval workflows

### Research Expansion

1. **New Safety Mechanisms**: Continuous improvement of security controls
2. **Advanced Evidence Management**: Semantic similarity and relationship detection
3. **Human-AI Collaboration**: Adaptive approval workflows
4. **Explainable AI**: Transparent decision-making process
5. **Cross-Domain Adaptation**: Transfer learning for different research fields

## Important Notes

### System Limitations

- **Hardware Requirements**: Runs on standard research workstations
- **Model Dependencies**: Requires access to LLM APIs or local models
- **Network Requirements**: Internet access for some tools (where approved)
- **Storage Requirements**: Evidence graphs and audit logs consume disk space

### Known Issues

1. **Container Overhead**: Docker sandboxing adds latency
2. **Model Variability**: LLM responses vary between model versions
3. **Scalability**: Concurrent user handling under high load
4. **User Training**: System requires operator training for optimal use

### Future Directions

1. **Cloud Integration**: AWS/GCP/Azure deployment options
2. **Enterprise Features**: SSO, LDAP, advanced compliance
3. **Mobile Access**: Smartphone and tablet interfaces
4. **Collaboration Features**: Team workspaces and shared research
5. **Marketplace**: Community tool marketplace

---

## Acknowledgments

This project builds upon numerous open-source components and research contributions:

- **LLM Providers**: OpenAI, Anthropic, Google, Meta models
- **Libraries**: FastAPI, PyTorch, Transformers, SQLAlchemy
- **Security Tools**: Bandit, Safety, Black Duck
- **Development Tools**: Git, Docker, GitHub Actions
- **Research Papers**: Academic literature on AI safety and verification

## License

```license
MIT License

Copyright (c) 2026 DomainForge

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

*Built with ❤️ for academic research and AI safety by the DomainForge team*