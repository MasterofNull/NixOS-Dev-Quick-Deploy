# CI shellcheck findings (system-integrity P0.2)

## Objective

Make the two shellcheck CI jobs that were masked by `continue-on-error: true` real gates. Backlog: CI-KNOWN-FAILING-GATES. Scope rule: if a job has more than ~40 distinct finding sites, fix the error-severity set, unmask only the job that then passes, and list the remainder.

## Workflow/Session IDs

- GitHub runs observed failing on main: 41875000366 (`shellcheck.yml`, ShellCheck Analysis), 41875000213 (`validate-shell-scripts.yml`, ShellCheck linting)
- Branch: `fix/ci-shellcheck-findings` (from origin/main c2b542320)
- Date 2026-11-04; implementer Claude Sonnet 5.5, orchestrator claude-opus

## Delegation Decision

Rule 17: bounded implementation delegated to the Sonnet tier by the orchestrator. Outcome: `shellcheck.yml` unmasked (3 findings fixed). `validate-shell-scripts.yml` stays masked: 227 finding sites across 51 files exceeds the ~40-site slice limit, so it is deferred to follow-up slices.

## Commands Executed

Local reproduction of each job's invocation (file set = `scripts/**/*.sh|*.bash`, 435 files, shellcheck 0.11.0, run as one `xargs -0` batch):

```
# Job 1: shellcheck.yml (severity error, SHELLCHECK_OPTS excludes, --shell=bash)
shellcheck --severity=error --exclude=SC1090,SC1091,SC2034,SC2154,SC2086,SC2046 --shell=bash -f gcc <files>
# Job 2: validate-shell-scripts.yml (severity warning, no excludes)
shellcheck --severity=warning -f gcc <files>
```

Fixes:

- `scripts/automation/run-prsi-cycle-evidence.sh:18`: `$($@)` -> `$("$@")`
- `scripts/data/sync-flatpak-profile.sh:211,219`: `${install_cmd[@]}` -> `"${install_cmd[@]}"`
- `.github/workflows/shellcheck.yml`: removed `continue-on-error: true` on the Run ShellCheck step (no KNOWN-FAILING/NON-GATING marker lines existed on main for it)

`bash -n` on both touched scripts: OK. Only test referencing them (`scripts/testing/verify-flake-first-roadmap-completion.sh`) is a text-pattern grep for `sudo -n flatpak`, unaffected.

## Validation Evidence

Findings before/after:

| Job | Before | After |
|-----|--------|-------|
| shellcheck.yml (error) | 3 (SC2068 x3) | 0, exit 0 |
| validate-shell-scripts.yml (warning) | 230 | 227, exit 1 |

Job 1 findings before:

```
scripts/automation/run-prsi-cycle-evidence.sh:18:10: error: ... [SC2068]
scripts/data/sync-flatpak-profile.sh:211:16: error: ... [SC2068]
scripts/data/sync-flatpak-profile.sh:219:43: error: ... [SC2068]
```

Job 2 before, by code: SC2155 131, SC2034 54, SC2207 15, SC2164 5, SC2088 3, SC2068 3, SC2318 2, SC2222 2, SC2221 2, SC2124 2, SC1010 2, and one each of SC2183, SC2140, SC2076, SC2063, SC2053, SC2046, SC2038, SC2011, SC2010. After: same minus the 3 SC2068.

Behaviour is identical for callers: all pass word-split-free argument lists or arrays.

## Rollback Plan

`git revert` the commit. Restores `continue-on-error: true` and the unquoted expansions.

## Residual Risk

- `validate-shell-scripts.yml` "ShellCheck linting" remains masked (`continue-on-error: true`) with 227 findings in 51 files; needs follow-up slices (SC2155 131 and SC2034 54 dominate). Its WORKAROUND-REGISTER entry stays open.
- PR #685 (which adds the CI-MASK-* register entries) was still OPEN on origin/main, so `.agent/WORKAROUND-REGISTER.md` was not edited; the CI-MASK-SHELLCHECK-SHELLCHECK-ANALYSIS entry should be closed once #685 lands.
- Local findings for job 2 (SC2155/SC2034/SC2207/...) are broader than the codes seen in the CI log; the action's file discovery may differ slightly from `find`.

## Hint Feedback

Hook rewrites mangle `$VAR` and `cd` in inline shell; a script file run with `bash <abs path>` worked reliably.
