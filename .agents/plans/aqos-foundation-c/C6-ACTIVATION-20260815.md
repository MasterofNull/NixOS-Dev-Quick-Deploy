---
doc_type: plan
id: c6-activation-20260815
title: C6 — activation (fleet revocation kill-switch)
status: in-progress
parent_prd: trusted-execution-gateway
slice: c6-activate
---

# C6 activation

Owner activation grant emitted 2026-08-15 (event `575ca3a27cf9489581ef674b6f919dd5`, subject `c6-ACTIVATE`,
design `eea88865cb5da6899f0b8f716229ef99bc03c21c8e98e337d8bb6f1223d7eb33`, build_head `10e5eafe`).

## What this activates
- **Owner kill-switch authority (OFFLINE key):** the owner's real Ed25519 **public** key
  `0eb4b5939271e80ea5987a6dc214c5ef1a76f6bafc02d843b1353160b7a3c65f` (key_id `owner-2026-08`) replaces the
  all-zeros placeholder in `config/aqos/c6-owner-public-keys.json` (rev 2). The **private key is offline** —
  never on the host, never in SOPS. The revocation-epoch authority is SOPS-free and verifies owner-signed
  `aq.revocation-epoch-bump/1` documents against this public allowlist; the owner signs bumps offline via
  `aq-epoch-bump`.
- **Revocation fence ON:** switchboard `CAPABILITY_SCHEDULER_LEASE_GATE=1` + `AQ_REVOCATION_EPOCH_SOCKET_PATH`
  (the slot_queue fence + gate epoch resolver read the authoritative epoch over the authority UDS). This
  also closes C6-B3 review CP-3 (the deferred switchboard epoch-socket injection). primaryUser reaches the
  authority via `aq-revocation-epoch-clients`.
- The epoch-authority READ side was already enabled (during C2-SCI); this adds the owner-verify (bump) key
  + the enforcing fence.

## Activation Gate attestation
- **Integrated:** slot_queue verified-context fence + the gate epoch resolver (C6-B3, committed).
- **Turned ON:** owner key + flag (this commit); active on the owner's next rebuild.
- **Validated real-world:** PENDING the rebuild — the kill-switch proof (below).
- **Observable:** epoch authority service state + audit receipts (`epoch.audit.jsonl`); dashboard revocation surface.
- **Intervenable:** the owner-signed epoch bump IS the intervention (the fleet kill-switch); revoke = bump the epoch.

## Validation plan (post-rebuild, Claude) — the kill-switch proof
1. `aq-c2-scheduler-context-issuer`/`aq-revocation-epoch-authority`/switchboard active; the fence flag live.
2. `aq-epoch-bump build ...` → the owner signs the canonical domain-separated bytes OFFLINE with the private
   key → submit the signed bump → the authority verifies it against `0eb4b593…` and increments the epoch.
3. Prove revocation: a held scheduler reservation stamped with the OLD epoch is DROPPED after the bump; a
   fresh mint at the NEW epoch succeeds. A forged/wrong-key bump DENIES (fail-closed).

## Revert
switchboard: remove the two C6 env lines (flag → default OFF byte-parity). The owner key can remain (it
verifies bumps; unused when the fence is off).
