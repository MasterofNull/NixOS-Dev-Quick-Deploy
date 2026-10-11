# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-121

## Objective
- NOTE: the guard itself already landed in #471. Antigravity pushed its own task branch and self-merged it
  10s after creation, bypassing the lane contract ("do not push") and this review, so #471 shipped WITHOUT
  the apparmor override below. Until this PR merges, owner-approved AppArmor rule commits
  (`aq-approve --commit-staged`) fail in the primary checkout.
- Enforce the canonical delivery workflow at commit time: refuse direct commits on `main` in the primary
  (non-worktree) checkout. Until now it was instruction-only, and a 2026-10-09 agent session committed
  straight onto main there; that was caught only later by the nrs checkout-fresh guard.
- This is the first production slice implemented by the Antigravity (Gemini) implementer lane (#461), in
  task `antigravity-20261010-170154-am6w3f`, inside its own worktree.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f
- Antigravity task: antigravity-20261010-170154-am6w3f (claim → completion in ~3 min; validator accepted;
  patch `.agents/delegation/outputs/antigravity-20261010-170154-am6w3f.patch`)

## Delegation Decision
- Implementer: Antigravity (bounded, non-critical, two files). The owner directive is for the Antigravity
  lane to do implementation work.
- Reviewer: the orchestrator reviewed the diff, re-ran the test independently, and swept for automation
  that commits on main in the primary checkout. That sweep found `apparmor-fix-agent.py`, used by
  `aq-approve --commit-staged` and `aq-health-spider`, which the guard would have broken.
- The orchestrator added an explicit `AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1` on that commit and registered
  WR-11, whose fix path is to migrate it to branch + PR. Antigravity's one-line commit message was reworded
  to meet commit-verbosity and attribution rules.

## Commands Executed
```bash
python3 scripts/testing/test-precommit-main-checkout-guard.py
bash -n .githooks/pre-commit
python3 -m py_compile scripts/automation/apparmor-fix-agent.py
rg -n 'git[^|;&]*\bcommit\b' scripts/automation scripts/ai nix/modules   # automation sweep
git config --global --get core.hooksPath                                 # none: temp clones unaffected
```

## Validation Evidence
- `test-precommit-main-checkout-guard.py` PASS (orchestrator re-run). It makes real `git commit` calls in a
  temp repo:
  - primary-checkout main: refused;
  - with the override: allowed;
  - on a feature branch: allowed;
  - in a linked worktree: allowed.
- Automation sweep:
  - `aq-factory-push` commits in its own temporary clone, and `core.hooksPath` is not global, so it is
    unaffected;
  - `apparmor-fix-agent.py` now sets the override explicitly (WR-11);
  - `integration_guard` / `aq-commit-agent` run in worktrees.

## Rollback Plan
- Revert the PR. Or, for a one-off owner commit, set `AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1`.

## Residual Risk
- Any agent can also set the override; it is an explicit, auditable bypass, not a security boundary.
- `git commit --no-verify` bypasses all hooks, as before.
- Owner `flake.lock` chore commits in the main checkout now need the override:
  `AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1 git commit ...`.

## Hint Feedback
- None.
