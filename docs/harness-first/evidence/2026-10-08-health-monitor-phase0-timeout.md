# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-003

## Objective
- Make QA phase 0 actually complete in the scheduled ai-stack-health-monitor (every run timed out at 120s; unit pinned at MemoryMax 256M with swap), so phase-0 checks execute in real monitoring.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementer: Claude Haiku 4.5. Orchestrator re-measured: the delegate's 384M figure had no RSS measurement behind it (its /usr/bin/time output lacked max RSS); measured peak child RSS 504MB, wall 171s → corrected sizing.

## Commands Executed
```bash
python3 -c 'subprocess.run([... harness_runner.py 0 --json]); getrusage(RUSAGE_CHILDREN)'   # rc=0 wall=171s max_child_rss=504MB
python3 scripts/testing/test-ai-stack-health-monitor.py
nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.services.ai-stack-health-monitor.serviceConfig
```

## Validation Evidence
- Live latest.json before: phase 0 "harness_runner.py 0 --json timed out after 120 seconds" (every 15-min run ~2:00 wall).
- Measured: wall 147–171s, peak child RSS 504MB.
- New: HARNESS_TIMEOUT_S=430 (env, default in script), TimeoutStartSec=490, MemoryMax=768M; test passes; nix eval confirms.

## Rollback Plan
- Revert; nixos-rebuild switch.

## Residual Risk
- Phase 0 at ~3 min per 15-min cycle is heavy for an APU; consider a lighter monitored subset later. Live proof after rebuild: latest.json phase 0 status ok and QA ids (e.g. 0.10.57/0.10.58) present.

## Hint Feedback
- No aq-hints consulted.
