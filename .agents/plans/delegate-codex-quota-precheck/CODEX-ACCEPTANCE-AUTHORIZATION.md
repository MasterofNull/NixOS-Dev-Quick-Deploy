# delegate-to-codex quota pre-check — codex acceptance authorization

**Status:** PREPARED_ONLY / QUEUED FOR CODEX — activatable by codex on its 2026-07-25 quota return
**Prepared:** 2026-07-20, Fable 5 orchestrator (spot-review only; not binding acceptance)
**Required reviewer:** codex (binding independent acceptance of the fix to its own dispatch path)
**Operating model:** staged-for-codex (`.agent/collaboration/CODEX-REVIEW-QUEUE.md` entry 2). The
candidate is staged (uncommitted); codex executes this acceptance on return; only after codex `PASS`
does the orchestrator run Tier-0 and commit.

## Frozen candidate subject (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/delegate-to-codex` | `3bbd82513846cf7fd39d6d4bf12fbce8a7f51fa7b721616445907adf727aa8a2` |
| NEW | `scripts/testing/test-delegate-codex-quota-precheck.sh` | `27dbb2e4c98b7fd6fbd4c544b74030433c87c43421be4a476a3a13d074079299` |
| MODIFY | `.gitignore` (one line: `.agents/delegation/.codex-quota-cooldown`) | `2ad65904e421190bcc2c20afad0f13e67b42bf6c49aef091419ca0440addce30` |

Predecessor `delegate-to-codex` = `90d41bb46aac705614f9cb8aad40f8242b6be0dd9c03d505932ae83b190c1711`.
Design/authorization = `.agents/plans/delegate-codex-quota-precheck/SLICE-DESIGN-AND-AUTHORIZATION.md`
(`660b0fe0c5c4ad1f58672c59e95cbe364f9ea1f75fa500f454c7067d9eb5f213`).

## Acceptance criteria for codex

1. Three-file hashes match exactly; nothing else in the staged set; runtime cooldown file
   `.agents/delegation/.codex-quota-cooldown` is gitignored and not staged.
2. Design parts 1-4 implemented as specified: cooldown state file; `quota_cooldown_active()`
   pre-check in `cmd_delegate` after the existing A2A guard/policy/budget checks (fast-fails via
   `die`, clears stale/corrupt cooldown); `quota_capture_from_output()` parsing `try again at
   <date>` → ISO-8601 UTC with bounded now+1h fallback, atomic write; bypass via
   `DELEGATE_CODEX_IGNORE_COOLDOWN=1` and `--force-quota-retry`, with forced-attempt re-arm.
3. **Both run modes covered:** wait-mode capture after the `tee`, and background/`nohup` mode via the
   `--internal-quota-capture` self-re-entry subcommand (the detached process cannot see the parent
   script's functions). Verify the self-re-entry is correct and bounded.
4. **Adjudicate the disclosed in-scope bug fix:** the candidate added `|| true` after wait-mode's
   `"${cmd[@]}" | tee "$output_file"` because `set -euo pipefail` otherwise aborted the script on a
   non-zero codex exit — before `exit_code`, the pre-existing failed-status registry update, *or* the
   new capture ran. Confirm `PIPESTATUS[0]` still captures the true codex exit code and the fix does
   not mask other failures. This is on the exact line the design targets and necessary for the
   capture to be reachable, but it is a behavior change to the existing failure path — verify it.
5. Fail-safe: no cooldown path can crash or fail the dispatch caller under `set -e`; healthy runs
   write no cooldown; unparseable reset writes a bounded cooldown, never unbounded/absent.
6. Re-run validation fresh: `scripts/testing/test-delegate-codex-quota-precheck.sh` (expect 12/12,
   fully offline — no real codex/network), `bash -n` on both files, `git diff --check`, secret-scan.
   Confirm the test snapshots/restores live registry + cooldown state and pollutes nothing.
7. No prohibited action: no other delegate-* wrapper / dispatch.py / registry-schema / A2 / QPPR file
   touched; no real codex or network invocation anywhere.

On codex `PASS`, the orchestrator runs `scripts/governance/tier0-validation-gate.sh --pre-commit`,
stages (already staged), and commits the three-file candidate. A codex `REQUEST_REVISION` returns the
slice to a bounded revision cycle with fresh hashes.

`RECORD: PREPARED_ONLY / QUEUED FOR CODEX. Binding acceptance and commit remain unauthorized until
codex reviews on return.`
