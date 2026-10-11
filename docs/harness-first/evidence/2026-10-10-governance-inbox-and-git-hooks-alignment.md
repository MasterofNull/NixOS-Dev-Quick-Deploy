# Evidence: Governance Inbox Member Resolution and Git Hooks Alignment

## Context
Date: 2026-10-10
Slice: `fix/governance-inbox-wake-and-secret-scan-alignment`
Components: `scripts/ai/aq-antigravity-inbox`, `.githooks/pre-commit`, `.githooks/pre-push`, `.agent/memory/issues-backlog.md`
Implementation Lane: Antigravity

## Problems Addressed
1. **Inbox Member Resolution (`antigravity-wake-unsafe-inbox-member`)**:
   - `delegate-to-antigravity` writes task files as `<task-id>.md` inside `.agent/collaboration/antigravity-inbox/`.
   - When operator or tooling runs `aq-antigravity-inbox wake <task-id>`, `_safe_member` raised `InboxError("invalid inbox member")` because it expected exact member names.
2. **Pre-Commit Secret Scan Coverage on Tests (`sop-local-gate-misses-gitleaks-on-tests`)**:
   - `.githooks/pre-commit` excluded `*/test_*.py` and `*/test-*.py` unconditionally from `run_secret_scan()`.
   - CI Secret Detection (Gitleaks) caught unlabelled token literals in tests that local hooks missed.
3. **Pre-Push Rebase Sync False Positives (`pre-push-sync-check-blocks-rebase-force-push`)**:
   - Rebasing feature branches onto `origin/main` produced non-zero `behind_count` against stale remote tracking branches, blocking pushes and forcing manual `SKIP_PRE_PUSH_SYNC_CHECK=true` overrides.

## Solutions
1. **Bare Task ID Resolution in Inbox**:
   - Updated `_safe_member` in `scripts/ai/aq-antigravity-inbox` to resolve bare task IDs to `<task-id>.md` (when unclaimed) or `.claimed-<task-id>` (when claimed) if the file exists, while preserving strict directory confinement and directory traversal protection.
2. **Scan Python Test Files in Pre-Commit**:
   - Removed blanket `*/test_*.py` and `*/test-*.py` exclusion from `excluded_paths` in `.githooks/pre-commit`.
   - Test files are now scanned for real token leaks while respecting placeholder regexes (`AKIAIOSFODNN7EXAMPLE`, `sk-test-...`, `ghp_dummy...`) and inline exemptions (`nosec`, `example`, `test`, `placeholder`, `fake`, `dummy`, `sample`).
3. **Rebased Feature Branch Detection in Pre-Push**:
   - Added cherry-pick equivalence verification (`git rev-list --left-only --cherry-pick`) in `run_upstream_sync_check` in `.githooks/pre-push`.
   - If `HEAD` contains `origin/main` and all upstream commits have matching cherry-picked equivalents in `HEAD`, the hook safely permits the push without requiring manual bypass flags.
4. **Backlog Reconciliation**:
   - Updated `.agent/memory/issues-backlog.md` marking all three items as `[FIXED 2026-10-10]`.

## Validation Evidence
- `python3 scripts/testing/test-antigravity-inbox.py`: PASS
- `python3 scripts/testing/test-antigravity-claim-receipt.py`: PASS
- `bash -n .githooks/pre-commit`: PASS
- `bash -n .githooks/pre-push`: PASS
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS (55/55 checks passed)
