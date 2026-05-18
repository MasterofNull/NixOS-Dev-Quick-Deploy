# Canonical Kernel Declaration

**Status:** Accepted — Phase 58A.0 (2026-05-18)
**Stability:** Kernel objects below are frozen for Phase 58A. Changes require a named kernel-revision slice; downstream slices (58A.1–58A.7) may not redefine them unilaterally.
**Purpose:** Name the harness kernel before the project hardens additional role, profile, and instruction surfaces.

## Decision

The canonical harness kernel is **not** a specific model, prompt file, CLI wrapper, or NixOS module. It is the smallest set of control-plane concepts that must remain coherent across every agent lane:

1. **Intent** — what kind of work is being requested.
2. **Route / execution profile** — how that intent is executed and under which policy.
3. **Workflow session** — the resumable unit of planned work, evidence, and state transition.
4. **Delegation / review** — who may act, who must review, and what artifact closes the loop.
5. **Memory / evidence** — what the system remembers, how it is retrieved, and what proves a decision or capability is valid.

Everything else should either support these kernel objects, adapt external callers into them, or be explicitly marked as legacy/research-only.

## Canonical architecture model

### 1. Intent is upstream of routing

The front door should accept human-meaningful intent and resolve that into execution policy. Current route aliases already gesture in this direction; future work should make the mapping singular and explicit rather than letting task semantics fragment across wrappers, prompts, and profile docs.

### 2. The coordinator is the control plane

The **hybrid-coordinator** is the canonical orchestration/control-plane service. It owns:
- workflow/session state,
- hints and context enrichment,
- memory-facing decisions,
- delegation/review policy,
- routing metadata and evidence collection.

It may call the switchboard for model execution, but the switchboard is **not** the orchestrator.

### 3. The switchboard is the execution-profile plane

The **switchboard** is the canonical model-execution proxy. It owns provider/profile execution behavior, not workflow truth. It should receive already-declared routing intent/profile context from the control plane whenever the request is orchestrated work.

### 4. NixOS is the substrate, not the product brain

NixOS remains the canonical deployment substrate:
- services,
- secrets wiring,
- ports,
- packages,
- hardware-aware defaults,
- rollback and reproducibility.

Application behavior such as evolving prompt text, role policy, or orchestration semantics should be authored as versioned harness data and packaged by Nix, not progressively embedded into Nix modules as the primary source of truth.

### 5. Memory writes converge through the broker

New memory-bearing work should write through the brokered memory path rather than creating additional direct-store islands. Existing alternate paths may remain temporarily, but new development should reduce rather than increase write-path fragmentation.

### 6. Research surfaces remain in-process under monitoring (provisional)

The affective / identity / trading-style coordinator extensions are **not** being moved to separate services in Phase 58A. They remain in-process but are explicitly labelled research-only and must not be called from canonical routing paths. If a future slice adds new research surfaces, it must justify in-process residency; the default for new experimental work is a separate opt-in service.

### 7. Baseline health and enforcement threshold

As of 2026-05-18, `aq-qa 0` reports **2 failures** against the full 63-check suite. Forward rules in this document are **aspirational, not enforceable** until those failures are resolved and the baseline is green. Slices that target the failed surfaces must fix the failures before marking acceptance criteria met.

## Canonical object model

| Object | Canonical meaning | Current anchor |
|---|---|---|
| Intent | semantic task class / requested work type | front-door aliases, task classifiers |
| Route profile | execution policy chosen for an intent | switchboard profiles + routing contract |
| Workflow session | resumable unit of planned work and state | `WorkflowExecutor` + `workflow_checkpointer.py` (runtime); `LifecycleSession`/FSM (agent lifecycle only) |
| Delegation | bounded assignment from orchestrator to actor | delegation handlers + scripts |
| Review | acceptance gate over delegated or generated work | reviewer policy + handoff artifacts |
| Memory evidence | persisted context plus validation trail | memory broker / AIDB / collaboration artifacts |

## Component classification

### Canonical

| Surface | Why canonical |
|---|---|
| `hybrid-coordinator` | orchestration/control-plane authority |
| `switchboard` | execution-profile authority |
| `AIDB` + brokered memory surfaces | knowledge/memory authority |
| `.agent/WORKFLOW-CANON.md` | workflow contract SSOT until instruction compilation is centralized |
| `nix/modules/core/options.nix` | port/deployment option SSOT |

### Adapters

| Surface | Why adapter |
|---|---|
| `scripts/ai/local-orchestrator` | CLI front door into coordinator behavior |
| `delegate-to-*` scripts | external-agent ingress / audit bridge |
| generated agent instruction projections | model-specific views over shared rules |
| IDE/editor direct lanes | alternate ingress into switchboard execution |

### Legacy / transitional

| Surface | Why transitional |
|---|---|
| duplicate workflow/session models | overlap pending consolidation |
| independently maintained instruction islands | drift risk until generation is centralized |
| older local-orchestrator implementation paths | compatibility, not authority |
| duplicated coordinator modules outside the intended split | retirement/refactor candidates |

### Research-only or opt-in

| Surface | Why not kernel |
|---|---|
| affective / identity / trading-style coordinator extensions | valuable experiments but not required for baseline harness correctness |
| optional experimental learning loops | may inform future kernel evolution but must not define today's minimum contract |

## Forward rules

1. **One routing story:** front-door intent resolves into one canonical routing/profile model; wrappers may adapt, not redefine it.
2. **One workflow story:** new resumable work should target the chosen workflow/session abstraction rather than minting parallel lifecycle systems.
3. **One delegation story:** agent roles, review gates, and handoff artifacts must point back to the same delegation/review model. The canonical protocol is coordinator `POST /workflow/graph/run` (or equivalent workflow-session entry) plus a handoff artifact committed to `.agent/collaboration/`. The `delegate-to-*` scripts are adapters into this protocol, not the protocol itself.
4. **One memory write path for new work:** favor broker-mediated writes and record exceptions explicitly.
5. **Thin substrate boundary:** Nix packages and deploys the application; it should not become the editing surface for fast-changing behavioral policy.
6. **No silent accretion:** new work that enlarges `http_server.py` or duplicates kernel concepts must justify why it cannot land behind a declared module boundary.

## Consequences for later Phase 58A slices

### 58A.1 — role matrix
Roles should be derived from kernel responsibilities:
- orchestrator = workflow/delegation/review authority,
- architect = design/risk synthesis,
- implementer = bounded execution actor,
- reviewer = acceptance gate,
not from model branding alone.

### 58A.2 — routing/profile inventory
The inventory should distinguish:
- human-facing intent alias,
- canonical profile,
- provider/model realization,
- adapter surface,
instead of treating those as interchangeable labels.

### 58A.3 — instruction projections
Instruction surfaces should become generated views of kernel policy where practical. The goal is not identical prose everywhere; it is one underlying contract with lane-specific projection.

## Open decisions still requiring later work

1. **Workflow/session lifecycle authority (provisional decision required for 58A.1).**
   Current candidates:
   - `WorkflowExecutor` + `workflow_checkpointer.py` in the coordinator (DAG + DLQ, Phase 54) — strongest durable semantics.
   - `LifecycleSession` / `lifecycle_fsm.py` UAG FSM (Phase 26/37) — agent lifecycle focus, not general workflow.
   - Ad hoc phase-plan DAGs in `.agents/plans/` — planning artifacts only, not runtime state.
   **Provisional:** `WorkflowExecutor` + `workflow_checkpointer.py` is the canonical workflow runtime. The UAG FSM is canonical for agent lifecycle only. Ad hoc DAG plans remain planning artifacts and are not runtime authority. This must be confirmed in 58A.1 before the role matrix cites "workflow authority."

2. Which legacy coordinator paths to retire, merge, or keep as adapter-only (58A.2 drift report will enumerate these).

3. Research-surface containment: resolved provisionally in §6 above (in-process, monitored, gated from canonical paths).

4. How instruction compilation should be centralized without overloading the local-agent lane (target for 58A.3).

5. Baseline health: resolved in §7 above — 2 aq-qa failures; enforcement deferred until green.

## Summary

The harness should evolve as a **local-first agent operating platform with a small explicit kernel**, not as an ever-growing collection of adjacent clever features. The immediate task is therefore architectural convergence: make intent, routing, workflow, delegation, and memory agree before adding more domains on top.
