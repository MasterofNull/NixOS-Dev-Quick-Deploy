# Service Status

Use `systemctl`, dashboard health endpoints, and `aq-qa` as the source of truth for current service state.

## Quick Commands

```bash
aq-qa 0                                       # Layer 0: Core Services (61 checks)
aq-qa 1                                       # Layer 1: Data Stores
aq-qa 2                                       # Layer 2: Orchestration
aq-qa 3                                       # Layer 3: Agent Runtime
systemctl --failed
```

## Core Services

```bash
systemctl status ai-switchboard.service --no-pager
systemctl status ai-hybrid-coordinator.service --no-pager
systemctl status ai-aidb.service --no-pager
systemctl status llama-cpp.service --no-pager
systemctl status llama-cpp-embed.service --no-pager
systemctl status qdrant.service --no-pager
systemctl status postgresql.service --no-pager
systemctl status redis.service --no-pager
```

## Health Endpoints

```bash
curl -fsS http://127.0.0.1:8889/api/health | jq
curl -fsS http://127.0.0.1:8002/health | jq
```

Authenticated hybrid example:

```bash
HYBRID_KEY="$(sudo cat /run/secrets/hybrid_coordinator_api_key)"
curl -fsS -H "X-API-Key: $HYBRID_KEY" http://127.0.0.1:8003/stats | jq
```

## Validation

```bash
python3 -m pytest tests/integration/test_mcp_contracts.py -v
scripts/ai/aqd skill validate
bash scripts/testing/test-real-world-workflows.sh
```
