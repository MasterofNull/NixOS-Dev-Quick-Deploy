# G2-HOOK-TRUST evidence — 2026-11-27

## Objective

Implement slice G2 (acceptance J3) of
`.agents/plans/greenlight-gating-20261119/DESIGN.md`, including Revision 1
F1/F2/F13 and owner decisions 1 and 3. `.githooks/pre-commit` accepts a fresh
`aq-greenlight` record for the exact staged tree, parent and branch in place of
the focused-CI step. Every earlier guard in the hook still runs.

Behavior delivered:

- `aq-greenlight --verify` accepts a base that moved past the recorded
  `main_sha` only when that commit is still an ancestor, the base is at most
  `--max-behind` / `AQ_GREENLIGHT_MAX_BEHIND` (default 20, positive integer)
  commits ahead, and nothing changed under `scripts/governance/`,
  `scripts/testing/`, `config/`, `nix/` or `.githooks/`. `--show` still requires
  the exact base.
- `--audit` appends one JSONL row to `<state_dir>/audit.jsonl` (0600, appended
  under flock). If the row cannot be written, verification fails and the hook
  runs focused CI, so no acceptance goes unlogged.
- Verification rejects a commit whose `GIT_INDEX_FILE` tree differs from the
  staged tree, and a record whose `main_sha` is not a full object id.
- The hook skips only `run_focused_ci_checks`, and only on a zero exit from
  `--verify --audit`. `AQ_GREENLIGHT_DISABLE=1`, a missing base ref, a missing
  or non-executable CLI, and any verifier failure run focused CI as before.
- `AQ_GREENLIGHT_BASE_REF` sets the CLI's default base ref.

## Workflow/Session IDs

Plan: `.agents/plans/greenlight-gating-20261119/DESIGN.md`, tracker item
`g2-hook-trust`. Branch: `feat/g2-hook-trust`, based on `1e0f03a59`. Lane:
Claude Sonnet 5.5 headless implementer, 2026-11-27. No workflow run ID or
delegation ID was supplied to this slice.

## Delegation Decision

Bounded implementer slice limited to six owned paths. No sub-agents, no commit,
no staging in this worktree, no tier0 run and no deployment. Independent review,
integration gates and the commit belong to the orchestrator.

## Commands Executed

```text
bash -n .githooks/pre-commit
python3 -m py_compile scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
ruff check scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
basedpyright scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
python3 scripts/testing/test-aq-greenlight.py
python3 scripts/testing/test-aq-usage-logging.py
python3 scripts/governance/check-activation-manifest.py --base origin/main --repo-root .
git diff --check
```

Also run: `test-gitleaks-ci-parity.py`, `test-security-cve-rsi-gate.py`,
`test-lane-hook-parity.py`, `test-factory-hook-composition.py`,
`test-factory-kit-k3.py`, `test-sweep-gates.py`, `test-install-git-hooks.py`,
`test-risk-tier.py` (all under `scripts/testing/`). The shell had
`AQ_USAGE_TELEMETRY=0`.

## Validation Evidence

Verification output after the last code change:

```text
$ bash -n .githooks/pre-commit
[exit 0]
$ python3 -m py_compile scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
[exit 0]
$ ruff check scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
All checks passed!
[exit 0]
$ basedpyright scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
0 errors, 0 warnings, 0 notes
[exit 0]
$ python3 scripts/testing/test-aq-greenlight.py
.....................................
----------------------------------------------------------------------
Ran 37 tests in 33.706s

OK
[exit 0]
$ python3 scripts/testing/test-aq-usage-logging.py
PASS: aq-* usage logging (hooks, schema, no arg values, kill switch, non-fatal, coverage, audit preference)
[exit 0]
$ python3 scripts/governance/check-activation-manifest.py --base origin/main --repo-root .
[activation-manifest] deferred: aq-oncalld autonomous on-call incident daemon (2026-10-28)
[activation-manifest] deferred: operator guidance spool (aq-human-intervention control queue) (2026-10-28)
[activation-manifest] deferred: durable runtime (idempotent effect ledger, aq-durable) (2026-10-28)
[activation-manifest] deferred: RSI convene expert rounds (Codex, Gemini, local design-only seats) (2026-11-06)
[activation-manifest] deferred: durable work ledger CLI (aq-ledger, S1 core) (2026-11-26)
[activation-manifest] 11 entries, 0 fail, 0 warn
[exit 0]
$ git diff --check
[exit 0]
```

The 37 tests are the 20 existing ones, unchanged in what they assert, and 17 new
ones. The new hook tests run real `git commit` through the real hook and
verifier in a disposable repository, with logging stubs for gitleaks, the
repo-structure lint, the echo lint, the nine migration checks and focused CI.
They cover acceptance, an edited file, the disable switch, a missing base ref, a
verifier error, a partial commit and a failing focused-CI run.

Mutation checks (each targeted test failed with the protection removed, then the
source was restored):

| Mutation | Test that failed |
|---|---|
| drop `--no-renames` from the freshness diff | `test_f13_move_out_of_covered_path_is_stale` |
| drop the commit-index check | `test_foreign_commit_index_is_rejected` |
| hook always skips focused CI | `test_hook_runs_focused_ci_after_edit` |

Dry run with real guards, in a disposable clone holding the five changed code,
config and test files. The greenlight run used the override
`tier0_pre_commit=python3 -c pass`; evidence and CI-coverage gates were real.
The hook was invoked directly (no commit). State directory shown as `<tmp>`:

```text
== real hook, greenlit (real guards)
Running pre-commit validation...
0 commits scanned.
scanned ~20486 bytes (20.49 KB) in 209ms
no leaks found
Color echo lint passed.
[repo-structure] PASS: structure policy checks passed (staged).
greenlight live%2Fg2-dry-run-22a01567a2ab1bdfba0a15973cebaeee506d470b accepted
exit=0 seconds=18
700 <tmp>/state
600 <tmp>/state/audit.jsonl
== verify after edit
aq-greenlight: Refusing unstaged tracked modifications or untracked non-ignored files
exit=1
```

(gitleaks timestamps and color codes removed from the block above.)

The same dry run repeated with all six files staged, including this document,
passed the cached whitespace check, the evidence-section gate and every hook
guard, and the hook exited 0 with the greenlight accepted.

Hook consumer regressions: seven of the eight exit 0.
`test-security-cve-rsi-gate.py` exits 1
(`test_pre_commit_blocks_staged_vulnerable_package`: gitleaks cannot load
`.gitleaks.toml` in the test's temporary repository, so the secret scan blocks
before the CVE check). The same assertion fails in a clone of unmodified
`1e0f03a59`; this slice does not change it.

## Rollback Plan

Set `AQ_GREENLIGHT_DISABLE=1` to make the hook run focused CI on every commit.
To remove the feature, revert the slice commit through the normal reviewed
workflow; this restores the unconditional `run_focused_ci_checks` call and the
activation deferral. Existing records and `audit.jsonl` live outside the
repository and can be left or archived.

## Residual Risk

- Real tier0 was not run, neither as a greenlight gate nor as an integration
  gate. J3 with a real tier0 greenlight followed by a real commit of this
  repository is not yet attested.
- Records are unsigned, and a run made with `--gate-cmd` overrides produces a
  record the hook accepts. The design treats the record as a convenience; CI and
  independent review remain the authority.
- Freshness is measured against the local base ref. The hook does not fetch, so
  an old `origin/main` makes a record look fresher than it is.
- `flake.nix`, `flake.lock`, `scripts/ai/` and `.gitleaks.toml` are outside the
  covered prefixes; changes there count only toward the commit bound.
- An audit row records an accepted pre-commit verification. A later failure
  (for example in `commit-msg`) can still abort that commit.
- F2 names port guards. The hook had no separate port guard before this change,
  and a name search of governance scripts and CI check configs found none.
- `config/ci-checks.json` does not list `.githooks/pre-commit` as a trigger path
  for the group that runs `test-aq-greenlight.py`, so a hook-only change does not
  select it locally. That file is outside this slice.
- Activation takes effect for a checkout once it contains the merged hook and
  has `core.hooksPath` set to `.githooks`.

## Hint Feedback

No harness hint or AIDB query was made in this headless slice; the brief supplied
the design and paths. One finding came from reading the code: the existing
library scrubs `GIT_INDEX_FILE`, which in a hook would compare the worktree index
instead of the index being committed. The added commit-index check closes that.
