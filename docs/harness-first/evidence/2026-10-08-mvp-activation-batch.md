# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-220

## Objective
- Owner: turn on every implemented feature that is ready to test (MVP; enabled ≠ done). This batch is SWB_ADAPTIVE_LOCAL_BUDGET=1, AQ_PRM_STEERING=1 (coordinator env and the delegate-to-local export; inert without AQ_EDIT_VERIFY_CMD), and shellCompletions + motdReport. Left OFF with reasons: QUERY_EXPANSION_ENABLED (no consumer reads it) and metaOptimization (its migrations and routing_log table don't exist, so it would fail at runtime).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (multi-module activation, per-item eval and runtime checks). The orchestrator reviewed the diff and re-ran the tests.

## Commands Executed
```bash
python3 scripts/testing/test-switchboard-adaptive-local-budget.py   # ok (9 cases)
python3 scripts/testing/test-prm-steering.py                        # 10/10
nix build .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel   # exit 0
```

## Validation Evidence
- Each item's unit env/etc entry was proven by nix eval. Live-verify commands and kill switches are in .agent/ACTIVATION-AUDIT.md (MVP activation batch 2026-10-08), labelled "enabled for MVP testing -- development continues".

## Rollback Plan
- Per-item kill switches (see ACTIVATION-AUDIT), or revert the commit.

## Residual Risk
- PRM steering only acts on tasks that supply a verify command. The adaptive budget clamps local max_tokens when the slot is busy (400), which may truncate long local answers under load.

## Hint Feedback
- None.
