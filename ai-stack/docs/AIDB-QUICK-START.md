# AI-Optimizer Quick Start Guide

## 🚀 One-Command Deployment

```bash
./deploy.sh
```

That's it! The script handles everything automatically.

---

## ⚡ Quick Commands

### Deployment

```bash
# First-time deployment (full build)
./deploy.sh

# Fast deployment (use cached images)
./deploy.sh --quick

# Clean slate deployment
./deploy.sh --reset
```

### Health Checks

```bash
# Comprehensive health check
./scripts/test_services.sh

# Quick model check
for port in 8080; do
  curl -sf http://localhost:$port/health && echo "Port $port: OK"
done

# Container status
podman ps | grep -E "llama-cpp|postgres|redis|prometheus|grafana"
```

### Benchmarking

```bash
# Run all benchmarks
./scripts/benchmark_models.py --suite comprehensive

# Code generation only
./scripts/benchmark_models.py --suite code_generation

# Specific models
./scripts/benchmark_models.py --models "Qwen2.5-Coder" --suite code_generation
```

### Snapshots

```bash
# Create snapshot
./scripts/manage_snapshots.py create --name baseline --with-prometheus

# List snapshots
./scripts/manage_snapshots.py list

# Compare snapshots
./scripts/manage_snapshots.py compare baseline-v1 optimized-v2
```

### Monitoring

```bash
# Archive metrics
./scripts/archive_prometheus_metrics.py --hours 24 --aggregate hourly

# Check Prometheus targets
curl -sf http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"'
```

---

## 🌐 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Grafana | http://localhost:3001 | Dashboards |
| Prometheus | http://localhost:9090 | Metrics |
| Redis Insight | http://localhost:5540 | Cache viewer |
| Qwen3-4B | http://localhost:8080 | General reasoning |
| MCP Server | http://localhost:8091 | RAG + orchestration |

---

## 🔧 Container Management

```bash
# View logs
podman logs llama-cpp

# Restart service
podman restart llama-cpp

# Stop all services
podman-compose down

# Start all services
podman-compose up -d

# Rebuild specific service
podman-compose build llama-cpp && podman-compose up -d llama-cpp
```

---

## 📊 Database Access

```bash
# Connect to PostgreSQL
podman exec -it ai-optimizer_postgres_1 sh -c \
  'export PGPASSWORD=$(cat /run/secrets/postgres_password) && psql -U mcp -d mcp'

# Quick query
podman exec ai-optimizer_postgres_1 sh -c \
  'export PGPASSWORD=$(cat /run/secrets/postgres_password) && \
   psql -U mcp -d mcp -c "SELECT * FROM model_benchmarks ORDER BY created_at DESC LIMIT 5;"'

# View CED configuration
podman exec ai-optimizer_postgres_1 sh -c \
  'export PGPASSWORD=$(cat /run/secrets/postgres_password) && \
   psql -U mcp -d mcp -c "SELECT * FROM design_decisions WHERE id=100;"'
```

---

## 🎯 Common Workflows

### Initial Setup

```bash
# 1. Deploy
./deploy.sh

# 2. Wait for completion (~20 min first time)

# 3. Verify health
./scripts/test_services.sh

# 4. Create baseline
./scripts/manage_snapshots.py create --name baseline --with-prometheus

# 5. Access Grafana
open http://localhost:3001
```

### Daily Operations

```bash
# Morning health check
./scripts/test_services.sh

# Run benchmarks (weekly)
./scripts/benchmark_models.py --suite comprehensive

# Archive metrics (daily via cron)
./scripts/archive_prometheus_metrics.py --hours 24 --aggregate hourly
```

### Troubleshooting

```bash
# Model not responding
podman logs llama-cpp
podman restart llama-cpp

# Database issues
podman logs ai-optimizer_postgres_1
podman exec ai-optimizer_postgres_1 pg_isready -U mcp

# Prometheus not scraping
curl http://localhost:9090/api/v1/targets
podman restart prometheus

# Clean restart
podman-compose down
podman-compose up -d
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `deploy.sh` | One-command deployment |
| `.env` | Environment configuration |
| `secrets/postgres_password` | Database password |
| `docker-compose.yml` | Service definitions |
| `deployment/prometheus/prometheus.yml` | Metrics config |
| `deployment/postgres/migrations/` | Database schema |
| `mcp_server/parallel_inference.py` | CED engine |

---

## 💡 Tips

- Use `--quick` flag for fast restarts
- Models are cached in `~/.cache/huggingface/`
- Create snapshots before major changes
- Archive metrics daily to PostgreSQL
- Check Grafana dashboards for trends
- All data persists in Podman volumes

---

## 🆘 Help

```bash
# Script help
./deploy.sh --help
./scripts/benchmark_models.py --help
./scripts/manage_snapshots.py --help

# View logs
podman-compose logs -f [service]

# Container status
podman ps -a

# System resources
podman stats
```

---

## 📚 Documentation

- **AUTOMATION_COMPLETE.md** - Full automation guide
- **SYSTEM_FULLY_OPERATIONAL.md** - System overview
- **docs/MODEL_MONITORING_AND_COMPARISON.md** - Monitoring details
- **docs/CODEMACHINE_INTEGRATION_COMPLETE.md** - CED integration

---

**Everything you need in one place!** 🎉
