# delegate-to-codex quota pre-check — revision authorization (post-acceptance REQUEST_REVISION)

**Status:** PREPARED_ONLY — activatable under owner standing authorization
**Prepared:** 2026-07-20, Fable 5 orchestrator
**Required implementer:** `claude-subagent-delegate-codex-quota-implementer` (continuity; the verdict
supplies exact corrective direction)
**Binding acceptance after revision:** fresh Claude flagship reviewer (owner acceptance-lane-directive
2026-07-20), distinct from this implementer and the prior acceptance reviewer.

## Basis

Acceptance verdict `.agents/plans/delegate-codex-quota-precheck/CANDIDATE-ACCEPTANCE.md` returned
REQUEST_REVISION on criterion 4: the wait-mode `"${cmd[@]}" | tee "$output_file" || true` idiom runs
`true` on a non-zero codex exit, and `true` overwrites `PIPESTATUS`, so `PIPESTATUS[0]` reads 0 on
every failed run — pinning `exit_code=0`, firing the success branch, and marking a FAILED codex run
`status=done`/`success` (the pre-existing failed-status registry branch becomes dead code). Verified
empirically: real exit 37 → captured 0 with `|| true`; → 37 with the fix below. This is a
faithful-reporting regression (masks failures) and criterion-4 fail. Criteria 1,2,3,5,6,7 PASSED and
those bytes/behaviors are otherwise correct; background mode is correct (no set -e, no pipe).

## Ceiling: two MODIFY

| Path | Predecessor (rejected-candidate) SHA-256 | Op |
|---|---|---|
| `scripts/ai/delegate-to-codex` | `3bbd82513846cf7fd39d6d4bf12fbce8a7f51fa7b721616445907adf727aa8a2` | MODIFY |
| `scripts/testing/test-delegate-codex-quota-precheck.sh` | `27dbb2e4c98b7fd6fbd4c544b74030433c87c43421be4a476a3a13d074079299` | MODIFY |

`.gitignore` (`2ad65904…`) is FROZEN. No other file.

## Required revision (from the verdict, binding)

- **R1:** replace the wait-mode `| tee "$output_file" || true` with an idiom that preserves the true
  codex exit code, e.g. `local exit_code=0; "${cmd[@]}" ... | tee "$output_file" || exit_code="${PIPESTATUS[0]}"`
  (verified to yield 37 on a real 37 exit). The failed-status registry branch and the new quota
  capture must both remain reachable on a non-zero exit; the success branch must fire ONLY on a
  genuine zero exit. Preserve the pipefail-reachability intent of the original fix without clobbering
  `PIPESTATUS[0]`.
- **R2:** add a wait-mode test asserting `status=failed` (and a `failed`/error audit outcome, not
  `success`) when the stubbed codex exits non-zero — the coverage gap that let R1 slip (existing
  wait-mode test (a) asserts only the cooldown write, exit-code-independent).
- **R3:** correct the now-misleading inline comment to describe the actual behavior.

All prior passing behavior must be preserved: cooldown pre-check, both-mode capture, bypass, offline
determinism, registry snapshot/restore. Re-run the full suite (was 12/12; grows with R2).

## Validation & process

`scripts/testing/test-delegate-codex-quota-precheck.sh` (all pass, offline, no real codex/network),
`bash -n` both files, `git diff --check`, secret-scan. Governance events before edit (new intent id
`delegate-codex-quota-rev-20260720`). STAGE only the two MODIFY files; do NOT commit/Tier-0/self-accept.
A revised candidate needs fresh hashes and a NEW fresh-flagship binding acceptance; orchestrator
commits only after that PASS.

`RECORD: PREPARED_ONLY / single use. Activation under owner standing authorization names this exact
SHA-256, the implementer identity, and a ≤24h window.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-delegate-codex-quota-rev`, event_id `099715d110ed459b92ca169133bcaea2`, ts `2026-07-20T15:22:22Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
