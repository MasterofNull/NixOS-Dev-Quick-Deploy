# AI-Optimizer

**Multi-Model LLM System with Constraint-Engineered Development (CED)**

A production-ready AI orchestration platform featuring three specialized LLM models working in parallel, complete monitoring with Grafana/Prometheus, and comprehensive RAG capabilities.

---

## 🚀 Quick Start

```bash
# One-command deployment
./deploy.sh

# Access Grafana dashboards
open http://localhost:3001  # admin/admin

# View system status
cat FINAL_STATUS.md
```

**New here?** → Read [START_HERE.md](START_HERE.md) for onboarding

**AI Agent?** → Read [AGENTS.md](../../AGENTS.md) for comprehensive training

---

## 🎯 What Is This?

AI-Optimizer is a local LLM orchestration system that implements **Constraint-Engineered Development (CED)** - a methodology where multiple AI perspectives can be blended when needed.

### Default Model

1. **Qwen3-4B-Instruct** (port 8080)
   - **Role:** General reasoning & task coordination
   - **Use for:** Planning, high-level design, requirement analysis

Additional Lemonade instances can be enabled if you want specialized model routing.

### Architecture

```
┌─────────────────────────────────────┐
│  Grafana  │ Prometheus │ MCP Server │
│   :3001   │   :9090    │   :8091    │
└─────────────┬───────────────────────┘
              │ monitors & orchestrates
       ┌─────────────┐
       ▼             │
     Qwen3-4B        │
      :8080          │
       │             │
       └─────────────┘
              │ inference
              ▼
         Consensus Response
```

---

## 📊 System Status

**Version:** Production v1.0
**Status:** ✅ Fully Operational
**Last Updated:** 2025-12-03

### Components

| Service | Status | Port | Purpose |
|---------|--------|------|---------|
| **PostgreSQL** | 🟢 Running | 5432 | Main database + pgvector |
| **Redis** | 🟢 Running | 6379 | Cache & sessions |
| **Prometheus** | 🟢 Running | 9090 | Metrics collection |
| **Grafana** | 🟢 Running | 3001 | Visualization (5 dashboards) |
| **MCP Server** | 🟢 Running | 8091 | RAG + orchestration |
| **Qwen3-4B** | 🟢 Running | 8080 | General reasoning model |

---

## 📖 Documentation

### Essential Docs (Root Directory)

- **[AGENTS.md](../../AGENTS.md)** - Complete agent training & system guide
- **[QUICK_START.md](QUICK_START.md)** - Fast deployment guide
- **[START_HERE.md](START_HERE.md)** - New user onboarding
- **[FINAL_STATUS.md](FINAL_STATUS.md)** - Current system status

### Complete Documentation

📂 **[docs/README.md](docs/README.md)** - Full documentation index

**Key Sections:**
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Complete deployment
- [Grafana Setup](docs/GRAFANA_SETUP_COMPLETE.md) - Monitoring config
- [API Endpoints](docs/API_ENDPOINTS.md) - API reference
- [System Completion Report](docs/SYSTEM_COMPLETION_REPORT.md) - Architecture details
- [Development Archive](docs/archive/) - Historical reports
- [Agent Onboarding](docs/agent-onboarding/) - Agent training materials

---

## 🔧 Features

### Constraint-Engineered Development (CED)
- Parallel inference across 3 specialized models
- Consensus synthesis for improved quality
- Reduced hallucinations through cross-validation
- Specialized expertise per task type

### Monitoring & Observability
- Real-time metrics with Prometheus
- 5 Grafana dashboards for visualization
- Model performance comparison
- 30-day metrics retention

### RAG System
- PostgreSQL + pgvector for embeddings
- Document ingestion pipeline
- TimescaleDB for time-series data
- Design decisions database

### Automation
- One-command deployment (`./deploy.sh`)
- Automated health checks
- Database migrations
- Container orchestration

---

## 💻 Usage

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | http://localhost:3001 | admin/admin |
| **Prometheus** | http://localhost:9090 | (none) |
| **Redis Insight** | http://localhost:5540 | (none) |

### API Endpoints

```bash
# Lemonade (General reasoning)
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'

# MCP Server (CED parallel inference)
curl http://localhost:8091/inference \
  -H "Content-Type: application/json" \
  -d '{"task":"Generate and review a binary search function"}'
```

### Using CED

When CED is enabled (`CONSTRAINT_ENGINEERED_DEVELOPMENT=true`), the MCP server automatically:
1. Distributes requests to all 3 models in parallel
2. Each model processes with its specialization
3. Synthesizes responses into consensus output
4. Returns the best-of-three result

---

## 🚀 Deployment

### Quick Deployment

```bash
# Full automated deployment
./deploy.sh

# Options:
./deploy.sh --quick          # Skip builds, use cached images
./deploy.sh --reset          # Clean slate deployment
./deploy.sh --install-deps   # Install prerequisites first
```

### Prerequisites

- Podman or Docker
- Python 3.11+
- 32-64GB RAM recommended
- 100GB disk space for models

### What `deploy.sh` Does

1. ✅ Checks prerequisites
2. ✅ Sets up environment and secrets
3. ✅ Builds all container images
4. ✅ Starts infrastructure services
5. ✅ Initializes database with migrations
6. ✅ Seeds CED configuration
7. ✅ Starts all 3 LLM models
8. ✅ Starts MCP server and exporters
9. ✅ Runs validation
10. ✅ Generates deployment report

**Result:** Fully operational stack in ~10-15 minutes

---

## 📈 Monitoring

### Grafana Dashboards

Access at http://localhost:3001 (admin/admin)

**Available Dashboards:**
1. **Model Performance Comparison** - Side-by-side comparison of all 3 models
2. **AI-Optimizer Complete** - Full stack overview
3. **AIDB Overview** - MCP server & RAG metrics
4. **Lemonade Health** - Primary model monitoring
5. **Run Logs** - Historical log analysis

### Prometheus Metrics

- **Model exporters:** Ports 9100, 9101, 9102
- **Scrape interval:** 15 seconds
- **Retention:** 30 days
- **Query UI:** http://localhost:9090

---

## 🤖 For AI Agents

**Primary Training Document:** [AGENTS.md](../../AGENTS.md)

This document includes:
- Complete system architecture
- CED methodology (section 4.5)
- All model endpoints and roles
- CodeMachine-CLI integration
- Usage patterns and best practices
- Database schema and RAG system
- Performance monitoring

**Quick Reference:** [docs/AGENT_ONBOARDING_INDEX.md](docs/AGENT_ONBOARDING_INDEX.md)

---

## 🛠️ Development

### Project Status

- ✅ **Development Stage:** Complete
- ✅ **Production Status:** Ready
- ✅ **Monitoring:** Fully configured
- ✅ **Documentation:** Comprehensive
- ✅ **Automation:** One-command deployment

### Project Goals

1. ✅ NixOS development assistance
2. ✅ Multi-model LLM orchestration (CED)
3. ✅ Complete observability stack
4. ✅ RAG system with pgvector
5. ✅ Agent training & collaboration

### Architecture Decisions

See [docs/development/](docs/development/) for:
- Stack modernization history
- Migration plans
- Technical decisions
- Improvement summaries

---

## 🔍 Troubleshooting

### Dashboards Empty?

Dashboards populate with data as models receive requests. To generate initial metrics:

```bash
python3 scripts/generate_test_metrics.py
```

### Models Not Responding?

Models load on first request (can take 30-60s). Be patient on initial request.

### Can't Login to Grafana?

- Default credentials: admin/admin
- If locked out, wait 5 minutes
- Check logs: `podman logs grafana`

### More Help

See [FINAL_STATUS.md](FINAL_STATUS.md) for complete troubleshooting guide.

---

## 📦 Repository Structure

```
AI-Optimizer/
├── README.md (this file)           # Project overview
├── AGENTS.md                       # Agent training guide
├── QUICK_START.md                  # Fast deployment
├── START_HERE.md                   # New user onboarding
├── FINAL_STATUS.md                 # Current system status
├── deploy.sh                       # One-command deployment
├── docker-compose.yml              # Container orchestration
├── mcp_server/                     # MCP server & CED engine
├── scripts/                        # Automation scripts
├── deployment/                     # Deployment configs
│   ├── grafana/                    # Grafana dashboards & provisioning
│   ├── prometheus/                 # Prometheus config
│   └── postgres/                   # Database migrations
├── docs/                           # Complete documentation
│   ├── README.md                   # Documentation index
│   ├── archive/                    # Historical reports
│   ├── development/                # Development docs
│   └── agent-onboarding/          # Agent training
└── data/                           # Persistent data
```

---

## 📄 License

[Specify license here]

---

## 🙏 Acknowledgments

- **Constraint-Engineered Development (CED)** methodology from [rootcx.com](https://rootcx.com/blog/constraint-engineered-development)
- **Models:** Qwen, Deepseek teams for excellent open-source models
- **Infrastructure:** Grafana, Prometheus, PostgreSQL communities

---

## 📞 Support

- **Documentation:** [docs/README.md](docs/README.md)
- **System Status:** [FINAL_STATUS.md](FINAL_STATUS.md)
- **Issues:** [Report an issue](#)

---

**Status:** ✅ Production Ready
**Last Updated:** 2025-12-03
**Version:** 1.0.0
