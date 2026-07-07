# Codex Foundation Critique — Flat-Collaborative Factory Core

## Verdict

Promising direction, not yet a foundation. The current core is a useful prototype of a flat collaborative factory, but it is still too dependent on scripts, conventions, implicit files, and operator discipline. Before more features depend on it, promote the workflow into explicit, testable primitives: a round state machine, a typed capability contract, and a measured scheduler for local inference.

The biggest risk is not that the design is wrong; it is that the system currently looks more deterministic than it is. `aq-collab-round` creates files and dispatches lanes, but the lifecycle guarantees in the epic are broader than what the engine enforces.

## Top 3 Changes

1. Build a real round/workflow state machine.

   Replace "open/status/collect plus conventions" with an explicit durable state model: `CREATED -> DISPATCHED -> CONTRIBUTING -> COLLECTED -> CONFLICTS_IDENTIFIED -> CONSENSUS_LOCKED -> ASSIGNED -> IMPLEMENTING -> VALIDATING -> CLOSED`.

   Requirements:
   - JSON schema for round manifest, contribution metadata, lane status, deadlines, retries, and signed verdicts.
   - Idempotent commands: rerunning `open`, `collect`, or `aggregate` must never duplicate dispatches or overwrite prior contribution state.
   - Quorum and timeout policy: late local contributions should remain admissible, but consensus cannot be an informal "whatever landed".
   - Explicit conflict objects, not prose-only aggregation.
   - Tests that simulate missing lane, late lane, duplicate run, malformed contribution, dispatch failure, and recovery after process death.

   Systems to study: Temporal, Durable Task, Ray workflows, Prefect, Airflow DAG semantics, LangGraph state graphs, AutoGen group chat state handling, CrewAI process abstractions. The harness probably does not need those dependencies, but it does need their durable execution lessons.

2. Replace capability auto-selection by convention with an admission and lease contract.

   The exposure map documents five capability-selection times, which is good. The weakness is that each layer has different semantics: Nix activation, service startup, skills, manifests, model-driven leasing, keyword hot-swap, RAG, security, and zero-trust stripping. That is too much implicit coupling.

   Add one canonical `CapabilityLease` contract:
   - capability id, version, source, owner, permissions, input/output schema, trust tier, zero-trust behavior, cost class, observability hooks, and revocation rule.
   - deny-by-default admission for external plugins/MCP/tools, using the existing capability-intake path.
   - monotonic least privilege within a request: additions allowed only through policy, privilege elevation requires audit, zero-trust strips must be irreversible for that request.
   - dashboard/API visibility for current leases per lane.
   - property tests: "stripped tools cannot be reacquired", "caller false cannot downgrade zero_trust", "lease cache cannot revive stale privileged tools".

   Techniques/papers/systems to study: object-capability security, macaroons for attenuated credentials, SPIFFE/SPIRE workload identity, The Update Framework/Sigstore for capability provenance, OpenTelemetry semantic conventions for tracing leases, Zanzibar-style authorization modeling for relationship-based access.

3. Fix local utilization with measured model-tier scheduling, not just "never skip local".

   The evidence is decisive: one 35B slot at 1-4 tok/s, no grammar gate, no KV reuse, no small resident model, and repair loops consuming the scarce slot. "Never skip local" is correct as a policy goal but wrong as a scheduler. The local lane should always participate, but not always with the 35B.

   Recommended design:
   - Resident 4B or 8B lane for classification, JSON/tool-call validation, schema repair, short critiques, grep-summary synthesis, and quick risk scoring.
   - 35B session mode only for architecture, multi-file planning, high-risk code reasoning, and final local dissent reviews.
   - Queue classes: interactive, validation, background, batch. Use MLFQ plus aging to avoid starvation.
   - Concurrency: keep embeddings on `:8081`; add at least one small-gen slot separate from the 35B slot if memory permits. If not, prefer resident 8B over resident 35B for factory control loops.
   - GBNF/structured decoding on final post-filter tool schemas before local tool calls; cache grammars by schema hash plus zero-trust state.
   - Prefix/KV reuse for stable grounding and tool schemas; measure cache hit rate and prefill cost.
   - Back-pressure: if local queue exceeds SLO, shrink prompt, downgrade task, or return a typed "local delayed" state rather than silently letting consensus move on.

   Acceptance metrics:
   - invalid tool JSON repair attempts down at least 90%.
   - local contribution landing rate, p50/p95 latency, slot occupancy, queue depth, tok/s by tier.
   - percent of factory rounds where local contributes before consensus lock.
   - 35B time spent on high-value tasks versus trivial repair/validation.

## Where It Is Too Ad-Hoc

- `aq-collab-round` writes `README.md`, `.round-prompt.txt`, `.round-dispatch.json`, and inbox tasks, but these are not a full protocol. There is no schema version, no state transition validation, no contribution envelope, no verdict parser, and no formal consensus object.
- Antigravity is a file-drop lane, not yet a first-class A2A node. The OAuth decision is right, but a watched folder without a signed task envelope, lease, heartbeat, and output contract is operationally fragile.
- "Each agent selects its own expert team" is underspecified. It encourages diversity, but without a required role roster, rationale, and coverage matrix, it can become untestable theater.
- Capability selection is layered but not normalized. Build-time flags, startup services, skill loading, per-request RAG, tool leases, and keyword hot-swap should all project into one inspectable capability graph.
- Consensus is mostly prose. The factory needs machine-readable disagreement, confidence, blocking issues, and sign-off status.
- Validation is strong for commits but weaker for orchestration itself. The round engine needs its own chaos tests and replay tests.

## Missing Work Before Continuing

- Formal schemas:
  - round manifest
  - dispatch record
  - contribution envelope
  - consensus verdict
  - assignment manifest
  - integration contract
  - capability lease
  - model scheduling decision

- Orchestration tests:
  - late local result
  - missing antigravity watcher
  - duplicate `open`
  - crashed dispatcher
  - malformed agent file
  - secret-bearing prompt
  - zero-trust remote downgrade
  - concurrent clean and secret rounds
  - aggregation with explicit conflict

- Observability:
  - OpenTelemetry traces across intake, dispatch, tool lease, model route, contribution write, aggregate, assignment, validation.
  - SLOs for round completion, local contribution latency, invalid JSON rate, repair-loop burn, consensus churn, and human intervention count.
  - Dashboard tiles for active rounds, blocked rounds, local queue, lane health, capability leases, and zero-trust decisions.

- Safety and security:
  - Signed or checksummed task envelopes for file-drop lanes.
  - Prompt/output redaction audit attached to the round manifest.
  - Capability revocation semantics.
  - Sandbox failure reason taxonomy promoted into every lane, not only Slice 2.

## Papers, Techniques, and Systems To Study

- ReAct: reasoning plus acting loops for tool-using agents.
- Reflexion and Self-Refine: structured self-feedback, useful for critique passes but dangerous unless bounded by tests.
- Tree of Thoughts and Graph of Thoughts: useful for multi-pass planning, but should become bounded search, not unconstrained debate.
- Constitutional AI / RLAIF: relevant to policy framing, but not a substitute for runtime controls.
- Voyager: skill discovery and accumulation; study for skill lifecycle, not for unbounded autonomy.
- Toolformer and Gorilla: tool-use grounding and API selection.
- Constrained decoding work: JSONFormer, Outlines, Guidance, llama.cpp GBNF, LMQL, Microsoft Guidance.
- Multi-agent systems: AutoGen, MetaGPT, ChatDev, CAMEL, CrewAI, LangGraph.
- Workflow/runtime systems: Temporal, Durable Task, Ray, Prefect, Argo Workflows.
- Distributed systems patterns: event sourcing, saga pattern, idempotency keys, leases, back-pressure, circuit breakers, quorum/consensus vocabulary.
- Observability standards: OpenTelemetry traces/metrics/logs, RED/USE metrics, SLO/error-budget practice.
- Security standards: object-capability model, SPIFFE/SPIRE, Sigstore, TUF, SLSA, OWASP Agentic Top 10, NIST AI RMF.

## Highest Operability Target

The factory should be operable like a distributed system, not like a collection of helper scripts.

Minimum bar:
 - every round has a state, owner, version, deadline, policy, and replay log.
 - every dispatch has an idempotency key and a typed result.
 - every capability is admitted, leased, observable, and revocable.
 - every model-routing decision records why this lane/model/tier was chosen.
 - every consensus decision records dissent and unresolved risk.
 - every local-model delay is visible, not silently bypassed.
 - every failure has a reason code and a retry/escalation policy.

The current design has the right instincts: per-agent files avoid lost writes, zero-trust is the right keystone, OAuth-bound remote lanes avoid key sprawl, and local must remain a participant. The next step is to turn those instincts into enforceable contracts.

