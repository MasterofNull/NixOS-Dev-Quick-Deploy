# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-030

## Objective
- nvd-sync.service failed at 00:19:29 during the owner's nrs ("AIDB not available"). The unit already orders After=ai-aidb.service, but AIDB reaches "active" before its HTTP API answers, and the script checked /health once and exited 1, leaving a failed unit on every rebuild that coincides with the timer. Fix: a bounded /health wait (36 x 5s = 180s) before failing.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Orchestrator, direct: a 10-line producer fix found during deploy verification.

## Commands Executed
```bash
journalctl -u nvd-sync   # ERROR: AIDB not available (00:19:29, during nrs)
nix build ...systemd.units."nvd-sync.service".unit   # ok
bash -n <generated ExecStart script>                  # ok; contains the bounded wait
```

## Validation Evidence
- The unit builds and the script is syntactically valid. It is not executed here (it performs a live CVE sync and writes root-owned logs). It is verified on the next timer run, or with `sudo systemctl start nvd-sync`.

## Rollback Plan
- Revert the commit.

## Residual Risk
- A genuinely down AIDB now takes 180s to fail instead of failing instantly (within TimeoutStartSec=15min).

## Hint Feedback
- None.
