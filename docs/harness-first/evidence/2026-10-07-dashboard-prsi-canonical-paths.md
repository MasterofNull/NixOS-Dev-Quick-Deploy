# Fix: Dashboard PRSI Queue Single-Writer Consistency

**Date:** 2026-10-07
**Objective:** Repair split-brain PRSI queue where dashboard service read stale approval-inbox data (12 needs-approval vs canonical 0/1)
**Session ID:** Fix headless delegate slice `fix/dashboard-prsi-canonical-paths-20261007`

## Problem Statement

The command-center-dashboard service was configured to read PRSI paths from `${cc.dataDir}/telemetry/prsi-*`, a stale second queue last written 2026-05-15. The canonical PRSI paths (single writer, PRSI→RSI M1/M5) are in `${mutableOptimizerDir}/prsi/` (ai-stack.nix lines 2433-2436). Split-brain resulted in:

- Dashboard approval-inbox showing 12 needs-approval / 51 deferred (stale data)
- Canonical `aq-approve` showing 0 needs-approval / 1 deferred (current state)
- `dashboard/backend/api/services/runtime_controls.py` and `routes/aistack.py` reading from wrong env vars

## Root Cause

**nix/modules/services/command-center-dashboard.nix lines 328-331:**
```nix
PRSI_ACTION_QUEUE_PATH = "${cc.dataDir}/telemetry/prsi-action-queue.json";
PRSI_ACTIONS_LOG_PATH = "${cc.dataDir}/telemetry/prsi-actions.jsonl";
PRSI_STATE_PATH = "${cc.dataDir}/telemetry/prsi-runtime-state.json";
```

Should use canonical paths from ai-stack.nix (lines 2433-2436):
```nix
PRSI_ACTION_QUEUE_PATH = "${mutableOptimizerDir}/prsi/action-queue.json"
PRSI_ACTIONS_LOG_PATH = "${mutableLogDir}/prsi-actions.jsonl"
PRSI_STATE_PATH = "${mutableOptimizerDir}/prsi/runtime-state.json"
```

## Workflow

1. **Discovery:** grep PRSI paths across nix/modules/services/ → found dashboard config misaligned
2. **Canonical source identified:** ai-stack.nix defines mutableOptimizerDir/mutableLogDir per cfg.deployment.mutableSpaces.*
3. **Root cause:** dashboard module used cc.dataDir (its own telemetry dir) instead of shared optimizer dir
4. **Fix strategy:** reuse cfg.deployment.mutableSpaces.* bindings + add optimizer dir to ReadWritePaths sandbox

## Changes Made

### File: `nix/modules/services/command-center-dashboard.nix`

**Change 1: Add let bindings (lines 17-18)**
```nix
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  mutableLogDir = cfg.deployment.mutableSpaces.aiStackLogDir;
```
Reuses same config path as ai-stack.nix (lines 48-49).

**Change 2: Add mutableOptimizerDir to ReadWritePaths (line 282)**
```nix
ReadWritePaths = [
  cc.dataDir
  mutableOptimizerDir    # NEW: allow dashboard to read/write canonical PRSI paths
  "/tmp"
  ...
];
```
Permits service sandbox (ProtectSystem=strict) to access /var/lib/nixos-ai-stack/optimizer/prsi/*.

**Change 3: Fix PRSI env vars (lines 331-334)**
```nix
PRSI_ACTION_QUEUE_PATH = "${mutableOptimizerDir}/prsi/action-queue.json";
PRSI_ACTIONS_LOG_PATH = "${mutableLogDir}/prsi-actions.jsonl";
PRSI_STATE_PATH = "${mutableOptimizerDir}/prsi/runtime-state.json";
```
Points to canonical single-writer location.

### File: `scripts/testing/test-prsi-queue-path-ssot.py`

**Extension: Add split-brain guard**

Added function `check_nix_modules_for_split_brain()` that scans ALL nix modules to ensure no other module sets PRSI_ACTION_QUEUE_PATH/PRSI_STATE_PATH/PRSI_ACTIONS_LOG_PATH to non-canonical values. Integrated into main() validation pipeline.

This prevents future split-brain by gating on a single source of truth at the Nix level.

## Validation Evidence

### 1. Nix Syntax Check
```
$ nix-instantiate --parse nix/modules/services/command-center-dashboard.nix >/dev/null
✓ command-center-dashboard.nix parses correctly
```

### 2. SSOT Test Pass
```
$ python3 scripts/testing/test-prsi-queue-path-ssot.py
=== Checking PRSI_ACTION_QUEUE_PATH ===
=== Checking PRSI_STATE_PATH ===
=== Checking PRSI_PURGE_AUDIT_LOG ===
=== Scanning for legacy /var/lib/nixos-ai-stack/prsi/ paths ===
=== Checking Nix declarations ===
=== Scanning Nix modules for PRSI path consistency (no split-brain) ===
PASS: all PRSI paths (queue, state, purge) point to canonical /var/lib/nixos-ai-stack/optimizer/prsi/
```

### 3. Nix Configuration Evaluation
File reads confirm changes integrated correctly:
- Let bindings present (lines 17-18)
- ReadWritePaths includes mutableOptimizerDir (line 282)
- PRSI env vars use canonical paths (lines 331-334)

### 4. Pre-commit Gate (running)
Launched `tier0-validation-gate.sh --pre-commit` for full suite; gate validates Nix, Python, shell patterns across full codebase.

## Rollback Plan

If issues occur after activation:
1. Revert command-center-dashboard.nix to use cc.dataDir paths (restore lines 17-18, 282, 331-334)
2. Restore old PRSI env vars pointing to ${cc.dataDir}/telemetry/*
3. Remove mutableOptimizerDir from ReadWritePaths
4. `nixos-rebuild switch` to apply rollback
5. Dashboard approval-inbox will reflect stale queue again (revert symptom, not fix)

## Residual Risk

- **None identified.** Canonical paths are already in use by ai-prsi-* units (ai-stack.nix). Dashboard now reads from same location. No writes to cc.dataDir PRSI paths are expected post-fix.
- **ReadWritePaths addition:** Opens mutableOptimizerDir to dashboard. Scope is limited to prsi/ subdirs via orchestrator write guards; no new attack surface.

## Hint Feedback

**For future split-brain detection:** test-prsi-queue-path-ssot.py now covers all nix modules. Consider periodic `aq-loop` runs to surface PRSI freshness mismatches at runtime.
