# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-013

## Objective
- Refuse rebuild/switch when the local checkout is behind origin/main. Happened twice on 2026-10-07: PRs merged on GitHub, owner rebuilt/switch from an unpulled checkout → stale code deployed (silent no-op activation).

## Workflow/Session IDs
- Workflow ID: wf-rebuild-stale-checkout-guard-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementer: Claude Haiku 4.5. Reviewer: Claude Opus 5.5 — rejected first hand-back (test suite never executed; TEST 1 exit 127; runner exited 0 on failure); accepted after fix, re-ran tests independently (4/4).

## Commands Executed
```bash
bash scripts/testing/test-check-checkout-fresh.sh
nix build --no-link .#homeConfigurations.hyperd.activationPackage
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Guard tests 4/4 (up-to-date → 0; behind → 3 + pull hint; ALLOW_STALE_CHECKOUT=1 → 0; offline → 0 + warning); runner exits non-zero on failure.
- Wired into pre-rebuild-preflight (nrs), nrs-force(), hms(), nixos-quick-deploy.sh switch path; HM activation builds.

## Rollback Plan
- Revert; home-manager switch.

## Residual Risk
- Raw `sudo nixos-rebuild switch` / `home-manager switch` typed directly bypass the guard; use nrs/hms.

## Hint Feedback
- No aq-hints consulted.
