# Phase 58A — Team Synthesis Plan

## Objective

Establish the shared control-plane foundation required before broad multi-domain expansion:

- one canonical agent role model,
- one authoritative routing/profile inventory,
- explicit Gemini and Qwen trust boundaries,
- one capability lifecycle schema,
- one reusable domain-activation template.

This phase intentionally prepares the system to add capabilities well before it tries to add every capability at once.

## Inputs Considered

- `.agent/PROJECT-CAPABILITY-EXPANSION-MASTER-PRD.md`
- `.agent/PROJECT-CAPABILITY-EXPANSION-CODEX-PRD.md`
- Claude capability-expansion PRD perspective
- Gemini capability-expansion PRD and Phase 58A plan perspectives
- Codex repo explorers on:
  - current capability inventory,
  - instruction-plane drift,
  - reusable prior-PRD themes

## Team Consensus

The agents converge on five points:

1. **Role and instruction drift must be fixed first.**
2. **Gemini requires an explicit review gate, not just guidance prose.**
3. **Qwen should remain bounded and local-first, not overloaded.**
4. **Capabilities need lifecycle state and evidence, not package sprawl.**
5. **Future domains should instantiate a standard pattern instead of inventing new orchestration every time.**

## Workstreams

### 1. Instruction-plane convergence
- Canonical role matrix
- Generated-vs-hand-authored instruction-surface policy
- First-class Codex instructions
- Cleanup plan for stale Claude/Gemini/Qwen/local-orchestrator guidance

### 2. Routing and profile normalization
- One authoritative lane/profile inventory
- Role → lane → profile mapping
- Reconcile docs, config, generated client surfaces, and active runtime behavior

### 3. Trust and review boundaries
- Gemini review-gate contract and enforcement point
- Qwen bounded-task eligibility contract
- Approval-gated categories for destructive, dual-use, and external-account work

### 4. Capability lifecycle model
- State machine
- Evidence requirements
- Runtime / operator / validation / rollback surfaces
- Registry shape for available / missing / candidate / promoted / blocked

### 5. Domain activation pattern
- Domain tag schema
- Instruction payload
- Tool preferences
- AIDB namespace binding
- Validation hook template

## Recommended Ordered Slices

| Slice | Purpose | Primary owner | Review |
|---|---|---|---|
| 58A.x | Agent tool contract hardening and runtime/doc alignment | Codex | Claude |
| 58A.0 | Canonical kernel declaration + canonical/adapter/legacy map | Codex + Claude | Codex final |
| 58A.1 | Canonical role matrix SSOT | Codex | Claude |
| 58A.2 | Active routing/profile inventory and drift report | Codex | Claude |
| 58A.3 | Codex first-class instruction surface | Codex | Claude |
| 58A.4 | Gemini review-gate contract | Claude + Codex | Codex final |
| 58A.5 | Qwen bounded-task eligibility contract | Codex | Claude |
| 58A.6 | Capability lifecycle schema | Claude + Codex | Codex final |
| 58A.7 | Domain activation template | Gemini proposal, Codex/Claude review | Codex final |

## Agent Responsibilities

### Codex
Own:
- orchestration,
- decomposition,
- SSOT integration,
- routing consistency,
- final acceptance.

Do not own:
- long-form architecture in isolation when Claude should review it,
- unreviewed Gemini implementation,
- routine low-value local checks.

### Claude
Own:
- architecture,
- policy/risk synthesis,
- review of role model, lifecycle, and trust boundaries.

Do not own:
- broad slice orchestration or final repo integration alone.

### Gemini
Own:
- research synthesis,
- candidate proposals,
- comparative option analysis,
- domain activation ideas.

Do not own:
- unreviewed implementation,
- direct commit authority,
- final acceptance.

### Qwen local
Own:
- bounded inventories,
- small validation helpers,
- simple template checks,
- compact summaries.

Do not own:
- open-ended architecture,
- large-context synthesis,
- cross-file policy decisions,
- final acceptance.

## Dependencies

- `.agent/WORKFLOW-CANON.md` remains the workflow SSOT.
- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` defines the low-friction tool baseline agents should use before broader capability expansion.
- Existing Gemini hardening work remains active.
- Existing local-agent coding work remains bounded and evidence-based.
- Routing/profile reconciliation should happen before generating new agent instructions from stale assumptions.

## Risks

| Risk | Mitigation |
|---|---|
| Planning turns into doc churn | Every slice must unlock a future machine-checkable behavior |
| Stale runtime facts leak into new docs | Inspect active runtime/config before writing projection docs |
| Review gate becomes ceremonial | Define artifact, enforcement point, and failure mode |
| Qwen is either underused or overtrusted | Define explicit task classes and promotion path |
| Profile SSOT becomes another duplicate | Make drift detection part of validation |

## Validation

Phase 58A is complete when:

1. every active agent surface refers to the same role model,
2. docs/config/runtime agree on active lanes and profile semantics,
3. Codex has an explicit instruction home,
4. Gemini review policy is concrete enough to implement,
5. Qwen bounded-task eligibility is explicit and testable,
6. the lifecycle schema can represent at least:
   - proposed,
   - implemented,
   - validated,
   - candidate,
   - promoted,
   - default,
   - superseded / retired,
7. a future domain can be described from a standard template rather than bespoke prose.

## Recommended First Implementation Delegation

### Slice 58A.x — Agent tool contract hardening

**Why first:** recent Gemini friction exposed that docs and runtime allowlists disagree about the default tool surface. This is a small enabling slice that removes repeated token waste before the architecture-contract work continues.

**Expected outputs**
- canonical tool-contract guide,
- aligned instruction text,
- aligned default runtime allowlists,
- explicit return to `58A.0` afterward.

### Slice 58A.0 — Canonical kernel declaration

**Why first:** the architecture review showed that role text is downstream of a more fundamental choice: what the canonical kernel actually is. We should not project roles, profiles, or instruction surfaces from a model that still has unresolved overlaps in workflow, delegation, routing, and OS/application boundaries.

**Current draft artifact**
- `docs/architecture/canonical-kernel-declaration.md`

**Likely files / surfaces to inspect before editing**
- `docs/AGENTS.md`
- `AGENTS.md`
- `.agent/WORKFLOW-CANON.md`
- `.agent/GEMINI.md`
- `.qwen/SESSION-RULES.md`
- `.qwen/settings.json`
- `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`
- `ai-stack/local-orchestrator/system-prompt*.md`
- switchboard profile definitions
- `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
- `docs/architecture/front-door-routing.md`
- workflow/session implementations under `ai-stack/`
- coordinator route/module topology
- `nix/modules/roles/ai-stack.nix`
- `nix/modules/services/switchboard.nix`

**Proposed split**
- Codex: inventory + synthesis + final patch
- Claude: architecture review of the canonical kernel, module boundaries, and retirement map
- Gemini: research/proposal only if needed
- Qwen: no role in this slice beyond optional bounded file inventory

## Rollback

- Keep early slices additive and contract-focused.
- Do not mutate runtime behavior until the contract and drift report are accepted.
- If live runtime contradicts docs, record the contradiction before changing projections.
