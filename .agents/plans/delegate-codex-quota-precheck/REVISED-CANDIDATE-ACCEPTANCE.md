# delegate-to-codex quota pre-check — REVISED candidate BINDING ACCEPTANCE

**Reviewer:** fresh independent Claude flagship acceptance reviewer
(`claude-subagent-delegate-codex-quota-revised-acceptance-reviewer`), model
claude-opus-4-8. Distinct from the Sonnet implementer and from the first-round
reviewer (`claude-subagent-delegate-codex-quota-acceptance-reviewer`, whose
REQUEST_REVISION on criterion 4 is retained lineage). Not the orchestrator.
**Verdict is binding.**

**Date:** 2026-07-20
**Authority:** owner `[acceptance-lane-directive]` PULSE entry
2026-07-20T08:14:39-0700 (binding acceptance redirected from codex-wait to fresh
Claude flagship; commit on PASS). Confirmed present — CONFIRMED.
**Criteria SSOT:** `.agents/plans/delegate-codex-quota-precheck/REVISED-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md`

## Recomputed hashes (all match the authorization exactly)

| Op | Path | Expected | Recomputed | Match |
|---|---|---|---|---|
| MODIFY | `scripts/ai/delegate-to-codex` | `d0f018a6…6f73d` | `d0f018a6a5d2ef505c7de907cc6ac879dd3a647f3312df87519ad1dcbf16f73d` | ✅ |
| MODIFY | `scripts/testing/test-delegate-codex-quota-precheck.sh` | `2adcfead…93318` | `2adcfead26152b51f4028ce8d469c615661dc9382b94293318` (full: `2adcfead6fa2aeff481ede26152b51f4028ce8d469c615661dc9382b94293318`) | ✅ |
| FROZEN | `.gitignore` | `2ad65904…dce30` | `2ad65904e421190bcc2c20afad0f13e67b42bf6c49aef091419ca0440addce30` | ✅ |

No hash mismatch — review proceeded.

## Per-criterion evidence

### 1. Hashes match; `.gitignore` unchanged; only the two MODIFY files changed — PASS
All three SHA-256 recomputations match the authorization byte-for-byte. `.gitignore`
is frozen and hash-identical. The revision is confined to the two MODIFY files;
`.gitignore` carries only the pre-existing frozen cooldown-ignore line.

### 2. Exit-code fix is correct in the bytes — PASS
Wait-mode block (`scripts/ai/delegate-to-codex` lines 424–436):
```
local exit_code=0
"${cmd[@]}" < /dev/null 2>&1 | tee "$output_file" || exit_code="${PIPESTATUS[0]}"
quota_capture_from_output "$output_file" || true
if [[ "$exit_code" -eq 0 ]]; then  … status done / audit success
else                               … status failed / audit error
```
- `${PIPESTATUS[0]}` is expanded within the `||` right-hand side, at which point
  PIPESTATUS still reflects the `codex | tee` pipeline — it captures the TRUE codex
  exit code, not `tee`'s and not a reset value. A plain variable assignment does not
  run a pipeline that would reset PIPESTATUS before the expansion is read.
- No downstream re-clobber: line 426 (`quota_capture_from_output … || true`) runs
  AFTER the capture, and every subsequent branch (427, 433, 436) keys off the
  `$exit_code` **variable**, never re-reading `PIPESTATUS`.
- Contrast with the rejected `|| true` idiom, which ran `true` as its own
  one-element pipeline, resetting `PIPESTATUS[0]` to 0 before it was read.
The success branch now fires only on a genuine 0; a non-zero codex exit reaches the
failed-status registry branch and the error-outcome audit branch.

### 3. New test genuinely catches the original defect — PASS
Test case (g), lines 242–298, asserts three real behaviors on a non-zero (quota,
exit 1) stub run: info line "Task … failed.", registry `status=failed` (line 284,
read back via `--status` and JSON-parsed — a behavioral assertion, not a string
match), and audit `outcome=error` (line 293, parsed from a captured curl `-d`
payload). **Independently re-verified by reconstruction:** I rebuilt the pre-fix
`|| true` bytes and ran the identical isolated harness (real `lib/` sourced, same
stub, same env):
- PRE-FIX bytes → info "Task … completed.", registry `status=done` (DEFECT
  reproduced — (g) would fail).
- FIXED candidate bytes → info "Task … failed.", registry `status=failed` ((g)
  passes).
Same harness, same stub — only the two-line idiom differs. The test is a genuine
regression guard for the criterion-4 defect.

### 4. Everything previously accepted still holds — PASS
Full offline suite: **15 passed, 0 failed.** Covers cooldown write with parsed
reset time (a), fast-fail without invoking the stub during active cooldown (b),
both bypass paths — `DELEGATE_CODEX_IGNORE_COOLDOWN=1` and `--force-quota-retry` —
plus forced-attempt re-arm (c), expired-cooldown clear + proceed (d), healthy
success writes no cooldown (e), unparseable reset line → bounded ~1h fallback (f),
and background (nohup) run-mode capture via the `--internal-quota-capture`
self-re-entry for both quota (a-bg) and healthy (e-bg). Registry snapshot/restore
and cooldown isolation via the cleanup trap verified — real `.agents/delegation/`
left clean.

### 5. Re-run fresh, offline, static checks — PASS
- `test-delegate-codex-quota-precheck.sh`: 15/15 pass, exit 0. Offline confirmed
  via stub marker file (`(a) stub invoked exactly once`, `(b) stub NOT invoked`)
  and `HYBRID_COORDINATOR_URL=http://127.0.0.1:1`; a real codex on PATH is never
  reached because `CODEX_BIN` is stubbed and the marker proves the stub, not real
  codex, ran. The (g) curl is stubbed locally — no network I/O.
- `bash -n` both files: OK.
- `git diff --check`: clean (no whitespace errors).
- Secret-scan (api-key/secret/token/private-key/sk-/ghp_/AKIA patterns): only
  matches are safety-comment strings in the A2A outbound-guard documentation and a
  test comment — no actual secrets.
- No `.codex-quota-cooldown` leak: file absent post-run and confirmed gitignored
  (`git check-ignore` → IGNORED). `.agents/delegation/` git status clean.

### 6. No prohibited action; no conflation — PASS
Staged index contains exactly two slices. Quota slice (this verdict): `.gitignore`,
`scripts/ai/delegate-to-codex`, `scripts/testing/test-delegate-codex-quota-precheck.sh`
— matches the authorization. The five QPPR-A2 dashboard files
(`assets/dashboard.js`, `dashboard.html`,
`dashboard/backend/api/routes/aistack.py`,
`dashboard/backend/api/services/qa_runner.py`,
`scripts/testing/test-dashboard-qa-provider-probe.py`) are a separate staged slice
and are NOT part of this acceptance. Two untracked repo-root files
(`1ncat`, `1necho`) are shell-shim artifacts, unstaged and unrelated to either
slice — out of scope, not deleted (Rule 12).

## Verdict

VERDICT: PASS
