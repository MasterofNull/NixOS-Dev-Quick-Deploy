# Focused Re-Review — factory/c6d-impl-v3 (closure of REVIEW-c6d-impl-20260925.md)

**Reviewer**: independent, read-only on git (`command git`), scratch-copy test execution only.
**Subject**: `factory/c6d-impl-v3` @ `4c6db070`, based on `origin/main` (fetched fresh).
**Baseline**: `.agent/collaboration/REVIEW-c6d-impl-20260925.md` — prior binding review, disposition `REQUEST_REVISION, NO HIGH`. Exactly-once/crash-consistency was already verified solid there and is **not re-litigated**; this pass only confirms the v2→v3 delta didn't disturb it, and confirms closure of the two coupled MEDIUM findings.

## Disposition

**VERDICT: APPROVE**

## Digest reproduction

```
command git diff origin/main..factory/c6d-impl-v3 | sha256sum
f0d12c24ffe610e0d04e912d60851fae71040542058402901cd4679a89c63251
```
Matches the required digest exactly. No subject drift.

Fix delta (`factory/c6d-impl-v2..factory/c6d-impl-v3`) touches **only**:
```
scripts/ai/lib/revocation_epoch.py       |  64 +++++++++++--   (+64/-6, matches spec)
scripts/testing/test-revocation-epoch.py | 159 +++++++++++++++ (+159/-0, purely additive)
```
Confirmed via `git diff --numstat` — 0 deletions in the test file (all prior assertions retained verbatim, none edited/removed). Nix module (`nix/modules/services/revocation-epoch-authority.nix`), transport (`scripts/ai/lib/revocation_epoch_transport.py`), owner-keys (`config/aqos/c6-owner-public-keys.json`), and the phase0 QA registry are **untouched** by this delta (they were already part of the v2 baseline vs `origin/main`, not part of this fix) — `enable=false` gating intact, nothing re-opened.

## Finding 1 — audit_pending persisted + reconciled: **CLOSED**

Verified directly against `factory/c6d-impl-v3:scripts/ai/lib/revocation_epoch.py`:

- **Committed branch persists then reconciles** — `apply_bump` step 5 now writes `committed_entry["audit_pending"] = True` into the same atomic rewrite that sets `phase="committed"` (line 1210), *before* the best-effort append attempt (step 6, lines ~1231-1238). On append success it does a second atomic rewrite clearing the flag to `False` (lines 1236-1238); on `OSError` it leaves the persisted entry as `audit_pending=True` and only marks the *in-memory receipt* `audit_pending=True` (line 1235) — the durable record already carries the correct value from step 5, no separate write needed on the failure path.
- **`_reconcile_audit_pending`** (lines 782-804): retries `_append_audit_receipt`; on `OSError` returns `dict(entry)` unchanged — audit_pending stays `True`, nothing cleared speculatively (fail-closed, confirmed). On success it clears the flag via `_atomic_rewrite_journal_entry` (the *existing* temp+fsync+rename primitive at line 723 — same one used everywhere else in the file, e.g. `_write_epoch_atomic`), then returns the reconciled dict. Never raises.
- **`resolve()`'s committed branch** (lines 852-862): `if entry.get("audit_pending", False): entry = _reconcile_audit_pending(...)`, then unconditionally `return _receipt_ok_from_entry(entry)` — same exactly-once return path as before, now operating on the (possibly reconciled) entry.
- **Vector g / intent→committed finalize branch** (lines 871-884): identical treatment — sets `audit_pending=True` on the finalize rewrite, then immediately calls `_reconcile_audit_pending`, then builds the receipt from the reconciled entry.
- **(a) Additive-only, confirmed**: `resolve()`'s identity-conflict row (line 844-848, `DENY_IDENTITY_CONFLICT`) returns *before* the phase dispatch — unreachable from the audit-reconciliation code. The `intent`→CAS-never-happened row (`DENY_RETRY`, lines 885-894) and the `aborted`/dangling-index row (`DENY_RETRY`, lines 902-911) are separate `if phase == ...` branches, structurally untouched by this diff (confirmed by the `git diff` hunks — no lines inside those branches changed). The epoch CAS (`read_epoch`/`write_epoch`) is not touched by `_reconcile_audit_pending` at all — it only appends to the audit JSONL and rewrites the journal entry file.
- **(b) Fail-closed, confirmed**: the only way `audit_pending` clears is a *confirmed* successful append (no exception raised) followed by the rewrite; any `OSError` short-circuits to `return dict(entry)` before the rewrite is even attempted.
- **(c) Primitive reuse, confirmed**: `_atomic_rewrite_journal_entry` (line 723) is the same same-directory-temp + `fsync(file)` + `os.replace` + `fsync(dir)` primitive used for every other phase transition (`intent→committed/aborted`, `aborted→intent` tombstone reuse per its own docstring, line 723-727) — no new write primitive was introduced, no new crash window beyond the ones already accepted for phase transitions.
- **(d) Reconstructed receipts report true state, confirmed**: `_receipt_ok_from_entry` (line 768-779) reads `entry.get("audit_pending", False)` directly off the entry passed in — since `resolve()` reconciles the entry *before* calling this, the receipt always reflects the entry's true post-reconciliation state (or true still-pending state on a failed retry).

One minor, out-of-scope, non-blocking observation: there is a narrow crash window between a *successful* append in `apply_bump` (step 6) or `_reconcile_audit_pending` and the follow-up atomic rewrite that clears the flag — a crash there would leave `audit_pending=True` durably, and a later `recover()` would retry the append, producing a duplicate (but harmless) audit-log line. The audit log is explicitly documented (line 613-619) as best-effort observability, *not* authoritative for whether the bump happened, so this doesn't threaten exactly-once or crash-consistency of the epoch/journal state — the actual subject of the binding review. Not raised as a finding; noting for completeness only.

## Finding 2 — the two tests: **CLOSED**

Read both tests directly from `factory/c6d-impl-v3:scripts/testing/test-revocation-epoch.py`:

- `test_vector_h_audit_pending_persisted_and_reconciled` (lines 810-901): monkeypatches `_append_audit_receipt` to raise `OSError`, does a live `apply_bump`, and asserts: bump still `ok=True`; immediate receipt `audit_pending=True`; epoch advances 0→1; no audit line written; **on-disk journal entry durably has `audit_pending=True`**; a receipt reconstructed from that on-disk entry via `_receipt_ok_from_entry` also reports `True` (never a hardcoded `False`). It restores the real append, calls `recover()`, and asserts `resolved_committed == 1`, on-disk entry now `audit_pending=False`, **exactly one** audit line was written, epoch is still `1` (no double-bump), and a `resolve()` reconstruction after reconciliation reports `audit_pending=False` with `old_epoch=0, new_epoch=1` unchanged. This is exactly the exercise the review charter specified.
- `test_case2_live_reverse_cross_identity_conflict_denies` (lines 904-964): same `idempotency_key`, different `request_id`, live path. Asserts `second["ok"] is False`, `second["reason"] == DENY_IDENTITY_CONFLICT`, `second.get("receipt") is None`, epoch stays at `1`, doc2's own freshly-created request-id index was rolled back, the legitimate entry's by-idempotency-key index and by-request-id index are both untouched, and the legitimate journal entry is still `phase="committed"` and unchanged. Matches the charter's ask exactly.

## Regression check on the exactly-once core

No lines inside the `DENY_IDENTITY_CONFLICT` gate, the `intent`-CAS-never-happened abort branch, the `aborted`-tombstone branch, `apply_bump`'s reservation/CAS steps 1-4, or `_atomic_rewrite_journal_entry`/`_write_epoch_atomic`/`_create_exclusive_json` were touched by this delta (confirmed by inspecting the full diff hunks — the only additions are the new `_reconcile_audit_pending` function and the `audit_pending` bookkeeping inside the `committed` branch, the intent→committed finalize branch, and `apply_bump` steps 5-6). The exactly-once epoch CAS and journal-phase state machine verified in the prior binding review are structurally unchanged.

## Test suite — real count

Ran the suite (not pytest — the file is a self-contained assertion counter with its own `main()`), from a scratch mirror (`<scratch>/scripts/ai/lib/revocation_epoch.py`, `<scratch>/scripts/testing/test-revocation-epoch.py`, `<scratch>/config/aqos/c6-owner-public-keys.json`, pulled via `git show factory/c6d-impl-v3:<path>`) so `REPO_ROOT = Path(__file__).resolve().parents[2]` resolves correctly, no in-tree checkout performed:

```
136 passed, 0 failed (of 136 assertions)
```

Cross-checked against a second scratch mirror built from `factory/c6d-impl-v2` (pre-fix): **113 passed, 0 failed** — the pre-fix baseline. Since the test-file diff is purely additive (`+159/-0`, no deletions), the 23 new assertions (`136 - 113`) come entirely from the two new tests above, and all 113 prior assertions are verbatim-preserved and still passing. No regression.

## Summary

- Digest: exact match, no drift.
- Files touched by fix: exactly the 2 named files; Nix module/transport/registry/owner-keys untouched, `enable=false` intact.
- Finding 1: **CLOSED** — persisted, reconciled, fail-closed, additive, correct primitive reuse, vector-g mirrored correctly.
- Finding 2: **CLOSED** — both tests exercise exactly what was asked and pass.
- Regression: exactly-once core untouched; 113/113 prior assertions still pass; 136/136 total pass.

**VERDICT: APPROVE**
