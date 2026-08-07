# B2 Independent Code Review — C2 Scheduler-Context Issuer (commit 03a3eb6c)

Reviewer: fresh Claude flagship (Opus 4.8), Codex-substitute per Rule 18. Not the author.
Scope: actual committed code in `03a3eb6c`, compared to proven `nix/modules/services/lease-signing-authority.nix` (ALA).
Method: `git show`, direct file reads, nix parse, live test run.

## 1. CONFINEMENT — PASS
`nix/modules/services/c2-scheduler-context-issuer.nix`:
- Dedicated system user + group `aq-c2-scheduler-context-issuer` (`:59-67`, `isSystemUser`).
- SOPS key `/run/secrets/c6-scheduler-context-signing-key`, `0400`, owner+group = the dedicated user — `secrets.nix:179-183`.
- Gated `needsC2SciSecret = cfg.aiStack.c2SchedulerContextIssuer.enable` (`secrets.nix:30`), emitted via `lib.optionalAttrs needsC2SciSecret` (`:167`). A disabled host never chowns to a missing user — mirrors `needsAlaSecret` exactly.
- `NoNewPrivileges=true`, `CapabilityBoundingSet=""`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, `RestrictSUIDSGID`, `LockPersonality`, `RestrictAddressFamilies=["AF_UNIX"]` (`:131-146`) — byte-for-byte the ALA hardening set.
- Self-contained 3-module bundle transport+issuer+capability_lease (`:47-51`); `ReadOnlyPaths=[leaseKeysPath epochPath]` (`:147`).
- `enable` default `false` (`:71`). Module ships INERT. Nix parses (`nix-instantiate --parse` OK for both files). `default.nix:25` registers the module.

## 2. CLIENT-ACCESS (the ALA lesson) — PASS
- Shared group `aq-c2-scheduler-context-clients` (`:76`); issuer user is a member via `extraGroups` (`:63`); `primaryUser` added via `users.users.${primaryUser}.extraGroups = mkAfter [...]` (`:77`). Both members — matches ALA `:71/:79`.
- Socket-dir `d /run/aq-c2-scheduler-context-issuer 0755` (`:82`) = world-traversable; agrees with default RuntimeDirectoryMode so the two never disagree across rebuilds. The `0660` socket is the actual access control.
- `serve()` (`scheduler_context_transport.py:114-141`): binds, `chmod 0660`, then `os.chown(path, -1, getgrnam(AQ_SCHEDULER_CONTEXT_CLIENT_GROUP).gr_gid)` + re-`chmod 0660`. **Fail-closed + non-widening**: on `KeyError/PermissionError/OSError` it WARNs and leaves the socket in the issuer's own group (`:135-141`) — no `0666`, no fallback widening. Clients simply fail-closed.
- B3's future outbound client (switchboard as `primaryUser`) CAN reach it: primaryUser ∈ client group, dir 0755, socket 0660 group=client-group. Will not fail-close.

## 3. KEY ISOLATION — PASS
- Private key `0400` owner=dedicated user only (`secrets.nix:180-182`); switchboard/owner uid and the ALA lease-signer never hold it (distinct user, distinct key family — commit-documented and enforced by owner/group).
- `config/aqos/c6-scheduler-signer-keys.json` is public-only (`ed25519_public_key` + `status:"active"`, placeholder), status-bearing, DISTINCT `key_id` (`c2-scheduler-context-signer-2026-08`) vs ALA's `lease-signer-2026-08`. Verified distinct via grep. This file is the downstream (B3) verifier allowlist for the *minted context*; the service itself reads only `lease-signer-keys.json` (the admission-lease verifier) at runtime — correct separation.

## 4. TRANSPORT EDIT — PASS
- Edit adds `_read_private_key`/`_load_json_file`/`_resolve_epoch`/`build_env_handler` + `__main__` binding to `serve()` (fail-closed helpers, lazy cryptography import). It did NOT touch `serve()`'s frame/timeout/SO_PEERCRED discipline: `MAX_REQUEST_BYTES=65536`, `settimeout(RECV_TIMEOUT_S)`, per-connection try/except (one bad conn never crashes the loop, `:158`), handler exception → typed `handler-error` deny (`:154-155`). SO_PEERCRED remains log-only defense-in-depth (`:147`).
- `build_env_handler` re-derives everything from env; on missing/unreadable key → `None` → `DENY_SIGNER_UNAVAILABLE`; missing allowlist → `verifier-allowlist-unavailable`; both fail-closed.
- **B1 suite: 53 passed, 0 failed** (`scripts/testing/test-scheduler-context-issuer.py`, run live). The chgrp addition weakened nothing.

## 5. DURABLE-LEDGER GAP (B2.5) — CONFIRMED, correctly gated
- `build_env_handler` instantiates `sci.InMemorySingleUseLedger()` (`transport.py:~268`; class at `scheduler_context_issuer.py:127-141` — a per-process `set`).
- **Safe while default-OFF? YES.** Service is inert (`enable=false`), no unit runs, nothing mints. No live exposure.
- **Durable ledger REQUIRED before enable? YES — this is a real fail-open at activation.** On restart the in-memory set resets, so an already-consumed `{lease_id, grant_digest}` re-mints a fresh signed scheduler-context — the single-use guarantee (design §3 mandate 3) breaks across restarts = fail-open. Correctly tracked as B2.5 and named a hard pre-enable blocker in the commit body. Affirmed: enabling the unit before B2.5 lands would be a fail-open footgun.
- The seam is already fail-closed on fault: `mint_scheduler_context` wraps `check_and_record` in try/except → `DENY_LEDGER_UNAVAILABLE` (`issuer.py:286-288`). A file/DB-backed impl inherits that contract.
- **Requirements the durable slice MUST get right (flag):**
  a. **Atomic check-and-record.** Current `serve()` is single-threaded (synchronous accept loop, `listen(16)` but one conn at a time), so no in-process race today. A durable store that read-then-writes non-atomically — or any future multi-worker/socket-activated fan-out — reintroduces a concurrent double-mint race. Require an atomic primitive (unique-constraint INSERT, `O_CREAT|O_EXCL` marker, or held lock) that returns first-use/replay atomically.
  b. **Fail-closed on IO error** mapped to `DENY_LEDGER_UNAVAILABLE` (never silently treat an IO failure as first-use).
  c. **Durable-store location under `StateDirectory`** (already declared) with owner-only perms; must not become world/group-writable.
  d. Observability (O2/O3) for ledger health + replay-deny count before enable, per design.

## 6. SCHEMA — PASS
`config/schemas/scheduler-lease-gate-decision.schema.json`: `additionalProperties:false`; enum-bounded `decision`/`reason`/`latency_bucket` (latency is a bucket, never raw ms → low cardinality); `context_id`/`lease_id` are opaque correlation ids. No signature, no key material, no lease/context body, no prompt, no filesystem path. Matches the `execution-cell-adapter-receipt` precedent. Observability-only (never a mint gate). secrets.nix + default.nix wiring correct (§1).

## 7. FAIL-OPEN / MIS-CONFINEMENT / ACTIVATION FOOTGUN
- No fail-open in the shipped default-OFF state. The one latent fail-open (in-memory ledger across restart) is inert while disabled and correctly gated behind B2.5.
- No mis-confinement: confinement set is identical to the proven ALA; socket access is non-widening on failure.
- Activation footgun (already tracked, restating for the activation reviewer): do NOT set `enable=true` (nor flip B3 `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`) until (1) B2.5 durable ledger with atomic check-and-record lands, and (2) the real SOPS private key replaces the placeholder public key in `c6-scheduler-signer-keys.json`. Enabling with the placeholder key = signatures no verifier trusts (fail-closed, not fail-open — safe but non-functional); enabling without B2.5 = fail-open across restarts.

## Summary
The commit is a faithful, confinement-correct mirror of the proven ALA pattern. Confinement, client-access (the ALA lesson), key isolation, transport hardening, schema hygiene, and secret gating all verified against actual committed code. B1 suite 53/53. The sole risk (in-memory single-use ledger) is a genuine cross-restart fail-open, but it is inert under default-OFF and correctly tracked as B2.5 with a stated pre-enable block. No unresolved defect in the shipped inert artifact.

VERDICT: PASS
