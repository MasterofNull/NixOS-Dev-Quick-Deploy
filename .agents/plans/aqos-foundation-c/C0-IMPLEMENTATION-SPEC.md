# Foundation C — C0 Implementation Spec + Authorization (report-only entry)

**Parent design:** `.agents/plans/aqos-foundation-c/DESIGN-PACKET.md` (rev2, independently
reviewed) §8 C0. **Author:** fable-5. **Idempotency key:**
`aqos-foundation-c:c0:lease-schema-signer-cli-fixtures:v1:20260724`.

**Class:** REPORT-ONLY, zero enforcement, offline-first, **no Nix/service/dispatch/
switchboard/network change**. Nothing in this slice is wired into any live path — it ships
the lease *primitive* (schema + sign/verify + CLI + fixtures) that later enforcement slices
(C1+) consume. Lowest-risk entry (same class as the B1 shadow oracle).

**Activation basis:** report-only lowest-risk slice on the owner's explicit standing
authorization ("i authorize all next steps, slices, and changes" + 2026-07-24 "drive the
next steps and slices"), drift-verified at acceptance. No enforcement ⇒ no runtime risk
surface. (Enforcement slices C2+ remain individually hash-bound + single-use activated.)

## File ceiling (exactly 5 — NEW only; no edits to existing files)
1. `config/schemas/capability-lease.schema.json` — JSON Schema (draft 2020-12) for the
   **Principal** and **CapabilityLease** objects (F3 consensus fields, DESIGN §2).
2. `scripts/ai/lib/capability_lease.py` — the library: dataclasses, canonical-JSON
   serializer, `sign()`/`verify()`, `attenuate()`, `is_expired()`, `epoch_stale()`.
3. `scripts/ai/aq-lease` — CLI (executable): `new`, `verify`, `inspect`, `attenuate`.
4. `scripts/testing/test-capability-lease.py` — the acceptance tests.
5. `scripts/testing/fixtures/capability-lease-golden.json` — golden leases.

## Schema (file 1) — fields from F3 consensus (DESIGN §2)
- **Principal:** `principal_id, kind(enum: agent|service|human|remote-lane), attestation
  (str: OAuth-session-ref | systemd-unit-cred | signed-a2a-envelope), trust_tier(int),
  session_epoch(int)`.
- **CapabilityLease:** `lease_id, version(int), source, owner, issued_to(principal_id),
  issued_at(ISO), expires_at(ISO), permissions{actions[], resources[], constraints{}},
  input_schema, output_schema, trust_tier(int), zero_trust_behavior(enum: none|strip),
  cost_class, parent_lease_id(nullable), revocation_epoch(int), signature(str)`.
  Required + additionalProperties:false. `signature` excluded from the signable digest.

## Library (file 2) — signing = LOCAL, NO extracted keys
- **Canonicalization:** deterministic JSON (sorted keys, no whitespace, UTF-8) over every
  field EXCEPT `signature`. This is the signable payload.
- **Signature:** `HMAC-SHA256(canonical_payload, key)` hex. The key is a **machine-local
  secret** read from a configurable path (`AQ_LEASE_SIGNING_KEY` env → default a documented
  `/run/secrets/…` path). This is NOT an API/provider key (Rule: no extracted OAuth/provider
  keys) — it is a local HMAC secret. **This slice does NOT provision a SOPS secret** (that's
  a later infra slice); for offline/tests the key resolves to a documented deterministic
  DEV key when the secret path is absent, and the CLI prints a clear "DEV-KEY (unsigned-for-
  production)" banner so a dev signature can never be mistaken for a trust-rooted one.
- **`verify(lease, key)`** → recompute + constant-time compare; returns typed result
  (`ok | bad-signature | expired | epoch-stale | malformed`). `epoch_stale(lease, current_epoch)`
  → `lease.revocation_epoch < current_epoch`. Report-only: verify never *acts*, only reports.
- **`attenuate(parent, delta)`** → child lease with `parent_lease_id=parent.lease_id`,
  permissions ⊆ parent (actions/resources intersected, constraints only tightened),
  `trust_tier ≤ parent`, `expires_at ≤ parent`. Raises if delta tries to widen (monotonic).

## CLI (file 3) — report-only
- `aq-lease new --spec <file|-> [--key <path>] [--json]` — build + sign a lease from a spec.
- `aq-lease verify <lease-file> [--key <path>] [--current-epoch N] [--json]` — typed verdict.
- `aq-lease inspect <lease-file> [--json]` — pretty-print + attenuation chain + expiry/epoch.
- `aq-lease attenuate <parent> --delta <file> [--key] [--json]` — emit a signed child lease.
- All read-only w.r.t. the system; no service calls, no writes outside an explicit `--out`.

## Acceptance tests (file 4) — the F3 proof obligations applicable at C0 (schema/crypto layer)
- Schema validates the golden leases; rejects an extra/missing field.
- **Sign/verify roundtrip** + **tamper-detection** (mutate any signable field → `bad-signature`).
- **Canonical determinism** (field-order-independent signature; re-serialize → identical digest).
- **Expiry** (past `expires_at` → `expired`).
- **Epoch-stale** (lease.revocation_epoch < current → `epoch-stale`) — the schema/lib check;
  the *executor* enforcement is C2, explicitly out of scope here.
- **Attenuation monotonicity** — child ⊆ parent accepted; any widen (extra action/resource,
  higher trust_tier, later expiry) → raises. (F3 property (2) downgrade-inherited-stricter.)
- **DEV-key banner** present when the production secret path is absent (no silent dev-signing).
- Offline: tests use the deterministic DEV key; no network, no `/run/secrets` dependency.

## Out of scope (deferred, written)
No enforcement, no switchboard/dispatch/capability-intake wiring, no network profiles, no
cells/bwrap, no OTel spans, no SOPS secret provisioning, no epoch *bump control surface*
(C6). Those are later hash-bound slices. C0 is the inert primitive + its proof tests.

## Reviewer / next
Implementer = cheapest-eligible (multi-file build > local single-edit envelope ⇒ Claude
fast tier, capability-override recorded per Rule 17). Independent review of the RESULT
(not the author) before commit; never-skip-local self-check. codex confirmatory audit
queued (cooldown).
