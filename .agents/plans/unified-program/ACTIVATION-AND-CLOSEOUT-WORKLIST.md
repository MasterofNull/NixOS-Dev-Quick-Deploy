# AQ-OS Refactor — Activation & Close-Out Worklist

**Compiled:** 2026-07-23 by fable-5 (orchestrator), from the owner-activation event
ledger (`.agents/events/*.jsonl`, authoritative), the authorization corpus
(`.agents/plans/**/*AUTHORIZATION*.md`), and `UNIFIED-PROGRAM-PLAN.md`.

## Headline: the refactor is NOT blocked on a pile of owner activations
The owner-activation ledger records **38 owner `pulse.append` activations** through
2026-07-22. The **frontier slice of every live track is already activated.** The
authorization-doc *headers* that still read `PREPARED_ONLY / NOT ACTIVATED` are
**stale** — the activation happened in the ledger but the doc header was never
updated (confirmed on B2-C1: header says NOT ACTIVATED, ledger shows owner activation
2026-07-18, and the accepted 8-file candidate is committed with matching hashes).

So the close-out work is **(A) reconcile stale records** and **(B) prepare the
remaining forward slices** — not chase activations.

---

## Section 1 — Activated frontier (DONE per the ledger; records may be stale)
Owner-activated; implementation accepted/committed. Verify each doc header is
updated to ACTIVATED (many are not — see Section 2).

| Slice | Authorization (activated) | Ledger date |
|---|---|---|
| Foundation B2-C1 (pure-contract oracle) | `auth-aqos-foundation-b2-c1-20260718` | 07-18 |
| Foundation B2-M1A-AM2 (+ acceptance) | `auth-aqos-foundation-b2-m1a-am2-20260719` | 07-19 |
| Foundation B3-C1 (canon compiler) | `auth-aqos-foundation-b3-c1` | 07-21 |
| B1 / L2B-B live payload adoption (+ corrected, reactivate, AM2, AM4, rev) | `auth-local-inference-l2b-b(-corrected/-am2/-am4/-rev)` | 07-21 → 07-22 |
| QPPR A1-AM3 (+ rev2 + acceptances) | `auth-qa-provider-probe-reliability-a1-am3(-rev2)` | 07-19 → 07-20 |
| QPPR A2-AM1 (+ candidate-rev) | `auth-qa-provider-probe-reliability-a2-am1` | 07-20 |
| QPPR C1C-AM2, C1C-AM3 (+ acceptances) | `auth-qa-provider-probe-reliability-c1c-am2/-am3` | 07-19 |
| Agent-conn C0.6-T-AM6 (AM3/AM5 too) | `C0.6-T-AM6` | 07-22 |
| Track V VF-7 (evidence path) | `auth-verified-factory-vf-7` | 07-22 |
| delegate-codex-quota-precheck (+ rev) | `auth-delegate-codex-quota-precheck` | 07-20 |

Superseded / non-activatable intermediates (correctly NOT activated, contained):
C0.6-T-AM4 (superseded), L2B-B-AM1 (suspended: pre-review subject drift), L2B-B-AM3
(superseded by AM4). Historical done tracks: Cycle-0 C0.1–C0.3, C0.5A/B, agent-ops
M1/M2A, R0.1, program-progress-tracker, generic-flake-baseline, Foundation-A
adjudication+registry-projection (Foundation A EXIT complete, 10/10 adjudicated).

## Section 2 — RECONCILE stale records (bounded, safe, orchestrator-doable NOW)
These authorization docs were owner-activated per the ledger but their headers still
read `PREPARED_ONLY / NOT ACTIVATED`, making the plan *look* unfinished. Reconcile
each header to ACTIVATED with a pointer to the ledger event + the committed candidate.
No code change; pure record hygiene. Confirmed stale (spot-checked):
- `aqos-foundation-b2/B2-C1-IMPLEMENTATION-AUTHORIZATION.md` — activated 07-18, candidate committed.
- `aqos-foundation-b3/B3-C1-CANON-COMPILER-AUTHORIZATION.md` — activated 07-21.
- `local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` — activated 07-21 (+corrected/AM2/AM4).
- (full sweep) any `*AUTHORIZATION*.md` whose id appears in the ledger but header ≠ ACTIVATED.

**Action:** one bounded reconciliation pass over the corpus (a `*.md` header update +
a "§ Owner Activation Record" stub citing the ledger event_id/ts). This is the single
highest-leverage close-out task — it makes the plan's paper state match reality.

## Section 3 — FORWARD slices to actually close the refactor (need prep, not activation)
Ordered by the program cadence (one foundation in-flight at a time; Track V T0/T1 may
interleave). Each needs DESIGN + authorization PREPARATION + independent review, then
owner activation — normal forward work, not a stuck activation.

1. **Foundation B1 — chat/batch parity in shadow** (closes B1). L2B-B adoption is
   activated; parity is the last B1 slice. Needs a design packet + authorization.
2. **Foundation B2 — evidence-driven expansion/replacement** decision after the
   shadow-vertical (M1A/C1) evidence. Owner decision, then next B2 slice.
3. **Foundation C — identity, leases, execution cells.** Gated on ratified security
   model (Q3, still pending). Needs Q3 first, then design.
4. **Product D — inference/client convergence** (switchboard sole gateway; closes the
   dormant F2.5 HIGH). Gated on B1 parity + C boundaries. Note: LEC Slice 3
   (switchboard KV-stable prune) is a D-adjacent optimization already designed.
5. **Product E → F → G** — eval factory, unified CLI, release/retirement (later cycles).
6. **Track V** — VF-1/2/3/6/9 remaining (VF-7 activated). VF was REQUEST_REVISION;
   amended contracts need re-review (Q9).

Owner decisions still open (from the decision gate): Q3 (security model), Q4 (canon
policy), Q5 (lane-eligibility registry), Q6 (CLI front door), Q7 (eval gate), Q9 (VF
activation), Q10 (memory envelope rebudget). Q1/Q2/Q8 resolved.

## Section 4 — Non-blocking open issues (logged)
- `task_registry-golden-pin-stale` (MED) — reliability golden pin stale; reviewed re-pin needed.
- `local-single-inference-slot-contention` (MED) — serialize local jobs via aq-loop-queue --no-fanout.
- `generic-nixos-ai-dev-flake-check-baseline` (HIGH) — generic template flake-check.
- `lean-ctx-global-session-pointer` (HIGH, third-party).
- LEC 2b activation-validation + Slice 3 (deferred, this program's own follow-ups).

---

## Recommended close-out sequence
1. **Reconcile stale records** (Section 2) — makes the plan honest; bounded, safe, now.
2. **Prepare B1 chat/batch parity** design + authorization (Section 3.1) — closes the
   nearest Foundation; owner activates; implement.
3. **Owner works Q3** to unblock Foundation C.
4. Proceed D→E→F→G per cadence, Track V interleaving after Q9.

There is no "activate these N authorizations" backlog — the owner is current. The
gap is stale paperwork + the un-started forward cycles.
