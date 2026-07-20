# delegate-to-codex quota pre-check — REVISED candidate acceptance authorization

**Status:** PREPARED_ONLY — fresh Claude-flagship binding acceptance (owner acceptance-lane-directive
2026-07-20). Prepared 2026-07-20, Fable 5 orchestrator (spot-review only; not binding).
**Required reviewer:** fresh Claude flagship, distinct from the Sonnet implementer AND from the first
acceptance reviewer (`claude-subagent-delegate-codex-quota-acceptance-reviewer`, whose
REQUEST_REVISION is retained lineage).

## Basis

The original candidate acceptance (`CANDIDATE-ACCEPTANCE.md`) returned REQUEST_REVISION on criterion 4
only — the `| tee … || true` idiom clobbered `PIPESTATUS[0]` to 0, mislabeling failed codex runs as
`done`/`success`. Criteria 1,2,3,5,6,7 PASSED. The bounded revision (auth `REVISION-AUTHORIZATION.md`
`9d6af07610643352e53dd9862f490a3e748feea5767b34118879c678201dfefc`) fixed exactly that.

## Frozen revised candidate (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/delegate-to-codex` | `d0f018a6a5d2ef505c7de907cc6ac879dd3a647f3312df87519ad1dcbf16f73d` |
| MODIFY | `scripts/testing/test-delegate-codex-quota-precheck.sh` | `2adcfead6fa2aeff481ede26152b51f4028ce8d469c615661dc9382b94293318` |
| FROZEN | `.gitignore` | `2ad65904e421190bcc2c20afad0f13e67b42bf6c49aef091419ca0440addce30` |

## Acceptance criteria

1. All three hashes match exactly; `.gitignore` unchanged; only the two MODIFY files changed vs the
   first-round candidate.
2. **The exit-code fix is correct in the bytes:** wait-mode now captures the true codex exit via
   `exit_code="${PIPESTATUS[0]}"` (not `|| true`), so a non-zero codex exit reaches the failed-status
   registry branch and the success branch fires only on genuine 0. Confirm `PIPESTATUS[0]` is not
   re-clobbered anywhere downstream.
3. **The new test genuinely catches the original defect:** the wait-mode failed-run test asserts
   registry `status=failed` and audit `outcome=error` (not done/success) on a non-zero stub exit, and
   would fail against the pre-fix `|| true` bytes. (The implementer reports having proven this by
   swapping the reconstructed pre-fix file back in — re-verify or spot-check the assertion logic.)
4. Everything previously accepted still holds (cooldown pre-check, both-mode capture, bypass, offline
   determinism, registry snapshot/restore).
5. Re-run fresh: `scripts/testing/test-delegate-codex-quota-precheck.sh` (all pass, offline, NO real
   codex/network — verify via stub marker), `bash -n` both files, `git diff --check`, secret-scan;
   confirm no `.codex-quota-cooldown` leaks and `.agents/delegation/` git status stays clean.
6. No prohibited action; nothing staged beyond these two (the five QPPR-A2 dashboard files staged
   alongside are a separate slice — do not conflate).

On PASS, the orchestrator runs Tier-0 and commits the three-file quota slice (the two MODIFY + the
frozen `.gitignore` line). A REQUEST_REVISION returns to a bounded cycle with fresh hashes.

`RECORD: PREPARED_ONLY. Binding acceptance by fresh Claude flagship; commit only after PASS.`
