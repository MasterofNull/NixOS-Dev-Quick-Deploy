# C6-P0 Trust Anchors rev3 — FREEZE record

status: FROZEN 2026-08-06 — design bytes locked; build NOT yet authorized (single-use owner activation required)
tier: declarative trust anchors (enables no runtime capability)

## Frozen subject
- Design: `.agents/plans/aqos-foundation-c/C6-P0-TRUST-ANCHORS-REV3-20260806.md`
  sha256 `54d6443907c39a430add95e1b881c1114ac8ff6fc7a7d6409da7f0495bc27759`
- Base HEAD at freeze: `1a1058eddc0334d4e9cde45b8bc44d8bb8b5a521`

## Review + predecessor gate (all satisfied)
- **Binding independent review — PASS** (fresh Claude flagship, Rule 18): `C6-P0-AND-C2-ISSUER-BINDING-REVIEW-20260806.md`. Narrowing to declarative-only is honest; PASS authorizes freeze only, not build/activation.
- **Contingency satisfied:** the parent-C6 schema-ownership amendment is applied (`C6-DESIGN-AND-AUTHORIZATION.md` top-of-file amendment, commit `d8702e4c`) — the two schemas are C6-P0-provided verify-only anchors at C6-main freeze.
- **Codex confirmatory:** queued (advisory, non-blocking, Rule 18).

## Ceiling (locked — the build may do EXACTLY this; all 4 NEW, verified ABSENT at freeze)
1. NEW `config/aqos/c6-owner-public-keys.json` — owner epoch-bump public-key allowlist (public data ONLY: schema_version, monotonic revision, per-key `{key_id, ed25519_public_key, status∈{active,revoked}, not_before?, not_after?}`).
2. NEW `config/schemas/revocation-epoch-bump.schema.json` — closed `aq.revocation-epoch-bump/1` schema.
3. NEW `config/schemas/scheduler-lease-context.schema.json` — closed `aq.scheduler-lease-context/1` schema.
4. NEW `scripts/testing/test-c6-p0-trust-anchors.py` — offline validation: schemas well-formed; allowlist public-only (rejects any private-material field), revisioned, duplicate-key-free, status-enum-bounded; negative vectors (private material present, non-monotonic revision, symlink/writable key file, unknown status). Pure file/parse assertions — no signature, socket, or service.

**Excluded (freeze fail-stop if touched):** any service, socket, signer, private key, dispatch/gate edit, Nix module, `phase0.py`, dashboard, deployment, activation, and every unlisted path. C6-P0 ships NO enabled service → NO Service Coverage claim.

## Build gate (required, ordered)
1. **Single-use owner activation** hash-bound to subject `54d64439…` (the owner's act — freeze authorizes nothing). Correct command (interface: `aq-event emit --agent --type --subject --payload`; hash/key live in the payload JSON):
   ```
   scripts/ai/aq-event emit --agent owner --type activation.grant \
     --subject aqos-foundation-c-c6-p0-trust-anchors-rev3 \
     --payload '{"idempotency_key":"aqos-foundation-c:c6-p0:trust-anchors:rev3:v1:20260806","subject_design_sha256":"54d6443907c39a430add95e1b881c1114ac8ff6fc7a7d6409da7f0495bc27759","build_head":"REPLACE_WITH_git_rev-parse_HEAD_at_emit","predecessors":{"binding_review":"C6-P0-AND-C2-ISSUER-BINDING-REVIEW-20260806.md:PASS","parent_c6_amendment":"d8702e4c"},"implementer":"claude-fast","window_hours":24,"note":"C6-P0 rev3 declarative trust anchors; flagship binding PASS (freeze-only); parent-C6 schema-ownership amendment applied; 4 NEW files verified absent at freeze; codex confirmatory queued"}'
   ```
   Drift preflight (already CLEAN at freeze): `sha256sum` the design == `54d64439…`; all 4 NEW paths absent; HEAD == `1a1058ed` (or a later HEAD with these facts unchanged).
2. build within the ceiling (cheapest-eligible implementer, Rule 17 — declarative + one offline test) → tier0 `--pre-commit` green → independent code review → small-batched commit.
3. C6-P0 ships declarative anchors only; it does NOT freeze/activate the epoch authority, the C2 issuer, C6, or C4 — each remains separately gated. C6-P0 landing is a freeze prerequisite for the C6-main re-freeze (schemas become verify-only there).

The freeze locks the bytes; it authorizes no build, activation, or commit of implementation.
