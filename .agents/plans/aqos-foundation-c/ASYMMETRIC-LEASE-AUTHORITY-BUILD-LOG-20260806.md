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

## Slice 2 — confined service + gate wiring (DONE)

First dispatch died on the usage limit (wrote nothing); a re-dispatch stalled without delivering, so
the orchestrator built it directly (stated Rule-17 deviation: delegation blocked/non-delivering across
two dispatches + owner asked for completion). Every piece orchestrator-verified.

- NEW `scripts/ai/lib/lease_signing_authority.py` — the SOLE minter. `mint_first_party_leases(manifest,
  epoch, private_key_bytes, key_id)` mints the full first-party set from the MANIFEST (never a caller
  payload), authority-clock temporals, `sig_scheme="ed25519"` + `issuer_key_id`, Ed25519-signed. Reads
  the manifest + epoch DIRECTLY (self-contained — no `capability_lease_gate` import, so the confined
  bundle is just this + `capability_lease.py`, both self-contained). `handle_request` (server) + a
  fail-closed `serve()`.
- EDIT `ai-stack/switchboard/capability_lease_gate.py` — flag-gated branch: `CAPABILITY_ASYMMETRIC_LEASE=1`
  → `_request_asymmetric_first_party_leases()` (UDS client, **fail-CLOSED to {} deny-all, never HMAC**);
  flag=0 → the in-process path UNCHANGED. **codex-1 guard intact** (the mint-once `_FIRST_PARTY_LEASE_CACHE`
  early-return + reset-only reissue are untouched; the new branch just populates the cache once and never
  re-requests on an epoch bump).
- NEW `nix/modules/services/lease-signing-authority.nix` — default-OFF `aq-lease-signing-authority`
  (dedicated user, SOPS key `0400`, UDS 0660 group-restricted, `NoNewPrivileges`, empty
  `CapabilityBoundingSet`, `ProtectSystem=strict`, `RestrictAddressFamilies=AF_UNIX`, no network, 2-file
  bundle). `enable=false`. **switchboard.nix untouched.**
- EDIT `nix/modules/services/default.nix` (import) + `config/env-contract.yaml` (`CAPABILITY_ASYMMETRIC_LEASE` default 0).
- NEW `scripts/testing/test-lease-signing-authority.py`.

**Verification:** flag-OFF byte-parity — regression `test-capability-lease.py` 54/54 UNCHANGED; the new
test proves **field-parity** (authority-minted fields byte-match the gate's `issue_first_party_leases`),
mint+`verify_authoritative` accept, mint-from-manifest (no caller-payload param), server round-trip, and
both fail-closed paths; slice-1 crypto test still green; nix parses; env-contract YAML valid; bundle
closure complete (only `capability_lease`). switchboard.nix untouched.

**Owner activation steps deferred (default-OFF ships without them):** (1) generate the Ed25519 keypair,
put the public key in `config/aqos/lease-signer-keys.json` (currently placeholder), SOPS-encrypt the
private key to `/run/secrets/lease-signing-ed25519-private-key`; (2) enable the service; (3) flip
`CAPABILITY_ASYMMETRIC_LEASE=1`. A WR-3-style deploy preflight + the live GREEN round-trip validate at
activation. OBLIG-1 (expiry/epoch layering) is the downstream C2-issuer's job, not the minter's.

## Slice 3 — Service Coverage (DONE) → ALA BUILD COMPLETE

- **AQ-QA coverage:** NEW `scripts/testing/test-ala-service-coverage.py` (offline cross-surface
  contract: flag defaults 0 in env-contract; the nix service defaults enable=false + is confined
  (dedicated user, AF_UNIX only); the signer allowlist is public-only + has an active key; the
  dashboard API + JS render ALA state; the crypto/authority tests exist). Registered in focused-ci
  (`config/validation-check-registry.json` id `ala-service-coverage`), triggering on any ALA file.
- **Dashboard visibility:** `dashboard/backend/api/routes/aistack.py` `/stats/capability-enforcement`
  now returns an `ala` section (asymmetric_lease on/off, signer-allowlist active-key count + revision,
  status — default-OFF is the healthy resting state; ON without an active key is degraded);
  `assets/dashboard.js` renders the ALA rows + folds `ala.status` into the card badge.
- **health-spider:** deferred to activation — a default-OFF service exposes no live signer to probe;
  the signer-unavailable/authority-failure health check lands with the service-enable act (the
  dashboard already surfaces the governance state). Noted, not silently skipped.

**Verification:** coverage test PASS; registry JSON valid; aistack.py parses; dashboard.js edited
(card badge + rows). All ALA tests still green (crypto 24/24, authority, regression 54/54). tier0 25/0.

## ACTIVATION — Phase 0 + Phase 1 (2026-08-06)

**Phase 0 — key provisioned (owner + orchestrator):** owner generated an Ed25519 keypair; the PRIVATE
key was sops-encrypted into the host secrets file (`…/secrets/hyperd/secrets.sops.yaml`) as
`lease-signing-ed25519-private-key` (verified decryptable) and the plaintext shredded — the private key
never entered the transcript (encrypted via `$(cat)` substitution; only the derived PUBLIC key was
printed). PUBLIC key `c2f0549ebc1c133f497774ed3f77b907700e71d4a0550c7b820905f55eca1cef` placed in
`config/aqos/lease-signer-keys.json` (replacing the `524279cd…` placeholder), key_id `lease-signer-2026-08`.

**Phase 1 — service enabled, flag still 0 (no-behavior-change canary):**
- `nix/modules/core/secrets.nix` — NEW gated secret `lease-signing-ed25519-private-key` (0400, owned by
  the dedicated `aq-lease-signing-authority` user), guarded by `needsAlaSecret = leaseSigningAuthority.enable`
  so hosts with the ai-stack secrets block but ALA off never chown to a missing user.
- `nix/modules/profiles/ai-dev.nix` — `mySystem.aiStack.leaseSigningAuthority.enable = true`;
  `CAPABILITY_ASYMMETRIC_LEASE` untouched (stays 0 → gate keeps in-process HMAC).
- **WR-3 deploy-context preflight (found + fixed a real bug):** `cryptography` confirmed in the service's
  `authPython`; import closure = {lease_signing_authority, capability_lease} both copied into the bundle;
  `config/first-party-tools.json` exists + world-readable (DAC ok). **BUG:** `config/capability-lease-epoch`
  was missing but bound via `ReadOnlyPaths` → the unit would have started FAILED. FIXED by creating the
  epoch SSOT file (`= 0`, genesis); parity-verified both readers resolve 0 before + after (issues-backlog
  `ala-epoch-file-missing-readonlypaths-unit-fail`).
- Validation: crypto 24/24, authority PASS, service-coverage PASS, HMAC regression 54/54 (byte-parity);
  all changed .nix parse; lease-signer-keys.json valid + active.

**Remaining owner acts:** rebuild (brings up the confined authority with the provisioned key, gate still
HMAC → no outage), then verify `systemctl status aq-lease-signing-authority` active + `--check` = ready.
THEN Phase 2: flip `CAPABILITY_ASYMMETRIC_LEASE=1` (switchboard) + rebuild + validate the live mint.

## Status: ALA rev4 BUILD COMPLETE (default-OFF), 3 slices, each verified

Owner activation to turn it live (all separate acts, in order): (1) generate an Ed25519 keypair, put
the public key in `config/aqos/lease-signer-keys.json` (replacing the placeholder), SOPS-encrypt the
private key to `/run/secrets/lease-signing-ed25519-private-key`; (2) `enable` the
`aq-lease-signing-authority` service (rebuild) — run a WR-3-style deploy-context preflight for its
bundle; (3) flip `CAPABILITY_ASYMMETRIC_LEASE=1` (switchboard) + validate a live first-party lease
mints via the authority and `verify_authoritative` accepts it. THEN the C2 scheduler-context issuer
rev3 (verifies asymmetric leases via `verify_authoritative` + a consumed-lease ledger + expiry/epoch
per OBLIG-1) → C6 main → C6 activation → C4.
