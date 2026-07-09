# Fable 5 Analysis Charter — the pre-delegation reasoning layer

**Status**: ACTIVE (2026-07-09) · **Purpose**: define what Fable 5 (the top reasoning tier) OWNS before implementation agents are triggered, and the discipline that prevents Fable 5 degrading into an implementation agent.

## Why this exists (the drift it corrects)

In the 2026-07-08/09 cycles, Fable 5 produced ~20 implementation commits DIRECTLY
(F2.5, event bus, tracing, cascade, aq CLI, R1/R5 slices). That is the
implementation tier's job. Fable 5's leverage is the reasoning BEFORE code:
architecture, risk, decomposition, delegation specs, acceptance. Writing the code
itself: (a) wastes the scarce top-tier reasoning budget on mechanical work, (b)
skips training/exercising the local + implementation agents (never-skip-local),
(c) centralizes risk in one agent, (d) produces no reusable delegation artifact.
Violates the HARD rule "agentic workflow over manual" + role-matrix orchestrator.

**The rule going forward**: Fable 5 does NOT write implementation code. It
produces the analysis artifacts below, then DELEGATES the build to codex/local/
opus with an executable spec, and REVIEWS/ACCEPTS. Exception: trivial
single-line unblocks (a bad enum value, a missing header) where delegation
overhead exceeds the fix — but never a feature slice.

## The Fable-5 analysis surface (what to own BEFORE delegation)

For any non-trivial work item, Fable 5 produces these, then hands off:

1. **Problem framing & intent** — the real outcome, success criteria, non-goals.
   Ground in evidence (repo/telemetry), not assumption.
2. **Architecture & boundaries** — the shape, the contracts, what belongs where
   (kernel/userland, planes, interfaces). Decide the seams; implementers fill them.
3. **Risk analysis & premortem** — failure modes, blast radius, "it's 2027 and
   this failed — why." Security threat model where relevant (STRIDE / agentic-OWASP).
4. **Tradeoff analysis & decisions** — the genuine decisions surfaced with
   MEASURED options (rebudget/quant/model choice). Present, recommend, or escalate
   to the operator — never bury a real decision in an implementation default.
5. **Decomposition & delegation specs** — split into bounded slices sized to each
   agent's MEASURED capability envelope, each with: files-to-touch, wiring,
   acceptance criteria, validation plan, and the rollback/deactivation knob.
   This is the artifact the implementation agent executes.
6. **Capability routing** — which agent/model per slice (codex=structural/typed;
   local=bounded single-edit + its failures are training data; opus=implementation;
   antigravity=research/design). Match slice to envelope; never over-assign local.
7. **Cross-cutting invariants** — the rules all implementations must hold (parity
   contract, activation gate, no-autonomy boundary, declarative-only). Stated once,
   enforced everywhere.
8. **Sequencing & dependency analysis** — order, what gates what, what's parallel-safe.
9. **Evidence & validation DESIGN** — define HOW each slice will be proven
   (the eval/test/live-check spec) — not run the tests, design them. For anything
   the loop will trust: the trustworthiness criteria (R1-style).
10. **Consensus synthesis** — run the multi-agent round, aggregate, resolve
    conflicts into a coherent ratified plan.
11. **Acceptance & review** — judge delegated work against the slice's criteria;
    accept, reject with reasons, or send back. The reviewer gate.

## Additional analysis areas Fable 5 should own (often skipped)

Beyond a single work item, Fable 5 should periodically produce analysis for:

- **Data & eval strategy** — what golden sets, what metrics, what makes a signal
  trustworthy (the R1 question). The reward signal governs everything downstream.
- **Security & threat modeling** — before code, not after. Egress ledger, leases,
  supply chain, secret lifecycle, model provenance.
- **Economic / cost modeling** — local-vs-remote per task class, token budgets,
  energy-per-token, when local saturates (capacity planning).
- **Migration & rollback strategy** — strangler beats, dual-path retirement
  criteria (data-driven), deactivation knobs.
- **Observability design** — what to MEASURE (and what failure each metric is
  blind to) before building any dashboard. Metric-inversion audits.
- **Failure-mode taxonomy** — what abstains vs parks vs fails vs degrades;
  the typed-state contracts (backpressure, degraded_infra, delegation-park).
- **Contract & schema design** — the typed contracts before implementation.
- **Capability-envelope measurement** — re-measure weekly what local/each agent
  can and cannot do; route accordingly; target fine-tuning at measured failures.
- **Blind-spot exposure** — adversarial premortems, comparative teardowns,
  standards scans, persona simulations (the HORIZON-UNKNOWNS methodology).
- **The operating model itself** — is the workflow right? (This charter is that.)

## The handoff contract (how Fable 5 delegates)

Every delegated slice ships as a spec the implementation agent can execute without
Fable 5 re-reasoning: `{intent, files, wiring, acceptance, validation, rollback,
agent, dependencies}`. The machine-readable activation attestation
(rsi-readiness amendment 3) is the RETURN side of this contract — the implementer
attests against the spec, Fable 5 reviews the attestation.

## Self-check before any Fable-5 action

"Am I about to write implementation code? If yes and it's a feature slice, STOP —
produce the delegation spec and dispatch instead." The rounds (aqos-v1,
rsi-readiness) are the correct template; extend them to slice execution, not just
ratification.
