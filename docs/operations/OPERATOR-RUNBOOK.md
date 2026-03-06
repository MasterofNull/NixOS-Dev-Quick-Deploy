# Operator Runbook

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-06

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
systemctl restart llama-cpp llama-cpp-embed ai-aidb ai-hybrid-coordinator

# Verify service health
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
scripts/testing/test-prompt-injection-resilience.sh
```

Detailed credential handling procedures:
- `docs/operations/procedures/CREDENTIAL-MANAGEMENT-PROCEDURES.md`

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
# MCP/runtime health
scripts/testing/check-mcp-health.sh
scripts/testing/check-prsi-phase7-program.sh

# Weekly performance summary
scripts/ai/aq-report --since=7d --format=text

# Metrics endpoint
KEY="$(tr -d '\n' < /run/secrets/hybrid_coordinator_api_key)"
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
