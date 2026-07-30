# A2A task for Antigravity — agent/model configuration parity design

Dropped: 2026-07-29T05:20:00Z

Respond by writing only:
`.agents/plans/agent-model-config-parity/antigravity-design-input.md`

## Role and boundary

Act as an advisory flagship architect, SRE, security engineer, and agent-runtime
specialist. Produce design input only. Do not edit configs, wrappers, tests,
runtime state, shared documents, or services. Do not stage, commit, deploy, or
route another agent.

## Objective

Propose how AQ-OS should structure, implement, validate, deploy, and continuously
monitor every parent-agent and sub-agent configuration so role behavior does not
drift across Codex, Claude, Antigravity/Gemini, local-agent/coding, local
logic/direct, and embedded retrieval lanes.

## Required sources

- `docs/architecture/role-matrix.md`
- `docs/architecture/local-agent-task-eligibility.md`
- `docs/architecture/routing-profile-inventory.md`
- `config/model-coordinator.json`
- `config/env-contract.yaml`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `nix/home/base.nix` (Codex/Claude configuration projection)
- `scripts/ai/delegate-to-claude`
- `scripts/ai/delegate-to-antigravity`
- `scripts/ai/delegate-to-local`
- `scripts/ai/aq-antigravity-agent`
- relevant focused configuration/routing tests

## Questions to answer

1. What is the canonical typed object for an agent deployment? Include identity,
   role/authority, model and reasoning tier, modality, context and phase budgets,
   prompt/system/developer payload lineage, tools, sandbox/network, nested
   delegation, schema, timeout/retry/parking, monitoring, reviewer eligibility,
   and fallback.
2. Which fields belong in one provider-neutral SSOT, and which require
   provider/modality-specific projections?
3. How should config precedence and effective merged configuration be computed,
   fingerprinted, displayed, and tested so a stale Home Manager generation or
   user override cannot silently reintroduce deprecated/unsafe settings?
4. How should remote flagship, economical implementer, local coding/logic, and
   embedded retrieval deployments differ without changing their common
   zero-trust authority/evidence contract?
5. What strict request/response schemas and golden vectors should every
   delegation wrapper share?
6. What lifecycle states, receipts, low-cardinality metrics, dashboard panels,
   alerts, capacity/quota parking, retry budgets, and catch-up behavior are
   required?
7. What migration sequence provides fast value without breaking current lanes?
   Separate contract-only, shadow, canary, adoption, and cleanup slices.
8. Identify conflicts or stale claims in the current sources, with exact paths
   and severity.

Return:

- proposed canonical contract;
- provider/modality projection matrix;
- threat model and failure modes;
- validation and observability gates;
- ordered bounded slices with acceptance criteria;
- explicit dissent/unknowns;
- final line:
  `VERDICT: READY_FOR_SYNTHESIS | REQUEST_REVISION — <reason>`

After writing the response, complete this inbox item with:
`scripts/ai/aq-antigravity-inbox complete agent-model-config-parity-design-input.md`
