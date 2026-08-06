# Binding Independent Review — C6-P0 rev3 + C2 Scheduler-Context Issuer

Reviewer: fresh Claude Opus flagship, independent of author (separate session, no shared reasoning
state; all factual claims re-derived from files). Rule 18 binding.
Date: 2026-08-06. Advisory lanes (local Qwen, Antigravity, codex) folded/queued separately.

## Verdicts

- **C6-P0 Trust Anchors rev3 → PASS** (authorizes freeze only, NOT build/activation), contingent on
  the parent-C6 schema-ownership amendment (applied 2026-08-06). The narrowing to declarative-only
  is honest — it withdraws the unspecified issuer/transport claims rather than hiding them.
- **C2 Scheduler-Context Issuer rev1 → REQUEST_REVISION** (2 HIGH + 1 LOW-MED). Superseded by rev2.

## The HIGH defect (confirmed by the reviewer AND re-verified by the orchestrator)

The switchboard hosting the C2 gate runs as `cfg.primaryUser` (`switchboard.nix:542`; gate imported
at `switchboard.py:1253`) — the **human owner uid**. Therefore `SO_PEERCRED` + group membership on
the issuer socket cannot distinguish the legitimate switchboard client from any other owner-uid
process (shell, `delegate-to-local`, compromised tool). Combined with rev1's issuer trusting a
caller-asserted ALLOW, an owner-uid process could present a fabricated `{ALLOW, principal, task}`
and receive a validly-signed context. Peer-uid was not authority.

## Closure in rev2 (`C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`, revision 2)

- **Findings 1+2 (HIGH):** authority moved from peer-uid to the **already-Ed25519-signed C2 lease**.
  The issuer verifies the presented lease signature (lease-issuer public key), re-checks
  freshness/epoch, and re-derives the tuple from the lease's own signed fields — never a
  caller-asserted ALLOW. A shell caller cannot forge a signed lease; `SO_PEERCRED` is
  defense-in-depth only. The switchboard-as-human-uid fact no longer matters.
- **Finding 3 (LOW-MED):** `config/aqos/c6-scheduler-signer-keys.json` (status-bearing) is the SOLE
  signer-verifier source; the status-less bare public-key file is dropped.
- **Doc-1 Finding 2 (MED, parent-C6):** amendment added to `C6-DESIGN-AND-AUTHORIZATION.md` marking
  the two schemas as C6-P0-provided verify-only anchors at C6-main freeze.

## What the review confirmed was already correct (do not re-litigate)

Signer authority (SOPS `/run/secrets` `0400`, dedicated principal, rotation/revocation, fail-closed
`signer-unavailable`); the SOPS re-encrypt hazard flagged HARD; key isolation from switchboard
(separate uid); issuer hosted as its own default-OFF service independent of the disabled epoch
authority; two-flag independence.

## Combined recommendation (reviewer)

The C6→C4 chain cannot freeze on the rev1 bytes. C6-P0 rev3 is freeze-ready once the parent-C6
amendment lands (done). The C2 issuer slice required the trust-model revision (done in rev2). rev2
now needs a fresh independent PASS before freeze.

## Advisory lanes (folded 2026-08-06)

- **Local Qwen (never-skip, advisory):** independently CORROBORATED the flagship's HIGH finding —
  flagged "SO_PEERCRED (UID/GID) to authenticate the switchboard is fragile" as a trust-boundary
  violation. Also raised replay-via-missing-nonce. Verification: replay/single-use is ALREADY
  covered — parent C6 §3.1 makes the context single-use (`slot_queue` durably records the context
  digest before a reservation and refuses replay/digest conflict) + `context_id` + bounded expiry.
  No new unaddressed defect; the concern is a re-review verification item (already queued for codex).
- **Antigravity:** dispatched via the sanctioned `--loop` lane; ran async into its agent loop
  (no inline verdict returned this cycle). Untrusted-advisory regardless; not gate-clearing.
- **Codex:** confirmatory queued (rev2 subject) — verify the lease-verification seam + single-use.

Consensus: the binding (flagship) verdict stands; local corroborates; rev2's signed-lease trust
model + parent-C6 single-use enforcement address both HIGH findings. rev2 needs a fresh binding PASS.

## Binding RE-REVIEW of rev2 (2026-08-06) — VERDICT: FAIL

Fresh flagship (independent of author + rev1 reviewer), re-verified by orchestrator against code.

**C2 issuer rev2 → FAIL.** The rev2 trust model ("issuer verifies an Ed25519-signed C2 lease against
a lease-issuer public key") depends on a primitive that DOES NOT EXIST:
- `capability_lease.py:178` `sign()` = HMAC-SHA256 (symmetric); `:284` `verify()` = `hmac.compare_digest`;
  no Ed25519/keypair/public-verifier anywhere in the C2 lease path (grep confirmed zero).
- HMAC is symmetric: whoever can verify can forge. The key is `/run/secrets/aq-lease-signing-key`,
  currently UNPROVISIONED so it falls back to in-repo `DEV_SIGNING_KEY` (`:40,201`,
  "DO-NOT-TRUST-IN-PRODUCTION"); leases are minted in-process by the switchboard as `cfg.primaryUser`.
  So the signing secret lives in the SAME owner-uid domain as the shell the fix excludes. rev2
  RELOCATED the defect (peer-uid -> symmetric-secret-in-same-uid), did not close it.
- `capability_lease_issuance.py` is C1 SHADOW/LOG-ONLY — there is no production asymmetric C2 lease issuer.

Additional findings: (2 HIGH) no issuer-side one-to-one lease->context binding — one valid lease can
mint many contexts (fresh context_id each; slot_queue single-use is on the CONTEXT digest, not the
lease); (3 MED) context expiry not bound to lease expiry + epoch re-check is inert while the authority
is disabled (must be stated as a limitation, not a live guarantee); (4 LOW) §2 still names the bare
public-key file that finding-3 dropped (internal inconsistency).

**C6-P0 rev3 → PASS re-affirmed** (freeze-only), independent of the C2 issuer; parent-C6
schema-ownership amendment correct.

**Chain:** cannot freeze on the C2 issuer rev2 bytes. Q-C6-1 remains OPEN and is DEEPER than designed:
the C2 issuer must EITHER (a) build a real asymmetric, confined lease-signing authority (Ed25519
private key confined to a principal the owner uid cannot read + public verifier) and verify the
presented lease with the public half, OR (b) redesign the admission authority off the
symmetric-HMAC-in-owner-uid dependency — then return for a fresh binding review. This is an
owner/architect decision (a foundational capability-lease crypto upgrade), not a self-revision.

## Local Qwen advisory on rev2 (folded 2026-08-06)
Corroborated Finding 2 (one-lease-many-contexts): "without explicit binding, one valid lease can
mint many contexts… enforce at the ISSUER side via a consumed-lease ledger; slot_queue is
defense-in-depth only." Two independent lanes converged. The fix is carried into the C2 issuer rev3
requirements (see ASYMMETRIC-LEASE-AUTHORITY-DESIGN §5). No new defect beyond the flagship FAIL.

## Owner decision (2026-08-06)
"Asymmetric lease authority first." New foundational prerequisite drafted:
`ASYMMETRIC-LEASE-AUTHORITY-DESIGN-20260806.md` (Ed25519 confined signer per the execution-grant
precedent) precedes the C2 issuer rev3. Revised chain:
ALA → C2 issuer rev3 → C6 main → C6 activation → C4 freeze. C6-P0 rev3 remains independently
freeze-ready (PASS).

## Binding review — Asymmetric Lease Authority rev1 (2026-08-06) — VERDICT: REQUEST_REVISION → rev2

Fresh flagship, independent. Direction CONFIRMED correct (closes offline-forgery + key-theft; the
execution_grant Ed25519 precedent + capability_lease HMAC current-state all verified accurate). Two
HIGH crux policies were left open and had to be MANDATED:
- **Scheme-downgrade (HIGH, confirmed exploit):** `sig_scheme` inside the lease + a dispatching
  verifier + live HMAC dev key ⇒ attacker sets `sig_scheme=hmac-sha256`, forges with the dev key,
  bypasses Ed25519. rev1's defense lived downstream (wrong layer). **rev2 mandate 1:** scheme-pinned
  authoritative verify (`verify_authoritative`, ed25519-only, required signed field, no HMAC
  fallback); HMAC `verify()` is a separate C1-shadow-only call.
- **Signing-oracle (HIGH):** "cannot forge past policy checks" was unsubstantiated — the authority
  signed whatever the owner-uid gate presented. **rev2 mandate 2 (option a):** the authority
  independently reconstructs the lease from the manifest+epoch and byte-compares before signing; the
  gate is pure transport. Makes the claim true.
- Plus: byte-parity absent-field semantics (mandate 3), confinement threat-model note — holds vs a
  compromised owner-uid process, NOT vs owner sudo/root (mandate 4), rotation precision — key_id
  required-signed, malformed keys file ⇒ deny-all, re-check at every verify (mandate 5).

rev2 (committed) makes all five MANDATES. Needs a fresh binding PASS. Local Qwen advisory on the two
crux risks folded when it lands. Codex confirmatory queued.

## Local Qwen advisory on ALA (folded 2026-08-06)
Corroborated the signing-oracle finding: "the authority acts as an oracle for the owner-uid
process… it cannot independently validate policy compliance at signing time… the authority should
NOT sign raw payloads." Matches the flagship Finding 2 + rev2 mandate 2 (independent reconstruction
+ byte-compare). Two lanes converged; no new defect. Codex confirmatory queued (393b623e).
