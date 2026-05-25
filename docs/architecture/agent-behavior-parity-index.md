# Agent Behavior Parity Index

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-25

## Purpose

This is the front-door index for agent behavior, instruction, routing, and parity work. Agents should read this before loading broad historical PRDs or old phase plans.

The repo contains many valid historical plans. They are useful as evidence, but they are not all current operating authority. This index separates active authority from reference material so agents do not drift by following stale documents.

## Read Order

1. `docs/architecture/role-matrix.md`
   - Canonical role authority for Codex, Claude, Gemini, Qwen/local, and any future agent.
   - Governs what each role may do, must do, and may not do.

2. `docs/architecture/routing-profile-inventory.md`
   - Canonical routing/profile drift report.
   - Governs profile names, route aliases, known routing drift, and routing cleanup priorities.

3. `.agents/plans/phase-58a-instruction-projections.md`
   - Current record of instruction projection work.
   - Use it to understand which agent surfaces were aligned and which follow-ups remain.

4. `.agents/plans/phase-58a-agent-tool-contract.md`
   - Tool-surface hardening plan.
   - Use it with `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` when changing agent tool behavior.

5. `.agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md`
   - Current parity implementation bridge.
   - Use it to map MAEAH parity work onto concrete Phase 60-63 slices.

6. `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md`
   - Comprehensive MAEAH vision and requirements.
   - Treat as strategic product authority, not a direct implementation task list.

## Active Authority

| Surface | Authority |
|---|---|
| Agent roles | `docs/architecture/role-matrix.md` |
| Routing/profile semantics | `docs/architecture/routing-profile-inventory.md` |
| Kernel boundaries | `docs/architecture/canonical-kernel-declaration.md` |
| Tool selection baseline | `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` |
| Workflow steps | `.agent/WORKFLOW-CANON.md` |
| Capability lifecycle | `docs/architecture/capability-lifecycle.md` |
| Domain activation | `docs/architecture/domain-activation-template.md` |
| Cross-surface visibility | `docs/architecture/cross-surface-change-contract.md` |
| Document lifecycle hygiene | `docs/operations/document-lifecycle-hygiene.md` |

If another document conflicts with these surfaces, use the active authority and record the conflict in the current plan or handoff.

## Reference Material

The following documents remain important but should not be loaded first for day-to-day agent behavior work:

| Surface | Use |
|---|---|
| `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md` | Strategic MAEAH product/runtime vision |
| `.agents/plans/multi-agent-edge-harness/AGENT-PARITY-REVIEW.md` | Team review notes and parity amendment rationale |
| `.agent/PROJECT-CAPABILITY-EXPANSION-MASTER-PRD.md` | Capability expansion problem statement and domain model |
| `.agents/plans/phase-58-capability-expansion-foundation.md` | Foundation planning context |
| `.agents/plans/phase-58a-capability-expansion-team-plan.md` | Team synthesis and recommended slice order |

When using reference material, quote or summarize only the section needed for the current slice.

## Operational Rules

1. Prefer this index over broad `rg PRD` or loading whole plan directories.
2. Treat `Status: Active` docs as current operating guidance.
3. Treat `Status: Reference` docs as historical evidence or rationale.
4. Treat `Status: Superseded` docs as pointers only; follow their `Superseded-By` target.
5. Treat `Status: Archived` docs as cold history. Do not implement from them without revalidating against active authority.
6. Every new PRD or plan must declare its lifecycle state and owner near the top.
7. Every completed PRD or plan must either be collapsed to an index entry, marked reference/superseded, or moved under an archive path with a pointer.

## Current Priority Work

| Priority | Work | Current status |
|---|---|---|
| P0 | Keep local-agent tool context bounded without blocking long work | Active; switchboard active tool lease and `lease_tools` broker are implemented |
| P0 | Enforce role and routing SSOTs across agent surfaces | Active; needs drift check expansion beyond current projection docs |
| P1 | Runtime bounded delegation envelopes for agent identity/delegation | Partial per `PARITY-INTEGRATION-PLAN.md` |
| P1 | MCP tool-boundary profile enforcement | Partial per `PARITY-INTEGRATION-PLAN.md` |
| P1 | Trace path view: prompt -> route -> memory -> tools -> response -> review | Partial per `PARITY-INTEGRATION-PLAN.md` |
| P2 | Historical PRD/plan retirement and archive hygiene | Active; governed by `docs/operations/document-lifecycle-hygiene.md` |

