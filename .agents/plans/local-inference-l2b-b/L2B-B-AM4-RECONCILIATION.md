# L2B-B AM4 reconciliation — follow-up on committed L2B-B base

**Status:** PREPARED — Codex binding acceptance (isolated, stdout-only). Fable 5 orchestrator.
**Owner directive:** 2026-07-22 — reconcile the two parallel L2B-B tracks by adopting the stranded
Codex AM4 work as a follow-up slice on the committed Fable L2B-B base (`99364942`, R1/R2/R3), rather
than running duplicate tracks. The Codex AM track (AM2–AM5) is paused; this record captures its
completed AM4 candidate under a single reconciled authority.

## Background (both tracks legitimate; safety discipline held)

The owner ran a Fable L2B-B revision track (R1/R2/R3, committed `99364942`) and a Codex AM track
(`codex-subagent-l2b-b-am2/am3/am4-implementer`) in parallel. The Codex track's fail-stop discipline
correctly prevented clobbering: AM2 zero-write-stopped on the overlapping Fable auth; AM4 completed +
offline-validated its candidate, then fail-stopped on HEAD drift (authorized `99364942` advanced to
`e5578e5c` when Fable committed VF-7), leaving its work **unstaged** and requesting an AM5 refreeze.
This reconciliation is that refreeze, rebased to current HEAD, under one authority.

## Candidate (the stranded AM4 work, now on HEAD `e5578e5c`)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | `e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82` |
| MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `a72c796368229865e7689a0069791d6f9789311992de7fbcdd85655a68307cd6` |
| MODIFY | `dashboard/backend/api/routes/aistack.py` | `a5831eecf7b36cc178f72565a998836133e512e66c17d291e92fbc80cb28d8b6` |

Base: committed L2B-B at `99364942` (transport `39ee836f`, test `33ab4d84`, aistack pre-passthrough).

## What the AM4 work adds (over the committed R1/R2/R3 base)

1. **NFC key-collision detection** — when two distinct object keys collapse to the same key after NFC
   normalization, fail closed with `nfc_key_collision` (rather than silently dropping one). Tested
   (`{"é":..., "é":...}` → rejected).
2. **VRAM budget canonicalization** — resident-model names are NFC + casefold + strip canonicalized
   before budgeting, so declaration variants can't evade the 27GB guard.
3. **Backend passthrough** — `dashboard/backend/api/routes/aistack.py`
   `_local_inference_l2b_health_sync()` now passes through `payload_normalization_status` (default
   "unavailable", fails closed), closing the follow-up the R1/R2/R3 implementer disclosed so the
   dashboard row renders real status instead of always "unavailable". This is the one file OUTSIDE the
   original L2B-B ceiling — legitimately in scope for this follow-up.
4. Corresponding tests for all three (suite includes the collision, VRAM-canonical, and
   normalization-status-projection cases).

## Acceptance criteria for Codex

1. Recompute the 4 hashes (read files directly); confirm match.
2. The three additions above are present in the bytes and correct: collision detection fails closed
   with a structured audit trace (no leak); VRAM canonicalization can't be evaded; the aistack
   passthrough defaults to "unavailable" / fails closed and does not fabricate a value.
3. No regression to the committed R1/R2/R3 behavior (NFC value+key normalization, opaque
   REJECTED_SCHEMA_INVALID, VRAM guard, credential-leak guard, key sort, non-finite strip).
4. `python3 scripts/testing/test-local-inference-l2b.py` passes (offline); py_compile the transport;
   `git diff --check` clean; no secret/credential added.
5. `dashboard/backend/api/routes/aistack.py` change is minimal + additive (passthrough only; the A2
   `_qaProbe*` and other health fields untouched).

Isolated, stdout-only verdict (do not write files — the sandbox blocks `.agents` writes; the
orchestrator records the verdict). Terminal line `VERDICT: PASS` or `VERDICT: REQUEST_REVISION — …`.

`RECORD: PREPARED. Codex binding acceptance; commit only after PASS. Supersedes/absorbs the paused
Codex AM2–AM5 track for L2B-B.`
