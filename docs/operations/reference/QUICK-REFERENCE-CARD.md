# AI Stack Quick Reference Card

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-08

## Critical Locations

```text
Project root: ~/Documents/NixOS-Dev-Quick-Deploy
Main README: README.md
Operator runbook: docs/operations/OPERATOR-RUNBOOK.md
Quick reference: docs/operations/reference/QUICK-REFERENCE.md
Nix options: nix/modules/core/options.nix
AI role wiring: nix/modules/roles/ai-stack.nix
Endpoint config: config/service-endpoints.sh
```

## Primary Endpoints

```text
Dashboard UI/API: http://127.0.0.1:8889
AIDB API:        http://127.0.0.1:8002
Hybrid API:      http://127.0.0.1:8003
llama.cpp:       http://127.0.0.1:8080
Embeddings:      http://127.0.0.1:8081
Qdrant:          http://127.0.0.1:6333
PostgreSQL:      127.0.0.1:5432
Redis:           127.0.0.1:6379
```

## 30-Second Checks

```bash
bash scripts/health/system-health-check.sh --detailed
bash scripts/ai/ai-stack-health.sh
aq-qa 0 --json
aq-qa 1 --json
python3 -m pytest tests/integration/test_mcp_contracts.py -v
```

## Service Status

```bash
systemctl --user --failed
systemctl --failed
systemctl status command-center-dashboard-api.service --no-pager
systemctl status ai-hybrid-coordinator.service --no-pager
systemctl status ai-prsi-orchestrator.service --no-pager
```

## API Smoke

```bash
curl -fsS http://127.0.0.1:8889/api/health | jq
curl -fsS http://127.0.0.1:8889/api/health/aggregate | jq
curl -fsS http://127.0.0.1:8889/api/ai/metrics | jq
curl -fsS http://127.0.0.1:8002/health | jq
```

Hybrid endpoints that require auth:

```bash
HYBRID_KEY="$(sudo cat /run/secrets/hybrid_coordinator_api_key)"
curl -fsS -H "X-API-Key: $HYBRID_KEY" http://127.0.0.1:8003/stats | jq
```

## PRSI Checks

```bash
systemctl status ai-prsi-orchestrator.timer --no-pager
systemctl status ai-prsi-orchestrator.service --no-pager
python3 scripts/automation/prsi-orchestrator.py cycle --since=1d --execute-limit=5 --dry-run
```

## Real-World Workflow Smoke

```bash
scripts/ai/aqd skill validate
bash scripts/testing/test-real-world-workflows.sh
```

## Canonical Docs

- `README.md`
- `docs/operations/OPERATOR-RUNBOOK.md`
- `docs/operations/reference/QUICK-REFERENCE.md`
- `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
- `docs/agent-guides/01-QUICK-START.md`
- `docs/agent-guides/02-SERVICE-STATUS.md`
- `docs/agent-guides/20-LOCAL-LLM-USAGE.md`
