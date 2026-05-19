# Sign-Off Review: Codex (Senior Staff Engineer)

## Overall Verdict: APPROVE WITH AMENDMENTS

I approve the Combined PRD directionally. It captures the core Staff Engineer position: MAEAH should be a typed, observable, recoverable control plane around constrained local inference, with OpenAI-compatible APIs for applications, A2A for agent coordination, MCP for tool access, OpenTelemetry for observability, and durable model lifecycle operations.

This is not a request to rework the architecture. The required amendments are contract corrections and implementation-scope clarifications that should be fixed before this document becomes the implementation source of truth.

## Amendments Required (if any)

1. Normalize the API surface against the Staff Engineer PRD.
   - Add `POST /v1/responses` as a required OpenAI-compatible endpoint, or explicitly defer it with compatibility consequences.
   - Restore the admin namespace as `/admin/v1/*` for lifecycle, scheduler, agent, and trace operations, or explicitly declare `/models/*` as an alias over the admin API. Lifecycle operations must not be ambiguous public endpoints.
   - Align A2A discovery and task endpoints. The Codex PRD used `GET /.well-known/agent-card.json`, `POST /a2a/jsonrpc`, and `GET /a2a/tasks/{task_id}/events`; the Combined PRD uses `/.well-known/agent.json` and REST-shaped `/a2a/tasks/send`. Pick one canonical A2A contract and document any compatibility aliases.

2. Correct the security boundary language.
   - The Combined PRD says loopback is exempt from API key. My PRD required local authentication for admin APIs by default and no default exposure beyond loopback. Loopback may reduce network exposure; it must not silently make model promotion, rollback, tool invocation, or admin operations unauthenticated.
   - Signed Agent Cards are not only a future v2 idea for mesh mode. For networked A2A peers, unsigned cards must be rejected or quarantined unless a local allowlist explicitly permits them.

3. Correct the schema/type attribution.
   - Replace "typed Python dataclass schemas" with "versioned JSON Schema/OpenAPI contracts with implementation types generated or maintained in the runtime language." The Codex PRD explicitly preferred Go or Rust for the always-on gateway/kernel path and treated Python as acceptable for evals and research workflows.

4. Preserve the durable model lifecycle state machine.
   - The Combined PRD compresses lifecycle states to `available -> downloading -> staged -> active -> retiring -> archived`. The Staff Engineer PRD requires explicit `downloaded`, `verified`, `warming`, `candidate`, and `failed` states. Those states matter for restart safety, dashboard semantics, rollback, and contract tests.

5. Carry forward the testing appendix as normative acceptance criteria.
   - The Combined PRD correctly names contract testing, but the Staff Engineer PRD made the test matrix concrete: OpenAI compatibility, A2A lifecycle, MCP resource/tool calls, admin schema tests, event replay, scheduler behavior, model lifecycle restart/rollback, security boundary tests, and OTel span/metric tests. This should be included as a required validation section, not left as an implied implementation detail.

## Implementation Feasibility Concerns

- CPU-only hot-swap should remain capability-tiered. The Combined PRD's `<30s CPU-only` target is acceptable as a hardware-class SLA, but implementation must report SLA misses as structured events and keep the previous active model serving when promotion fails.
- Fine-grained preemption and direct KV-cache reload into attention internals are high-risk implementation items. They should be staged after the gateway, durable lifecycle manager, scheduler admission control, and event schema are stable.
- Dynamic quant-tier switching may require separate model artifacts rather than an in-place parameter change. Storage, catalog, and UMBM design must account for multiple quant files per model family.
- MCP-only tooling is the right target, but the migration from existing bespoke coordinator tools should be phased behind adapters so current automation is not broken before replacement contracts exist.
- Observability should pin an OTel GenAI SemConv version or commit and isolate mapping behind an adapter. Internal event envelopes should remain stable even if OTel attribute names change.
- The research-derived performance numbers should be treated as design targets until reproduced locally. Acceptance criteria should be based on measured local baselines, not imported benchmark claims.

## Items Correctly Captured

- The core Codex thesis is accurately represented: edge harness failures are more often runtime-contract failures than raw model-intelligence failures.
- The Combined PRD correctly preserves MCP, A2A, OpenAI-compatible HTTP, and OTel GenAI as the external protocol boundaries.
- The kernel manager decomposition matches the Staff Engineer PRD: scheduler, context, memory, storage, tool, access, model lifecycle, and observability managers.
- The priority on model pre-download, verified staging, atomic promotion, rollback, and dashboard-visible progress matches my PRD.
- The `edgeai` CLI direction is correctly captured, including doctor, model lifecycle, chat, A2A card validation, MCP tool listing, traces, and scheduler status.
- The emphasis on versioned schemas, contract testing, stable error codes, audit events, and untrusted MCP tool outputs is directionally correct.
- The preserve/change assessment for the current NixOS-Dev-Quick-Deploy system is consistent with my PRD: preserve NixOS packaging, validation discipline, dashboard/CLI culture, AIDB/project memory, and governance scripts; change weak runtime contracts, scheduling, lifecycle, observability, and protocol boundaries.

## Formal Sign-Off Statement

Reviewed by Codex (gpt-5.5), Senior Staff Software Engineer, on 2026-05-19.

Verdict: APPROVE WITH AMENDMENTS.

I sign off on the Combined PRD as the correct architectural direction for MAEAH, subject to the amendments above being incorporated before implementation planning begins. The remaining issues are not conceptual blockers, but they are important contract-level corrections. The implementation should start from a narrow v1: gateway and schema contracts, durable model lifecycle manager, scheduler admission control, admin API/CLI, event envelope, and contract tests. More speculative capabilities such as fine-grained preemption, split inference, advanced KV restore, and mesh gossip should follow only after the single-node control plane is stable and measurable.
