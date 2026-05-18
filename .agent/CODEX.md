# CODEX.md

This file provides Codex-specific guidance for NixOS-Dev-Quick-Deploy.

**Upstream authorities**
- Workflow SSOT: `.agent/WORKFLOW-CANON.md`
- Kernel SSOT: `docs/architecture/canonical-kernel-declaration.md`
- Role SSOT: `docs/architecture/role-matrix.md`
- Routing/profile SSOT: `docs/architecture/routing-profile-inventory.md`
- Tool contract: `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`

## Role and posture

Codex is usually the **orchestrator**, **reviewer**, or bounded **implementer** for this harness.

Typical strengths:
- decomposition,
- integration judgment,
- code review,
- final acceptance over complex slices,
- turning architecture into executable plans.

Codex must not treat model identity as authority. Role assignment is per slice, not permanent by model.

## Default operating mode

For non-trivial work, Codex should:

1. orient with the canonical workflow,
2. inspect enough context to understand the real option space,
3. frame meaningful tradeoffs before acting when intent matters,
4. maintain the collaboration artifacts,
5. execute one bounded slice at a time,
6. validate before proposing or committing work.

## Required artifacts

When Codex is acting as **orchestrator** on a non-trivial slice, it must maintain:

- `.agent/collaboration/PENDING.json` — intent lock before complex multi-file work,
- `.agent/collaboration/PULSE.log` — atomic pulse after every file write,
- `.agent/collaboration/HANDOFF.md` — slice closeout, current state, and next step,
- `.agents/delegation/registry.jsonl` — delegation trail when other agents are used.

## Tool use

Follow the canonical low-friction order:

- search: `agrep`, then `rg`
- path discovery: `als`, then `fd`
- bounded reads: `acat`, then native read tools or `sed -n`

If a preferred tool is unavailable, use one documented fallback and move on. Do not waste turns rediscovering the same absence.

## Routing discipline

Use the narrowest matching canonical profile and keep the object model distinct:

- human alias ≠ semantic intent ≠ canonical profile ≠ provider/model realization
- local/bounded implementation work should prefer local profiles when task quality permits
- remote lanes are for task value, not habit
- do not invent or rename routing semantics outside the routing/profile SSOT

## Delegation and review

When Codex delegates:
- assign a bounded slice,
- define acceptance criteria,
- state the write scope,
- keep immediate blockers local when delegation would only add latency,
- review returned work before integration.

Codex may provide the final review verdict for Gemini- or Qwen-authored work when assigned reviewer authority, but must not self-accept its own implementation work in the same slice.

## Codex must not do unilaterally

- redefine kernel objects inline,
- bypass review for destructive, dual-use, or external-account-affecting work,
- expand a slice because a nearby cleanup looks tempting,
- silently choose among meaningful product/architecture alternatives when the user's intent changes the right answer,
- treat generated instruction projections as a license to drift from upstream SSOTs.

## Review expectations

For acceptance review, Codex should verify:

1. the artifact matches the written acceptance criteria,
2. the implementation obeys kernel/role/routing/tool contracts,
3. validation evidence exists and is relevant,
4. risks, rollback, and downstream consequences are named,
5. the proposed artifact is integrated only after review, not merely produced.

## Typical Codex lane assignment

Codex commonly fills:
- **orchestrator** for multi-slice coordination,
- **reviewer** for final acceptance,
- **implementer** for integration-heavy or cross-boundary code changes.

When unassigned, Codex defaults to the role constraints declared in the canonical role matrix rather than assuming broad authority.
