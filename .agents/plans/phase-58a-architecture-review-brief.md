# Phase 58A Architecture Review Brief

## Why we paused

Before implementing the role-matrix SSOT, we stepped back to test whether the harness is reinforcing the right architecture at all. The immediate concern is that a correct-looking instruction-plane cleanup could still harden a structure that has not yet chosen its true kernel.

## High-level current architecture

The repo is best understood as four overlapping layers:

1. **Framework** — workflow DSLs, delegation, reviewer gates, routing contracts.
2. **Platform** — coordinator APIs, memory, hints, evals, dashboard, discovery.
3. **OS substrate** — NixOS modules, services, ports, secrets, hardware-aware deployment.
4. **Migration residue** — legacy local orchestrators, overlapping workflow models, duplicated prompt/profile sources.

The intended decomposition is sound:
- NixOS = deployment substrate
- coordinator = orchestration/control plane
- switchboard = profile execution proxy
- AIDB = knowledge service
- llama = inference runtime

## What the system is genuinely strong at

- Local-first and privacy-preserving by design.
- Declarative deployment and rollback through NixOS.
- Strong separation in principle between coordinator, switchboard, and runtime.
- Memory/learning/eval treated as product surfaces, not bolt-ons.
- Governance is unusually explicit: PRDs, slices, validation, handoff, review policy.

## Main architectural liabilities now visible

1. **Coordinator monolith risk** — the hybrid coordinator is becoming the platform kernel for too many concerns at once.
2. **Multiple object models** — workflow/session/orchestration concepts exist in several places with no single canonical lifecycle.
3. **Instruction and profile drift** — duplicated prompt/profile facts live in docs, Python, and Nix with conflicting values.
4. **OS/application entanglement** — Nix modules increasingly embed application policy and prompt behavior, not only deployment.
5. **Bypass paths and split-brain risk** — some tools use direct llama/repo-source paths while deployed services run from the Nix store.
6. **God-file and incomplete-boundary risk** — `http_server.py` remains a very large integration hub, and the `core/`, `workflow/`, and `extensions/` split is not yet an enforced architectural boundary.
7. **Research-surface bleed-through** — affective/identity/trading-style research features currently share process space with production routing concerns.
8. **Validation-system duplication** — shell-native gates and the newer registry-backed checks coexist without one clearly declared authority.

## Comparison against mature systems

### LangGraph / Microsoft Agent Framework
- They are stronger on explicit graph orchestration, checkpointing, durable execution, and human-in-the-loop workflow semantics.
- We are stronger on OS integration, local-first operation, and declarative machine management.
- Takeaway: keep our platform ambition, but make the workflow kernel more explicit and singular.

### OpenAI Agents SDK
- It is stronger on clean first-class concepts: agents, tools, handoffs, guardrails, tracing.
- We already have analogues, but they are more distributed and less canonical.
- Takeaway: define our own minimal kernel objects before adding more surfaces.

### AutoGen / CrewAI / LlamaIndex Workflows
- They are stronger on packaged collaboration patterns and developer ergonomics.
- We are solving a broader system problem: workstation + runtime + memory + governance.
- Takeaway: do not copy their breadth blindly; borrow clarity of abstraction.

### Temporal / Prefect-style durable workflows
- They are stronger on execution durability and replay semantics.
- We have workflow ambition, but not yet one durable workflow truth.
- Takeaway: choose whether durable workflow semantics are core, and if so centralize them rather than layering more ad hoc DAGs.

## Structural recommendations before further Phase 58A implementation

1. **Declare the canonical kernel before the role matrix.**
   - one routing model
   - one workflow/session model
   - one delegation/review model
   - one capability lifecycle model

2. **Defend the OS/application boundary.**
   - Nix should declare deployment, not evolving agent behavior.
   - Prompt/profile content should move toward versioned application data packaged by Nix, not authored inside Nix modules.

3. **Demote or retire adapter paths explicitly.**
   - local orchestrator, old workflow models, and compatibility wrappers should be marked canonical / adapter / legacy / retire.

4. **Unify instruction delivery rather than just instruction text.**
   - long-term target: generated or coordinator-compiled projections from one SSOT, not independently maintained markdown islands.

5. **Treat role-matrix work as part of kernel cleanup, not as a standalone docs task.**
   - the role matrix should be authored only after the canonical kernel and adapter boundaries are named.

6. **Freeze further `http_server.py` accretion unless a slice explicitly reduces coupling.**
   - prefer self-registering route modules or an equivalent registry pattern before new features continue to accumulate there.

7. **Make MemoryBroker the forward write path for new memory-bearing features.**
   - do not add more direct write paths while the memory model is being unified.

8. **Resolve baseline health before locking more contracts.**
   - the current `aq-qa 0` failures mean new architecture work would otherwise be written against a non-green baseline.

## Provisional decision

Do **not** jump straight into the earlier Slice 58A.1 exactly as written.

Instead, complete one small enabling hardening slice, then insert the architecture-contract pre-slice:

### 58A.x — Agent Tool Contract Hardening

Deliverables:
- canonical low-friction tool baseline,
- bounded fallback order,
- instruction/runtime allowlist alignment,
- reduced recurring tool-discovery waste before larger architecture work.

Then continue with:

### 58A.0 — Canonical Kernel Declaration

Deliverables:
- architecture decision record naming the canonical kernel objects,
- map of canonical vs adapter vs legacy components,
- boundary rule for NixOS substrate vs harness application,
- explicit consequences for the later role matrix and profile SSOT work,
- decision on which workflow/session abstraction is canonical,
- decision on whether research-only coordinator surfaces remain in-process or become opt-in side services,
- forward rule that new memory-capable work writes through the broker,
- baseline-health note identifying which pre-existing failures must be resolved before architecture contracts are considered enforceable.

**Draft artifact:** `docs/architecture/canonical-kernel-declaration.md`

Only after that should we implement:
- 58A.1 role matrix SSOT,
- 58A.2 profile/routing SSOT,
- 58A.3 instruction-plane projections.
