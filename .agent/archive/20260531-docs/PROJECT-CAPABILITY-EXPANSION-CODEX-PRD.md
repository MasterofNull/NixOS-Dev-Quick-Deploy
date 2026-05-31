# PRD — Codex Perspective: Capability Expansion Through an Instruction Plane

**Author:** Codex  
**Date:** 2026-05-18  
**Status:** Draft peer contribution to the team synthesis

---

## Problem

The harness does not mainly suffer from “too few tools.” It suffers from an incomplete **capability operating system**.

Several strong components already exist:

- good NixOS and Linux systems foundations,
- meaningful security infrastructure,
- a local/remote agent team,
- a canonical workflow,
- memory, delegation, validation, and hardware-promotion primitives.

But these components are not yet organized into a single reusable pattern for entering a new domain, understanding what is already available, creating what is missing, assigning the right agent, validating the result, and retaining the new capability for later reuse.

If we add GIS tools, firmware tools, scientific packages, and mobile SDKs before fixing that control plane, we will make the harness larger without making it much smarter.

---

## Thesis

The next capability leap should be **instruction-plane first, domain expansion second**.

The system should learn one durable pattern:

1. classify the domain,
2. activate the right instructions, tools, knowledge, and safety posture,
3. inspect available capabilities,
4. create missing pieces through a bounded workflow,
5. validate them,
6. promote them only when evidence is sufficient,
7. expose them through operator and agent surfaces.

Once that exists, adding GIS or firmware is not a bespoke project every time; it is a new instance of a known lifecycle.

---

## Goals

1. Establish one canonical instruction and routing plane for all agents.
2. Make capabilities first-class, lifecycle-managed objects rather than scattered packages and docs.
3. Make domain activation cheap, explicit, and inspectable.
4. Preserve local-first behavior without overloading the local agent.
5. Ensure risky or low-confidence outputs are review-gated before implementation.
6. Enable future domains to be added by configuration and templates more often than by bespoke orchestration code.

---

## What Must Exist Before Broad Domain Expansion

### 1. Canonical role model

| Role | Default owner |
|---|---|
| Orchestrator / integration reviewer | Codex |
| Architect / policy / high-risk reviewer | Claude |
| Research synthesizer | Gemini |
| Bounded local executor | Qwen local |

This must be written once and projected everywhere, not redefined differently by each agent-specific file.

### 2. Canonical profile and routing model

The repo currently shows drift between docs, config, and runtime profile definitions. Before adding six new domains, there must be one profile inventory and one alias map that every surface reads from or is validated against.

### 3. Capability lifecycle registry

Each major capability should record:

- domain,
- lifecycle state,
- available tools,
- required knowledge,
- validation evidence,
- operator surface,
- rollback surface,
- owner / reviewer policy.

### 4. Domain activation contract

Domain activation should load only what is relevant:

- domain instructions,
- preferred tools,
- AIDB namespaces,
- safety rules,
- validation checks,
- routing hints.

This prevents context bloat while giving agents the right local worldview for the task.

### 5. Review and trust boundaries

- Gemini may propose; Claude or Codex must approve before implementation or commit.
- Qwen may assist; it should not own open-ended planning, architecture, or final acceptance.
- Destructive hardware, dual-use security, and external-account operations remain approval-gated.

---

## Design Principles

1. **Fewer hidden heuristics, more declarative contracts.**
2. **Generate projections; do not hand-maintain conflicting instruction copies.**
3. **Prefer templates over one-off integrations.**
4. **The dashboard should reveal state, not silently become the source of truth.**
5. **Validation should be path-aware, not universally expensive.**
6. **Every expansion should leave the next expansion cheaper.**

---

## Recommended First Three Domain Probes

I would not begin with the strongest current domains. I would begin with the domains that most stress the extension model:

1. **GIS** — almost absent today; proves end-to-end domain bootstrapping.
2. **Embedded / firmware** — tests toolchains, safety boundaries, datasheet ingestion, hardware-aware workflows.
3. **Scientific research** — tests reproducibility, literature ingestion, datasets, and report generation.

If the foundation can absorb those three cleanly, mobile/web and security productization become easier rather than harder.

---

## Non-Goals

- Installing every plausible tool in the default environment.
- Treating “more local” as automatically better.
- Duplicating workflow logic for each domain.
- Letting agent-specific prompt files become new drifting SSOTs.
- Shipping domain breadth before the review, validation, and lifecycle machinery exists.

---

## Acceptance Criteria

1. A new domain can be added from a standard template without inventing a new orchestration model.
2. Agent role guidance is consistent across active surfaces.
3. Runtime routing and documentation refer to the same profile model.
4. Gemini review requirements are enforceable, not merely advisory.
5. Qwen task eligibility is machine-checkable.
6. The system can distinguish:
   - available now,
   - build when missing,
   - candidate,
   - promoted,
   - blocked / retired.
7. The first probe domain can be brought online with:
   - dev shell,
   - memory namespace,
   - activation payload,
   - smoke test,
   - rollback note,
   - operator visibility.

---

## Recommended Sequence

1. Instruction-plane convergence
2. Capability registry and lifecycle
3. Domain activation / gap-resolution contracts
4. Review-gate enforcement
5. GIS pilot
6. Embedded / firmware pilot
7. Scientific research pilot
8. Second-wave domains and cross-domain evaluation

---

## Why This Matters

The user’s real goal is not six disconnected specialty environments. It is a harness that can keep becoming whatever it needs to become without losing safety, memory, or coherence. The architecture should optimize for that compounding property.

