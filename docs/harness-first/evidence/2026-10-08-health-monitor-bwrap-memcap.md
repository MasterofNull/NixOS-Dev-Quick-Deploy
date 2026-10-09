# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-140

## Objective
- After #419, the health monitor dropped from 15 failures to 1. The remaining one is 0.10.44: the execution-cell fixture reports success=skipped-no-bwrap under the unit (green interactively), because bwrap exists only in the user profile. This adds pkgs.bubblewrap to the unit path, and sets the timeout and memory from the first full measurement (282s wall, MemoryPeak 551M).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Orchestrator, direct: a 3-attribute Nix edit derived from live unit measurement.

## Commands Executed
```bash
systemctl show -p MemoryPeak ai-stack-health-monitor   # 577843200 (551M), wall 4m42s, Result=success
python3 scripts/testing/test-execution-cell-adapter.py  # interactive: success=green
nix eval ...ai-stack-health-monitor.environment.PATH | rg bubblewrap
```

## Validation Evidence
- .agents/health-monitor/latest.json: total_failures=1 (0.10.44 skipped-no-bwrap), down from 15. The evaluated unit PATH now contains bubblewrap-0.12.0.

## Rollback Plan
- Revert the commit and rebuild.

## Residual Risk
- bwrap inside the unit sandbox (NoNewPrivileges, ProtectSystem=strict) relies on unprivileged user namespaces, which work interactively. To be confirmed by the next monitor run after rebuild.

## Hint Feedback
- None.
