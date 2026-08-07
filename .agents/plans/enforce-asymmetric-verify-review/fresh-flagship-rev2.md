# Independent Binding Re-Review (rev2) — ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807

- Reviewer: fresh flagship (Claude Opus 4.8), substituting for quota-blocked Codex per Rule 18.
- Role: INDEPENDENT BINDING reviewer. Focused confirmation pass gating a freeze.
- Date: 2026-08-07
- Scope: confirm rev2 converted rev1 findings F1–F5 into pinned normative requirements N1–N5,
  and that nothing new is broken. Crypto core was CONFIRMED SAFE in rev1; not re-litigated
  (no regression found).

## VERDICT: PASS — rev2 is freeze-ready; N1–N5 pinned normatively.

## Confirmation matrix (design § + code anchor verified)

1. **N1 (was F1, keys_json load-site)** — PINNED. §Rev2 lines 26–32 make it a MUST: `json.loads`
   into a **dict** (raw string denies-ALL and is explicitly forbidden), inside a LOCAL try/except
   yielding a deny-all sentinel `{}` (never a raise), no exception propagation to the S-c wrapper
   (`capability_lease_gate.py:736` — verified: that wrapper total-denies EVERY tool incl. HMAC),
   and a failed cached load stays sentinel. HMAC path unaffected (never reads keys_json). All four
   rev1 sub-constraints present. ✓

2. **N2 (was F2, helper placement)** — PINNED. §Rev2 lines 33–38: `_admission_verify` MUST be
   called INSIDE the existing try/except in BOTH branches (`:644-647` candidate, `:689-692`
   first-party — both verified), with the exact rationale: `is_expired`→`_parse_iso(expires_at)`
   raises on a signed-but-malformed temporal; inside the try it maps to `VERIFY_MALFORMED` → one-
   tool DENY; outside it escapes to `:736` and total-denies all tools. Normative, not incidental. ✓

3. **N3 (was F3, the most important)** — PINNED. §Rev2 lines 39–49 + §5 lines 162–167 mandate a
   pre-flip dry-run of the FULL `enforce()` path, not just `verify_authoritative`: (a) lease↔lookup
   `tool in bound_actions` (`:681-688`), (b) the codex-3 projection-equality tripwire
   (`:705-713`) — spelled out as authority-projection byte-equals switchboard manifest projection,
   SAME `first-party-tools.json`, identical risk-block stamping, (c) layered expiry/epoch. ✓

4. **N4 (was F4, epoch parity)** — PINNED. §Rev2 lines 50–56: authority `revocation_epoch` stamp
   and enforce `epoch_stale(lease, resolve_current_epoch())` MUST resolve the IDENTICAL source
   (env `AQ_LEASE_POLICY_EPOCH` → `config/capability-lease-epoch` → 0), stated as an activation
   gate, with both failure directions (self-stale outage / over-live fail-open) documented. ✓

5. **N5 (was F5, HMAC secret)** — PINNED as activation NOTE. §Rev2 lines 57–61: keep the HMAC SOPS
   secret provisioned post-flip; `is_dev` degrade to `SAFE_READ_ALLOWLIST` fires BEFORE any lease
   logic (`:609-614` verified) even under asymmetric mode. Non-blocking, documented. ✓

6. **Q-E1 / Q-E4** — RESOLVED. §Rev2 lines 63–68 + §3 lines 128–129: single shared
   `_admission_verify` for both branches (guarantees uniform N4 layering; opens no admit path —
   worst case is replay of a genuine authority-signed lease, still expiry/epoch/zero-trust gated;
   candidate branch correctly skips the first-party-only codex-3 tripwire). Q-E4 (§3 lines 132–136):
   verify is per-lease `sig_scheme`-dispatched and flag-agnostic; flag stays mint-side in
   `switchboard.nix`, so a flip rebuilds+restarts and re-inits `_FIRST_PARTY_LEASE_CACHE=None`
   (`:326`) — no hot cross-scheme cache window. ✓

7. **Test vectors §4 (9/10/11)** — EXERCISE N1/N2/N4.
   - V9 (N2): signed-but-malformed `expires_at` → one-tool DENY; asserts the exception does NOT
     escape the branch (other tools + HMAC leases still evaluate). ✓
   - V10 (N1): keys-file read/parse raises → deny-all sentinel; ed25519 DENY, HMAC ADMIT; asserts
     no exception reaches the S-c wrapper. ✓
   - V11 (N4): lease stamped at enforce-resolved epoch → ADMIT; lease at authority-epoch <
     enforce-epoch → DENY epoch-stale (proves the safety-critical mismatch-denies leg). ✓

## No new defects
§2 verifier semantics are byte-unchanged from the rev1-confirmed core (scheme-pin, OBLIG-1
co-located re-layering, typed deny-closed, codex-1/codex-3 preserved). No regression introduced by
the rev2 wording. Minor, non-blocking: V11 exercises only the deny direction of N4 (the outage-
critical leg); the milder over-live fail-open direction is covered by the pinned source-parity
activation gate rather than a vector — acceptable, as N4 is an activation gate not a pure unit
assertion.

Design is safe to freeze and proceed to hash-bound freeze → single-use owner activation.
