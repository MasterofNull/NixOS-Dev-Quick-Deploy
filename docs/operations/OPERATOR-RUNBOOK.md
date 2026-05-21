# Operator Runbook

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-20 (Phase 58+ Update)

## Table of Contents

1. [Objective](#objective)
2. [Service Restart](#service-restart)
3. [Secret Rotation](#secret-rotation)
4. [Backup and Restore](#backup-and-restore)
5. [Monitoring and Health Checks](#monitoring-and-health-checks)
6. [Escalation](#escalation)
7. [References](#references)

## Objective

This runbook provides the minimum operator procedures required for production
operations: restart, secret rotation, backup/restore, monitoring, and escalation.

## Service Restart

```bash
# Core AI services
systemctl restart llama-cpp llama-cpp-embed ai-aidb ai-hybrid-coordinator ai-switchboard

# Verify service health
aq-qa 0                                      # Layer 0 (61 checks)
scripts/testing/check-mcp-health.sh
curl -sf http://127.0.0.1:8003/health | jq .
```

## Secret Rotation

```bash
# Validate runtime secret wiring
test -r /run/secrets/aidb_api_key
test -r /run/secrets/hybrid_coordinator_api_key
test -r /run/secrets/postgres_password

# Re-run auth and security smoke checks after rotation
scripts/testing/check-api-auth-hardening.sh
```

Detailed credential handling procedures:
- `docs/operations/procedures/CREDENTIAL-MANAGEMENT-PROCEDURES.md`

## Security Features

Current operator-facing security controls:

- Runtime secrets are sourced from `/run/secrets/*`.
- Protected hybrid endpoints require API-key headers.
- The validated runtime path keeps core services on host-local addresses.
- Auth smoke should be rerun after secret rotation and service restarts.

Recommended quick verification:

```bash
scripts/testing/check-api-auth-hardening.sh
test -r /run/secrets/hybrid_coordinator_api_key
KEY="$(sudo cat /run/secrets/hybrid_coordinator_api_key)"
curl -sf -H "X-API-Key: ${KEY}" http://127.0.0.1:8003/stats | jq .
```

## Backup and Restore

```bash
# Dry-run restore drill (safe validation)
scripts/deploy/restore-drill.sh

# Execute restore drill
scripts/deploy/restore-drill.sh --execute

# Install backup timers (if needed)
scripts/deploy/install-backup-timers.sh
```

## Monitoring and Health Checks

```bash
# Layered health (Phase 58+)
aq-qa 0                                      # Layer 0: Core Services (llama, redis, postgres)
aq-qa 1                                      # Layer 1: Data Stores (qdrant, aidb)
aq-qa 2                                      # Layer 2: Orchestration (coordinator, ralph)
aq-qa 3                                      # Layer 3: Agent Runtime (switchboard, terminal)

# Weekly performance summary
aq-report --since=7d --format=text

# Metrics endpoint
KEY="$(sudo cat /run/secrets/hybrid_coordinator_api_key)"
curl -sf -H "X-API-Key: ${KEY}" http://127.0.0.1:8003/metrics | rg 'circuit|cache|latency'
```

## Escalation

```bash
# Capture recent service errors
journalctl -u ai-hybrid-coordinator -u ai-aidb -u llama-cpp --since="30 minutes ago" -p err --no-pager

# Check failed units
systemctl --failed --no-pager
```

Escalate when:
- production health checks fail repeatedly,
- data restore drill fails,
- security/auth checks fail after rotation.

## References

- `docs/operations/procedures/AI-STACK-RUNBOOK.md`
- `docs/operations/procedures/CREDENTIAL-MANAGEMENT-PROCEDURES.md`
- `docs/architecture/AI-STACK-ARCHITECTURE.md`
- `docs/api/hybrid-openapi.yaml`
- `docs/api/aidb-openapi.json`
