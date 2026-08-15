---
doc_type: plan
id: c2-sci-activation-20260815
title: C2-SCI — activation (owner-granted)
status: in-progress
parent_prd: trusted-execution-gateway
slice: c2sci-activate
---

# C2-SCI activation

Owner activation grant emitted 2026-08-15 (event `0aab588edd284521ab4bf0940000d35f`, subject
`c2-scheduler-context-issuer-ACTIVATE`, design `c36d375a622232aa045793399da0ccacc75e2773714f2f3c25709e4da303d55c`,
build_head `3f68911f87115973febed0dbccf2881da8c6fb51`). Defects were resolved by `3d45e03c` (verified).

## What this activates
- **Signer key:** owner-provisioned Ed25519 private seed in SOPS as `c6-scheduler-context-signing-key`
  → `/run/secrets/c6-scheduler-context-signing-key` (0400, owned by `aq-c2-scheduler-context-issuer`).
  The switchboard/owner-uid never holds it (verify != forge).
- **Verifier allowlist:** `config/aqos/c6-scheduler-signer-keys.json` rev 2 — the real public key
  `f5162de45d21cc0ee1c9237a3eda0dc42ec56d1b597cff7e9ae9d891144ce514`, key_id
  `c2-scheduler-context-signer-2026-08` (matches the service's `AQ_SCHEDULER_CONTEXT_KEY_ID`), status active.
- **Service:** `mySystem.aiStack.c2SchedulerContextIssuer.enable = true` — the confined issuer + its 0660
  UDS + the `aq-c2-scheduler-context-clients` group (primaryUser is a member, so the switchboard reaches it).
- **Flag:** switchboard `CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1` + `AQ_SCHEDULER_CONTEXT_SOCKET_PATH`.

## Activation Gate attestation
- **Integrated:** switchboard gate mints a signed scheduler-lease-context via the issuer UDS (B3 wiring, ad5d95dd).
- **Turned ON:** enable=true + flag=1 (this commit); active on the owner's next rebuild.
- **Validated real-world:** PENDING the rebuild — live mint round-trip (real ALA lease → signed
  `aq.scheduler-lease-context/1` → gate verifies vs the public key). This record is finalized after validation.
- **Observable:** dashboard `c2_scheduler_context_issuer` (`context_issuer`, `ledger_durable`, `signer_active`,
  `status`). Follow-up (non-blocking): surface the durable-ledger `recorded`/`replays` counts on the panel.
- **Intervenable:** durable single-use ledger — operator reset = delete the offending
  `{lease_id,grant_digest}` marker file under the issuer's StateDirectory ledger dir (owned by
  `aq-c2-scheduler-context-issuer`) to clear a slot burned by a transient signer outage (fail-closed
  over-deny). Documented in the issuer module.

## Validation plan (post-rebuild, Claude)
1. `systemctl is-active aq-c2-scheduler-context-issuer` = active; `/run/secrets/c6-scheduler-context-signing-key` present 0400.
2. Live mint round-trip: real ALA lease → issuer mints a signed context → gate `verify_authoritative` accepts
   against the public key; a tampered/foreign-key context DENIES.
3. Dashboard shows `context_issuer: on`, `status: ok`; flag-OFF byte-parity revert verified in principle.

## Revert
switchboard: remove the two C2-SCI env lines; profile: `enable = false`; rebuild → default-OFF byte-parity.
The signer key can remain provisioned (unused when disabled).
