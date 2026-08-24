---
doc_type: plan
id: aqos-refactor-completion-rundown-20260823
title: AQ-OS refactor — remaining-work rundown, priorities, and completion definition
status: draft
parent_prd: aqos-requirements-inventory
owner: hyperd
date: 2026-08-23
---

# AQ-OS refactor — what's left, what to start now, what to queue

Purpose: with Codex now orchestrating the operational (local-agent dogfooding) loop, this organizes the
BROADER AQ-OS refactor so we don't lose sight of the original program. Grounded in the honest trackers
(`aqos-requirements-inventory`) + `UNIFIED-PROGRAM-PLAN` + `DEFINITION-OF-DONE`, not memory.

## 1. What "AQ-OS refactor COMPLETE" actually means
The refactor = the **Local AI Factory reference architecture**, delivered as Cycles 0–6 (Foundations A–C,
Products D–G, cross-cutting Tracks V/S/F). "Complete" has a hard bar (`DEFINITION-OF-DONE`): every slice
must be **Integrated + Turned-ON + real-world-Validated + Observable + Intervenable + owner-ACCEPTED**, or
carry a written dated deferral. The program ENDPOINT is **Product G legacy retirement** — the old
system decommissioned after 2 clean cycles on the new one, at semver v1.0.

**The honest headline: 0 of 15 program items are ACCEPTED.** Most are 15–60% *integrated*; none has cleared
the full 5-dimension bar. So by our own definition, the refactor is early-middle, not near-done — and the
biggest systemic gap (below) is exactly why nothing is "accepted": most work isn't Observable/Intervenable yet.

## 2. Current honest state (the program map)
| Item | % (integration) | Status per unified plan |
|---|---|---|
| Foundation A — Cycle-0 truth exit | 40 | 10/10 authority rows owner-adjudicated; **physical convergence = Cycle 1 work, pending** |
| Foundation B1 — contract kernel + parity | 50 | **EXECUTING** (L1A/L2A/L2B-A landed; L2B-B unauthorized; chat/batch parity in shadow next) |
| Foundation B2 — one shadow-state vertical | (part of B) | B2-D0 accepted; B2-C1 authorization/review only |
| Foundation B3 — projector + canon-compiler | (part of B) | partial (aq-event projector live) |
| Foundation C — identity/leases/cells/net-profiles | 56 | **NOT STARTED as the full spine**; needs B1 + owner Q3 security ratification |
| Product D — inference/client live convergence | 20 | NOT STARTED; **closes the F2.5 dormant HIGH**; needs B1 parity + C boundaries |
| Product E — eval & learning factory | 15 | NOT STARTED; needs B2 evidence store + C integrity |
| Product F — one CLI (`aq <noun> <verb>`) + command center | 0 | NOT STARTED; needs authoritative telemetry from C/D |
| Product G — edge/release/retirement (v1.0) | 0 | NOT STARTED; needs everything prior; **the completion endpoint** |
| Track V — Verified Factory | 25 | REQUEST_REVISION; interim process armor; VF-1 waits on L2B-B |
| Track S — Defensive Security | 15 | design + S0-A only; build pending an eligible lane |
| Track F — Flat collaborative factory | 45 | F1 done; F2 partial (F2.5 dormant→Product D); F3 = Foundation C |
| HERDR — operator observation surface | 22 | H0+H1 done (sealed/inert by design); H2 presentation = 0% |
| 20 HARD behavioral rules (governance) | 55 | written + partly gated; full enforcement audit pending |
| Agent parity | 45 | matrix exists; drift possible |
| Observability parity (every blank `--` is a bug) | 35 | partial |
| ACP — beginner-friendly human control | 60 | built, default-OFF/crypto-deferred; not activated |

## 3. The critical path (dependency order — this is the spine)
```
Foundation B1 (local-inference, EXECUTING)  ─┐
Foundation A physical convergence           ─┼─► Foundation C (identity/leases/cells)  [GATE: owner Q3]
                                             │        │
                                             │        ▼
                                             └─► Product D (inference convergence, closes F2.5) [needs B1+C]
                                                      │
                                                      ▼
                                       Product E (eval factory) [needs B2+C]  [GATE: owner Q7]
                                                      │
                                                      ▼
                                       Product F (one CLI + command center) [needs C/D telemetry] [GATE: Q6]
                                                      │
                                                      ▼
                                       Product G (edge/release/RETIREMENT = COMPLETE) [needs all]
```
Cross-cutting (run alongside, gate acceptance everywhere): Track V (owner Q9), Observability pillar, HARD-rule enforcement, agent parity.

## 4. Where THIS session's work fits (so we don't lose sight — it WAS on-program)
The local-agent deep-dive was not a detour — it advanced the program:
- **Grammar fix / context supply chain / interventions / write_region / record-replay / defect fixes** →
  **Foundation B1** (local-inference contract) reliability + the "stable/extensive local harness" goal.
- **Workflow redesign + async-review discipline + tier0 test-gating** → the **20 HARD rules / governance**
  cross-cutting + closed the loophole that let defects ship.
- **Maturity-gap analysis (OTel + record/replay)** → scoped the **Observability** pillar.
So the two-phase north-star maps on: **Phase 1 (fix workflow) ≈ done; Phase 2 (local inference harness) =
finish Foundation B1 + build the Observability pillar + prep Product D convergence.**

## 5. START NOW (the 3 priorities — all unblocked, high-leverage)
1. **Close Phase 1 (Codex-orchestrated, in flight):** fold in the 6 queued independent reviews
   (provisional→accepted), run full tier0, push the ~17 commits, re-dogfood the FIXED local stack to get a
   real reliability number vs the ~21% baseline. → completes the B1-reliability slice + proves the process works.
2. **The OBSERVABILITY pillar (highest systemic leverage):** this is why 0/15 are accepted — most slices
   fail DoD dimensions 4 (observable) + 5 (intervenable). Build: (a) **OTel-GenAI event spine** (the maturity-gap
   #1 — token/cost/latency + typed spans; wire `aq-event` as the substrate) and (b) **HERDR H2 presentation**
   (owner-authorized slice) as the operator surface. This UNBLOCKS acceptance of many existing slices at once.
3. **Finish Foundation B1:** the local-inference contract is the executing spine; L2B-B authorization +
   chat/batch parity-in-shadow are the next slices. Feeds Product D and unblocks Track V (VF-1).

## 6. QUEUE AFTER (dependency-gated — do not start until their gate clears)
- **Foundation C** (identity/leases/cells/network-profiles) — GATE: **owner Q3** (security model ratification).
  Absorbs F3 + the WS9 core. The confinement spine.
- **Product D** (inference convergence: switchboard sole gateway, **activate the F2.5 scheduler**, route/profile
  registry) — needs B1 parity + C boundaries. This is the "one live inference path" and closes a standing HIGH.
- **Product E** (eval & learning factory) — GATE: **owner Q7**; needs B2 + C.
- **Product F** (one CLI + typed command center) — GATE: **owner Q6**; needs C/D telemetry (and the Observability
  pillar from §5.2 is its foundation).
- **Product G** (edge probes, install profiles, restore/upgrade drills, **v1.0 + legacy retirement**) = the
  completion endpoint.
- **Track V activation** — GATE: **owner Q9** (VF-0 round). **Track S** build (defensive security) — pending an
  eligible lane.

## 7. Owner decisions that GATE the queue (these unblock, not me)
| Q | Decision | Gates |
|---|---|---|
| Q3 | Security model (principal attestations + CapabilityLease, no fail-open; 8 network profiles) | Foundation C |
| Q6 | Kernel front door: keep `local-orchestrator` or revise toward `aq` gateway | Product F |
| Q7 | Eval factory as universal promotion gate | Product E |
| Q8 | Adjudicate remaining physical convergence of the 10 Cycle-0 authority rows | Foundation A exit |
| Q9 | Activate Track V after VF-0 round | Verified Factory |
| Q10 | Rebudget the 27 GB envelope for a resident small model / speculative decoding, or defer to fleet | Product D/E |

## 8. Recommendation
Do §5 (the three START-NOW priorities) now — they're unblocked, and #2 (Observability) is the single highest-
leverage move because it converts a pile of "integrated-but-not-accepted" slices into acceptable ones AND is
the maturity multiplier for everything after. Then resolve **Q3** (unblocks Foundation C → Product D, the
critical-path bottleneck). Products E/F/G follow the spine. "Complete" = Product G retirement at v1.0 with
all 15 items owner-accepted — realistically several cycles out; this rundown makes the path explicit so no
thread is lost.
