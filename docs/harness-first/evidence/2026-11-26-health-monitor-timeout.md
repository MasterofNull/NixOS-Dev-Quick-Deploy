# Health monitor timeout and memory headroom

## Objective
Clear the stale known-failing exemption for `scripts/testing/test-ai-stack-health-monitor.py` and give the health monitor unit real memory headroom.

Root cause of the exemption: it recorded a failure from before 974f2a608, which already set `TimeoutStartSec = "765"` (HARNESS_TIMEOUT_S 705 + 60s margin). The producer was fixed; the ci-checks.json exemption was never removed. The test rule (harness timeout + margin) is right and its 490 floor sits below 765, so the test is unchanged.

Second finding: the live unit peaked at 1.2G against `MemoryMax=1280M` (~94%). An OOM kill would silence the alert pipeline.

## Workflow/Session IDs
Headless fix slice, worktree `agent-a6fa7ac5263cad78a`, branch `worktree-agent-a6fa7ac5263cad78a` from origin/main 5e254f5c1. Changes staged, not committed.

## Delegation Decision
Implemented directly by the delegated slice agent (bounded, two-file config change plus one Nix constant); no further sub-agents.

## Commands Executed
- `python3 scripts/testing/test-ai-stack-health-monitor.py`
- `systemctl show ai-stack-health-monitor.service -p TimeoutStartUSec`
- `journalctl -u ai-stack-health-monitor --since -3d` and `--since -14d` (timeout, OOM, memory peak)
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix`
- `scripts/governance/run-ci-checks.sh --all --only ai-stack-health-monitor-tests`
- `scripts/governance/tier0.d/check-ci-test-coverage.sh`, `scripts/governance/check-cross-surface-contract.py`

Changes:
- `config/ci-checks.json`: removed the known-failing entry; added declared check `ai-stack-health-monitor-tests`.
- `.github/workflows/test.yml`: added `--only ai-stack-health-monitor-tests`.
- `nix/modules/roles/ai-stack.nix`: `MemoryMax` 1280M -> 2048M (about 1.7x the observed 1.2G peak, 7.5% of the 27 GB budget, and the unit runs only briefly every 15 minutes).

## Validation Evidence
- Live `TimeoutStartUSec` = 12min 45s (765s). Last run 2026-11-26 12:37: 2m17s wall, Result=success. No timeout or killed lines in 3 days.
- 14-day journal: no OOM or killed events for this unit; memory peaks seen about 1.0G to 1.2G.
- Test PASS (it asserts MemoryMax >= 768M in `NNNM` form, so "2048M" satisfies it); run-ci-checks 1 pass; check-ci-test-coverage PASS (814 tests: 723 declared, 91 exempt); nix-instantiate parse ok.
- The test is a static check of the Nix source; runtime proof is the journal above.

## Rollback Plan
Revert the staged commit. The MemoryMax change only takes effect on rebuild; reverting before rebuild has no runtime effect.

## Residual Risk
Owner rebuild needed: the MemoryMax change is a Nix change and applies only after `nixos-rebuild switch` (owner act). Until then the live unit keeps 1280M. The TimeoutStartSec fix needs no rebuild; the live unit already has 765s. If the peak keeps growing, reassess.

## Hint Feedback
No aq-hints used; the stale exemption pattern (a fixed producer with a surviving known-failing entry) is worth a periodic sweep of test_exempt entries.
