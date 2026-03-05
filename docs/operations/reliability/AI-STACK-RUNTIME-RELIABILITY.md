# AI Stack Runtime Reliability

## Scope

This document covers:
- Circuit breaker configuration and behavior
- Graceful degradation modes
- Detailed health and dependency checks
- Retry/backoff policy surfaces
- Reliability test procedures

## Circuit Breakers

### Where implemented
- `ai-stack/mcp-servers/aidb/server.py`
- `ai-stack/mcp-servers/hybrid-coordinator/server.py`
- `ai-stack/mcp-servers/shared/circuit_breaker.py`
- `ai-stack/mcp-servers/shared/hybrid_client.py`

### States
- `closed`: normal operation
- `half_open`: probing recovery
- `open`: service protected, requests blocked

### Monitoring surfaces
- AIDB metrics:
  - `aidb_circuit_breaker_state`
  - `aidb_circuit_breaker_failures_total`
- Health endpoints expose breaker snapshots:
  - `GET /health` and `GET /health/detailed` (AIDB/Hybrid)

## Graceful Degradation Modes

### AIDB
- Health readiness accepts degraded mode during partial dependency loss.
- Embedding chain degrades through fallback sequence instead of hard fail.

### Hybrid Coordinator
- Can continue serving with degraded dependency status surfaced in `/health/detailed`.
- Keeps circuit breaker state and capability-discovery state visible in health payloads.

### Ralph Wiggum
- Reports `degraded` when loop engine is not running or dependencies are unhealthy.
- `/health/detailed` includes explicit dependency statuses for Hybrid, AIDB, and Aider-wrapper.

## Health/Dependency/Performance Probes

### Endpoints
- `GET /health`
- `GET /health/detailed` (AIDB/Hybrid/Ralph)

### Dependency checks (detailed)
- Hybrid: Qdrant, AIDB, llama.cpp, Redis, PostgreSQL
- Ralph: Hybrid, AIDB, Aider-wrapper

### Performance indicators (detailed)
- Hybrid: query totals, context-hit rate, model queue depth/max
- Ralph: active tasks, loop state, timeout/iteration policy

## Retry/Backoff Policy

Retry and backoff logic is implemented in shared clients and helper modules:
- `ai-stack/mcp-servers/shared/retry_backoff.py`
- `ai-stack/mcp-servers/shared/hybrid_client.py`

Operational policy:
- Retry transient network/service failures with bounded attempts.
- Prefer fail-fast + circuit breaker open state for persistent failures.
- Surface failures to telemetry and health endpoints.

## Test Procedures

### Runtime reliability checks
```bash
scripts/reliability/check-runtime-reliability.sh
```

### Existing fallback/degradation checks
```bash
scripts/testing/check-routing-fallback.sh
scripts/testing/check-mcp-health.sh
```

### Recommended post-deploy verification
```bash
scripts/quick-deploy-lint.sh --mode fast
scripts/testing/validate-runtime-declarative.sh
scripts/testing/check-prsi-phase7-program.sh
```
