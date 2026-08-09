---
doc_type: plan
id: teg-c1-orchestrator-review-20260808
title: TEG C1 — orchestrator review (direction, scope/minimal-code, C4 boundary, sequencing)
status: draft
parent_prd: trusted-execution-gateway
slice: C6-B3R-C1
date: 2026-08-08
reviewer: "Claude Opus 4.8 (session orchestrator; analysis-tier, no implementation)"
role: orchestrator concurrence + minimal-code/staging guard
subjects:
  - .agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md
  - .agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md
  - .agents/plans/aqos-foundation-c/C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md
  - .agents/plans/aqos-foundation-c/TEG-C1-DESIGN-REVIEW-20260808.md (codex sub-agent, REQUEST_REVISION)
verdict: "CONCUR-WITH-DIRECTION · NOT-FREEZE-READY (concur R1–R5) · build must be STAGED"
head: 0579c5796730c443bca31612efa8e4aa6ce784b3
---

# TEG C1 orchestrator review

## 1. Direction — CONCUR
Codex's reconciliation correctly supersedes the shallow C6-B3 fix I briefed. The revocation race lives
between `slot_queue.acquire()` return and the provider `urlopen()` — outside `acquire()` — so an in-acquire
stable-snapshot cannot close it; and owner-uid/agent share a Unix identity, so no caller-presented context
(CLI/env/file) can carry authority without a same-UID confusion/replay surface. A dedicated-principal
broker that derives the lease/context itself and owns the launch linearization is the **minimal correct
boundary**, not gold-plating. My B3-fix dispatch is stood down (it also correctly halted on the consumed,
non-replayable grant).

## 2. Scope / minimal-code (Rule 20) — CONCUR with a STAGING guard
The trust boundary and the launch-linearization + crash matrix ARE the fix (correctness, not over-build).
But the packet mandates a big-bang atomic ship — service/env/Nix + consumer + cancellation authority +
numeric ceilings + dashboard API/panel + TUI + Agent Ops all together (DESIGN:53). Against ponytail:
- KEEP atomic (Activation Gate requires it): the broker principal, lifecycle/CAS/crash correctness, the
  launch linearization, hermetic fake-authority/fake-provider proof, and the minimum observable+intervenable
  telemetry. Without these together, activation is unsafe.
- STAGE (do NOT gate the first build on them): full ceiling matrix tuning, the separate
  `aq-teg-cancellation-authority` as its own service, TUI + Agent Ops panels beyond the minimum health
  surface. These are bounded follow-ons after the core broker is accepted — smaller first correct slice.
Directive: the eventual build grant is for the CORE broker + linearization + minimum activation surface;
the rest are tracked follow-on slices, not a reason to enlarge slice one.

## 3. C4 boundary — CLEAN
TEG governs launch/execution authority for scheduler-originated effectful execution; it does not touch
network egress. No C4 over-reach. TEG is upstream of C4 (its future intervention lever), distinct scope.
Naming discipline is correct: "TEG, not `aq-dispatchd`" — no unbuilt program is made authoritative.

## 4. Freeze-readiness — NOT YET (concur the sub-agent's REQUEST_REVISION)
R1–R5 are real and load-bearing (lifecycle omits `revoked`; token create/commit/consume/run ordering
collapsed; idempotency key not bound to the envelope digest; UDS server-identity binding unspecified; CAS
mechanics underspecified). The design must close them, then re-review, before any freeze.

## 5. Sequencing — a hard predecessor exists
The packet's own `depends_on` names "accepted ALA-C2 implementation," and TEG derives the C2 context. The
open **C2-SCI lease-contract fix (HIGH)** — real ALA leases lack `grant_digest`+`policy_revision` — is
therefore a HARD predecessor. C2-SCI must land its canonical lease contract before TEG can freeze/build.

## Owner decision (single, ordered)
1. **C2-SCI lease contract** — pick the signed-fields option (ALA emits owner-signed `grant_digest` +
   `policy_revision`); authorize a bounded fix slice (build grant). Unblocks C2-SCI AND is the TEG predecessor.
2. **TEG** — authorize the DESIGN-revision (close R1–R5) → independent re-review → freeze. Analysis-tier;
   **no build grant yet**. The staged core-broker build grant comes after freeze.

RECORD: orchestrator concurrence; no implementation authorized here.
