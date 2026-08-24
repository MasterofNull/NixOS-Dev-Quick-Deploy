---
doc_type: plan
id: aqos-refactor-completion-rundown-20260823
title: AQ-OS refactor — remaining-work rundown, priorities, and completion definition
status: draft
parent_prd: aqos-requirements-inventory
owner: hyperd
# Owner-direction gate: Q1–Q10 are resolved; future per-slice activation remains owner-authorized.
date: 2026-08-23
---

# AQ-OS refactor — what's left, what to start now, what to queue

Purpose: with Codex now orchestrating the operational (local-agent dogfooding) loop, this organizes the
BROADER AQ-OS refactor so we don't lose sight of the original program. Grounded in the honest trackers
(`aqos-requirements-inventory`) + `UNIFIED-PROGRAM-PLAN` + `DEFINITION-OF-DONE`, not memory.

## 1. What "AQ-OS refactor COMPLETE" actually means
The refactor = the **Local AI Factory reference architecture**, delivered as Cycles 0–6 (Foundations A–C,
Products D–G, cross-cutting Tracks V/S/F). "Complete" has a hard bar (`DEFINITION-OF-DONE`): every slice
must be **Integrated + Turned-ON + real-world-Validated + Observable + Intervenable + PM-tracked (live) + owner-ACCEPTED**, or
carry a written dated deferral. The program ENDPOINT is **Product G legacy retirement** — the old
system decommissioned after 2 clean cycles on the new one, at semver v1.0.

**The honest headline: 0 of 15 program items are ACCEPTED.** Most are 15–60% *integrated*; none has cleared
the full 6-dimension bar. So by our own definition, the refactor is early-middle, not near-done — and the
biggest systemic gap (below) is exactly why nothing is "accepted": most work isn't Observable/Intervenable yet.

## 2. Current honest state (the program map)
| Item | % (integration) | Status per unified plan |
|---|---|---|
| Foundation A — Cycle-0 truth exit | 100 | 10/10 authority rows owner-adjudicated (Q8 resolved); physical convergence is Cycle-1 execution under B2, not a pending decision |
| Foundation B1 — contract kernel + parity | 50 | **EXECUTING** (L1A/L2A/L2B-A landed; L2B-B unauthorized; chat/batch parity in shadow next) |
| Foundation B2 — one shadow-state vertical | (part of B) | B2-D0 accepted; B2-C1 authorization/review only |
| Foundation B3 — projector + canon-compiler | (part of B) | partial (aq-event projector live) |
| Foundation C — identity/leases/cells/net-profiles | 35 | C0/C1 shipped; C2 design is frozen but activation is blocked by the built-in-tool lease gap (not a pending Q3 decision) |
| Product D — inference/client live convergence | 20 | NOT STARTED; **closes the F2.5 dormant HIGH**; needs B1 parity + C boundaries |
| Product E — eval & learning factory | 15 | NOT STARTED; needs B2 evidence store + C integrity |
| Product F — one CLI (`aq <noun> <verb>`) + command center | 0 | NOT STARTED; needs authoritative telemetry from C/D |
| Product G — edge/release/retirement (v1.0) | 0 | NOT STARTED; needs everything prior; **the completion endpoint** |
| Track V — Verified Factory | 60 | amended VF contracts await exact-subject independent re-review; each accepted slice still needs explicit owner activation |
| Track S — Defensive Security | 15 | design + S0-A only; build pending an eligible lane |
| Track F — Flat collaborative factory | 45 | F1 done; F2 partial (F2.5 dormant→Product D); F3 = Foundation C |
| HERDR — operator observation surface | 22 | H0+H1 done (sealed/inert by design); H2 presentation = 0% |
| LEC — Local-Embed-Context | 75 | Slice 2b is blocked on the mechanically incomplete golden-fixture re-pin (two regressions), not on an owner decision |
| 20 HARD behavioral rules (governance) | 55 | written + partly gated; full enforcement audit pending |
| Agent parity | 45 | matrix exists; drift possible |
| Observability parity (every blank `--` is a bug) | 35 | partial |
| ACP — beginner-friendly human control | 60 | built, default-OFF/crypto-deferred; not activated |

## 3. The critical path (dependency order — this is the spine)
```
Foundation B1 (local-inference, EXECUTING)  ─┐
Foundation A physical convergence           ─┼─► Foundation C (identity/leases/cells)  [C2 blocker: built-in-tool lease source]
                                             │        │
                                             │        ▼
                                             └─► Product D (inference convergence, closes F2.5) [needs B1+C]
                                                      │
                                                      ▼
                                       Product E (eval factory) [needs B2+C]
                                                      │
                                                      ▼
                                       Product F (one CLI + command center) [needs C/D telemetry]
                                                      │
                                                      ▼
                                       Product G (edge/release/RETIREMENT = COMPLETE) [needs all]
```
Cross-cutting (run alongside, gate acceptance everywhere): Track V exact-subject independent review, Observability pillar, HARD-rule enforcement, agent parity. Any future activation remains an explicit owner decision per slice.

Owner-gate status is mechanically projected by `aq-refactor-status --machine`; the closed states are
`resolved`, `owner_decision`, `exact_activation`, and `dependency_blocked`. Tier0 rejects a rundown that
reintroduces a ratified direction as an unresolved owner gate. Both `owner_decision` and
`exact_activation` enter owner attention; dependency remediation remains visible without silently
blocking on the owner.

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
- **Foundation C** (identity/leases/cells/network-profiles) — the Q3 security direction is ratified. C2 remains
  blocked before activation until a first-party/built-in-tool lease source closes the fail-closed enforcement gap.
  Absorbs F3 + the WS9 core. The confinement spine.
- **Product D** (inference convergence: switchboard sole gateway, **activate the F2.5 scheduler**, route/profile
  registry) — needs B1 parity + C boundaries. This is the "one live inference path" and closes a standing HIGH.
- **Product E** (eval & learning factory) — Q7 is ratified; needs B2 + C.
- **Product F** (one CLI + typed command center) — Q6 is ratified; needs C/D telemetry (and the Observability
  pillar from §5.2 is its foundation).
- **Product G** (edge probes, install profiles, restore/upgrade drills, **v1.0 + legacy retirement**) = the
  completion endpoint.
- **Track V** — Q9 is ratified, but the amended VF contracts require exact-subject independent review before any
  per-slice owner activation. **Track S** build (defensive security) remains pending an eligible lane.
- **LEC Slice 2b** — re-pin the golden reliability fixture and clear its two regressions before binding acceptance.

## 7. Resolved program directions and remaining execution gates

All Q1–Q10 program directions are resolved and recorded in `ccc55ae9` / `aq-refactor-status --json`; they
are no longer queue blockers. This does **not** pre-authorize runtime, irreversible, or per-slice activation:
those remain explicit owner decisions after the relevant implementation, independent review, and activation
evidence are ready.

| Q | Resolved direction | Former gate |
|---|---|---|
| Q1–Q2 | Parent architecture and first shadow-vertical authority hypothesis | overall architecture / B2 |
| Q3 | Security model: leases, attestations, and zero-trust profiles | Foundation C |
| Q4 | Fable contract to model-neutral canon | B3 canon |
| Q5 | Measured, expiring lane-eligibility registry | delegation |
| Q6 | Kernel front-door direction | Product F |
| Q7 | Eval factory as universal promotion gate | Product E |
| Q8 | All ten Cycle-0 authority rows adjudicated | Foundation A |
| Q9 | Track V activation direction after VF-0 | Verified Factory |
| Q10 | 27 GB resident-small-model / speculative-decoding envelope direction | Product D/E |

Actual blockers now are: **C2's built-in-tool lease gap** (a flag-on enforcement would deny first-party
tools); **Track V's exact-subject independent review followed by per-slice activation**; and **LEC's golden
fixture re-pin** (its source manifest remains stale and produces two regressions).

## 8. Recommendation
Do §5 (the three START-NOW priorities) now — they're unblocked, and #2 (Observability) is the single highest-
leverage move because it converts a pile of "integrated-but-not-accepted" slices into acceptable ones AND is
the maturity multiplier for everything after. Then close **C2's built-in-tool lease gap** before requesting
its per-slice activation; Product D follows the B1+C spine. Products E/F/G follow in dependency order.
"Complete" = Product G retirement at v1.0 with
all 15 items owner-accepted — realistically several cycles out; this rundown makes the path explicit so no
thread is lost.
