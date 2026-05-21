# External Parity Amendments for MAEAH
> Source inputs: `.agents/scratchpad/EXTERNAL-PARITY-CATALOG.md`, `.agents/scratchpad/SEARCH-LOG.md`
> Owner: Codex synthesis, pending team review fold-in
> Date: 2026-05-21
> Status: PRD/plan supplement for the current multi-agent-edge-harness cycle

## Purpose

The original MAEAH PRD already covers the core edge-agent OS direction: model lifecycle, scheduler, context isolation, memory tiers, A2A/MCP/OTel, and NixOS deployment. The external parity catalog adds useful industry/research references, but not all of them should become immediate scope. This amendment separates high-value additions from distracting frontier work so the team can improve architecture without destabilizing Claude's active coordinator refactor.

## Adoption policy

1. **Adopt patterns, not dependency sprawl.** Prefer contract tests, schemas, and small local implementations over vendoring large frameworks.
2. **Stabilize before expanding.** No new runtime surface should land until the coordinator refactor has live endpoint gates and tier0 green.
3. **Security gates precede autonomy.** Sandboxing, identity, and auditability must ship before broader autonomous SWE or distributed mesh execution.
4. **Measure before optimizing.** RAG, memory, scheduler, and observability additions require baseline metrics and acceptance gates.

## P0 amendments — required before new autonomous capability

### PA-1: Bitemporal memory contract

**Reference parity:** Zep temporal knowledge graph, Nemori temporal anchors, CoALA memory taxonomy.

**Amendment:** Extend the Memory Manager/AIDB plan beyond AMV-L utility tiers to include bitemporal metadata:

- `event_time`: when the fact/action was true or occurred.
- `ingestion_time`: when the harness learned or stored it.
- `supersedes` / `superseded_by`: explicit correction chain.
- `source_agent` and `trust_state`: agent/source attribution for poisoning defense.

**Why:** The team repeatedly depends on agentic memory to resume long dev cycles. Without bitemporal semantics, stale or corrected facts look equivalent to current facts, which creates false coordination state.

**Canonical memory envelope field names:** `event_time`, `ingestion_time`, `valid_from`, `valid_until`, `supersedes`, `superseded_by`, `source_agent`, `trust_state`. Use `ingestion_time` rather than `ingested_at` to match Phase 60.1 implementation.

**Acceptance criteria:**

- Memory write path accepts event time separately from ingestion time.
- Recall can filter “current”, “as known at time T”, and “facts true at time T”.
- Superseded memories do not appear in default recall unless explicitly requested.
- Memory poisoning tests cover untrusted source, retroactive correction, and stale coordination-state recall.

### PA-2: Tool execution sandbox ladder

**Reference parity:** E2B Firecracker microVMs, Wasmtime `agent-sandbox`, OWASP ASI05 Code Execution.

**Amendment:** Replace the single “workspace isolation” idea with a policy ladder:

| Tier | Allowed work | Isolation target | Default |
|---|---|---|---|
| T0 | read-only repo/search/format validation | host subprocess with bounded env | yes |
| T1 | deterministic local code execution/tests | per-run workspace + seccomp/AppArmor profile | yes for repo tests |
| T2 | untrusted generated scripts/tools | Wasmtime or equivalent lightweight sandbox | opt-in gate |
| T3 | networked/untrusted package execution | Firecracker/microVM or container with egress policy | approval/policy gate |

**Why:** The project goal includes creating security systems, drivers, firmware, web/mobile apps, GIS, and research tooling. That breadth requires explicit execution isolation before autonomous tool creation grows.

**Acceptance criteria:**

- Tool declarations carry `sandbox_tier`, `network_policy`, `write_policy`, and `secret_policy`.
- Tier mismatch fails closed before execution.
- Agent-generated code must pass static checks before moving from generated artifact to executable slice.
- Audit logs record sandbox tier and policy decision for every tool execution.

### PA-3: Agent identity and delegation hardening

**Reference parity:** Agent Identity Protocol, Biscuit delegation, Vouch certificates, signed A2A cards.

**Amendment:** Strengthen the existing signed Agent Card requirement into a minimal trust chain:

- Local agents have stable Ed25519 identities.
- Remote/non-loopback agents require signed Agent Cards.
- Delegated authority is scoped by capability, repo path, expiry, and sandbox tier.
- Agent outputs that request commits or privileged tools must be attributable to an identity and delegation grant.

**Why:** Multi-agent review only works if agent responsibility is auditable. This is also the concrete control for “Gemini code must be reviewed by Claude or Codex before implementation/commits.”

**Acceptance criteria:**

- Unsigned remote agent cards quarantine by default.
- Delegation grants have expiry and path/capability scope.
- Review gate records reviewer identity and verdict before integration of Gemini-authored code.
- Audit event includes agent DID/card fingerprint for privileged actions.

### PA-4: MCP/A2A governance profile

**Reference parity:** MCP Roots, OAuth 2.1, mxcp policy/monitoring, `.agents` protocol duties.

**Amendment:** Add a governance profile for each MCP/A2A endpoint:

- `roots`: allowed filesystem/project roots.
- `auth_mode`: loopback, API key, OAuth/resource-server, or signed-card.
- `sampling_allowed`: whether server-initiated LLM calls are allowed.
- `duties`: segregation-of-duties constraints from `.agents/DUTIES.md`.

**Why:** The harness is adding more tools and agents; capability discovery without scoped roots/auth becomes a privilege expansion path.

**Acceptance criteria:**

- Every registered MCP/A2A service has a machine-readable governance record.
- Governance lint fails if remote endpoints lack auth, roots, and audit policy.
- Server-initiated sampling is disabled unless explicitly allowed.


### PA-9: Security contract gates

**Reference parity:** OWASP Agentic Top 10, MCP policy/monitoring, signed Agent Cards, model supply-chain controls.

**Amendment:** Add `MAEAH-SECURITY-CONTRACT-GATES.md` as the normative checklist for identity, auth, delegation, sandboxing, MCP output taint, model catalog supply chain, memory provenance, audit, and independent review.

**Why:** The plan already names most controls, but security reviewers found several places where controls remained aspirational or internally inconsistent. The gates convert them into pass/fail acceptance criteria.

**Acceptance criteria:**

- Tier0/MAEAH gates include checks for auth, sandbox profile declarations, MCP governance metadata, Agent Card validation, model catalog verification, and memory provenance before remote exposure.
- Security-sensitive slices cannot self-accept.
- Loopback mutation without explicit auth is rejected.

### PA-10: Deployment, pressure, and chaos gates

**Reference parity:** edge hardening patterns, impermanence, local chaos/fault testing.

**Amendment:** Add deployment promotion and pressure-state contracts before broader runtime changes:

- deployment: preflight → switch → converge → canary → promote/rollback evidence;
- pressure: `normal → elevated → constrained → critical → shed`;
- chaos: local systemd/shell fault cases before Kubernetes/Chaos Mesh;
- hardening: service classes and resource ceilings for MAEAH units.

**Acceptance criteria:**

- Deployment is not complete until post-switch canary passes.
- Pressure state and active policy are exposed by admin/hardware/scheduler status endpoints.
- Chaos tests verify rollback/recovery without leaving invalid model registry or zombie tasks.
- MAEAH units declare hardening class and resource ceilings.

## P1 amendments — next-cycle quality and stability improvements

### PA-5: RAG quality and graph retrieval gates

**Reference parity:** Microsoft GraphRAG, Stanford STORM, RAGAS, Phoenix.

**Amendment:** Treat GraphRAG/STORM as design patterns, not immediate platform dependencies. Add measured retrieval gates first:

- multi-perspective query expansion for research tasks;
- entity/relation extraction for durable architecture decisions;
- RAGAS-style faithfulness, answer relevance, and context precision metrics;
- regression corpus for agentic memory and project-plan recall.

**Acceptance criteria:**

- Existing memory recall benchmark reports precision/recall-like metrics, not only pass/fail.
- At least one architecture/research corpus has deterministic expected supporting contexts.
- Retrieval changes require before/after metrics in the PR/handoff.

### PA-6: Observability parity map

**Reference parity:** Langfuse, Phoenix, AgentOps, TraceCoder, agent-debugger.

**Amendment:** Extend OTel GenAI migration with explicit parity fields:

- prompt/template version and hash;
- model/router profile chosen and fallback reason;
- tool sequence and sandbox decision;
- memory recall IDs and relevance scores;
- agent state transitions and review verdicts.

**Acceptance criteria:**

- `aq-report` can show one request path from prompt → route → memory → tools → response → review.
- Failed agent runs include enough trace IDs to reproduce route/tool decisions.
- Eval and production traces use the same span schema.

### PA-7: Scheduler semantic blocks and resource pressure policy

**Reference parity:** AIOS, Agent Processor Unit semantic blocks, AgentRM, power-aware scheduling.

**Amendment:** Keep MLFQ as the scheduler base, then add semantic resource descriptors:

- task class: interactive, reasoning, batch, research, codegen, validation;
- context block class: active, compressed, hibernated, persistent;
- resource pressure: thermal, RAM, VRAM/iGPU, queue depth, battery/AC state.

**Acceptance criteria:**

- Scheduler decisions are explainable in logs: queue, priority, demotion reason, pressure signal.
- Background/batch tasks demote under thermal/RAM pressure before interactive tasks are impacted.
- No host eBPF scheduler changes in this phase.

### PA-8: Edge persistence and rollback boundary

**Reference parity:** nix-community/impermanence, local-first/CRDT edge state.

**Amendment:** Add an edge persistence map before adopting tmpfs-root or CRDT sync:

- declarative config: Nix/store/repo;
- durable operational state: `/persist` candidates;
- volatile state: caches, scratchpads, transient traces;
- syncable state: plans, agent memory snapshots, audit digests.

**Acceptance criteria:**

- Documented persistence classification for AIDB, Qdrant, model catalog, traces, agent scratchpads, and local model files.
- Rollback drill verifies no critical agent state is lost or silently forked.
- CRDT/local-first remains design-only until single-node persistence is clean.

## P2 amendments — useful, but defer until P0/P1 are stable

| Topic | Reference | Decision |
|---|---|---|
| OpenHands/CodeAct resolver | OpenHands | Defer to isolated PR-only resolver mode after sandbox ladder and identity are implemented. |
| Agentic UI/micro-frontends | Vercel AI SDK | Defer; useful for dashboard widgets, not core runtime. |
| Multimodal RAG | RAGFlow/txtai | Defer until text/project recall gates are stable. |
| NATS/gRPC mesh | AgentCrew/AgenticMesh | Defer until A2A/MCP governance is clean on single-node. |
| Chaos engineering | Chaos Mesh | Defer Kubernetes-specific tooling; keep lightweight local failure drills. |
| SurrealDB | Unified graph/vector/doc DB | Watchlist only; current Postgres + Qdrant should be improved before migration. |
| Federated learning / DLoRA | OpenFedLLM/Flora | Non-goal for v1; keep as future research. |
| Audio-to-audio, embodied AI, neuromorphic, cryptoeconomics, PQC | Frontier references | Explicit non-goals for the current system-improvement cycle unless user opens a dedicated track. |

## Search-log follow-up policy

The failed searches in `SEARCH-LOG.md` are not dead ends; they define watchlist queries. Re-run them only when a slice needs that area. Do not spend implementation time chasing failed-query categories unless they map to an accepted amendment above.

Immediate re-search candidates only if implementation begins:

1. MCP Roots/OAuth 2.1 current spec and examples.
2. A2A signed Agent Card conventions and current spec language.
3. Qdrant binary quantization/inline storage and pgvector iterative scan docs.
4. OpenTelemetry GenAI semantic conventions current stable attribute names.
