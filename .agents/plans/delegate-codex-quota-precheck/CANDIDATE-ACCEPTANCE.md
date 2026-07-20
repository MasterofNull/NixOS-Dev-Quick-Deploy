# delegate-to-codex quota pre-check — binding candidate acceptance

**Verdict reviewer:** claude-subagent-delegate-codex-quota-acceptance-reviewer
**Model / identity:** Claude Opus 4.8 (`claude-opus-4-8`), fresh flagship session — not the implementer
(Sonnet subagent), not the orchestrator, not a prior reviewer.
**Date:** 2026-07-20
**Authority:** OWNER acceptance-lane-directive, `.agent/collaboration/PULSE.log` line 331
(`[2026-07-20T08:14:39-0700] [owner] [acceptance-lane-directive]`) — redirects binding acceptance of
the currently-staged candidates from codex-wait to fresh independent Claude flagship reviewers, NOW.
Frozen reviewer-agnostic criteria: `.agents/plans/delegate-codex-quota-precheck/CODEX-ACCEPTANCE-AUTHORIZATION.md`.

## VERDICT: REQUEST_REVISION — criterion 4 fails: `| tee … || true` resets `PIPESTATUS`, so wait-mode `exit_code` is always 0; every non-zero codex exit is mislabeled `done` (failed-status registry branch is dead code, failures masked)

---

## Recomputed subject hashes (criterion 1)

| Op | Path | Expected SHA-256 | Recomputed | Match |
|---|---|---|---|---|
| MODIFY | `scripts/ai/delegate-to-codex` | `3bbd…aa2` | `3bbd82513846cf7fd39d6d4bf12fbce8a7f51fa7b721616445907adf727aa8a2` | ✅ |
| NEW | `scripts/testing/test-delegate-codex-quota-precheck.sh` | `27db…299` | `27dbb2e4c98b7fd6fbd4c544b74030433c87c43421be4a476a3a13d074079299` | ✅ |
| MODIFY | `.gitignore` | `2ad6…e30` | `2ad65904e421190bcc2c20afad0f13e67b42bf6c49aef091419ca0440addce30` | ✅ |

All three match exactly. No hard-stop. Cooldown runtime file `.agents/delegation/.codex-quota-cooldown`
is gitignored (`.gitignore:185`), not tracked, not staged. The 5 QPPR-A2 dashboard files
(`assets/dashboard.js`, `dashboard.html`, `dashboard/backend/api/routes/aistack.py`,
`dashboard/backend/api/services/qa_runner.py`, `scripts/testing/test-dashboard-qa-provider-probe.py`)
are also staged but are the **separate** QPPR-A2 slice — not conflated, not part of this verdict.

---

## Per-criterion evidence

**1 — Hashes / staged set / gitignore.** PASS. See table above.

**2 — Design parts 1–4 in the bytes.**
- Part 1 (cooldown state file): `COOLDOWN_FILE="$DELEGATION_DIR/.codex-quota-cooldown"`, single ISO-8601
  UTC line, absent/empty = no cooldown. ✅
- Part 2 (`quota_cooldown_active()` pre-check): placed in `cmd_delegate` after `budget_gate_dispatch codex`
  (i.e. after the A2A guard/policy/budget checks), before launch; fast-fails via `die`; clears empty,
  corrupt/unparseable, and expired files (all `rm -f … || true`); called in an `if` condition so a
  non-active `return 1` never trips `set -e`. ✅
- Part 3 (`quota_capture_from_output()`): scans for `You've hit your usage limit`; parses
  `try again at <date>` → ISO-8601 UTC via python; ordinal-suffix strip, multi-format, year-less
  future-anchoring; bounded `now+1h` fallback on no-match/unparseable; atomic `mktemp`+`mv -f`; python
  wrapped `|| true`; healthy run writes nothing. ✅
- Part 4 (bypass): `DELEGATE_CODEX_IGNORE_COOLDOWN=1` and `--force-quota-retry` both skip the pre-check;
  capture runs unconditionally after the run so a forced attempt that still hits the limit re-arms. ✅

**3 — Both run modes.**
- Wait-mode capture after `tee` + `PIPESTATUS` read (line 419–421). Present, but see criterion 4.
- Background/`nohup` via `--internal-quota-capture` self-re-entry: `SCRIPT_PATH` re-invokes the script
  (`quota-capture) … quota_capture_from_output "$SUBCMD_ARG"`), because the detached `bash -c` cannot see
  the parent's functions. Correct, bounded (one invocation after the run, `>/dev/null 2>&1 || true`),
  not on the public CLI surface. ✅

**4 — In-scope bug fix (`|| true`). FAIL — see adjudication below.**

**5 — Fail-safe.** Partial. No cooldown path crashes or fails the caller under `set -e` (verified: all
cooldown rm/mv/date/python calls are `|| true`-guarded or in `if`/`$()` contexts). Healthy runs write no
cooldown (test e / e-bg PASS). Unparseable reset writes a bounded `now+1h` cooldown, never absent/unbounded
(test f PASS). BUT the same `|| true` that makes the capture reachable also masks the true codex exit in
wait-mode (criterion 4) — a *different* failure surface than the cooldown paths, and it is not fail-safe:
it silently reports failed dispatches as successful.

**6 — Fresh validation.**
- `scripts/testing/test-delegate-codex-quota-precheck.sh`: **12 passed, 0 failed**, fully offline (stub
  `$CODEX_BIN`, no real codex, `HYBRID_COORDINATOR_URL` pointed at `127.0.0.1:1`). ✅ for what it covers.
- State hygiene: live `registry.jsonl` SHA-256 identical before and after
  (`d76003f9…4717f`); no `.codex-quota-cooldown` leaked into the repo. Test snapshots/restores state and
  pollutes nothing. ✅
- `bash -n` both files: clean. `git diff --check`: clean. Secret-scan: clean.
- **Test-coverage gap:** the stub exits `1` on quota error (test lines 88–95), but wait-mode test (a)
  asserts only that the cooldown was written (text-based, exit-code-independent) and stub-invocation
  count — it never asserts the resulting registry `status`. So 12/12 green does **not** exercise the
  criterion-4 defect. No test asserts `status == failed` after a non-zero wait-mode exit.

**7 — No prohibited action.** PASS. Only the three ceiling files changed; no other `delegate-*` wrapper,
`dispatch.py`, registry schema, A2/QPPR file, or runtime inference path touched; no real codex/network
invocation anywhere (tests stub the binary and isolate the coordinator).

---

## Bug-fix adjudication (criterion 4) — the crux

**Claim under review (candidate comment, lines 416–418):** adding `|| true` after
`"${cmd[@]}" < /dev/null 2>&1 | tee "$output_file"` keeps the failure path — `exit_code` capture,
the pre-existing failed-status registry update, and the new quota capture — reachable under
`set -euo pipefail`, while `PIPESTATUS[0]` still yields the true codex exit code.

**Finding: the `PIPESTATUS[0]` claim is FALSE.** In bash, `pipeline || true` executes `true` whenever the
pipeline exits non-zero (which, under `pipefail`, it does on any codex failure). `true` is itself a
pipeline, so it overwrites `PIPESTATUS` — leaving `PIPESTATUS[0] == 0`. The very next line
`local exit_code="${PIPESTATUS[0]}"` therefore reads **0 on every failed run**.

Empirically reproduced under `bash` (session shell is zsh; the script is `#!/usr/bin/env bash`, tested
accordingly):

```
{ echo out; exit 37; } | tee f >/dev/null || true ; echo ${PIPESTATUS[0]}   # -> 0   (WRONG)
{ echo out; exit 37; } | tee f >/dev/null         ; echo ${PIPESTATUS[0]}   # -> 37  (correct)
{ echo out; exit 37; } | tee f >/dev/null && ec=0 || ec=${PIPESTATUS[0]}     # -> ec=37 (correct idiom)
```

**Consequence (wait-mode only):** with `exit_code` pinned to 0, the `if [[ "$exit_code" -eq 0 ]]` branch
(lines 422–430) always takes the **success** arm — marks the registry entry `status=done`, emits a
`success` audit event, prints "Task … completed" — even when codex exited non-zero (quota exhaustion,
sandbox denial, crash). The pre-existing `else`/failed arm is **dead code** in wait-mode. This is exactly
the outcome criterion 4 forbids: PIPESTATUS[0] does *not* capture the true exit, and the fix *masks other
failures* by reporting them as success. It is also a faithful-reporting / anti-gaming regression (a failed
dispatch is recorded as done).

Note the asymmetry: **background mode is correct** — its `bash -c` runs without `set -e` and uses a bare
`… > "$output_file" 2>&1; exit_code=$?` (no pipe, no `|| true`, lines 439–440), so its failed-status
update fires properly. Only the wait-mode branch is defective.

The quota *capture* itself is unaffected (it is text-pattern based, not exit-code based), which is why the
cooldown tests pass. The defect is confined to exit-status fidelity — but that is a named acceptance
criterion and a real behavior regression, so it blocks.

**Direction for the bounded revision (not applied here):** preserve the pipe status while still avoiding
the `set -e` abort, e.g.
`local exit_code=0; "${cmd[@]}" < /dev/null 2>&1 | tee "$output_file" || exit_code="${PIPESTATUS[0]}"`
(verified above to yield 37), and add a wait-mode test asserting `status=failed` after a non-zero exit.
Correct the misleading comment on lines 416–418. Re-freeze with fresh hashes.

---

## Scope of this review

Read-only except this verdict artifact and the closing pulse. No subject edits, no staging, no commit, no
Tier-0, no delegation. A PASS would authorize only the orchestrator to Tier-0/stage/commit; this verdict
is REQUEST_REVISION, returning the slice to a bounded revision cycle with fresh hashes.

`RECORD: REQUEST_REVISION. Candidate hashes verified and design parts 1–4 present, but wait-mode
`| tee … || true` clobbers PIPESTATUS[0] → failed codex runs mislabeled done (criterion 4). Commit remains
unauthorized.`
