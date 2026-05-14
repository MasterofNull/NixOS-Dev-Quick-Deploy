# PAR-012: Staged Rollout and Rollback Runbook

**Owner:** hyperd / AI Ops
**Phase:** PAR-012 (Tier 5)
**Dependencies:** PAR-004 (lifecycle endpoints), PAR-007 (approval gate), PAR-009 (trust validation)
**Drill script:** `scripts/testing/drill-rollback.sh`

---

## Overview

This runbook covers the deploy → verify → rollback lifecycle for the NixOS-Dev-Quick-Deploy AI agent stack. It applies to:

- Hybrid coordinator (`ai-hybrid-coordinator.service`, port 8003)
- AIDB (`ai-aidb.service`, port 8002)
- llama.cpp inference (`llama-cpp.service`, port 8080)
- Agent skill bundles (deployed via skill registry)

---

## Staged Rollout Procedure

### Step 1: Pre-deploy checks

```bash
# Confirm all services healthy
scripts/ai/aq-qa

# Verify budget policy is active
curl -sf http://127.0.0.1:8003/control/budget/policy | python3 -m json.tool

# Check current fleet state
curl -sf http://127.0.0.1:8003/control/fleet/summary | python3 -m json.tool
```

### Step 2: Stage the rollout (canary)

Register/update the runtime with a canary deployment:

```bash
curl -sf -X POST http://127.0.0.1:8003/control/runtimes/register \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_id": "hybrid-coordinator",
    "name": "Hybrid Coordinator",
    "profile": "production",
    "deployment": {
      "image": "nixos-flake:.#hyperd-ai-dev",
      "version": "NEW_VERSION",
      "rollout_strategy": "canary",
      "canary_pct": 10,
      "notes": "Staged rollout — canary 10%"
    }
  }'
```

### Step 3: NixOS rebuild (actual service update)

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
git add <changed-files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "feat: <description>"
/run/wrappers/bin/sudo nixos-rebuild switch --flake .#hyperd-ai-dev
```

### Step 4: Verify rollout

```bash
# Check services restarted cleanly
systemctl status ai-hybrid-coordinator.service ai-aidb.service llama-cpp.service

# Confirm health endpoints
curl -sf http://127.0.0.1:8003/health | python3 -m json.tool
curl -sf http://127.0.0.1:8002/health | python3 -m json.tool

# Run smoke checks
scripts/testing/check-ai-stack-health.sh
scripts/ai/aq-qa
```

### Step 5: Promote to stable

Update the runtime status to `active`:

```bash
curl -sf -X POST http://127.0.0.1:8003/control/runtimes/hybrid-coordinator/status \
  -H "Content-Type: application/json" \
  -d '{"status": "active", "reason": "canary verified, promoted to stable"}'
```

---

## Rollback Procedure

### Immediate rollback (systemd)

```bash
# Roll back to the previous NixOS generation
/run/wrappers/bin/sudo nixos-rebuild switch --rollback

# Verify services came back
systemctl status ai-hybrid-coordinator.service ai-aidb.service llama-cpp.service
```

### API-level rollback record

```bash
curl -sf -X POST http://127.0.0.1:8003/control/runtimes/hybrid-coordinator/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "rollback: <describe issue>",
    "target_version": "<previous-version>"
  }'
```

### Verify rollback

```bash
scripts/ai/aq-qa
scripts/testing/check-ai-stack-health.sh
curl -sf http://127.0.0.1:8003/control/runtimes/hybrid-coordinator/deployments \
  | python3 -m json.tool   # should show rollback event at top
```

---

## Drill Execution

Run the full staged rollout + rollback drill (safe; uses ephemeral drill runtime):

```bash
# Live drill (requires stack running)
scripts/testing/drill-rollback.sh

# Offline validation only (no stack required)
scripts/testing/drill-rollback.sh --offline

# Options
scripts/testing/drill-rollback.sh --port 8003 --skip-cleanup
```

**Drill stages:**
1. Prerequisite checks (policy files, harness runner)
2. Register drill runtime
3. Fleet listing verification
4. Staged canary deploy (v1.0 → v1.1)
5. Deployment history verification
6. Rollback drill (v1.1 → v1.0)
7. Budget policy API round-trip
8. Cleanup (deregister drill runtime)

---

## Budget Guardrail Reference

Default limits (`config/runtime-budget-policy.json`):

| Mode | token_limit | tool_call_limit | fail_safe |
|---|---|---|---|
| default | 8,000 | 40 | abort |
| plan-readonly | 4,000 | 20 | abort |
| execute-mutating | 16,000 | 80 | warn |
| strict | 2,000 | 10 | abort |

Override at runtime:

```bash
curl -X POST http://127.0.0.1:8003/control/budget/policy \
  -H "Content-Type: application/json" \
  -d '{"default": {"token_limit": 12000, "fail_safe": "warn"}}'
```

---

## Evidence Checklist

Before closing a rollout:

- [ ] `aq-qa` output shows 0 failures
- [ ] `check-ai-stack-health.sh` exits 0
- [ ] Deployment history shows expected events (deploy + promote or rollback)
- [ ] Budget policy active and enforced
- [ ] No unexpected service restarts in `journalctl -u ai-*.service --since "1 hour ago"`
- [ ] `drill-rollback.sh` exits 0 (or `--offline` pass)
