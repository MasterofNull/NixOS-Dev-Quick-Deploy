---
title: "C6 rev3 — Independent BINDING re-review (fresh Claude flagship, Codex-substitute per Rule 18)"
slice: "C6"
kind: "binding review (last gate before hash-bound freeze)"
date: "2026-08-07"
reviewer: "Claude Opus 4.8 (independent; Codex-substitute per Rule 18 — Codex lane not the actor)"
target: "C6-DESIGN-AND-AUTHORIZATION.md revision 3 + C6-RECONCILIATION-POST-C2SCI-20260807.md"
base_head_claimed: "e7bf91deb4693a6667cd3c3ed10b0988b4143ef6"
verdict: "PASS (freeze-eligible)"
---

# C6 rev3 — Independent Binding Re-Review

Method: every hash re-computed with `sha256sum` against the working tree TODAY; every
Q-C6-1/Q-C6-2 resolution claim verified against the ACTUAL built code, not the design's prose.
Findings ranked; fail-open / auto-reissue / byte-parity-break weighted HIGH. No speculative findings.

## 1. Re-anchor correctness (rev3 §1 table) — VERIFIED, all 12 match

| path | rev3 (current) claim | actual `sha256sum` (8) | match |
|---|---|---|---|
| `scripts/ai/lib/capability_lease.py` | `611f1af8` | `611f1af8` | ✅ |
| `ai-stack/switchboard/capability_lease_gate.py` | `970d10f7` | `970d10f7` | ✅ |
| `scripts/ai/lib/slot_scheduler.py` (UNCHANGED) | `ea3b5b9a` | `ea3b5b9a` | ✅ |
| `scripts/ai/lib/slot_queue.py` (UNCHANGED) | `e4e7e9b1` | `e4e7e9b1` | ✅ |
| `scripts/ai/lib/dispatch.py` | `77ba0c25` | `77ba0c25` | ✅ |
| `scripts/ai/delegate-to-local` (UNCHANGED) | `b5d2c5cb` | `b5d2c5cb` | ✅ |
| `scripts/ai/aq-event` (UNCHANGED) | `5deba81b` | `5deba81b` | ✅ |
| `config/env-contract.yaml` | `74c10eb2` | `74c10eb2` | ✅ |
| `dashboard/backend/api/routes/aistack.py` | `aa855d61` | `aa855d61` | ✅ |
| `assets/dashboard.js` | `9c892841` | `9c892841` | ✅ |
| `scripts/testing/harness_qa/phases/phase0.py` (UNCHANGED) | `5e6f2208` | `5e6f2208` | ✅ |
| `nix/modules/services/default.nix` | `f772a1eb` | `f772a1eb` | ✅ |

No mismatch. No re-freeze churn. The §1 rev3 baseline is faithful to the tree. The freeze may bind
these exact anchors.

## 2. Q-C6-1 (C2 scheduler-lease-context issuer + signed ingress) — GENUINELY RESOLVED

- **Issuer built and correct.** `scripts/ai/lib/scheduler_context_issuer.py` (present; `de21c748`):
  `CONTEXT_SCHEMA = "aq.scheduler-lease-context/1"` (L75); `mint_scheduler_context()` (L347) runs the
  full chain `verify_authoritative` → OBLIG-1 → re-derive admission tuple → **single-use durable ledger**
  → Ed25519-sign. Ledger is keyed on `{lease_id, grant_digest}` with a `O_CREAT|O_EXCL` durable
  filesystem marker (`_DurableSingleUseLedger`, L151+) that survives process/service restart and
  **fails CLOSED** on any ledger fault (L400 `except → deny`). `context_id = sched-ctx::{lease_id}::{grant_digest}`.
- **Signed ingress verifier built and correct.** `dispatch.py::verify_ingress_scheduler_context` (L1180)
  verifies schema-tag → signature/active-key (via `_sci.verify_scheduler_context`) → audience
  (`aq-f2.5-slot-queue`, L1149) → freshness → epoch-stale, against
  `config/aqos/c6-scheduler-signer-keys.json` (L1148 — a **distinct key family** from the owner epoch keys,
  correctly separated). It is a **total function** (try/except returns typed deny, never raises — L1228)
  with **no fail-open branch**.
- **Naming reconcile accurate.** rev2 reserved `scripts/ai/lib/scheduler_lease_context.py`; the built
  artifact is the separate confined service `scheduler_context_issuer.py` (+ `scheduler_context_transport.py`,
  `nix/modules/services/c2-scheduler-context-issuer.nix`). rev3 §1 documents the supersession correctly.
- **C6 consumes, does not re-create.** The ingress verifier is **INERT**: `verify_ingress_scheduler_context`
  is referenced only in tests — `test-c2-gate-dispatch-wiring.py` explicitly asserts
  `"verify_ingress_scheduler_context" not in src(main)` and `not in src(dispatch_task)` plus
  `_scheduler_context_issuer_enabled() is False` by default. Flag `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`
  default `"0"`. No live call site in `scripts/`, `ai-stack/`, `dashboard/`. C6-main's job is to SPLICE
  the existing verifier into the live path under the *independent* `CAPABILITY_SCHEDULER_LEASE_GATE`.
- **Schema compatible with C6 gate + slot_queue.** `config/schemas/scheduler-lease-context.schema.json`
  is a **closed** schema (`additionalProperties:false`) with required = `{schema_version, context_id,
  lease_id, grant_digest, task_id, audience, principal, dispatch_mode, action_class, issued_at, expires_at,
  revocation_epoch, policy_revision, issuer_key_id, signature}` — every field C6's gate + `slot_queue`
  fence need (lease_id, grant_digest, audience, epoch, single-use context digest) is present.

## 3. Q-C6-2 (owner key allowlist + P0 hardening) — RESOLVED, verify-only anchors present

- `config/aqos/c6-owner-public-keys.json` — present (279 B).
- `config/schemas/revocation-epoch-bump.schema.json` — present, **closed** (`additionalProperties:false`),
  required = `{schema_version, request_id, idempotency_key, issued_at, expires_at, actor_key_id,
  expected_epoch, reason_code, scope, signature}` — matches design §2.1 exactly.
- `config/schemas/scheduler-lease-context.schema.json` — present, closed (see §2).

All three are pre-existing anchors (C6-P0); C6 main must NOT re-create them. Confirmed as verify-only.

## 4. Core C6 security design — SOUND (re-verified against built prerequisites)

- Epoch authority (owner-signed `aq.revocation-epoch-bump/1` only; SO_PEERCRED defense-in-depth not
  authority; durable epoch + replay ledger; fail-closed on unavailable/malformed/replay/stale; no
  bootstrap-to-zero / env fallback / direct file write / auto-reissue) — design §2 is internally
  consistent and consumes the built closed bump schema. This is C6-main NEW code (correctly absent today).
- Scheduler gate — `slot_queue.py` today has **no** `CAPABILITY_SCHEDULER_LEASE_GATE`, no `verify_ingress`
  reference (confirmed by search): byte-parity trivially holds at the current base, and C6-main is the
  slice that adds the fence (verify immutable signed context BEFORE mutating queue state; single-use
  durable reservation digest; epoch-bump drops queued/held reservations). Flag default-0, byte-parity-off,
  and INDEPENDENT of `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` — the two flags are separate env vars, verified.

## 5. Fail-open / oracle / byte-parity — no HIGH finding on the live path

The live `slot_queue`/`dispatch` path is unchanged (byte-parity preserved; both flags default-0). The
built ingress verifier is total and fail-closed on every branch. No oracle: denials are low-cardinality
typed reasons (`DENY_INGRESS_*`), no secret/lease/prompt leakage. R1–R6 closures (§7) are consistent with
the built artifacts; none re-opened.

### Advisory notes (NON-BLOCKING — record at freeze, do not gate)

- **A1 (activation-provisioning, not fail-open):** `c6-owner-public-keys.json` ships a **placeholder
  all-zeros** Ed25519 key (`key_id: owner-2026-08`, revision 1). This is the epoch-bump authority key,
  consumed only by not-yet-built C6-main code. A real owner key MUST be provisioned at owner activation
  before any bump can be authorized. An all-zeros (low-order) key **fails closed** — a genuine signature
  cannot verify against it — so this is not a fail-open surface; but the freeze record must name it as an
  activation-time gate and not treat the anchor as production key material. Consistent with design §6
  (activation = separate owner act). The scheduler-signer key (`c6-scheduler-signer-keys.json`) by
  contrast carries **real** material (`dbae8529…`, active) — the C2-SCI signing path is functional.
- **A2 (highest-risk C6-main code-review checkpoint):** `verify_ingress_scheduler_context(current_epoch:
  int = 0)` defaults epoch to 0. Inert today (tests only). When C6-main wires it, it MUST pass the
  authoritative epoch from `revocation_epoch.resolve_current_epoch()` and deny-on-unavailable — **never**
  the default 0. With `current_epoch=0`, `epoch_stale` would treat every context as fresh and the
  revocation drop would never fire (fail-open revocation). Design §2.2/§3.2 already mandate the authority
  reader and deny-on-unavailable, so the design is sound; this is the single item the eventual C6-main
  code review must confirm in the wiring diff. Not a freeze blocker.
- **A3 (cosmetic):** both schemas omit `$id`; the schema tag (`aq.*/1`) is carried in the document's
  `schema`/`schema_version` field and matched by the issuer/verifier. No correctness impact.

## Conclusion

The rev3 re-anchor is hash-accurate (12/12), both freeze blockers are genuinely closed by landed,
independently-reviewed default-OFF work that C6 CONSUMES rather than re-creates, the core epoch-authority
and scheduler-gate semantics remain sound, and there is no fail-open / auto-reissue / byte-parity-break on
the live path. Two items (A1 owner-key provisioning at activation; A2 authoritative-epoch wiring at
C6-main code review) must be recorded — neither blocks the freeze.

VERDICT: PASS
