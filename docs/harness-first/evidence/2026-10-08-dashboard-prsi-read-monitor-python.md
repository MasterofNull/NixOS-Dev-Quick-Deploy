# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-120

## Objective
- Dashboard /api/approval-inbox degraded: AppArmor profile command-center-dashboard-api denied reading optimizer/prsi/{action-queue,approval-inbox}.json. Add a narrow read-only allow.
- Health monitor: 14 of 15 monitor-only phase-0 failures were ModuleNotFoundError (jsonschema/cryptography/pytest/fastapi/rich) because the unit ran a narrow monitorPython. Run it under the system cliPython instead; MemoryMax 768M was hit exactly, so raise it provisionally to 1536M.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Diagnosis by a Sonnet subagent (aa401a86567123075). The orchestrator made the edits directly: they are 2 small Nix edits, and the worktree git guard blocks subagent commits.

## Commands Executed
```bash
nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.security.apparmor.policies.command-center-dashboard-api.profile | rg optimizer/prsi
nix eval --raw .#...ai-stack-health-monitor.serviceConfig.ExecStart   # /run/current-system/sw/bin/python3 ...
/run/current-system/sw/bin/python3 scripts/testing/<8 formerly failing check scripts>.py   # all rc=0
```

## Validation Evidence
- The profile renders the 2 prsi read rules. All 8 formerly failing check scripts exit 0 under the system python, versus ModuleNotFoundError under monitorPython.
- 0.2.1:aidb was a transient: the aidb restart overlapped the run.

## Rollback Plan
- Revert this commit and rebuild.

## Residual Risk
- The monitor now follows /run/current-system's python. That keeps it aligned with interactive phase 0, but a cliPython regression would hit both. The 1536M cap is provisional until MemoryPeak is measured after rebuild.

## Hint Feedback
- None.
