# C6-B1 Independent CODE Review — Revocation-Epoch Kill-Switch Primitive

- **Commit:** `91c91f36` — feat(foundation-c): C6-B1 durable authenticated revocation-epoch primitive + bump CLI (default-OFF, unwired)
- **Reviewer:** Fresh Claude flagship (Opus 4.8), Codex-substitute per Rule 18. NOT the author.
- **Date:** 2026-08-07
- **Scope:** 3 new files — `scripts/ai/lib/revocation_epoch.py`, `scripts/ai/aq-epoch-bump`, `scripts/testing/test-revocation-epoch.py`. Verified against ACTUAL committed code.
- **Method:** Line-by-line read of all 3 files; ran both test suites; grepped the whole repo for env reads, mutation callers, and wiring.

## Verification results (most-critical first)

### 1. FAIL-CLOSED EPOCH READ — no bootstrap-to-zero — PASS (HIGH)
`read_epoch` (`revocation_epoch.py:150-197`) raises a typed `EpochStoreError` on every bad-read class and NEVER returns a sentinel `0`:
- missing / `NotADirectoryError` → `EPOCH_ERR_MISSING` (`:164-167`)
- symlink: opened `O_NOFOLLOW`, `ELOOP` → `EPOCH_ERR_SYMLINK` (`:161,169-170`)
- non-regular: `fstat`+`S_ISREG` → `EPOCH_ERR_NOT_REGULAR` (`:175-176`)
- oversized: `len(raw) >= 65536` → `EPOCH_ERR_MALFORMED`, refuses to parse a truncated read (`:177-181`)
- non-UTF-8 → `EPOCH_ERR_MALFORMED` (`:190-192`)
- malformed content: strict `^(0|[1-9][0-9]*)$` after strip; empty/no-match → malformed (`:134,194-195`)
- other `OSError` → `EPOCH_ERR_IO` (`:168-171,184-185`)

The **only** path that returns `0` is a present, strict `"0"` (genesis) at `:197`. The sole caller inside the flow, `apply_bump`, converts `EpochStoreError` into a deny (`:592-594`) — it never turns a read failure into epoch 0. Proven end-to-end by `test_no_bootstrap_to_zero_end_to_end` (store stays absent, `reason=epoch-store-missing`).

### 2. ATOMIC +1, private, single caller — PASS (HIGH)
`_write_epoch_atomic` (`:508-527`): same-dir `mkstemp` → write → `fsync(file)` → `os.replace` → `fsync(dir)`. Repo-wide grep confirms exactly one invocation — `apply_bump:612`. It is private, and `new_epoch = current + 1` (`:610`) is the only value ever written — there is no arbitrary-set path and no public epoch writer.

### 3. VERIFY-BEFORE-MUTATE + ordering — PASS (HIGH)
`apply_bump` (`:553-636`) executes strictly: `verify_bump` (no state touched, `:577-579`) → exclusive `flock` (`:586`) → `read_epoch` under lock (`:592`) → `expected_epoch == current` else `DENY_EPOCH_MISMATCH` (`:596-600`) → durable `ledger.check_and_record` O_EXCL+fsync, replay → `DENY_REPLAY` (`:602-608`) → **only then** `_write_epoch_atomic` (`:612`). All under one lock, released in `finally` (`:634`).
- A **replay** or a **stale/forged** bump reaches NO mutation — verified by `test_replay_*` (epoch stays 1) and `test_expected_epoch_mismatch_denies` (stays 7).
- **Replay-record-before-write is strictly safer**, confirmed: the ledger slot is keyed on the *signed* `{request_id, idempotency_key}` (both fields are inside the canonical signed payload, so they cannot be swapped without breaking the signature). No double-advance is possible.
- **Slot-burn does NOT fail open:** if the ledger records the key and the write then fails (`DENY_EPOCH_WRITE_FAILED`, `:613-614`), the epoch is unchanged, so a *fresh* signed request with the same `expected_epoch` still succeeds. The burned request_id denies as replay, but the remedy (new signed request) is available and the failure direction is denial, never a silent advance.

### 4. No env fallback / no auto-reissue / total functions — PASS
- Repo grep: `os.environ`/`os.getenv` appear ONLY in a docstring (`:26`), never in executable code. Every trust-bearing path (epoch/ledger/keys) is an explicit argument.
- `verify_bump` (`:376-405`) and `apply_bump` (`:553-636`) are both wrapped in an outer `try/except` that returns a typed deny (`BumpVerdict(False, DENY_MALFORMED,...)` / `_bump_deny(DENY_INTERNAL,...)`) — neither raises into the caller.
- No retry/re-sign/re-submit logic anywhere.
- Placeholder all-zeros owner key denies **naturally**: `Ed25519PublicKey.from_public_bytes` accepts the 32 zero bytes, then `verify` raises `InvalidSignature` → `DENY_BAD_SIGNATURE` (`:368-371`). No all-zeros special-case shortcut. Proven by `test_placeholder_owner_key_denies` against the real committed `config/aqos/c6-owner-public-keys.json` (confirmed all-zeros, status active).
- Per-call `status == "active"` re-check, no caching (`:349-352`).

### 5. CLI holds no private key, never writes epoch, fail-closed — PASS
`aq-epoch-bump` (`aq-epoch-bump:1-186`): `build` prints canonical bytes for OFFLINE signing and holds no key (`sign_bump` is never called here); `submit` calls `apply_bump` only (`:133`) — no direct epoch write mechanism exists. Defaults resolve `--owner-keys` to the all-zeros placeholder, so a default `submit` fail-closes until real keys are provisioned. `--ledger-dir` is required with no default. `build` denies if `read_epoch` fails unless `--expected-epoch` is explicit (`:58-67`). Exit code 2 on any deny.

### 6. Tests genuine — PASS
Real fresh Ed25519 keypairs (`_make_keypair`), temp epoch file + temp ledger dir, restart-simulated replay via a NEW `DurableReplayLedger` on the SAME dir (`:319`). The replay test deliberately sets `expected_epoch=1` to isolate the replay-ledger deny from epoch-mismatch (`:327-338`) — no vector passes for the wrong reason. Placeholder test signs with a real key against the placeholder allowlist, proving a genuine crypto failure rather than a shortcut. Both suites run clean: **test-revocation-epoch 55/55**, **test-capability-lease 54/54**.

### 7. Fail-open / oracle / non-atomic sweep — none found (HIGH)
No path advances the epoch for a forged/replayed/stale bump; no read failure yields 0; no double-advance; no non-atomic window (single `os.replace`, held lock, fsync file+dir). The signed payload binds `actor_key_id`, `expected_epoch`, `request_id`, and `idempotency_key`, closing signature-reuse/replay-key-swap. Domain tag (`:114`) prevents cross-family signature reuse. Module is genuinely unwired — repo grep shows no importer of the `revocation_epoch` module besides the CLI and its test (all other `revocation_epoch` hits are an unrelated lease/grant *field name*).

## Observations (non-blocking, LOW)
- **O1 (observability, not fail-open):** if `_write_epoch_atomic` raises *after* `os.replace` but during the trailing dir-`fsync` (`:523-527`), the epoch is already durably advanced yet the call returns `DENY_EPOCH_WRITE_FAILED` and burns the ledger slot. This is over-revocation (the SAFE direction) reported as a failure — a false-negative report, never a silent success or a missed revocation. The stale request then denies via epoch-mismatch; a fresh request reads the advanced epoch. Acceptable; worth a one-line note when C6-B2 wires audit/alerting so an operator isn't misled by the deny string.
- **O2:** `DurableReplayLedger.stats()` counters reset on restart (documented at `:478-483`); durability lives in the marker files, so decisions remain correct. Fine.

Neither observation is a defect in this slice's stated scope (durable, fail-closed primitive). Both are downstream-wiring notes for C6-B2/B3.

## Conclusion
The primitive is fail-closed on every axis the C6 design requires: no bootstrap-to-zero, no env fallback, single private atomic +1 mutation gated behind verify → epoch-match → durable replay-check, total functions, offline-signing CLI with no key material, and honest tests. No forged/replayed/stale bump can advance the epoch; no read failure degrades to 0; no double-advance or non-atomic window exists.

VERDICT: PASS
