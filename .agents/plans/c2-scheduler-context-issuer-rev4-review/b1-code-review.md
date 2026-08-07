# C2 Scheduler-Context Issuer B1 — Independent Code Review

**Commit:** `e01d48a7` (foundation-c: C2 scheduler-context issuer B1)
**Reviewer:** Fresh Claude Opus 4.8 flagship (Codex-substitute, Rule 18). NOT the author (sonnet implementer).
**Scope:** `scheduler_context_issuer.py`, `scheduler_context_transport.py`, `test-scheduler-context-issuer.py`.
**Design:** `.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md` (rev4 §2/§3/§4).
**Method:** Read actual committed code; consumed `capability_lease.py` as-is; ran both suites.

---

## Verification against the 9 review points

### 1. TRUST ROOT — PASS
`mint_scheduler_context` step 1 (issuer.py:255-257) calls `cl.verify_authoritative(presented_lease, keys_json_dict)` FIRST and returns `_deny(DENY_LEASE_UNVERIFIED)` on `not verdict.ok`. Every subsequent step (OBLIG-1, admission extraction, ledger, sign) is reached only after this passes. There is no code path in the function that assembles/signs a context without a passing verdict — the context dict is not even constructed until after ledger+signer checks (issuer.py:308-329). Trust is the signed lease. The caller / `correlation` / `SO_PEERCRED` are never consulted for authority. **Confirmed: no mint without a verified lease.**

### 2. OBLIG-1 — PASS
After verify, issuer.py:267-270 independently calls `cl.is_expired(lease_data, now=now)` → `DENY_LEASE_EXPIRED`, then `cl.epoch_stale(lease_data, current_epoch)` → `DENY_LEASE_EPOCH_STALE`, both before any admission extraction, ledger record, or sign. `verify_authoritative` proves provenance only (checks sig_scheme/key/signature — never expiry/epoch), so these two checks are genuinely additive and mandatory. Correct.

Note (informational, not a B1 defect): the design prose (§ line 48) phrases the epoch check as `revocation_epoch != current epoch`, whereas `capability_lease.epoch_stale` uses strict `<` (issuer consumes it as-is per instruction). A lease with `revocation_epoch > current` would pass. This is **not exploitable**: `revocation_epoch` is a signature-covered field (in `canonical_payload`), set to the current epoch at mint and monotonic — an attacker cannot forge a future-epoch signed lease, and a real signer never mints one ahead of the authority epoch. Inherited shared-lib semantics, flagged for design-prose reconciliation only.

### 3. RE-DERIVATION — PASS
`_extract_admission_fields` (issuer.py:186-217) reads `lease_id`, `grant_digest`, `trust_tier`, `policy_revision` ONLY from `lease_data` (the verified lease) with strict type checks (`bool` explicitly rejected for the int fields), and `action_class` via `_derive_action_class` from `permissions.actions` — never caller input. All these fields are inside `canonical_payload` (capability_lease.py:185 includes every field except `signature`), so they are signature-bound; extraction after a passing verify means they are authentic.
`_extract_correlation_fields` (issuer.py:220-235) reads EXACTLY `{task_id, principal, dispatch_mode}` via a fixed `REQUIRED_CORRELATION_FIELDS` loop; any extra key in `correlation` is structurally never read. Context assembly (issuer.py:308-329) sources authority fields from `admission[...]` and only the 3 dispatch fields from `correlation_fields[...]`. **Extra correlation keys are inert; correlation cannot widen authority.**

### 4. SINGLE-USE LEDGER + ordering — PASS (ordering choice CORRECT)
Ledger key is `(admission["lease_id"], admission["grant_digest"])` (issuer.py:299) — per-lease, NOT per-task (`task_id` is not in the key). `check_and_record` is an atomic check-and-record contract; a second attempt returns False → `DENY_REPLAY`. A raising ledger is caught → `DENY_LEDGER_UNAVAILABLE` (fail CLOSED, issuer.py:301-305).
**Ordering assessment:** the ledger records at step 4, BEFORE the signer step 5. I **agree** this is the correct fail-closed single-use choice: record-before-sign guarantees the `{lease_id,grant_digest}` can mint at most once even if the signer partially fails after the record — the lease is consumed and future attempts deny. The alternative (sign-then-record) could mint a valid context and then fail to record it, allowing a second valid mint = fail-open. Correctly chosen.
Note (operational, for B2 — not a B1 security defect): with the durable ledger B2 will add, a *transient* signer outage after the record permanently burns an otherwise-valid lease (availability cost). This is the correct security tradeoff (fail-closed > fail-open); flag it for the B2 durable-ledger design so the burn is observable/intervenable. Also correct: correlation-malformed and key-id-missing denies occur BEFORE the ledger record (issuer.py:290-297), so a caller-side input error does not burn the lease.

### 5. FAIL-CLOSED / TOTAL — PASS
Every deny path returns `_deny(...)` with `"context": None` (issuer.py:158) — nothing minted. An outer `try/except Exception` (issuer.py:254, 331-332) makes the function total: any unhandled exception (e.g. missing `expires_at` KeyError after verify, since `verify_authoritative` does not validate expiry-field presence) returns `DENY_LEASE_FIELDS_MALFORMED`, never propagates. Signer-unavailable: `not private_key_bytes` / non-bytes → `DENY_SIGNER_UNAVAILABLE` (issuer.py:307); a raising `sign_ed25519` (bad-length/invalid key material) is caught → `DENY_SIGNER_UNAVAILABLE` (issuer.py:329-330). No env fallback, no unsigned path. Correct.

### 6. CONTEXT SIGNATURE — PASS
Minted context sets `sig_scheme: cl.SIG_SCHEME_ED25519`, `issuer_key_id: key_id`, `signature: ""` then `cl.sign_ed25519(context, ...)` (issuer.py:325-327). `sign_ed25519` signs `canonical_payload` which excludes only `signature`, so `sig_scheme`/`issuer_key_id` are signed. `verify_scheduler_context` (issuer.py:335-342) calls `verify_authoritative(context, signer_keys_json)` — scheme-pinned to ed25519, resolves `issuer_key_id` against the SEPARATE context-signer allowlist family (`c6-scheduler-signer-keys.json` per design §2). Test proves the context verifies under the context-signer key and does NOT verify under the lease-signer allowlist (test.py:169-171). Correct key-family separation.

### 7. TRANSPORT — PASS
`get_peer_credentials` reads `SO_PEERCRED`, returns None on failure, never raises, and the docstring + `serve` comment mark it log-only (transport.py:60-67, 175). Authority is never derived from it. `read_frame` is size-bounded (`MAX_REQUEST_BYTES`, `DENY_OVERSIZE`), timeout-bounded (`socket.timeout` → `DENY_TIMEOUT`), and returns typed denies for empty/malformed JSON/non-dict — never raises past itself. `serve` wraps the handler in try/except (`handler-error` deny) and the whole per-connection block in a bare try/except with `finally: conn.close()` — one bad connection never crashes the loop. Response is truncated to `MAX_RESPONSE_BYTES`. Socket created `0o660`, optional client-group chgrp fails closed (issuer-only) with a WARN. Correct defense-in-depth posture.

### 8. TESTS — PASS (genuine, 53/53)
Ran: `53 passed, 0 failed`. Regression `test-capability-lease.py`: `54 passed, 0 failed` (shared lib untouched). Leases are built with REAL `cl.sign_ed25519` over two independent throwaway Ed25519 keypairs (lease-signer vs context-signer) — not mocked. Specifically verified the load-bearing vectors are honest, not passing-for-the-wrong-reason:
- **Replay is per-lease not per-task:** `test_single_use_replay_per_lease_not_per_task` mints once, then re-mints the SAME lease under `task_id="task-2-DIFFERENT"` and asserts `DENY_REPLAY` — proves the ledger key excludes task_id.
- **Correlation can't widen:** `test_correlation_cannot_widen_authority` stuffs `trust_tier:999`, `action_class`, `policy_revision:999`, `grant_digest`, `lease_id` into correlation; asserts the minted context carries the LEASE's values (2 / run_cmd / 1 / digest-1 / lease-1) and that the 3 real correlation fields pass through. Genuine.
- **OBLIG-1 denies:** expired and epoch-stale (epoch 1 vs current 5) both assert deny + no context.
- **expires_at = min:** both branches tested (cap-bound 300s and lease-bound 5min).
- **Forgery:** both bit-flipped signature AND a lease signed by an off-allowlist key deny with `DENY_LEASE_UNVERIFIED`.
- **Fail-closed:** raising ledger → `DENY_LEDGER_UNAVAILABLE`; None/empty/wrong-length key → `DENY_SIGNER_UNAVAILABLE`.
- **Transport smoke:** real socketpair, `SO_PEERCRED` tuple, malformed-JSON and oversize denies.
No vector observed passing for the wrong reason.

### 9. Fail-open / oracle / defect scan — NONE FOUND (HIGH-severity clean)
No path mints on an unverifiable, expired, epoch-stale, malformed, replayed, or ledger-faulting lease, nor with unavailable/invalid signer material. No signature/timing oracle: `verify_authoritative` uses `public_key.verify` (constant-time Ed25519) and denies uniformly with `AUTH_DENY_BAD_SIGNATURE`; deny reasons carry no security-bearing detail. Canonicalization is shared between sign and verify (excludes `signature` only), so no sign/verify field-coverage mismatch. `sig_scheme` is signed and scheme-pinned before any key lookup — no HMAC/dev-key fallback reachable.

---

## Observations (non-blocking, informational)
- **O1 (design-prose reconciliation):** `epoch_stale` semantics are `<` (monotonic staleness), design §line 48 prose says `!=`. Not exploitable (revocation_epoch is signed + monotonic); reconcile the prose or note the intended `<` in a later rev. Shared-lib behavior, consumed as-is.
- **O2 (B2 durable-ledger):** record-before-sign (correctly fail-closed) will burn a valid lease on a transient signer outage once the ledger is durable. Make that burn observable/intervenable in B2 (Activation Gate). Not a B1 issue.
- **O3 (documented seam):** `InMemorySingleUseLedger` is per-process, non-durable — explicitly a B2 seam; correct for an INERT B1.

## Activation posture
Correctly INERT: no imports of these modules exist in the tree; `serve()` has no B1 entrypoint (`__main__` exits 1); default-OFF. Matches the commit claim.

---

**VERDICT: PASS**
