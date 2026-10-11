# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-170

## Objective
Close findings from independent review of Network Profile PRs #463/#465/#467: remove the self-activation bypass
on `aq-network-policy trust replace`, make `mode = "policy"` unselectable until N3, and add the missing PM tracker.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f
- Branch: fix/network-policy-n2-activation-gate-20261010

## Delegation Decision
Bounded implementer sub-agent slice dispatched by the orchestrator; no commit or tier0 run by the implementer.

## Commands Executed
- python3 scripts/testing/test-network-dns-policy.py
- nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath
- nix eval with extendModules setting mode="policy"
- python3 scripts/ai/aq-pm-tracker .agents/plans/network-profile-interoperability --check

## Validation Evidence
- Tests: 27 tests OK, including proof that the env var and `--n3-canary` no longer unlock `trust replace`.
- Default config evaluates (drv path produced).
- mode="policy" fails with: mySystem.networkPolicyObservability.mode = "policy" is not selectable until N3 owner activation.
- Tracker check: PASS, valid and projects. Editorial only (no acceptance, status or pct).
- /run/aq-network-policy stays 0755: it holds the world-readable health projection; the plan's 0700 applies to the private subdirectory, which is 0700.

## Rollback Plan
Revert the commit; legacy default is unaffected either way.

## Residual Risk
- Hardcoded resolver IPs and unconditional tmpfiles rules remain (low, noted for N3).
- No independent acceptance exists for N0-N2; tracker intentionally carries none.

## Hint Feedback
No hints queried for this slice.
