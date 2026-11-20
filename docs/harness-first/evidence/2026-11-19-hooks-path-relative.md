# Harness-First Task Evidence: relative core.hooksPath self-heal

Date: 2026-11-19
Task ID: SEC-HOOKSPATH-20261119-001

## Objective
Clear tier0 check-lane-hook-parity GAPs (W4/W5 of security-warnings-inventory-20261119): core.hooksPath was the ABSOLUTE primary-checkout path, so every worktree ran the primary checkout's hooks. Delivered: `scripts/deploy/install-git-hooks.sh` hardened (idempotent, `--quiet` self-heal, bare-repo refusal, per-worktree override unset), self-heal wired into `aq-session-start`, new test. Live repo config set to relative `.githooks`.

## Workflow/Session IDs
- Workflow ID: n/a (owner-directed warning sweep, 2026-11-19)
- Session ID: Simurg@claude/sonnet under orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
Delegated bounded implementer slice (Rule 17, sonnet). No NixOS state involved: core.hooksPath is repo-local git config, not Nix-managed, so Rule 13 does not apply; the declarative equivalent is the committed installer plus the session-start self-heal.

## Commands Executed
```bash
bash scripts/governance/tier0.d/check-lane-hook-parity.sh      # before: 2 GAP
bash scripts/deploy/install-git-hooks.sh
bash scripts/governance/tier0.d/check-lane-hook-parity.sh      # after: 0 GAP
python3 scripts/testing/test-install-git-hooks.py
python3 scripts/testing/test-lane-hook-parity.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Before: `GAP: core.hooksPath is ABSOLUTE (/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.githooks)` and `GAP: agent worktrees not resolving hooks ...`; `WARN: 2 lane parity gap(s)`.
- After: `PASS: repo root core.hooksPath is relative .githooks`, `PASS: agent worktrees (255) resolve hooks to .githooks`, `PASS: every lane reaches the same commit gate`.
- test-install-git-hooks.py PASS (heals absolute and /dev/null values, idempotent and silent when correct, linked worktree resolves its OWN .githooks, bare repo refused). test-lane-hook-parity.py PASS.
- Root cause of the absolute value: UNKNOWN writer. Every in-repo writer (install-git-hooks.sh, aq-factory, factory_gate_install.py) writes relative; no nix/ or setup path writes it (backlog 2026-10-30 records the same unexplained drift). Mitigation is detection plus self-heal at every session start, so a regression is repaired and logged (`[install-git-hooks] healed core.hooksPath`) instead of silently persisting.
- Unsafe cases for a relative path: bare repos (resolves against GIT_DIR; installer refuses); a worktree lacking `.githooks` (parity check reports it). Both handled.

## Rollback Plan
`git revert <commit-sha>`; to restore the old live state (not recommended) `git config core.hooksPath <abs path>`.

## Residual Risk
Low. The unknown absolute-path writer may recur; the self-heal only fires at aq-session-start, so drift between sessions persists until the next one (tier0 still reports it). Candidate follow-up: identify the writer via git config audit.

## Hint Feedback
- No aq-hints used; policy template followed (all 8 sections present).
