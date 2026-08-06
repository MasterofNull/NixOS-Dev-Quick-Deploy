# Asymmetric Lease Authority rev4 — FREEZE record

status: FROZEN 2026-08-06 — design bytes locked; build NOT yet authorized (single-use owner activation required)
tier: foundational (asymmetric crypto in a core lease primitive + a confined signing service; DEFAULT-OFF)

## Frozen subject
- Design: `.agents/plans/aqos-foundation-c/ASYMMETRIC-LEASE-AUTHORITY-DESIGN-20260806.md` (revision 4)
  sha256 `24c748b958b803b02eba2ecc079738a1f36d4403c1fc3b16a7ec3b609d1a5f42`
- Base HEAD at freeze: `5f6d04b9e2352839546528f083c8716dbe485392`

## Review (four rounds → PASS)
- rev1 REQUEST_REVISION (2 HIGH: scheme-downgrade, signing-oracle) → rev2
- rev2 REQUEST_REVISION (1 HIGH: byte-equality vs wall-clock fields; scheme-pinning + byte-parity + confinement + rotation CONFIRMED) → rev3
- rev3 REQUEST_REVISION (narrow; **ORACLE CONFIRMED CLOSED BY CONSTRUCTION** — selectors-only; codex-1 guard + 3 LOW text asks) → rev4
- **rev4 → PASS** (fresh Claude flagship, Rule 18): all four rev4 clauses faithful to code, no findings; oracle-closure + all five mandates complete. Authorizes **freeze only**, not build/activation. Trail: `C6-P0-AND-C2-ISSUER-BINDING-REVIEW-20260806.md`.
- Codex confirmatory queued (advisory, non-blocking).

## Ceiling (locked — the build may do EXACTLY this)
MODIFY (current SHA-256 anchors; drift ⇒ re-freeze):
- `scripts/ai/lib/capability_lease.py` `a6f923924071618b…` — add `sign_ed25519` + `verify_authoritative` (ed25519-only, required signed `sig_scheme`, no HMAC fallback); legacy HMAC `verify()` unchanged, C1-shadow-only. `sig_scheme` in signed payload for ed25519 leases ONLY (byte-parity for legacy).
- `ai-stack/switchboard/capability_lease_gate.py` `3e92d2fe97a1ea8b…` — under `CAPABILITY_ASYMMETRIC_LEASE=1`, send SELECTORS ONLY `{tool, caller-principal, task}` to the authority; RETAIN the codex-1 mint-once `_FIRST_PARTY_LEASE_CACHE` + reset-only reissue (swap ONLY the sign step; never re-request on epoch bump). Flag OFF = byte-parity HMAC.
- `nix/modules/services/default.nix` `a36d0b21013ff335…` — import the new authority module.
- `config/env-contract.yaml` `7bf49e7d3b64fb8e…` — `CAPABILITY_ASYMMETRIC_LEASE` default `0`; fixed authority socket/key refs.
- EDIT (hashes at freeze-time preflight): `scripts/testing/harness_qa/phases/phase0.py`, `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`.

NEW (verified ABSENT at freeze):
- `scripts/ai/lib/lease_signing_authority.py` — sole minter (selectors → manifest+epoch+own-clock mint → Ed25519 sign its own reconstruction).
- `nix/modules/services/lease-signing-authority.nix` — dedicated default-OFF `aq-lease-signing-authority` service (own principal, SOPS Ed25519 private key `0400`, UDS + SO_PEERCRED, hardened, no network, `enable=false`). switchboard.nix untouched.
- `config/aqos/lease-signer-keys.json` — SOLE signer-verifier allowlist (key-id → public + `status` + revision; `key_id` required-signed; malformed ⇒ deny-all).
- `scripts/testing/test-asymmetric-lease-authority.py` + `scripts/testing/test-lease-signing-authority-service-coverage.py`.
- SOPS: `lease-signing-ed25519-private-key` (add to `secrets.nix` + `sops` re-encrypt — HARD).

**Excluded (freeze fail-stop):** `switchboard.nix`, C1-shadow authoritativeness, provider calls, C2/C6/C4 code, deployment, activation, and every unlisted path.

## Build gate (required, ordered)
1. **Single-use owner activation** hash-bound to subject `24c748b9…` (owner act; freeze authorizes nothing):
   ```
   scripts/ai/aq-event emit --agent owner --type activation.grant \
     --subject aqos-foundation-c-asymmetric-lease-authority-rev4 \
     --payload '{"idempotency_key":"aqos-foundation-c:asymmetric-lease-authority:rev4:v1:20260806","subject_design_sha256":"24c748b958b803b02eba2ecc079738a1f36d4403c1fc3b16a7ec3b609d1a5f42","build_head":"REPLACE_WITH_git_rev-parse_HEAD_at_emit","predecessors":{"binding_review":"rev4-PASS","capability_lease":"a6f923924071618b","capability_lease_gate":"3e92d2fe97a1ea8b"},"implementer":"claude-fast","window_hours":24,"note":"asymmetric lease authority rev4; 4-round flagship review -> PASS; oracle closed by construction; crypto core (capability_lease.py asymmetric path + codex-1 guard) warrants a capable implementer + mandatory independent code review; switchboard.nix anchor no-edit"}'
   ```
   Drift preflight (CLEAN at freeze): design sha256 == `24c748b9…`; 3 NEW absent; MODIFY anchors match.
2. build within the ceiling (Rule 17 — crypto core is sensitive: route to the cheapest tier whose MEASURED capability satisfies asymmetric-crypto + byte-parity + the codex-1 invariant; NOT a trivial-declarative envelope) → tier0 `--pre-commit` green → **mandatory independent code review** (asserts: zero authoritative refs to HMAC `verify()`; codex-1 cache-guard intact; byte-parity for legacy leases) → small-batched commit.
3. Default-OFF; turning `CAPABILITY_ASYMMETRIC_LEASE=1` is a further separate owner act. Does NOT enable the C2 issuer, C6, or C4.

The freeze locks the bytes; it authorizes no build, activation, or commit of implementation.
