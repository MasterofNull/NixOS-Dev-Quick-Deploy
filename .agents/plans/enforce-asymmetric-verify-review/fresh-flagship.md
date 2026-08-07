# Independent Binding Review — ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807

- Reviewer: fresh flagship (Claude Opus 4.8), substituting for quota-blocked Codex per Rule 18.
- Role: INDEPENDENT BINDING reviewer. Not the author. Every claim verified against repo code.
- Date: 2026-08-07
- Design under review: `.agents/plans/aqos-foundation-c/ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807.md`
- Gates: the `CAPABILITY_ASYMMETRIC_LEASE=1` flag flip on a LIVE-enforcing switchboard.

## VERDICT: REQUEST_REVISION

The verifier **cryptographic core is correct and safe** — I found **no fail-open, no
downgrade, and no oracle**. Scheme-pinning, OBLIG-1 layering, allowlist-rooted trust, and
byte-identical legacy regression all hold against the actual code.

The revision is required not for a crypto defect but because the design leaves the
**fail-CLOSED / outage-prevention specification incomplete** — and preventing exactly that
outage is this slice's entire reason to exist. Three items (F1, F2, F3 below) are currently
"open questions" (Q-E1..Q-E4) that must be converted to **pinned normative requirements**
before freeze, plus the activation-validation scope must widen (F3). None of these are
fail-open; all are in the safe (over-deny) direction, but each can turn the flag flip into a
switchboard outage — the precise failure the design promises to prevent.

---

## Per-question findings (verified against code)

### Q1 — SCHEME-PIN / NO DOWNGRADE — CONFIRMED SAFE

The proposed `_admission_verify` branches solely on the lease's own `sig_scheme`
(design §2 lines 45/53). An Ed25519 lease (`sig_scheme=="ed25519"`) routes only to
`cl.verify_authoritative`; every other value (absent/None/`"hmac-sha256"`) routes only to
`cl.verify` HMAC. No lease can be verified by the wrong verifier:

- Cross-over attempt "HMAC lease + forged `sig_scheme=ed25519`": `verify_authoritative`
  recomputes `canonical_payload` including `sig_scheme` and the HMAC-hex signature fails
  Ed25519 verification → `AUTH_DENY_BAD_SIGNATURE` (`capability_lease.py:432-435`). No admit.
- Cross-over attempt "Ed25519 lease with `sig_scheme` stripped": routed to HMAC `cl.verify`;
  the Ed25519-hex signature fails `hmac.compare_digest` → `VERIFY_BAD_SIGNATURE`
  (`capability_lease.py:299-300`). No admit.

`verify_authoritative` denies non-ed25519 **before any key lookup or crypto**: the scheme
pin is the first check at `capability_lease.py:390-391`, ahead of the `keys_json` dict check
(`:393`), the key-id lookup (`:399-409`), and the Ed25519 math (`:433`). Confirmed exactly as
the design asserts.

### Q2 — OBLIG-1 LAYERING (fail-open risk HIGH) — CONFIRMED SAFE, one wiring constraint

`verify_authoritative` checks **signature + active-key ONLY** — it never calls `is_expired`
or `epoch_stale` (whole body `capability_lease.py:380-439`; returns `AUTH_VERIFY_OK` at `:437`
on a good signature over an active key). So the design MUST re-layer validity, and it does
(design §2 lines 50-51): `cl.is_expired` then `cl.epoch_stale(lease, current_epoch)` after an
`ok` signature.

- **Same helpers**: identical `cl.is_expired` / `cl.epoch_stale` the HMAC path uses inside
  `cl.verify` (`capability_lease.py:302-306`). ✓
- **Same epoch source**: `current_epoch` is `resolve_current_epoch(epoch_source)` computed
  once at `capability_lease_gate.py:616` and passed into both branches; enforce guarantees it
  is a non-None int (degrade at `:617-618`), so the design's unconditional
  `epoch_stale(lease, current_epoch)` is equivalent to HMAC's
  `current_epoch is not None and epoch_stale(...)`. ✓

An expired or stale-epoch Ed25519 lease therefore **cannot admit**. This closes the
identified HIGH fail-open. **Wiring constraint (must be explicit in the frozen spec):** the
helper must be dropped in **inside the existing `try/except`** of each branch
(`:644-647` candidate, `:689-692` first-party). Rationale: `is_expired` calls
`_parse_iso(data["expires_at"])` (`capability_lease.py:236-238`), which `verify_authoritative`
does not pre-validate; a signed-but-malformed `expires_at` would raise. Inside the existing
try/except that raise maps to `VERIFY_MALFORMED` → DENY (fail-closed). Outside it, the raise
escapes to the S-c wrapper (`:736`) and total-denies **all** tools including HMAC ones — a
broader outage. The design implies "replace the bare `cl.verify` call" (which is inside the
try/except) but should state this normatively.

### Q3 — Q-E1 candidate branch — SAFE to scheme-dispatch; no admit path opened

Applying `verify_authoritative` to a caller-presented Ed25519 candidate lease is safe because
the allowlist (`config/aqos/lease-signer-keys.json`) is the **sole, unforgeable** root of
trust — only the confined authority holds the private seed for `lease-signer-2026-08`. A
malicious caller cannot mint a lease that passes `verify_authoritative`; an unknown/inactive
key denies at `capability_lease.py:408-414`. The worst a caller can do is **replay a genuine
authority-signed lease** as a candidate — which grants only the actions that lease was
already signed for, still gated by the same `is_expired`/`epoch_stale` layering and the same
`zero-trust-strip` + `_is_privileged` checks (`:662-671`); no capability the caller couldn't
already obtain through the first-party path. So dispatching the candidate branch through the
**shared** helper opens no admit path. Keeping candidate HMAC-only is equally safe today (no
Ed25519 candidate leases are minted yet). **Recommendation: use the single shared helper for
both branches** — its value is that OBLIG-1 layering (Q2) is then guaranteed uniform; a
candidate-only HMAC path that later grows an ad-hoc ed25519 branch would risk forgetting the
expiry/epoch re-check. Note the candidate branch does not run the codex-3 manifest tripwire
(first-party only), but that is correct: a signed candidate lease's risk block is itself
authenticated, so reading risk from the signed payload is sound.

### Q4 — Q-E3 keys_json must be a PARSED DICT — CONFIRMED requirement, load-site under-specified

`verify_authoritative` denies-all unless `keys_json` is a dict with a non-empty `keys` list:
`isinstance(keys_json, dict)` (`:393`) then `isinstance(keys, list) and keys` (`:395-397`).
A **raw string** (the live-probe bug the design cites) → not a dict → `AUTH_DENY_MALFORMED_KEYS`
→ deny-all. Confirmed. A missing/malformed allowlist fail-closes Ed25519 **without touching
the HMAC path**, because the HMAC path (`cl.verify`) never reads `keys_json`. Confirmed.

**But the design does not specify the load site**, and this is the single largest
implementation risk. Required constraints to pin (currently only an open question):

1. Parse with `json.loads(...)` into a dict; pass the dict — never the raw file text.
2. The load MUST be **locally try/excepted** with a deny-all sentinel (`{}` or `None`; both
   are non-valid-keys → `AUTH_DENY_MALFORMED_KEYS`). A keys-file read/parse error must NOT
   propagate — if it reaches the S-c wrapper (`:736`) it total-denies every tool including
   HMAC leases = a full switchboard outage, not the intended "Ed25519-only" fail-closed.
3. Load posture (once-per-enforce vs cached) should be fixed; caching is fine but a cache of
   a failed load must remain the deny-all sentinel, not raise on reuse.

### Q5 — REGRESSION (flag-OFF / legacy path byte-identical) — CONFIRMED

For any lease without `sig_scheme` (all current leases, and all leases while the mint flag is
0), the helper's fallthrough is exactly `cl.verify(lease, hmac_key, current_epoch=current_epoch)`
— identical call and args to today's `:645` and `:690`. The only added work is one
`dict.get("sig_scheme")` comparison returning None. Verdict is byte-identical; no behavior
change for existing leases. The scheme-dispatch is inert until an Ed25519 lease appears (i.e.
until the mint flag flips). Confirmed. Caveat folded into F2: if `keys_json` is loaded
eagerly even on the pure-HMAC path, that load must be fail-closed-local so a keys-file problem
in an HMAC-only deployment cannot regress the HMAC path.

---

## Other defects (Q6) — ranked

No fail-open, downgrade, or oracle found. The remaining items are fail-CLOSED / outage-
prevention gaps that undermine the design's "flip safely" guarantee.

### F1 (MEDIUM — outage) keys_json load-site cascade — see Q4
Convert Q-E3 into a normative requirement: parsed-dict, locally fail-closed with a deny-all
sentinel, no exception escape into the S-c wrapper. As written this is an open question, which
is not sufficient to authorize a live flip.

### F2 (MEDIUM — outage) helper must live inside the existing try/except in BOTH branches
See Q2. Without this, a signed-but-unparseable temporal field raises past the branch and the
S-c wrapper total-denies all tools. Make the placement normative.

### F3 (MEDIUM — outage; the most important activation gap) mint canary did NOT exercise the full enforce() path
The 25/25 canary proved the minter's leases pass `verify_authoritative` only. But
`enforce()`'s first-party branch applies **additional gates that `verify_authoritative` does
not**, any of which will DENY an authentic Ed25519 lease and cause the outage the flip is
meant to avoid:

- lease-vs-lookup-key match: `tool in bound_actions` (`:681-688`).
- codex-3 tamper tripwire: `_lease_bound_security_projection(lease) ==
  _manifest_bound_security_projection(manifest_entry)` (`:704-713`). This requires the
  confined authority's minted projection (actions/resources/constraints/risk block/
  trust_tier/zero_trust_behavior) to **exactly equal** the switchboard's live manifest
  projection. If the authority and the switchboard load even slightly divergent manifests, or
  the authority stamps the risk block differently, every first-party tool denies.
- layered expiry/epoch (Q2), which the canary bypassed entirely.

**Required revision:** §5 must mandate a pre-flip dry-run of the **entire `enforce()` path**
against a real authority-minted lease (all four gates above green), not just
`verify_authoritative`, before `CAPABILITY_ASYMMETRIC_LEASE=1`.

### F4 (MEDIUM — outage) epoch-source parity between authority and enforce (Q-E2)
`epoch_stale` is `revocation_epoch < current_epoch` (`capability_lease.py:243-245`). The
confined authority stamps `revocation_epoch` by resolving the epoch itself; enforce resolves
it via `resolve_current_epoch` (env `AQ_LEASE_POLICY_EPOCH` → `config/capability-lease-epoch`
→ 0, `:210-238`). If the two read different sources, a freshly minted lease is either
self-stale (authority-epoch < enforce-epoch → DENY, outage) or over-live on a future
revocation (authority-epoch > enforce-epoch → survives a legitimate bump — a mild fail-open on
revocation, though bounded and requiring authority/enforce disagreement). Pin as an activation
gate: both MUST read the identical epoch source. The canary did not test this (verify_
authoritative ignores epoch).

### F5 (LOW/MEDIUM — outage surprise) is_dev degrade still requires the production HMAC secret under asymmetric mode
`enforce()` resolves the HMAC key and, if `is_dev` (no production HMAC secret), degrades to
`SAFE_READ_ALLOWLIST` for **all** tools **before** any lease logic (`:609-614`) — even when
first-party leases are Ed25519 and don't use the HMAC key. Consequence: an operator who
assumes "asymmetric replaces HMAC" and de-provisions the HMAC SOPS secret at flip time gets a
read-only degrade outage. Safe direction, but flag it: keep the HMAC secret provisioned
post-flip, or (future slice) re-scope the `is_dev` gate when asymmetric is active. Note only —
not blocking.

### Informational — `_is_malformed` is not applied on the ed25519 path
The HMAC path denies MALFORMED before checking the signature; the ed25519 path relies on the
signature as root of trust plus downstream `.get`-with-defaults and the codex-3 projection.
This is safe because only the confined authority can produce a validly-signed ed25519 lease
and it mints to schema; a malformed-but-signed lease can only originate from the trusted
authority, and a missing `expires_at` still fail-closes via the Q2 try/except. No action
required; documenting the asymmetry.

---

## What is already correct (no change needed)
- Scheme-pin ordering in `verify_authoritative` (`:390-391` before any key/crypto). ✓
- Allowlist is public-only, single active key `lease-signer-2026-08`, status re-checked every
  call (`:411-414`); no cached-active past a status flip. ✓
- `verify_authoritative` has **zero callers** in the switchboard today (grep confirmed) — the
  design's core premise that the enforce side is untouched is accurate; adding the helper is
  the missing piece. ✓
- Cache cross-scheme window (Q-E4): the flag lives in `switchboard.nix`, so flipping it
  rebuilds+restarts the service, which re-initializes the module-global
  `_FIRST_PARTY_LEASE_CACHE=None` (`:326`). No hot-flip path leaves a stale cross-scheme
  cache. Confirmed — verify is per-lease scheme-agnostic; the flag stays mint-side only, as
  the design recommends. ✓

## Path to PASS
Fold F1, F2, F3, F4 into the frozen spec as **normative requirements** (not open questions);
F5 as a documented activation note. The verifier semantics themselves need no change. On a
rev2 that pins the load-site fail-closed contract, the try/except placement, the full-path
pre-flip validation, and epoch-source parity, this design is safe to freeze and flip.
