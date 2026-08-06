---
title: "Foundation C — C6 Activation-Readiness Reconciliation"
slice: "C6"
kind: "readiness-assessment (analysis-tier; authorizes nothing)"
date: "2026-08-06"
author: "Claude Opus 4.8 (orchestrator/analysis)"
design_of_record: ".agents/plans/aqos-foundation-c/C6-DESIGN-AND-AUTHORIZATION.md (rev2, PREPARED_ONLY)"
verdict: "C6 is design-complete + anchor-stable, but BLOCKED on two pre-freeze questions; Q-C6-1 exposes a missing C2 issuer that is the real critical path"
---

# C6 Activation-Readiness Reconciliation

## 0. What this is

C6 (`C6-DESIGN-AND-AUTHORIZATION.md`, rev2) is the **intervention lever** C4 depends on: a durable
authenticated epoch authority + an F2.5 scheduler revocation gate. Its rev2 closes all six Codex
depth-review findings (R1–R6). This document reconciles its freeze prerequisites with reality and
charts the path. It authorizes nothing.

## 1. Readiness reconciliation

| C6 freeze prerequisite | Status (2026-08-06) | Verdict |
|---|---|---|
| §1 base anchors unchanged | all 12 checked anchors (`capability_lease_gate.py`, `slot_queue.py`, `dispatch.py`, `capability_lease.py`, `default.nix`, …) **UNCHANGED** | ✅ stable (no re-freeze churn, unlike C4) |
| **Q-C6-1: a C2 component that issues the signed `aq.scheduler-lease-context/1`** | **NO such issuer exists** (grep: no `scheduler-lease-context` producer in `scripts/ai/lib` or `switchboard`); the design itself states "the current C2 gate returns admission decisions but does not itself expose that handoff" | ❌ **OPEN — the critical path** |
| **Q-C6-2: owner public-key allowlist + authority service hardening** | addressed in `C6-P0-TRUST-ANCHORS-DESIGN` (`config/aqos/c6-owner-public-keys.json`), but that P0 review is **`REQUEST_REVISION — NOT FREEZE ELIGIBLE`** (missing: signer permission, rotation/revocation source, fail-closed key-unavailable path) | ⚠️ **partially closed — bounded revision needed** |
| Fresh independent PASS on C6 rev2 main bytes | codex depth-review was on rev1; rev2 answers it but has no PASS yet | ⚠️ re-review needed |

## 2. The two blockers, unpacked

### Q-C6-2 — bounded, actionable now
The P0 trust-anchors design already names the mechanism: a repo-declared, revisioned, immutable
`config/aqos/c6-owner-public-keys.json` (key-id → Ed25519 public key, status active|revoked). The
P0 rev2 review asked for three closures: (a) the **signer** identity + how the owner private key
signs a bump (without any key entering the repo/service — SOPS/offline), (b) **rotation/revocation**
source + immutable-revision semantics, (c) the **fail-closed key-unavailable** path. All three are
specification work on an existing design — no new architecture. **This is draftable now.**

### Q-C6-1 — the real critical path (a missing C2 issuer)
C6's scheduler gate is only meaningful if `dispatch.py` receives a *signed, audience-bound*
`aq.scheduler-lease-context/1` from the C2 admission issuer — never from the shell caller. That
issuer does not exist: C2's `capability_lease_issuance.py` mints capability leases but not this
scheduler-audience handoff, and there is no signed transport into `dispatch.py`. Per the C6 design
(§3.1), this is an explicit **stop condition**: "if C2 cannot produce this signed audience-bound
handoff at the frozen base, C6 stops for a separately reviewed C2 handoff slice." So the honest
dependency is:

> **C6 cannot freeze until a C2 scheduler-lease-context issuer + signed ingress transport is
> designed, reviewed, and anchored. That C2-handoff slice is the true next unit of work.**

Likely shape (for the owner/architect decision, not authorized here): extend the existing C2
admission issuer (`capability_lease_issuance.py`) to additionally mint the domain-separated
`aq.scheduler-lease-context/1` bound to {lease_id, grant_digest, task_id, audience, principal,
mode, epoch, policy_rev}, plus an authenticated local ingress adapter feeding `dispatch.py` — as
its own PREPARED_ONLY → review → freeze slice. This is a bounded C2 extension, but it is
architecture that must be reviewed, not assumed.

## 3. The full dependency chain (honest map)

```
C4 (network profiles)  ← blocked on →  C6 (intervention lever)
                                         ├─ Q-C6-2: C6-P0 trust-anchors rev3   [bounded, draftable now]
                                         └─ Q-C6-1: C2 scheduler-context issuer [NEW sub-slice: design→review→freeze]
```
R7 GREEN already cleared C4's *runner* prerequisite; the remaining Foundation-C activation frontier
is entirely inside C6's two questions.

## 4. Ordered path to C6 freeze → C4

1. **Draft C6-P0 trust-anchors rev3** — close the three REQUEST_REVISION items (signer/SOPS,
   rotation/revocation, fail-closed) → independent re-review → PASS. *(bounded; I can draft it)*
2. **Design the C2 scheduler-lease-context issuer + ingress** slice (Q-C6-1) → independent review →
   hash-bound freeze → build → accepted commit. *(new sub-slice; needs an architecture decision)*
3. **C6 main freeze** — bind rev2 hashes + the P0 trust-anchors accepted hash + the C2-issuer
   accepted commit; independent PASS on rev2 bytes.
4. **Single-use owner build activation** → default-OFF build (per §4 inventory) → offline vectors
   (§5) + Service Coverage → independent code review → commit.
5. **Separate owner activation** of the scheduler gate (`CAPABILITY_SCHEDULER_LEASE_GATE=1`) — the
   intervention lever goes live. **This unblocks C4's freeze.**

## 5. Recommendation

Two-track:
- **Now (bounded):** let me **draft the C6-P0 trust-anchors rev3** — it's pure specification on an
  existing design and closes Q-C6-2, the freeze-eligible half.
- **Owner/architect decision (Q-C6-1):** whether to open the **C2 scheduler-lease-context issuer**
  as its own slice (recommended shape above) — this is the real gate on the whole C4/C6 chain and
  needs your call before I draft it, since it touches the C2 issuer's trust boundary.

C6 stays PREPARED_ONLY; anchors are stable so no re-freeze churn. Say "draft P0 trust-anchors" and
I'll produce rev3, or decide the Q-C6-1 direction and I'll draft the C2-handoff slice.
