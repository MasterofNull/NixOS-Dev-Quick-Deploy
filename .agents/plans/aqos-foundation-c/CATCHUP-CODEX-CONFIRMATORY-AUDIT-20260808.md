---
reviewer: "Codex (independent, Rule-18 catch-up)"
date: "2026-08-08"
review_kind: "confirmatory advisory audit"
independence: "I did not author or substitute-review the audited slices. I inspected the live worktree and exercised the named seams independently of the prior review documents."
live_head: "04ddb9feaa4a612a502da588318eefaa91142573"
---

# Rule-18 Catch-up Confirmatory Audit

Scope was read-only against the live worktree. The requested `ai-stack/switchboard/dispatch.py`
does not exist; the live ingress implementation is `scripts/ai/lib/dispatch.py`, which is the path
audited below. Pre-existing worktree changes were not modified. The only audit write is this report.

## 1. ALA — Asymmetric Lease Authority

### Strongest attacks tried

1. **Signing oracle:** send an arbitrary request body from a socket-authorized owner-uid process and
   attempt to influence a signed field. `handle_request()` ignores the request bytes and calls
   `_load_manifest()` plus `_resolve_epoch()` itself, then `mint_first_party_leases()` constructs every
   signed field (`scripts/ai/lib/lease_signing_authority.py:62-123, 151-188, 197-206`). The UDS does
   return the complete manifest-authorized lease set to an allowed client, but it does not sign an
   opaque or caller-selected payload (`scripts/ai/lib/lease_signing_authority.py:209-256`). The service
   key remains confined to the dedicated principal and the client group grants socket access, not key
   access (`nix/modules/services/lease-signing-authority.nix:65-79, 93-123`). I found no field-level
   signing oracle past the owner-controlled manifest/epoch policy.
2. **Scheme downgrade:** set `sig_scheme="hmac-sha256"`, create a genuine HMAC signature with the
   known development key, and present it to the authoritative verifier. The primitive checks the
   signed scheme before key lookup and returns `scheme-not-ed25519`; there is no call to `verify()`,
   `resolve_key()`, or HMAC in this function (`scripts/ai/lib/capability_lease.py:361-439`). The
   asymmetric first-party request path also fails to `{}` without falling back to HMAC
   (`ai-stack/switchboard/capability_lease_gate.py:360-385, 409-427`). The existing regression test
   reproduced this deny.
3. **OBLIG-1 confusion:** use an authentic but expired/stale Ed25519 lease. As designed,
   `verify_authoritative()` proves signature plus active-key status only. The gate separately applies
   `is_expired()` and `epoch_stale()` before returning `ok`
   (`ai-stack/switchboard/capability_lease_gate.py:668-690`). The C2 issuer independently repeats the
   same temporal checks (`scripts/ai/lib/scheduler_context_issuer.py:363-380`).

**VERDICT: CONFIRM**

## 2. C2-SCI — Scheduler-context issuer

### Strongest attacks and failing inputs tried

1. **Lease replay across task IDs/processes/restarts:** the ledger key is exactly
   `(lease_id, grant_digest)`, not `task_id` (`scripts/ai/lib/scheduler_context_issuer.py:395-403`). Its
   marker creation is the atomic test-and-set `O_CREAT|O_EXCL|O_NOFOLLOW`; only `EEXIST` becomes replay,
   while other storage faults propagate. File and directory entries are fsync'd before success
   (`scripts/ai/lib/scheduler_context_issuer.py:216-247`). The service always supplies the durable
   StateDirectory ledger (`scripts/ai/lib/scheduler_context_transport.py:249-300`;
   `nix/modules/services/c2-scheduler-context-issuer.nix:91-103, 127-157`). The 32-thread, 16-process,
   and restart tests each produced exactly one winner. Ledger-before-sign prevents duplicate signed
   contexts; the documented consequence is fail-closed over-denial if signing fails after the burn,
   not a replay bypass (`scripts/ai/lib/scheduler_context_issuer.py:395-441`).
2. **Flag-OFF parity:** with `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` unset or `0`, the gate never calls
   the transport and attaches no context (`ai-stack/switchboard/capability_lease_gate.py:638-665,
   808-812, 866-870`). The ingress helper remains outside `main()`/`dispatch_task()`
   (`scripts/ai/lib/dispatch.py:1125-1232`). The C2 flag-off wiring suite and the legacy F2.5
   slot-queue suite both passed unchanged.
3. **Real ALA-to-C2 input:** I minted a lease using the live ALA minter and passed that exact,
   correctly Ed25519-signed lease to the live C2 issuer. It failed with
   `lease-fields-malformed`. ALA's closed lease construction does not emit `grant_digest` or
   `policy_revision` (`scripts/ai/lib/lease_signing_authority.py:68-100`), while C2 requires both
   (`scripts/ai/lib/scheduler_context_issuer.py:291-325`) before reaching its ledger/signing path.
   Existing C2 tests conceal this seam by fabricating both fields in their fixtures
   (`scripts/testing/test-scheduler-context-ledger.py:257-280`). Therefore the shipped, default-OFF
   issuer cannot mint a scheduler context from the shipped ALA first-party lease shape. Enabling the
   later scheduler fence would deny every such task for lack of a context. This is fail-closed, but it
   is a complete activation blocker for the claimed ALA -> C2-SCI integration.
4. **Epoch mismatch/failure:** a valid signed lease stamped `revocation_epoch=2` was accepted while
   `current_epoch=1`, and the issuer minted a context stamped `1`. The implementation tests only
   `lease_epoch < current_epoch` (`scripts/ai/lib/scheduler_context_issuer.py:375-380`), while the
   governing design requires `lease.revocation_epoch != current authoritative epoch` to deny
   (`.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md:46-58, 71-72`).
   Worse, the service resolver maps an absent or malformed epoch file to `0`
   (`scripts/ai/lib/scheduler_context_transport.py:238-246`) and then mints using that value
   (`scripts/ai/lib/scheduler_context_transport.py:276-300`). This is not a fail-closed authoritative
   epoch resolution. It is partially contained today by the independent default-OFF downstream C6
   fence, but it violates the issuer's own mandatory binding contract.

**VERDICT: DEFECT{HIGH} — activation-blocking ALA/C2 lease-schema mismatch; DEFECT{MEDIUM} — epoch mismatch and unavailable-store handling are not deny-closed**

## 3. C6-P0 rev3 + C2 issuer rev2 — Binding-review fix

### Strongest attacks tried

1. **Prerequisite hiding by document relabeling:** C6-P0 rev3 explicitly chooses the prior review's
   NARROW option, limits itself to a public owner-key allowlist plus two closed schemas, and lists the
   issuer, transport, signer, service, dispatch, Nix, deployment, and activation surfaces as removed
   or excluded (`.agents/plans/aqos-foundation-c/C6-P0-TRUST-ANCHORS-REV3-20260806.md:15-28,
   38-51, 63-80`). It says it closes neither runtime gate and points the issuer prerequisite to the
   sibling C2 design (`:30-36`). That is an honest narrowing, not prerequisite concealment.
2. **Human-uid peer impersonation:** connect as another process with the same primary-user UID and
   present fabricated correlation authority. The transport passes `SO_PEERCRED` only as log/defense
   metadata (`scripts/ai/lib/scheduler_context_transport.py:50-64, 114-155, 276-300`). The issuer first
   calls the scheme-pinned Ed25519 `verify_authoritative()`, then derives its authority tuple from
   signed lease fields; correlation can supply only `task_id`, `principal`, and `dispatch_mode`
   (`scripts/ai/lib/scheduler_context_issuer.py:291-344, 363-390, 416-435`). Hostile correlation fields
   cannot override trust tier, action class, policy revision, grant digest, or lease ID. Thus rev2's
   central correction—signed lease authority, peer UID as defense-in-depth only—is genuinely present.

The defects in subject 2 block successful activation and require follow-up, but they do not restore
the old `SO_PEERCRED == authority` vulnerability or make C6-P0 rev3 dishonest.

**VERDICT: CONFIRM**

## 4. C6 rev3 / B1 / B2 — Durable revocation-epoch kill-switch

### Strongest attacks tried

1. **Missing/malformed epoch bootstrap:** missing paths, symlinks, non-regular files, oversized data,
   negative/float/leading-zero/garbage content, and non-UTF-8 data all raise typed `EpochStoreError`;
   only a present strict non-negative integer can return an epoch
   (`scripts/ai/lib/revocation_epoch.py:206-253`). The missing and malformed vectors and the complete
   `apply_bump()` flow all denied without creating an epoch-zero store.
2. **Concurrent/replayed bump:** `apply_bump()` verifies first, acquires the stable adjacent lock,
   reads and compares `expected_epoch` under that lock, burns the durable replay key, and only then
   performs the same-directory fsync + atomic replace to exactly `current+1`
   (`scripts/ai/lib/revocation_epoch.py:549-583, 609-690`). Replay markers use
   `O_CREAT|O_EXCL|O_NOFOLLOW`, propagate non-`EEXIST` faults, and fsync file plus directory
   (`scripts/ai/lib/revocation_epoch.py:474-532`). A second signed request with the same replay tuple
   but correctly updated expected epoch was denied across a fresh ledger instance. A crash between
   ledger burn and epoch replace can over-deny that request, but cannot double-bump or downgrade the
   epoch; this tradeoff is explicit and fail-closed.
3. **Online signing/key extraction:** the authority service bundle contains only the verifier/mutator
   module and transport; its Nix unit provisions no SOPS secret or private-key path and exposes only
   the public owner-key allowlist read-only (`nix/modules/services/revocation-epoch-authority.nix:1-24,
   43-55, 87-90, 135-171`). The transport loads public JSON and calls `apply_bump()`
   (`scripts/ai/lib/revocation_epoch_transport.py:231-296`). `aq-epoch-bump` builds canonical bytes or
   submits an already signed document; it never accepts or loads a private key
   (`scripts/ai/aq-epoch-bump:6-27, 53-102, 105-135`). The library signing helper takes explicitly
   supplied offline/test key bytes and is not called by the service or CLI
   (`scripts/ai/lib/revocation_epoch.py:256-283`).

**VERDICT: CONFIRM**

## Validation evidence

All commands ran with `PYTHONDONTWRITEBYTECODE=1`; all exited 0:

- `scripts/testing/test-asymmetric-lease-authority.py` — 24/24
- `scripts/testing/test-enforce-asymmetric-verify.py` — 40/40
- `scripts/testing/test-scheduler-context-issuer.py` — 53/53
- `scripts/testing/test-scheduler-context-ledger.py` — 32/32, including threads/processes/restart
- `scripts/testing/test-c2-gate-dispatch-wiring.py` — 42/42
- `scripts/testing/test-c2-sci-service-coverage.py` — PASS
- `scripts/testing/test-revocation-epoch.py` — 55/55
- `scripts/testing/test-revocation-epoch-authority.py` — PASS
- `scripts/testing/test-slot-queue-wiring.py` and `scripts/testing/test-scheduler-lease-gate.py` — PASS

Two additional in-memory probes reproduced the ALA-to-C2 schema failure and the future-epoch
acceptance described in subject 2.

## ROLLUP

This is an advisory catch-up audit and does not rewrite prior review history. It is **not** a
confirmatory PASS because live code exposed bounded follow-ups:

1. **C2-SCI-HIGH — define and implement one canonical ALA/C2 lease contract.** Either add
   owner-authorized, signed `grant_digest` and `policy_revision` fields to real ALA leases, or amend
   C2's required admission tuple and replay key. Add an integration test that feeds
   `lease_signing_authority.mint_first_party_leases()` output directly into
   `scheduler_context_issuer.mint_scheduler_context()`; do not use a hand-augmented fixture.
2. **C2-SCI-MEDIUM — make epoch resolution and comparison exact and fail-closed.** An absent/malformed
   epoch authority must deny rather than substitute zero, and the issuer must enforce the design's
   exact epoch match (including a negative vector for a signed future-epoch lease).

No bounded follow-up is required for subjects 1, 3, or 4 from this pass.
