# Canonical Role Matrix

**Status:** Accepted — Phase 58A.1 (2026-05-18)
**Upstream authority:** `docs/architecture/canonical-kernel-declaration.md`
**Stability:** Roles below are derived from kernel responsibilities and are frozen for Phase 58A. Changes require a named role-revision slice; instruction projections generated from this document may not extend role authorities unilaterally.

## Purpose

This document is the single source of truth (SSOT) for agent roles in the harness. Every agent instruction surface — CLAUDE.md, GEMINI.md, SESSION-RULES.md, AIDER.md, generated projections — must derive role text from this document, not invent it independently.

Roles are defined by their authority and constraints over the five kernel objects (intent, route/execution profile, workflow session, delegation/review, memory/evidence). They are not defined by which model currently fills them.

---

## Role Definitions

### orchestrator

**Kernel authority:** workflow/delegation/review

| Dimension | Detail |
|---|---|
| **May** | open and close workflow sessions; assign slices to implementers; accept or reject delegated work; produce final commit after review; run tier0 validation gate; escalate to architect for design questions |
| **Must** | maintain `.agent/collaboration/PENDING.json` intent lock before complex multi-file operations; produce `.agent/collaboration/HANDOFF.md` at slice close; run `scripts/governance/tier0-validation-gate.sh --pre-commit` before every commit |
| **May not** | bypass review for destructive, dual-use, or external-account-affecting work; re-delegate without updating `.agents/delegation/registry.jsonl`; accept its own work without a separate reviewer pass |
| **Escalation trigger** | design question → architect; destructive action → explicit user confirmation |

---

### architect

**Kernel authority:** design/risk synthesis over all kernel objects

| Dimension | Detail |
|---|---|
| **May** | draft and revise architecture documents; propose kernel object changes; write PRDs; flag risk or contradiction; reject a slice plan that contradicts the kernel declaration |
| **Must** | cite upstream authority (kernel declaration, WORKFLOW-CANON) in every architectural artifact; flag contradictions rather than silently overriding them; produce a risk note for any proposal that changes kernel objects or forward rules |
| **May not** | commit architecture changes without orchestrator review and acceptance; unilaterally redefine kernel objects; propose scope outside the declared slice |
| **Escalation trigger** | kernel object change → requires a named kernel-revision slice (not inline edit) |

---

### implementer

**Kernel authority:** bounded execution within an assigned slice

| Dimension | Detail |
|---|---|
| **May** | read and edit files within the declared slice scope; run tests and validators; write to `.agents/scratchpad/`; write `.agent/collaboration/PULSE.log` atomic pulses; propose a commit with validation evidence |
| **Must** | operate strictly within declared slice scope; validate (`bash -n`, `py_compile`, tier0 gate) before proposing a commit; document assumptions in PULSE.log; stay within assigned tool surface (see `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`) |
| **May not** | re-scope goals beyond the assigned slice; route or assign other agents; finalize acceptance of its own work; commit directly without an orchestrator or reviewer gate; add new kernel concepts without an architect slice |
| **Escalation trigger** | out-of-scope finding → pause and surface to orchestrator; test failure → fix or surface, not skip |

---

### reviewer

**Kernel authority:** acceptance gate over delegated or generated work

| Dimension | Detail |
|---|---|
| **May** | reject delegated work for any acceptance-criteria failure; request revision with a specific finding; produce a review artifact (written verdict in HANDOFF.md or inline comment) |
| **Must** | check artifact against the slice's declared acceptance criteria; produce an explicit pass/fail/request-revision verdict; not accept work on behalf of the same agent that implemented it |
| **May not** | accept work without checking against acceptance criteria; propose new scope during review; skip the review step because the implementer "seems correct" |
| **Escalation trigger** | fundamental design question → escalate to architect before verdict; destructive or irreversible action found in implementation → escalate to orchestrator |

---

## Role Assignment Rules

1. **Roles are assigned per slice, not permanently per model.** The orchestrator for the session assigns roles at slice start. An agent may fill different roles across slices.

2. **A model filling implementer may not self-promote** to orchestrator or reviewer for that slice.

3. **Review of destructive, dual-use, or external-account-affecting work** must be performed by a different model from the one that implemented it.

4. **Parallel role fills are allowed for independent concerns.** An agent may act as architect for a design question while another acts as implementer in the same session, but the boundary must be explicit.

5. **Unassigned role = implementer.** If a session has no explicit role assignment, all agents default to implementer constraints until an orchestrator assigns roles.

---

## Model Defaults (Illustrative, Not Binding)

These are current typical assignments. Any model may fill any role when the orchestrator explicitly assigns it.

| Model | Typical default role(s) | Notes |
|---|---|---|
| Claude (Sonnet/Opus) | orchestrator, architect, reviewer | Primary orchestrator for Phase 58A |
| Codex | orchestrator (own sequences), implementer, reviewer | Final acceptance on most 58A slices per team plan |
| Gemini (Antigravity IDE) | **proposal, findings review, cross-check reviewer** | See lane-state rule below — NOT default implementer for stateful slices |
| Qwen local | implementer (bounded tasks only) | Constrained by task class eligibility (see 58A.5) |

### Lane state-observability rule (2026-07-11, from the C0.2 incident)

Delegation lanes differ in whether they can observe live round/authorization state:

- **State-observing lanes** (codex, local — dispatched through `scripts/ai/lib/dispatch.py`) read
  round.json / authorization records and receive the injected `config/local-agent-grounding.md`
  guardrail. They can honor a mid-flight suspension. **Prefer these as implementers for stateful,
  stop-condition-bearing slices** (anything with an authorization record, permitted-surface list, or
  budget gate).
- **State-blind lanes** (Antigravity/Gemini — pull/IDE inbox, no dispatch.py, no grounding injection)
  cannot see a suspension raised after their session starts. **Do not assign them as the implementer
  of a stateful slice.** They are excellent at one-shot, stateless work: proposals, findings reviews,
  and cross-check reviews. The inbox-drop preamble (`aq-collab-round INBOX_SCOPE_STOP_PREAMBLE`) is
  the only guardrail channel that reaches them.

Evidence: the C0.2 implementation assigned to Antigravity breached scope (symlinked a tracked
telemetry dir) and then kept recreating suspended files it could not see were stopped. A
state-observing lane (codex) detected and contained it. Match the lane to the task's state needs.

---

## Constraints Inherited from the Kernel Declaration

- **One delegation story:** role assignments, review gates, and handoff artifacts point to the coordinator protocol (`POST /workflow/graph/run` + `.agent/collaboration/` artifact). The `delegate-to-*` scripts are adapters into this protocol.
- **No silent accretion:** an implementer may not add new kernel concepts or expand `http_server.py` surface area without an architect slice and orchestrator acceptance.
- **Memory writes:** new memory-bearing work by any role must write through the brokered path; exceptions must be recorded explicitly.
- **Baseline enforcement:** role-based constraints are aspirational until the 2 aq-qa baseline failures are resolved (see kernel declaration §7).

---

## Consequences for Later Phase 58A Slices

### 58A.2 — routing/profile inventory
The inventory should map each route/profile to the role that may invoke or change it. Routing changes require at minimum implementer + reviewer, and architect sign-off if the change touches a canonical profile.

### 58A.3 — instruction projections
Each agent instruction surface should project role authorities and constraints from this document, not define them independently. The projection may omit roles the agent never fills, but may not relax constraints.

### 58A.4 — Gemini review-gate contract
The reviewer role constraints above are the upstream authority for Gemini's review gate definition. The gate must enforce: no self-acceptance, explicit pass/fail verdict, acceptance-criteria check required.

### 58A.5 — Qwen bounded-task eligibility
Qwen's implementer eligibility contract must cite the implementer constraints above and define the task-class filter that narrows what Qwen may take as an implementer.

---

## Resolved Items (closed in 58A.3)

1. **Sub-orchestrator delegation:** when any model fills the orchestrator role (Codex, Claude, or other), it must produce:
   - `.agent/collaboration/PENDING.json` — intent lock before complex multi-file operations
   - `.agent/collaboration/HANDOFF.md` — memo at slice close
   - `.agents/delegation/registry.jsonl` — entry for any sub-agent delegation
   The form is the same regardless of which model is the orchestrator. There is no model-specific artifact format.

2. **Role escalation time-bound:** if an implementer surfaces an escalation (out-of-scope finding, blocking ambiguity, architecture question) and it is not acknowledged within the current session, the implementer must:
   - Record the open question in `.agent/collaboration/PULSE.log`.
   - Stop the affected slice and leave it in a clean partial state.
   - Do not proceed past an unresolved blocking escalation by guessing or expanding scope.

---

## AgentType × Role Matrix (Phase 73)

**AgentType** = capability class (execution modality).
**Role** = authority class (what the agent is authorised to do this session).
These are orthogonal axes — neither replaces the other. Both must be tracked separately.

### AgentType → Default Role Mapping (SSOT)

This table is the single source of truth for auto-assignment in `agent_executor.py`.

| AgentType | Execution shape | Default role | Eligible roles | Notes |
|-----------|----------------|-------------|----------------|-------|
| `AGENT` | full coding loop (tool use, file edits, git) | `implementer` | `implementer`, `reviewer` | Default for coding tasks |
| `PLANNER` | synthesis + document production | `architect` | `architect`, `orchestrator`, `implementer` | PRDs, plans, risk docs |
| `CHAT` | conversational / Q&A | `implementer` | `implementer` | No tool use |
| `EMBEDDED` | retrieval only — no text generation | `None` | `[]` | Never receives role injection |

### Role Injection Contract

- Role is injected into the **system message** (`build_llama_payload(role=...)` in `shared/llm_config.py`).
- Injection occurs when `task.role` is set (auto-assigned or explicit).
- `EMBEDDED` agents: never injected — role would shift embedding vectors.
- Token overhead: ~25–35 tokens per injection.
- Implementation: `ai-stack/mcp-servers/shared/llm_config.py` → `ROLE_SYSTEM_PROMPTS` + `_inject_role()`.
- CLI wiring: `scripts/ai/delegate-to-local --role <value>` → `aq-agent-loop --role <value>` → `Task.role`.

### Role Blocks (injected verbatim into system prompt)

| Role | Injected text |
|------|--------------|
| `orchestrator` | `[Role: orchestrator] Open/close sessions, assign slices, accept work, commit integration. You may route other agents.` |
| `architect` | `[Role: architect] Draft architecture docs, flag risks, write PRDs. Requires orchestrator review before commit.` |
| `implementer` | `[Role: implementer] Execute assigned slice only. Validate output. Propose commit. Do not re-scope goals.` |
| `reviewer` | `[Role: reviewer] Explicit pass/fail verdict against criteria. Do not review your own work.` |
