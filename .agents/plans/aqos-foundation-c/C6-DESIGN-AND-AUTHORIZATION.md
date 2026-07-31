---
title: "Foundation C C6: Epoch-Revocation Control Surface + F2.5 Scheduler Seam — Design Packet"
slice: "C6"
status: "C6_DESIGN_REVIEWED_PASS — scheduler-seam build needs single-use owner activation (enforcement-tier); codex confirmatory REQUIRED (light-model review)"
revision: 1
kind: "design-only"
implementation_authorization: "NONE — the scheduler-seam is enforcement-tier: requires single-use owner activation before build"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C2 gate + executor revocation_epoch CHECK (shipped, 97131faa); C3b R3 runner epoch fence (ccbc0718)"
  - "F2.5 slot_scheduler (LIVE — dispatch.py wait_for_slot)"
successors:
  - "closes the Foundation C ref-arch (Cycle 6)"
---

# Foundation C — C6: Epoch-Revocation Control Surface + Scheduler Seam

## 0. Provenance & authority
Authored by Opus (codex-substitution). Independent review → antigravity/gemini + codex-on-return.
**DESIGN-ONLY.** C6 has two parts with different authority classes: (a) the **epoch-bump control
surface** — the operator's revocation lever (an owner action, like activation) — and (b) the
**F2.5 scheduler seam** — wiring the live slot scheduler to refuse slots for revoked/stale-epoch
leases, which is a NEW enforcement point ⇒ **enforcement-tier: its build requires single-use owner
activation**, ships flag-default-OFF. The executor epoch *check* already shipped (C2/R3); C6 adds
the *control* + the *scheduler* enforcement point.

## 1. Scope (DESIGN-PACKET §8)
Deliver: (a) an **epoch-bump control surface** — a governed operator command/event that increments
`config/capability-lease-epoch`, atomically revoking every in-flight lease whose `revocation_epoch`
is now stale (fleet-wide kill switch); (b) the **F2.5 scheduler seam** — the slot scheduler
consults lease validity/epoch before granting a slot and drops queued/held slots for revoked
leases, so a revoked capability cannot even be *scheduled* (not just cannot execute). **Out of
scope:** re-implementing the executor epoch check (shipped C2/R3); C5 spans; any new capability kind.

## 2. Build on what exists (grounded 2026-07-30)
- **Epoch source (shipped):** `ai-stack/switchboard/capability_lease_gate.py::resolve_current_epoch`
  (172) reading `config/capability-lease-epoch` (84; absent ⇒ 0); `capability_lease.epoch_stale()`
  (230). Executors (C2 `_admit_tool_call`, C3b R3 runner final fence) already deny stale-epoch leases.
- **F2.5 scheduler (LIVE — corrects a stale "dormant" note):** `dispatch.py:135` imports
  `slot_scheduler` (`wait_for_slot`, `SlotWaitTimeout`); ":137 F2.5 wiring: banded cross-process
  slot queue (scheduler + backpressure)"; ":502 Slot pre-poll via slot_scheduler.wait_for_slot()".
  So there is a real, integrated scheduler to add a lease gate to.
- **Owner-action pattern:** `scripts/ai/aq-event emit --agent owner` (the activation lever) is the
  precedent for the epoch-bump control surface (a governed, audited owner event).

## 3. Epoch-bump control surface (the revocation lever)
- A governed command `aq-epoch-bump` (or `aq-event emit --agent owner --type revocation.epoch-bump`)
  that **atomically** increments `config/capability-lease-epoch` (read-modify-write under a lock;
  the new value fsync'd) and emits an audited `revocation.epoch-bump` event with `{old, new, reason,
  scope}`. Effect: every lease with `revocation_epoch < new` is now stale ⇒ denied by the already-
  shipped executor checks AND (C6) refused a slot by the scheduler.
- **Authority:** bumping the epoch is an **owner/operator action** (it is a kill switch) — governed,
  audited, reversible-forward-only (epoch is monotonic; you cannot un-revoke by lowering it, you
  re-issue leases at the new epoch). Deny-closed: an unreadable/locked epoch file ⇒ executors treat
  `current_epoch=None` as stale (already shipped) ⇒ everything denies (fail-closed, never fail-open).
- **Non-self-healing (the codex-1 invariant, preserved):** a bump revokes; leases are NOT auto-
  reissued — re-issue is a deliberate later step. So the bump genuinely kills fleet-wide.

## 4. F2.5 scheduler seam (the enforcement point — flag-gated)
- The slot scheduler (`slot_scheduler.wait_for_slot`) gains a **lease pre-check**: before granting a
  slot to a lease-bearing request, verify the lease is valid + `revocation_epoch >= current_epoch`;
  a stale/revoked lease is **refused a slot** (typed denial, not a silent hang) and any *held* slot
  for a now-revoked lease is dropped on the next scheduler tick. This makes revocation bite at
  *scheduling* time, not only at execution time — an over-scoped/compromised lease can't monopolize
  or even acquire a slot after a bump.
- **Flag `CAPABILITY_SCHEDULER_LEASE_GATE` (default "0")**: OFF ⇒ the scheduler behaves byte-
  identically to today (F2.5 unchanged; parity-tested). ON ⇒ the lease pre-check is active. Non-
  lease-bearing requests (legacy paths) are unaffected (the gate only applies where a lease is
  present) — no regression to existing scheduling.
- Deny-closed: epoch unresolvable / lease unverifiable at schedule time ⇒ slot refused (never
  granted on doubt). The scheduler NEVER fails open.

## 5. Ceiling (frozen at C6 freeze)
- NEW `scripts/ai/aq-epoch-bump` (the control surface) + its audited event type + a lock/fsync
  atomic bump of `config/capability-lease-epoch`.
- EDIT `slot_scheduler.py` — the lease pre-check + held-slot-drop-on-revoke (flag-gated; flag-OFF
  byte-parity). (Predecessor: `dispatch.py` wiring is the live seam; the check is additive.)
- EDIT `config/env-contract.yaml` — `CAPABILITY_SCHEDULER_LEASE_GATE` (default "0").
- NEW decision/audit schema + NEW `scripts/testing/test-scheduler-lease-gate.py` +
  `test-epoch-bump.py` (offline: atomic bump under contention; monotonic-only; bump ⇒ stale leases
  refused a slot; held slot dropped on bump; non-lease request unaffected; flag-OFF byte-parity;
  deny-closed on unresolvable epoch; non-self-healing (no auto-reissue after bump)).
- **MUST NOT:** lower the epoch / un-revoke; auto-reissue leases on a bump; fail open on unresolvable
  epoch; change non-lease-bearing scheduling; weaken the shipped executor checks.

## 6. Acceptance bar
- an epoch bump is atomic (lock+fsync), monotonic (increment-only), audited, and immediately makes
  lower-epoch leases stale (executor + scheduler both deny).
- the scheduler refuses a slot to a stale/revoked lease and drops a held slot on the next tick;
  non-lease-bearing requests are unaffected; flag-OFF byte-parity with live F2.5.
- deny-closed on unresolvable epoch / unverifiable lease at schedule time; never fail-open.
- non-self-healing: a bump is not undone and leases are not auto-reissued.
- revocation-under-load (compose with C3b R4): a bump during active scheduling kills queued+held
  lease slots within budget and the scheduler stays responsive to new deny-closed requests.

## 7. Review obligations
1. epoch bump is atomic + monotonic + audited + fail-closed; unreadable epoch ⇒ deny everywhere.
2. the scheduler seam is deny-closed (refuse-on-doubt), flag-OFF byte-parity, no non-lease regression.
3. non-self-healing preserved (no auto-reissue; monotonic epoch; forward-only revocation).
4. the seam composes with the shipped executor checks (defense in depth), doesn't replace/weaken them.
5. F2.5 anchors are real (slot_scheduler/wait_for_slot live in dispatch.py) — verify, no fabrication.
6. bump control surface authority = owner/operator (kill switch), governed + audited like activation.

## 8. Ceremony (mixed authority)
Control surface (aq-epoch-bump) = a governed operator tool (standing-auth to BUILD the tool; USING
it to bump is an operator act). Scheduler seam = **enforcement-tier**: design → independent review →
freeze → **single-use owner activation** → build flag-default-OFF → review → commit; flipping
`CAPABILITY_SCHEDULER_LEASE_GATE` ON is a further separate act. Predecessor hashes: capability_lease.py,
gate, slot_scheduler.py, dispatch.py seam.

## 9. Open questions for review
- Q-C6-1: should the epoch-bump be `aq-event emit --agent owner --type revocation.epoch-bump`
  (reusing the activation event lane + audit) or a dedicated `aq-epoch-bump` command? Recommend the
  aq-event lane (one governed owner-action surface, already audited).
- Q-C6-2: held-slot-drop granularity — drop on the next scheduler tick vs immediate signal.
  Recommend next-tick (bounded, simple) with the executor final-fence as the immediate backstop
  (already shipped) — the two compose.
- Q-C6-3: scope of the scheduler gate to lease-bearing requests only (confirm no regression to the
  many existing non-lease dispatch paths). Recommend yes — the gate is a no-op without a lease.
- Q-C6-4: this closes Foundation C (Cycle 6). Confirm the executor-check (C2/R3) + scheduler-seam
  (C6) + control-surface together satisfy the ratified F3 obligation-3 (stale-lease-can't-revive-
  after-epoch) end to end.

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against C6 scope + §7. The
scheduler-seam build additionally requires single-use owner activation; no review outcome authorizes it.
