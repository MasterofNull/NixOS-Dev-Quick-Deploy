# CI: unmask always-pass gates (system-integrity P0.2)

## Objective

Find every failure mask in `.github/workflows/*.yml` (`|| true`, `continue-on-error: true`, `set +e`, `exit 0` after a failure), classify it as GATE-MASK or LEGIT, record what the masked command really does on main today, and stop masks from appearing silently. Source: CI/CD SOTA analysis (`.agents/delegation/outputs/cicd-sota-analysis-20261104.md`) top-10 item "remove masked failures".

Outcome: all three GATE-MASKs that were checked **fail today**, so none was unmasked (that would turn CI red with no fix). Each is annotated `# KNOWN-FAILING:` and registered in `.agent/WORKAROUND-REGISTER.md`. All LEGIT masks carry `# NON-GATING:`. New guard `scripts/governance/check-workflow-masks.py` fails any unannotated `|| true` / `continue-on-error: true`.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 (Rule 17); orchestrator claude-opus, 2026-11-04.
- Evidence runs on main (all workflow conclusions were `success`, which is what the masks produce): nix-build 41875000226, shellcheck 41875000366, validate-shell-scripts 41875000213, test 41875000198, tests-legacy 41875000163.

## Delegation Decision

Bounded slice (workflow comments, one checker, one test, one manifest entry, register text): cheapest eligible Claude tier (Sonnet). No local or Codex lane used; the work needed live `gh` reads and repo-wide judgment calls.

## Commands Executed

- `rg -n '\|\| *true|continue-on-error|set \+e|\|\| *echo|exit 0' .github/workflows/*.yml`
- `gh run list --workflow <file> --branch main --limit N --json databaseId,conclusion,headSha,event`
- `gh run view <id> --log | rg "<step>" | rg -i "error|SC[0-9]{4}|..."` (nix-build, shellcheck, validate-shell-scripts, test, tests-legacy)
- `python3 scripts/governance/check-workflow-masks.py`
- `python3 scripts/testing/test-check-workflow-masks.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('yaml ok')"`

## Validation Evidence

Inventory (line numbers are in the pre-change files).

| file:line | pattern | class | evidence of current outcome | action |
|---|---|---|---|---|
| nix-build.yml:59 | `nix flake check --all-systems \|\| true` | GATE-MASK | FAILS: run 41875000226 "Check flake": `error: Unsupported system: aarch64-linux` | kept; `# KNOWN-FAILING`, CI-MASK-NIX-BUILD-CHECK-FLAKE |
| shellcheck.yml:42 | `continue-on-error: true` (ShellCheck Analysis) | GATE-MASK | FAILS: run 41875000366 "Run ShellCheck": SC2068 errors, `##[error]Process completed with exit code 1` | kept; `# KNOWN-FAILING`, CI-MASK-SHELLCHECK-SHELLCHECK-ANALYSIS |
| validate-shell-scripts.yml:69 | `continue-on-error: true` (Run ShellCheck) | GATE-MASK | FAILS (findings reported): run 41875000213: SC2034, SC2088, SC2155 warnings at severity warning | kept; `# KNOWN-FAILING`, CI-MASK-VALIDATE-SHELL-SCRIPTS-RUN-SHELLCHECK |
| security.yml:59 | `continue-on-error: true` (PR comment) | LEGIT | cosmetic PR comment; fork PR token is read-only | `# NON-GATING` |
| security.yml:103 | `docker system prune ... \|\| true` | LEGIT | disk cleanup | `# NON-GATING` |
| nix-build.yml:46 | `docker system prune ... \|\| true` | LEGIT | disk cleanup | `# NON-GATING` |
| confine-tests.yml:94 | `loginctl enable-linger \|\| true` | LEGIT | best-effort; the `systemd-run --user --scope` probe right after is the gate | `# NON-GATING` |
| confine-tests.yml:95 | `systemctl start user@ \|\| true` | LEGIT | same probe follows | `# NON-GATING` |
| confine-tests.yml:100 | `cat cgroup.controllers \|\| true` | LEGIT | diagnostic print | `# NON-GATING` |
| tests.yml:68 | `apparmor_parser -r ... \|\| true` | LEGIT | best-effort profile load; confine tests fail on their own if bwrap is blocked | `# NON-GATING` |
| tests.yml:80 | `chmod +x ... \|\| true` | LEGIT | unmatched glob; a missing exec bit fails the step that runs the script | `# NON-GATING` |
| test.yml:770 | `chmod +x ... \|\| true` | LEGIT | same | `# NON-GATING` |
| tests.yml:108-114 | `set +e` ... `exit 0` on rc 5 | LEGIT | exit code captured as `rc`; only pytest "no tests collected" (5) is tolerated, others `exit "$rc"` | none (not covered by the checker) |
| nix-build.yml:75 | text `No \|\| true` in a comment | n/a | comment, not a mask | none |
| test.yml:341,355 | shellcheck step ends with `exit 0` ("warnings are informational") | GATE-MASK (by design) | NOT DETERMINED: step log not inspected beyond confirming the step runs | none; outside the `\|\| true`/`continue-on-error` checker scope; see Residual Risk |
| test.yml:802 | secrets scan ends `exit 0` ("Failing this check does not block CI") | GATE-MASK (by design) | NOT DETERMINED: log shows the step runs; finding count not extracted | none; see Residual Risk |
| tests-legacy.yml:30 | `bats ... \|\| { echo "...continuing"; exit 0; }` | GATE-MASK (by design) | NOT DETERMINED (no BATS output found in run 41875000163) | none; see Residual Risk |
| test.yml:412,436,582; tests-legacy.yml:32,36,79 | `exit 0` on empty-input or success branches | LEGIT | success paths, not failure masks | none |

Check output:

```
check-workflow-masks: PASS
test-check-workflow-masks: PASS
[tier0.d/check-ci-test-coverage] PASS (764 tests: 620 declared, 144 exempt)
[tier0.d/check-ci-manifest-coverage] PASS
yaml ok
```

The guard and its two `config/ci-checks.json` entries (`workflow-failure-masks`, `check-workflow-masks-test`, both `ci_workflow: test.yml#syntax`) run through `run-ci-checks.sh`.

## Rollback Plan

Revert the commit. Changes are comments in workflows, a new checker and test, two manifest entries, and appended register entries; no runtime behavior changed.

## Residual Risk

- The three KNOWN-FAILING gates remain non-blocking until their producers are fixed (register entries CI-MASK-*). The checker only forces them to stay annotated.
- Masks of the form `exit 0` after a failure (`test.yml` shellcheck and secrets scan, `tests-legacy.yml` bats) are not caught by the checker and their real outcome was not determined here. A follow-up should read those step logs and either annotate or unmask them.
- `tests-legacy.yml` triggers on the same events as `tests.yml`; whether it is still wanted is not assessed.
- The checker is line-based; a mask split across lines or built via `|| $(true)` would not be caught.

## Hint Feedback

No harness hints were queried for this slice. Observed friction: the command hook mangles `> file` redirects of `gh ... --log` output (target became `/name`), so logs were piped straight into `rg` instead.
