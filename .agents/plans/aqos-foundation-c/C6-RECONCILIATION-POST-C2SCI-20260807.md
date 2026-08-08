---
title: "Foundation C — C6 reconciliation after C2-SCI + C6-P0 landed (both blockers resolved)"
slice: "C6"
kind: "readiness reconciliation (analysis-tier; authorizes nothing)"
date: "2026-08-07"
author: "Claude Opus 4.8 (orchestrator/analysis)"
design_of_record: "C6-DESIGN-AND-AUTHORIZATION.md (rev2, PREPARED_ONLY) → needs a rev3 re-anchor per below"
verdict: "C6 is now UNBLOCKED — both pre-freeze blockers resolved; remaining path = rev3 re-anchor → fresh binding re-review → freeze → build → activate"
---

# C6 reconciliation — both blockers resolved

The C6 Activation-Readiness assessment (2026-08-06) held C6 BLOCKED on two questions. Both are now closed
by landed, reviewed work:

## Q-C6-1 (the critical path — a C2 scheduler-lease-context issuer + signed ingress) — RESOLVED
Built as the **C2-SCI slice** (design rev4 `c934db23`, binding review PASS, freeze
`C2-SCHEDULER-CONTEXT-ISSUER-FREEZE-20260807.md`, owner-activated, built default-OFF B1–B4):
- The issuer EXISTS: `scripts/ai/lib/scheduler_context_issuer.py` mints the domain-separated
  Ed25519-signed `aq.scheduler-lease-context/1` ONLY after `verify_authoritative`-verifying the presented
  lease + OBLIG-1 + re-deriving from signed fields + a DURABLE single-use `{lease_id,grant_digest}` ledger
  (commits `e01d48a7`/`0bd67174`). Confined service `nix/modules/services/c2-scheduler-context-issuer.nix`.
- The signed INGRESS adapter EXISTS: `dispatch.py::verify_ingress_scheduler_context` (commit `ad5d95dd`,
  B3) — Ed25519-verify against `config/aqos/c6-scheduler-signer-keys.json` + audience + expiry + epoch,
  total function, no signing key, currently INERT (defined, not yet spliced into the live dispatch flow),
  flag-gated `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`.
- NOTE vs the C6 rev2 design's speculation: the issuer is a SEPARATE confined service (NOT an extension of
  `capability_lease_issuance.py` as §the design guessed). C6 rev3 must reference the ACTUAL artifacts.

## Q-C6-2 (owner public-key allowlist + authority hardening) — RESOLVED
C6-P0 trust anchors rev3 BUILT (`config/aqos/c6-owner-public-keys.json`,
`config/schemas/revocation-epoch-bump.schema.json`, `config/schemas/scheduler-lease-context.schema.json`
all present; freeze+activation `C6-P0-FREEZE-AND-ACTIVATION-20260806.md`).

## Anchor reconciliation for the C6 rev3 re-anchor
| C6 §1 anchor | design hash | current | action |
|---|---|---|---|
| `scripts/ai/lib/slot_queue.py` | `e4e7e9b1…` | `e4e7e9b1…` | UNCHANGED ✅ (C6 main edits it — the fence) |
| `scripts/ai/lib/dispatch.py` | `1b083b10…` | `77ba0c25…` | **RE-ANCHOR** — C2-SCI B3 added `verify_ingress_scheduler_context` (expected; that IS the Q-C6-1 ingress) |
| `ai-stack/switchboard/capability_lease_gate.py`, `default.nix`, `capability_lease.py` | (per design) | drifted by ALA/enforce-verify/C2-SCI | RE-ANCHOR to current (all landed + reviewed) |

## Remaining C6 main scope (unchanged in shape; now consuming the built prerequisites)
C6 main is the SCHEDULER REVOCATION GATE + epoch authority, DISTINCT from the now-built C2-SCI issuer:
- EDIT `slot_queue.py`: before `acquire` mutates queue state, verify the immutable signed context (via the
  built ingress), fence on a durable reservation digest, drop queued/held reservations on an epoch bump.
  Flag `CAPABILITY_SCHEDULER_LEASE_GATE` (default 0, byte-parity off — independent of
  `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`).
- Wire the built `verify_ingress_scheduler_context` into the live dispatch→slot_queue path (it is inert
  today) under the gate flag.
- The epoch authority (durable authenticated revocation-epoch bump, owner-signed via
  `c6-owner-public-keys.json`, fail-closed key-unavailable) — the R1–R6 codex findings + C6-P0.

## Path (analysis-tier recommendation; authorizes nothing)
1. Draft **C6 rev3** = rev2 re-anchored to the current base + the "Q-C6-1/Q-C6-2 RESOLVED, consume the
   built C2-SCI + C6-P0" reconciliation above.
2. Fresh independent BINDING re-review of C6 rev3 (the codex depth-review was on rev1; rev2/rev3 have no
   PASS yet) — the last gate before freeze.
3. Hash-bound freeze → single-use owner build-activation → default-OFF build → independent code review →
   commit → owner flag/enable.
4. THEN C4 (network confinement) — C6 is its intervention-lever predecessor.

Blocks nothing on the C2-SCI confirmatory reviews (queued, lane-returned) — those are advisory on an
already-orchestrator-verified default-OFF slice.
