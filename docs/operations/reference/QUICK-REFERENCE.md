# Quick Reference Card
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-08

**System**: NixOS Hybrid AI Learning Stack  
**Runtime Model**: Declarative NixOS + systemd  
**Command Center**: `command-center-dashboard-api.service`

---

## Quick Start

```bash
# Check command center runtime
systemctl status command-center-dashboard-api.service

# Open command center
open http://127.0.0.1:8889/

# Check dashboard API health
curl http://127.0.0.1:8889/api/health

# Check aggregate stack health
curl http://127.0.0.1:8889/api/health/aggregate | jq .
```

---

## Access Points

| Resource | URL / Command |
|----------|----------------|
| Dashboard | `http://127.0.0.1:8889/` |
| Dashboard API docs | `http://127.0.0.1:8889/docs` |
| Dashboard health | `http://127.0.0.1:8889/api/health` |
| Aggregate health | `http://127.0.0.1:8889/api/health/aggregate` |
| Prometheus | `http://127.0.0.1:9090` |
| Declarative health check | `bash scripts/health/system-health-check.sh --detailed` |

---

## Running Services

```bash
# Dashboard service
systemctl status command-center-dashboard-api.service

# Core declarative AI stack
systemctl --no-pager --type=service --type=target | \
  awk '/ai-stack|ai-aidb|ai-hybrid|ai-ralph|qdrant|llama-cpp|postgresql|redis-mcp|command-center-dashboard/ {print}'
```

---

## Key Checks

```bash
# Full declarative stack check
bash scripts/health/system-health-check.sh --detailed

# AI stack focused check
bash scripts/ai/ai-stack-health.sh

# Prometheus readiness
curl http://127.0.0.1:9090/-/ready

# Dashboard aggregate health
curl http://127.0.0.1:8889/api/health/aggregate | jq '.overall_status'
```

---

## Notes

- The production command center is served by the FastAPI dashboard service on one port.
- Legacy `http.server` dashboard flows and standalone collectors are not the authoritative runtime path.
- For dashboard frontend development only, use `cd dashboard && ./start-dashboard.sh`.

## Security Features

```bash
# Runtime secret presence
test -r /run/secrets/aidb_api_key
test -r /run/secrets/hybrid_coordinator_api_key

# Auth hardening smoke
scripts/testing/check-api-auth-hardening.sh

# Authenticated hybrid probe
KEY="$(tr -d '\n' < /run/secrets/hybrid_coordinator_api_key)"
curl -sf -H "X-API-Key: ${KEY}" http://127.0.0.1:8003/stats | jq .
```

- Core services are expected on host-local ports unless you intentionally change the deployment model.
- Secrets and credentials should be managed through the repo secret workflows, not committed files.
