# Asymmetric Lease Authority rev4 — build log

Owner-activated 2026-08-06 (grant event `8c56e5f9…`, drift preflight CLEAN: subject `24c748b9`,
3 NEW absent, 4 MODIFY anchors matched). Built incrementally (crypto core → service → Service
Coverage), each slice orchestrator-verified before commit. Freeze ceiling:
`ASYMMETRIC-LEASE-AUTHORITY-FREEZE-20260806.md`.

## Slice 1 — crypto primitive (DONE, this commit)

Runtime change: `scripts/ai/lib/capability_lease.py` (asymmetric path added; HMAC path untouched).
Cheapest-eligible-capable implementer (sonnet, Rule 17 — crypto core exceeds the trivial envelope).

- `sign_ed25519(lease, private_key_bytes)` — Ed25519-signs the existing `canonical_payload()`
  (mirrors `execution_grant.py`).
- `verify_authoritative(lease, keys_json) -> AuthoritativeVerdict` — the scheme-PINNED authoritative
  verify (mandate 1): `sig_scheme != "ed25519"` denies FIRST (before any key lookup / Ed25519 math),
  no HMAC fallback, no dev-key path reachable; malformed `keys_json` denies-ALL; key-id looked up in
  `config/aqos/lease-signer-keys.json`, unknown/non-`active` denies (re-checked every call).
- NEW `config/aqos/lease-signer-keys.json` — sole signer-verifier allowlist (public-only).
- NEW `scripts/testing/test-asymmetric-lease-authority.py` — 24 offline assertions.

**Orchestrator verification (every byte, not the implementer's report):** scope = exactly these 3
files; `capability_lease.py` diff additive-only (the lone "-" is a benign `typing` import
extension); the legacy HMAC `sign()`/`verify()`/`canonical_payload()`/`resolve_key()`/attenuation are
byte-identical (regression `test-capability-lease.py` 54/54); `verify_authoritative` scheme-pin
confirmed FIRST by reading `:390`; the new suite proves scheme-downgrade denial + golden byte-parity
(24/24). Default-OFF and UNWIRED (no gate/service consumes it yet). tier0-green.

**Mandatory independent code review → PASS** (fresh flagship, 2026-08-06). Verified against the code:
scheme-pin fires before any key lookup/Ed25519 math with NO reachable HMAC/`resolve_key`/`DEV_SIGNING_KEY`
path; legacy HMAC bodies byte-identical (sole `-` = the `typing` import extension); Ed25519 correct +
fail-closed (all forged/malformed paths deny, never raise); allowlist deny-closed (unknown/revoked/
malformed → deny-ALL); the scheme-downgrade test uses a genuinely-valid HMAC sig and confirms denial
at the scheme gate. Slice 1 crypto is fully validated.

**Two integration obligations carried forward (reviewer LOW/INFO — none block slice 1):**
- OBLIG-1: `verify_authoritative` is signature+key-status ONLY — it does NOT check `expires_at` or
  `revocation_epoch`. Trust-rooted consumers (C2 issuer rev3 / C2 enforcement) MUST layer expiry +
  epoch validity on top; `ok=True` means "authentically signed by an active key," not "currently valid."
- OBLIG-2 (activation sequencing): the placeholder allowlist entry is `active` with no provisioned
  private key — safe while default-OFF, but SOPS private-key provisioning MUST land before the
  `CAPABILITY_ASYMMETRIC_LEASE=1` flip, else no lease can mint (fail-closed hard outage).

## Slice 2 — confined service + gate wiring (ATTEMPTED, BLOCKED on usage limit 2026-08-06)
The sonnet implementer dispatch terminated early on an account session/usage limit (resets ~1:30pm
PT); it wrote NO files (working tree clean, HEAD 65d6f507). Slice 2 is UNSTARTED and re-runs when the
limit clears. Scope (unchanged): `lease_signing_authority.py` (selectors-only mint) +
`lease-signing-authority.nix` (default-OFF `aq-lease-signing-authority`, SOPS Ed25519 key, UDS,
hardening) + `capability_lease_gate.py` (selectors-only request, **RETAIN codex-1 mint-once cache +
reset-only reissue, swap only the sign step, flag-OFF byte-parity**) + `default.nix` import +
`env-contract.yaml` flag + offline test. switchboard.nix untouched. SOPS private-key encryption = owner
activation step. Slice 2's minter must satisfy OBLIG-1 (its downstream issuer layers expiry/epoch).

## Slice 3 — Service Coverage (not started)
`phase0.py` AQ-QA + dashboard card + health-spider.
