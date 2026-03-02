---
name: ai-stack-qa
description: QA workflow for the NixOS-Dev-Quick-Deploy AI stack. Use when running health checks, smoke tests, or phase verification on the local AI stack.
---

# Skill: ai-stack-qa

## Description
Provides efficient QA patterns for the local AI stack harness. Prioritizes single-command batch checks over individual per-service calls to minimize token consumption.

## When to Use
- Verifying services after a deploy or restart
- Running QA plan phase checks
- Troubleshooting a failing service
- Before committing AI stack changes

## Key Commands (in order of preference)

### 1. Phase runner — use first, replaces 10-20 bash calls
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
aq-qa 0           # Phase 0: service health + ports + pings
aq-qa 1           # Phase 1: redis/postgres/qdrant/aidb/hybrid
aq-qa 0 --json    # Machine-readable output
aq-qa 0 --sudo    # Include AppArmor checks
```

### 2. Comprehensive health check — use when aq-qa isn't enough
```bash
bash scripts/ai-stack-health.sh
bash scripts/check-mcp-health.sh
```

### 3. Service-specific checks
```bash
# AIDB
curl -sf http://127.0.0.1:8002/health | python3 -m json.tool
AIDB_API_KEY=$(cat /run/secrets/aidb_api_key | tr -d '\n') \
  bash scripts/import-agent-instructions.sh

# Hybrid coordinator
curl -sf http://127.0.0.1:8003/health | python3 -m json.tool
curl -sf 'http://127.0.0.1:8003/hints?q=nixos' | python3 -m json.tool

# llama.cpp
curl -sf http://127.0.0.1:8080/health

# Qdrant
curl -sf http://127.0.0.1:6333/collections | python3 -m json.tool

# Redis
redis-cli ping && redis-cli info server | grep redis_version

# PostgreSQL
psql -U ai_user -d aidb -c '\dt'
```

### 4. Logs — use when a service fails
```bash
journalctl -u ai-aidb.service -n 30 --no-pager
journalctl -u ai-hybrid-coordinator.service -n 30 --no-pager
journalctl -u llama-cpp.service -n 20 --no-pager
```

### 5. Syntax validation before commit
```bash
python3 -m py_compile <file.py>
bash -n <file.sh>
nix-instantiate --parse <file.nix>
```

## QA Plan Reference
Full plan: `AI-STACK-QA-PLAN.md`
- Phase 21 (tooling) → do first
- Phase 0 (smoke) → `aq-qa 0`
- Phase 1 (infra) → `aq-qa 1`
- Phases 2-10 → see QA plan, run manually

## Token Efficiency Rules
1. Always run `aq-qa <phase>` before individual service checks.
2. Use `--json` when you need to parse results programmatically.
3. Only open log files if `aq-qa` reports a FAIL — don't pre-emptively read logs.
4. Trust exit codes — don't re-run checks after a pass.

## AIDB Import (Phase 11.2)
After AIDB restarts (to pick up schema migration):
```bash
sudo systemctl restart ai-aidb.service
sleep 5
AIDB_API_KEY=$(cat /run/secrets/aidb_api_key | tr -d '\n') \
  bash scripts/import-agent-instructions.sh
```

## Port Reference
| Service | Port |
|---------|------|
| Redis | 6379 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |
| llama.cpp | 8080 |
| llama-embed | 8081 |
| AIDB | 8002 |
| hybrid-coordinator | 8003 |
| ralph-wiggum | 8004 |
| switchboard | 8085 |
| Open WebUI | 3001 |
| Grafana | 3000 |
| Prometheus | 9090 |
