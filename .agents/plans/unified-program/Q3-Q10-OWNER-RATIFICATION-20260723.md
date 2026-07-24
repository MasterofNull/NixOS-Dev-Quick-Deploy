# Owner Ratification — Q3–Q10 (Unified Program decision gate)

**Date:** 2026-07-23. **Owner:** hyperd (direct ratification this session).
**Recorded by:** fable-5 (orchestrator). **Basis:** `OWNER-DECISION-SHEET.md`
recommendations, put to the owner and answered. This CLEARS the Q3–Q10 owner-decision
gate — the refactor's remaining Foundation/Product slices are no longer blocked on
owner input (they still follow per-slice design → review → hash-bound authorization →
activation, but the DIRECTION for each is now ratified).

Q1/Q2 ratified 2026-07-18; Q8 (Cycle-0 authority rows) adjudicated 2026-07-18.

## Ratified decisions

**Q3 — Security model (→ Foundation C).** APPROVED the zero-trust direction now:
principal attestations + CapabilityLease, **no fail-open modes**. The exact network-
profile list (the eight connected-zero-trust profiles) is ratified at Foundation C
planning after its own dedicated threat pass. Foundation C is UNBLOCKED to begin
design on this direction; the profile list is a bounded sub-decision inside C.

**Q4 — Behavior canon (→ B3).** APPROVED converting the Fable-parity behavior
contract into a **model-neutral, versioned canon behavior policy** — same content,
no per-model naming — then absorbed into the B3 canon compiler. Rename/relocate is
a mechanical migration; behavior semantics unchanged.

**Q5 — Lane-eligibility registry (→ all delegation; VF-8 feeds it).** APPROVED a
**measured, expiring lane-eligibility registry** (roles stay model-neutral;
eligibility is earned by evidence, not vendor default), with seed rows:
- codex = orchestrator / implementer / reviewer
- opus = bounded implementer
- **antigravity = research / review only, implementation-INELIGIBLE until measured
  promotion** (consistent with 2026-07-23 finding — [[feedback-antigravity-untrusted-advisory]])
- local = measured envelope
VF-8 promotion evidence updates the registry; entries expire and must be re-earned.

**Q6 — Kernel front door (→ Product F).** KEEP the `local-orchestrator` declaration;
the frozen front-door surface stays frozen. Any move toward an `aq` gateway requires
an explicit **named kernel revision**, revisited only when Product F (CLI/command
center) work starts.

**Q7 — Eval-gated promotion (→ Product E).** APPROVED as principle: eval-gated
promotion is the **universal change mechanism** for models, prompts, profiles,
policies, tools, scorers, and datasets. Concrete mechanics (golden-task bank,
certified scorers, promotion ledger — VF-4/5/8) land in Product E.

**Q9 — Track V / Verified Factory.** REVIEW the amended VF contracts (bounded
independent review), THEN authorize **per exact slice** after each slice's
prerequisites pass (VF-1/VF-3 authority + L2B sequencing). Not a blanket activation —
Track V slices remain hash-bound, interleaving T0/T1 only.

**Q10 — Inference envelope (→ Product D/E stacking).** MEASURE FIRST on the real
hardware, then improve the current system — AND keep the system **hardware-agnostic
so it adapts to deployments with differing hardware** (owner words: "measure first
and make improvements to the current system, but also leave our system able to adapt
to new deployments with differing levels of system hardware"). So: measure resident-
small-model and speculative-decoding economics (RAM/VRAM/latency) on the 27 GB
target before committing to one, both, or deferral; NEVER assume one quant step funds
two concurrent capabilities; every stacking choice must degrade gracefully across
hardware tiers (see [[feedback-hardware-agnostic-slow-steady-local]]). No fixed
27 GB assumption baked into the architecture.

## What this unblocks (per-slice work still hash-bound)
- **Foundation C** — design on the Q3 direction (leases/principals/cells); profile
  list ratified within C.
- **B3 canon** — the Q4 model-neutral behavior-policy migration + canon compiler.
- **Delegation everywhere** — the Q5 lane-eligibility registry (a real slice: build
  the measured/expiring registry; seed rows above).
- **Product E** — eval-gated promotion as the Q7 universal gate.
- **Track V** — per Q9, review amendments then per-slice authorize.
- **Product D/E stacking** — the Q10 measurement pass first.

**Status: Q1–Q10 all resolved.** The owner-decision gate is closed; the refactor is
no longer gated on owner input. Next actionable non-gated slice: the Q5 lane-
eligibility registry (pure infra, seeds ratified) and the Q10 measurement pass.
