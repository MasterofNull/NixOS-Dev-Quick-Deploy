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

Freeze-gate obligation carried forward: **mandatory independent code review** of the crypto diff
(assert: zero trust-rooted refs to HMAC `verify()`; byte-parity) — dispatched; advisory-until-defect
per Rule 18 (safe: unwired + default-OFF).

## Remaining slices (not yet built)
- **Slice 2 — confined service:** `lease_signing_authority.py` (selectors-only mint) +
  `lease-signing-authority.nix` (default-OFF `aq-lease-signing-authority`, SOPS Ed25519 key, UDS,
  hardening) + `capability_lease_gate.py` (selectors-only request, RETAIN the codex-1 mint-once
  cache + reset-only reissue) + `default.nix` import + `env-contract.yaml` flag. **SOPS private-key
  encryption needs the owner's sops key** — will be flagged at that slice.
- **Slice 3 — Service Coverage:** `phase0.py` AQ-QA + dashboard card + health-spider.
