# Shellcheck warnings fixed at the producer (2026-11-04)

## Objective
CI job "ShellCheck linting" (`.github/workflows/validate-shell-scripts.yml`) runs shellcheck on `./scripts` at warning severity. It failed on main and was masked with `continue-on-error`, registered as CI-MASK-VALIDATE-SHELL-SCRIPTS-RUN-SHELLCHECK. This slice fixes every finding in the scripts. A follow-up removes the mask after PR #685 lands, because that PR annotates the same workflow lines.

## Workflow/Session IDs
- Branch: `fix/validate-shell-findings`, from `origin/main` (2055db6b).
- Register entry: CI-MASK-VALIDATE-SHELL-SCRIPTS-RUN-SHELLCHECK. It closes when the mask is removed.
- Per-site logs: `.agents/delegation/outputs/validate-shell/` (REPORT.md, changes2155.txt, changes2034.txt, or_true_added.txt).

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17). The change touches 78 files and needs judgement on each site, so it was not a Haiku task.

## Commands Executed
- `shellcheck -f gcc --severity=warning` on all 513 shell files under `scripts/`: `*.sh`, `*.bash`, and extensionless files with an sh or bash shebang.
- `bash -n` on every changed file.
- The hermetic tests that cover the changed scripts, including `test-delegate-sleep-inhibit.py` and `test-delegate-wrapper-shell-safety.py`.

## Validation Evidence
- Baseline: 288 findings (SC2155 151, SC2034 84, and others). After: 0.
- `bash -n` passes on all 78 changed files.
- `test-security-cve-rsi-gate.py` fails identically on origin/main. The cause is a missing `.gitleaks.toml` in its fixture, not this change; logged as CVE-RSI-GATE-TEST-FIXTURE-NO-GITLEAKS-CONFIG. `tests/unit/aqd-parity.bats` was not run because bats is not installed.

How each finding was fixed:
- **SC2155:** split declaration from assignment. Under errexit, or in sourced libraries, `|| true` keeps the old behavior where `local` masked the exit status, wherever the command can fail. There are 41 plain splits for commands that cannot fail.
- **SC2034:** variables that are only assigned were removed. Flags that are parsed but unused are still accepted. Ten per-line disables name their reason. `AQ_INHIBIT_PREFIX` is read by the `delegate-to-*` scripts, and two arrays are read by nameref. The six toggles in `discover-system-facts.sh` are dead and are logged as DISCOVER-SYSTEM-FACTS-DEAD-TOGGLES.
- No `.shellcheckrc`, no file-level disables, and no workflow edits.

Changes that alter behavior:
- **`aqd`:** the `topology)` case could never match `"${topic}:${action}"`. It is now `topology:*)`, so `aqd topology` runs; before, it fell through to the default case.
- **`discover-system-facts.sh`:** `drm_drivers` listed the driver directory's contents instead of resolving the driver link. It now uses `readlink -f` and `basename`. This is untested on aarch64.
- **`aqos-install-vm-dogfood.sh`:** `$layout` was used inside the same `local` that set it.
- **`cli-enhanced.sh`:** the table separator width was wrong.
- **`check-checkout-fresh.sh`:** the symbolic-ref substitution is now quoted.
- **Several scripts:** dead `REPO_ROOT=$(cd ... && pwd)` lines were removed, so a failing `cd` no longer aborts those scripts under errexit.

## Rollback Plan
Revert the commit. No interfaces changed, and every removed variable was confirmed unused by a repo-wide `rg`.

## Residual Risk
- About 100 `|| true` additions keep the old masking. Some of those failures probably should abort, but this slice preserves behavior and does not decide that.
- The `aqd topology` path and the aarch64 `drm_drivers` detection now run for the first time.
- `scripts/data/cleanup-migrated-reports.sh` still has its subshell counter bug. It is logged as CLEANUP-MIGRATED-REPORTS-COUNT-SUBSHELL and left untouched.

## Hint Feedback
No hints were consulted.
