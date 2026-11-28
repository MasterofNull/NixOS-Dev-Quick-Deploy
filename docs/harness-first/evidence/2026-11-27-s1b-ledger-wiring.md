# S1B-LEDGER: wire the work ledger into the delegation wrappers

## Objective

Finish slice S1 (`s1-ledger`) of `.agents/plans/agent-work-durability-20261119/DESIGN.md`: fix the two low follow-ups from PR #882 (`S1-LEDGER-FOLLOWUPS-20261127`), add `--pid` to `aq-ledger`, record every `delegate-to-{codex,gemini,local,claude}` dispatch in the ledger, and add the tier0 ledger check.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5, headless delegate, branch `feat/s1b-ledger-wiring`, worktree `.agents/delegation/worktrees/feat-s1b-ledger-wiring`. Orchestrator session id not supplied.

## Delegation Decision

Bounded eleven-file slice assigned by the orchestrator. No further delegation. Changes left uncommitted for independent review.

How terminal status is recorded:

- Blocking runs: the wrapper's completion branches write `done` or `failed`. `delegate-to-claude` does it in `record_terminal`, which also covers aborts.
- Background runs: the background workers are outside this slice, and `test-delegate-sleep-inhibit.py` pins their launch lines. The command handed to the worker (for local, the dispatcher) is prefixed with a private re-entry, `--internal-ledger-run <id>`, which runs it, writes the status and returns its exit code.
- A failed worktree handback (codex, local) writes `failed` after any earlier `done`.
- `init` runs before launch with the wrapper pid; background launches then send a heartbeat with the worker pid. This order avoids a fast task finishing before its entry exists.

## Commands Executed

- `bash -n` on the four wrappers and `check-work-ledger.sh` (also each file separately)
- `shellcheck scripts/governance/tier0.d/check-work-ledger.sh`
- `python3 -m py_compile`, `ruff check`, `basedpyright` on `work_ledger.py`, `aq-ledger`, `test-work-ledger.py`
- `python3 scripts/testing/test-work-ledger.py`
- `python3 scripts/testing/test-delegate-wrapper-shell-safety.py`
- `python3 scripts/testing/test-no-tmpfs-guard.py`
- `python3 scripts/governance/check-activation-manifest.py --base origin/main --repo-root .`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `git diff --check`
- All 53 declared tests that mention a wrapper, the ledger or the activation manifest, through `run-test-group.py`'s `run_one`
- `test-delegate-to-claude-lifecycle.py` and `test-claude-dispatch-payload-safety.py` again with `AQ_DELEGATION_DIR` unset (they are standalone `ci-checks.json` commands)

## Validation Evidence

Final run:

```text
bash -n                      rc=0
shellcheck                   rc=0
py_compile                   rc=0
ruff                         All checks passed!
basedpyright                 0 errors, 0 warnings, 0 notes
test-work-ledger.py          Ran 41 tests in 27.743s  OK
shell-safety                 ALL PASS (rc=0)
test-no-tmpfs-guard.py       Ran 11 tests  OK
check-activation-manifest    10 entries, 0 fail, 0 warn (rc=0)
check-ci-test-coverage       PASS (821 tests: 733 declared, 88 exempt)
check-ci-manifest-coverage   PASS
git diff --check             rc=0
check-work-ledger.sh         PASS (0 entries) against the real delegation dir
claude lifecycle             Ran 8 tests  OK
claude payload safety        Ran 2 tests  OK
```

The first `basedpyright` run reported one error in the new test code (`**env` could bind to `rc`); fixed before the final run.

Mutation check: the three new library tests run against `HEAD`'s `work_ledger.py` fail (8 failures), and pass against the new one.

Wider run: 50/53 passed initially. Two failures were the standalone Claude tests, which break under the group runner's shared `AQ_DELEGATION_DIR` and pass as CI invokes them (above). The third was `test-tier0d-gate-mutation.py`, which was resolved in this PR by registering `"check-work-ledger.sh": "scripts/testing/test-work-ledger.py"` in `COVERED_ELSEWHERE` (`scripts/testing/test-tier0d-gate-mutation.py:48`), bringing `test-tier0d-gate-mutation.py` to `37/37 passed`.

Follow-up fix (PR #892 CI ShellCheck + Gemini review follow-up, `claude-20261127-174552-po4eqs`):
- Quoted `_ledger_status="done"` in all four `scripts/ai/delegate-to-{codex,gemini,local,claude}` wrappers to satisfy ShellCheck SC1010 (`shellcheck -S warning` exit 0 across all 4 wrappers).
- Added `registry.exists()` guard in `scripts/testing/test-work-ledger.py` background polling loop (`Ran 41 tests in 27.648s  OK`, `ruff`/`basedpyright` 0).

## Rollback Plan

Revert the commit. Ledger files are additive runtime state; archive `.agents/delegation/ledger/` (Rule 12) if it is no longer wanted.

## Residual Risk

- Tested with stub providers only. No real provider dispatch has written an entry, so the manifest's `live` state needs a post-merge check with `aq-ledger list --json`.
- No ledger heartbeats during a run: tasks longer than the window (default 1800 s) show a stale-heartbeat WARN.
- A blocking codex, gemini or local run that is killed leaves its entry `running` (stale, or `interrupted` after reboot). So does a background launch that dies before its command starts, except where local launch verification catches it.
- Background codex writes `done` when the provider exits, just before handback. A crash in between leaves `done` without a handed-back patch.
- Gemini `partial-success` is recorded as `failed` with reason `partial-success exit=N`.
- Background Claude: the registry's `provider_pid` is now the re-entry shell, the parent of the Claude process.
- Background local on a host without `systemd-inhibit`, in non-worktree modes: `dispatch.py` is no longer the process-group leader, so cancel signals only its own pid.
- `task` is the first 120 characters of the prompt, newlines replaced. The registry already stores the whole prompt.
- Refusals before launch (power gate, preflight, budget, egress) write no entry.
- One corrupt entry fails the tier0 check on every commit until the file is archived (fail closed, as specified).
- The new column-0 comments also appear in each wrapper's `--help` output.
- Not updated because they are outside the file list: PULSE.log, RESUME.json, HANDOFF.md, tracker.json.

## Hint Feedback

None. Headless delegate; `aq-hints` was not queried.
