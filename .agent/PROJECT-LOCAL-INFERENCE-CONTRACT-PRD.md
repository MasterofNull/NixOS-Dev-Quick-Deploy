# PRD — Canonical Local Inference Contract and `aq-chat` Parity

Status: L1A COMPLETE (`0c171504`) — L2A SHADOW SLICE AUTHORIZED; live adoption not authorized
Owner: Codex orchestrator
Kernel front door: `local-orchestrator` retained; `delegate-to-local` remains a batch adapter
Interactive client: `aq-chat`

## 0. Current evidence and transition posture

This PRD describes a target contract, not current truth. The 2026-07-13 parity audit found three live
lifecycle/routing paths: `delegate-to-local` owns a file registry and launches direct, hybrid, agent,
or Ralph work; agentic `aq-chat` calls the coordinator; conversational `aq-chat` calls the switchboard
directly. Caller-provided `agent_type=human`, `role=orchestrator`, and `human_gate` values can also
influence clearance even though requested and effective roles subsequently diverge.

| Concern | Current authority | Target authority | Transition authority |
|---|---|---|---|
| CLI front door | tracked kernel declares `local-orchestrator`; `delegate-to-local` is an adapter | one `aq`/contract gateway; exact front door requires named kernel revision | legacy CLIs remain adapters with measured use |
| Run lifecycle | delegation registry + coordinator async store + chat client interpretation | coordinator exactly-one-terminal lifecycle | no new store; shadow contract events only |
| Generation | direct llama, coordinator, and switchboard paths | switchboard execution gateway | legacy calls stay live until payload/result parity is measured |
| Role/clearance | caller fields, profile-derived role, and fallback defaults conflict | authenticated identity + resolver-issued effective role + lease | caller role is informational and cannot grant clearance |
| Budgets/context | hardcoded and heuristic per client | one resolved immutable plan | golden fixtures expose divergence before cutover |

The first implementation slice is therefore a pure contract/resolver seam. It does not move traffic,
change lifecycle ownership, add a compatibility environment variable, or authorize Postgres/CAS.

## 1. Problem

Local inference currently has two partially independent implementations:

- `delegate-to-local` plus `scripts/ai/lib/dispatch.py` and `task_config.py` owns persistent tasks,
  execution modes, roles, budgets, scheduling, artifacts, validation and recovery.
- `aq-chat` independently owns profile selection, tool intent, payloads, system grounding, local
  snapshots, coordinator calls, polling, fallback behavior and conversational history.

This produces configuration drift, inconsistent profiles and budgets, duplicate prompt logic,
different failure semantics, and tests that assert surface-specific behavior instead of one shared
contract. An interactive turn and an asynchronous delegation can therefore ask for the same local
operation and receive materially different routing, authority, context and evidence behavior.

## 2. Objective

Create one versioned, model-agnostic local inference contract. The hybrid coordinator remains the
canonical control-plane and run-lifecycle authority; the switchboard remains the model-execution
gateway. `local-orchestrator` remains the kernel-declared CLI front door and the delegation pipeline
remains a batch adapter, not a lifecycle writer.
`aq-chat` becomes a thin interactive adapter that submits the same request envelope and consumes the
same result/event envelopes while retaining terminal UX, conversation history and slash commands.

`aq-chat` must not shell out to the `delegate-to-local` CLI. Extract a reusable Python ingress/client
API from `scripts/ai/lib/dispatch.py`; the batch CLI and interactive client are peer adapters that
submit to the coordinator contract gateway. This preserves native streaming, cancellation and
multi-turn state without duplicating inference semantics or creating a second control plane.

Equivalent requests must have parity for:

- task classification and eligibility;
- selected local lane/profile and effective model;
- prompt construction and context policy;
- token, timeout, queue and tool budgets;
- tool authority and side-effect boundaries;
- fallback and degradation behavior;
- result schema, evidence, provenance and error codes;
- telemetry, replay, validation and recovery.

## 3. Non-goals

- Replacing the terminal UI or slash-command experience.
- Making every chat turn persistent by default.
- Giving chat broader tool or write authority than delegation.
- Moving architecture, destructive operations or security acceptance to a local model.
- Silently preserving legacy behavior when it conflicts with the canonical contract.
- Adding a second routing SSOT inside `aq-chat`.

## 4. Authority and ownership

| Concern | Canonical owner | `aq-chat` responsibility |
|---|---|---|
| Request schema and validation | coordinator contract gateway + generated shared client library | construct typed request |
| Role/task normalization | delegation/task-config library | provide caller/session metadata |
| Task eligibility | shared eligibility policy | render block/escalation reason |
| Profile and model routing | switchboard/delegation policy | display requested and selected route |
| Prompt building | shared prompt adapter | provide user turn and compact history refs |
| Llama payload | `build_llama_payload()` | never construct raw inference payload |
| Tools and side effects | capability/authority policy | request, never self-grant |
| Scheduling and retries | coordinator run lifecycle | stream progress/cancellation controls |
| Evidence and provenance | shared result contract | render claims and limitations |
| History and terminal UX | `aq-chat` | canonical owner |
| Deterministic slash commands | `aq-chat` | may execute only declared local UI commands |

The coordinator run store is the sole lifecycle authority for background and interactive requests.
The shared client library contains no accepted-to-terminal state machine; it validates ingress and
normalizes coordinator events/results. Delegation registries, transports and `aq-chat` may cache or
project observations but may not author independent lifecycle transitions.

This paragraph is target policy. It becomes current only after a separately reviewed migration slice
removes or projects each legacy transition and proves cancellation/restart behavior. Until then,
telemetry must report `current`, `target`, and `transition` owners rather than displaying target state
as already achieved.

## 5. Local inference request contract

Schema ID: `aq.local-inference-request/1.0`

```json
{
  "contract_version": "1.0",
  "request_id": "uuid",
  "trace_id": "uuid",
  "session_id": "optional uuid",
  "parent_run_id": "optional",
  "idempotency_key": "uuid",
  "requester": {
    "source": "aq-chat|delegate-to-local|remote-agent|workflow",
    "agent_id": "string",
    "model_class": "flagship|standard|budget|deterministic",
    "requested_role": "orchestrator|architect|implementer|reviewer|unassigned",
    "trust_boundary": "interactive|background|automation"
  },
  "task": {
    "objective": "one measurable outcome",
    "task_class": "lookup|extract|classify|summarize|review|validate|single_command|single_edit|decomposed_edit",
    "domain": "string",
    "repo_paths": [],
    "edit_sites": 0,
    "anti_goals": []
  },
  "execution": {
    "mode": "direct|hybrid|agent|ralph",
    "response_mode": "stream|final",
    "preferred_lane": "embedded|coding_logic|tool_agent",
    "requested_profile": "embedded-assist|continue-local|local-coding|local-tool-calling|local-agent|ralph",
    "side_effects": "none|read|write",
    "allowed_tools": [],
    "max_tool_calls": 0,
    "approval_ref": null,
    "tool_lease": {
      "lease_id": null,
      "expires_at": null,
      "repo_root": "absolute canonical path",
      "cwd": "repo-relative path",
      "path_globs": [],
      "command_prefixes": []
    }
  },
  "context": {
    "messages": [],
    "artifact_refs": [],
    "memory_keys": [],
    "summary": "",
    "inline_max_chars": 12000,
    "template_version": "string",
    "context_adapter_version": "string",
    "compaction_policy_version": "string"
  },
  "artifact": {
    "format": "text|json|patch|evidence_fragment",
    "schema_id": null,
    "max_chars": 12000,
    "acceptance_criteria": [],
    "evidence_requirements": []
  },
  "budget": {
    "input_tokens": 1200,
    "output_tokens": 256,
    "deadline_ms": 180000,
    "queue_wait_ms": 30000,
    "priority": "interactive|normal|background"
  },
  "fallback": {
    "mode": "deny|queue|same_capability|best_effort",
    "allowed_profiles": [],
    "equivalence_registry_version": "string",
    "max_attempts": 2
  },
  "validation": {
    "checks": [],
    "require_live": false,
    "reviewer_separation": false
  }
}
```

Unknown fields are rejected. Paths are normalized and authority-checked before scheduling. Caller
identity, priority, profile and tool authority are separate fields and must never be inferred from
one overloaded `agent_type` value.

`requester.requested_role` is untrusted intent, not an assignment. Under the frozen role SSOT, a
session with no trusted assignment defaults to **implementer constraints**; the resolver records that
effective role and must not treat caller text as orchestrator/reviewer authority. Changing unassigned
sessions from implementer constraints to rejection requires a named role-revision decision. Interactive
priority is assigned by the trusted ingress adapter and cannot be self-promoted in a request.

`context.messages` is an ordered list of typed `system|user|assistant|tool` messages. Assistant tool
calls and `role:tool` results carry matching call IDs; tool output may never be represented as a
user message. The context adapter deterministically accounts for characters/tokens, retains ordering,
and records the template, adapter and compaction versions needed to reproduce history selection.
Compaction retains the system message, the latest complete tool-call/result pair, and the newest
messages that fit the effective token/character cap; evicted turns are replaced by one deterministic
summary keyed by a content digest. The exact ordering and tie-break rules are versioned fixtures.
Before payload construction, an offline allowlist/redaction scanner removes credential patterns,
private keys and policy-declared PII from inline context. It records only rule IDs and digests—never
the secret value—and a required-context redaction may block rather than silently damage semantics.

`max_tool_calls=0` means tools are prohibited. A nonzero grant is valid only when the requested tool
set intersects eligibility policy, effective role, approval lease and runtime availability. Leases
are bounded by expiry, canonical repository root, resolved working directory, path patterns and
command prefixes. Existing paths are resolved through symlinks before authorization; nonexistent
outputs authorize the nearest existing parent and are rechecked immediately before atomic creation.
No tool may act outside the canonical repository boundary, and authorization is revalidated after
every filesystem-changing tool call to limit TOCTOU drift.

## 6. Result and event contract

Schema IDs: `aq.local-inference-result/1.0`, `aq.local-inference-event/1.0`, and
`aq.local-inference-error/1.0`.

The exact terminal envelope is:

```json
{
  "contract_version": "1.0",
  "request_id": "uuid",
  "run_id": "uuid",
  "trace_id": "uuid",
  "session_id": null,
  "sequence": 7,
  "status": "complete|partial|blocked|failed|cancelled",
  "resolved_plan": {},
  "artifact": {"format": "text", "content": "", "schema_valid": true},
  "claims": [],
  "validation": {"results": [], "missing_evidence": []},
  "effects": {"changed_files": [], "executed_tools": []},
  "usage": {"input_tokens": 0, "output_tokens": 0, "tool_calls": 0},
  "timing": {"queue_ms": 0, "ttft_ms": 0, "inference_ms": 0, "total_ms": 0},
  "provenance": {"producer": "", "template_version": "", "context_digest": "", "input_digest": "", "output_digest": ""},
  "error": null,
  "limitations": [],
  "next_action": ""
}
```

Every terminal result contains:

- request/run/trace IDs and `complete|partial|blocked|failed|cancelled` status;
- requested and selected route, model, routing reason and capability delta;
- typed artifact plus schema-valid flag;
- claims labeled `observed|inferred|proposed`, each with evidence references;
- validation results and missing evidence;
- changed files and executed tools when applicable;
- queue, inference and total latency plus token/tool usage;
- prompt-template version, input/output digests and producer provenance;
- limitations and a stable next action.

Progress events use the same request/run/trace identity and a monotonically increasing sequence and
cover `accepted`, `queued`, `started`,
`tool_call`, `validation`, `completed`, `blocked`, `failed` and `cancelled`. `aq-chat` renders these;
it does not invent an alternative state machine. Each accepted run produces exactly one terminal
event and one terminal result. A disconnect may preserve partial output but cannot create a second
terminal. Duplicate idempotency keys return or attach to the existing lifecycle.

Stable error codes are `invalid_request`, `ineligible`, `unauthorized`, `unavailable_profile`,
`queue_timeout`, `inference_timeout`, `cancelled`, `transport_error`, `malformed_result`, and
`degraded_fallback`. Each error includes a safe message, retryability, resolution reason and evidence
reference; backend-specific exception strings are diagnostic details, never the public contract.

The control-plane API exposes an async event iterator yielding typed content deltas, usage deltas,
tool-call status and the terminal envelope. `cancel(request_id, run_id)` sets the lifecycle-owned
cancellation token, aborts the active transport generation, terminates any adapter-owned child within
the measured cancellation budget, drains the iterator to one `cancelled` terminal and proves no
orphan PID/task remains. Clients never map request IDs to PIDs themselves.

Before inference, the driver emits a resolved execution plan containing effective mode, profile,
model, task type, role, tool set, token/deadline budgets, queue band, config version and stable
resolution reasons. The chat HUD and `/route` render this object rather than reconstructing route
state from client-side flags.

## 7. Routing and task eligibility

| Task shape | Canonical lane | Default output | Tools | Rule |
|---|---|---:|---|---|
| label, intent, extraction | embedded direct | 64–150 | none | autonomous |
| compact summary or constraint ranking | embedded direct | 150–300 | none | autonomous |
| repo-grounded lookup | embedded hybrid | 180–350 | retrieval only | autonomous |
| bounded diff review | coding/logic read-only | 300–512 | read/search | advisory |
| deterministic validation | tool agent | 150–300 | allowlisted validators | autonomous |
| single command or single edit | local agent | 300–800 | leased bounded tools | reviewed by risk |
| multiple edits | sequential decomposition | per-step budget | bounded tools | mandatory remote review |
| architecture, policy, destructive/security acceptance | remote/operator | n/a | n/a | local ineligible |

Routine calls must not inherit the current 4096-token direct default. Budgets are derived from task
class/profile and then capped by caller policy. Multi-edit requests are decomposed through the
canonical sequential-edit path rather than sent as one free-form local task.

Write authority is fail-closed and machine-decidable: a write-capable task requires eligible task
class, effective role, an unexpired approval reference and a bounded tool lease. Risk scoring may
require additional review but can never substitute for any of those grants.

## 8. `aq-chat` migration

Retain in `aq-chat`:

- terminal rendering, readline/history and steering;
- slash-command parsing and deterministic local UI commands;
- conversation/session state;
- cancellation and progress display;
- explicit operator route/tool toggles expressed as contract requests.

Remove or delegate from `aq-chat`:

- raw switchboard/coordinator inference payload construction;
- independent token/temperature/profile defaults;
- independent role and tool-authority decisions;
- duplicated system/role prompt text;
- independent fallback and retry chains;
- independent async task state interpretation;
- direct dependence on backend-specific response shapes.

Tool enablement is a capability request, never evidence that the caller is an orchestrator.
Conversational/tool-free turns must not silently assign reviewer authority, and automatic role
resolution may use the frozen SSOT's implementer-constraint default only for a genuinely unassigned
session; it cannot use caller fields or resolver failure to manufacture broader authority.

Conversation history is converted by a shared context adapter into a compact summary plus bounded
recent messages. Interactive priority affects queueing only; it does not grant tools or write access.

## 9. Configuration consolidation

One machine-readable policy must bind:

- profile aliases and effective model/runtime;
- task-class eligibility;
- budgets and timeouts;
- allowed tool/side-effect sets;
- requester-tier prompt adapters;
- fallback capability rules;
- schema and prompt-template versions.

The implementation must reconcile or retire drift among `switchboard-profiles.yaml`,
`routing-policy.yaml`, `agent-routing-policy.json`, `route-aliases.json`, task-config defaults and
`aq-chat` defaults. In particular, `local-coding` must either be registered everywhere as a valid
local route or retired; it may not remain a semantic fallback with incomplete routing metadata.
The same explicit register-or-retire decision applies to `continue-local` and Ralph; an unavailable
explicit profile returns `unavailable_profile` and never falls through to `default`.

The general local-tool profile must not embed unconditional edit/commit/self-improvement authority.
Write behavior belongs to an explicit capability grant or a dedicated profile.

The consolidated policy also owns model identifier resolution, port lookup through the Port SSOT,
environment names through `config/env-contract.yaml`, and effective budget calculation. Effective
budgets are the minimum of task-class default, profile cap, caller-tier cap and explicit request cap;
zero and negative values are invalid rather than magic defaults.

## 10. Prompt adapters by requester tier

- Flagship: compact typed envelope and evidence refs; may decompose; local results are evidence
  fragments, not replacement architecture decisions.
- Standard: explicit numbered mini-procedure, exact paths, one artifact, one validation branch.
- Budget: one objective, one operation, one input ref and compact strict JSON; deterministic code
  constructs the envelope and handles decomposition.
- Deterministic caller: fills the same schema without an LLM.

All tiers produce the same validated wire request. Prompt prose is an adapter, not authority.

## 11. Failure and fallback semantics

- `deny`: return a stable blocked reason; never change capability.
- `queue`: retain requested capability and wait within budget.
- `same_capability`: use only profiles proven equivalent for task shape and authority.
- `best_effort`: allowed only when explicitly requested; response must set `degraded_contract=true`
  and enumerate capability loss.

Retry once for schema repair using the prior output and validation errors. Do not broaden scope or
context during repair. Retry timeouts only when telemetry proves no terminal result was produced.

`same_capability` requires a versioned equivalence-registry entry proving equal task eligibility,
effective role, side effects, tool set, context policy, result schema and latency class. `best_effort`
is the only mode allowed to report a capability delta. No fallback or repair may alter role, tools,
paths, scope, evidence requirements, or output schema; schema repair may change formatting only.

## 12. Telemetry and dashboard gate

Required metrics:

- request/result schema validity;
- route parity and capability-changing fallbacks;
- queue, TTFT, inference and total latency by caller/profile/task class;
- token and tool usage;
- blocked/ineligible tasks and stable reason codes;
- repair attempts and success rate;
- evidence-reference validity;
- unauthorized-side-effect count;
- `aq-chat` versus delegation parity rate.

One canonical telemetry emitter records both clients. It applies field allowlists, secret and command
output redaction, content-size limits and digests before persistence. Full chat snapshots and raw tool
output are not telemetry. Durable audit events are distinct from optional persistent task lifecycle;
interactive turns may be nonpersistent while still emitting bounded provenance and aggregate metrics.

The dashboard must show contract version, parity rate, selected-lane distribution, degraded
fallbacks, invalid envelopes and unauthorized-side-effect count. A corresponding `aq-qa` integration
check ships with the contract.

## 13. Delivery slices

### L1 — Schemas and pure validation

- Add request/result/event schemas, fixtures and pure validators.
- No runtime routing change.
- Acceptance: unknown fields, invalid paths, authority escalation and invalid budgets fail closed.

### L2A — Canonical request, context, and policy shadow kernel

- Add shared prompt/context adapter and task eligibility/budget policy.
- Record explicit profile transition decisions and isolate write-capable behavior without changing
  live profile routing, callers, or tool execution.
- Acceptance: flagship, standard, budget and deterministic callers create equivalent valid requests.

### L2B — Transport and payload adapters

- Give direct llama, switchboard, coordinator and Ralph adapters one event/result interface.
- Route every llama-bound request through `build_llama_payload()`.
- Remove `dispatch.py`'s production inline fallback clone of the payload builder; import failure is a
  typed configuration error, with injection used only by isolated tests.
- Preserve streaming content/usage equivalence and cancellation propagation.

### L3 — Delegation pipeline adoption

- Make all `delegate-to-local` modes consume and emit the contract.
- Add explicit fallback provenance, progress events and schema repair.
- Preserve legacy CLI flags through a measured compatibility adapter with removal deadline.
- Emit compatibility-adapter usage telemetry; retire it only after the deadline, measured parity and
  error-rate gates pass. It may translate syntax, never silently restore legacy routing or authority.

### L4 — `aq-chat` thin-client migration

- Replace backend-specific inference branches with the canonical client.
- Preserve terminal UX and slash commands.
- Remove duplicated routing, prompt, budget, retry and authority logic after parity evidence passes.

### L5 — Evaluation, QA and observability

- Cross product: caller tier × local lane × task shape × failure mode.
- Add adversarial path, contradictory instruction, busy slot, timeout, malformed result and degraded
  fallback fixtures.
- Add Phase-0 integration and dashboard parity indicators.

## 14. Acceptance gates

- At least 99% request-schema validity across caller tiers.
- At least 95% correct routing for eligible tasks.
- 100% rejection/escalation for destructive and ineligible tasks.
- At least 98% result-schema validity after at most one repair.
- Zero unauthorized writes or untelemetried tool claims.
- At least 95% evidence-reference validity.
- Equivalent `aq-chat` and delegation requests select the same lane, authority, budgets and fallback
  semantics in 100% of parity fixtures.
- Streaming and final modes reconstruct identical assistant content and usage.
- A request has one trace across queue, model, tools and result, with exactly one terminal event.
- Explicit unavailable profiles fail with a typed error instead of falling through to `default`.
- No blank dashboard fields for the new contract.
- Live `aq-chat` and asynchronous delegation smokes pass before compatibility logic is retired.
- Canonical-driver overhead and `aq-chat` TTFT stay within frozen baselines; queue and batch completion
  budgets are measured separately so contract parity cannot hide an unusable interactive regression.

Required suites, in delivery order:

1. Contract rejection matrix: unknown fields, forged trusted/effective role, invalid budgets, traversal,
   symlink escape, side-effect/tool mismatch, write without approval and forged interactive priority.
2. Golden resolver matrix: identical typed requests through chat and delegation adapters produce
   byte-equivalent mode, profile, model, task type, role, tools, budgets, fallback and version fields.
3. Lifecycle matrix: success, block, timeout, cancel, transport failure, malformed output and duplicate
   idempotency key preserve monotonic sequence and exactly one terminal event/result.
4. Profile matrix: `embedded-assist`, `continue-local`, `local-coding`, `local-tool-calling`,
   `local-agent` and Ralph resolve explicitly or fail typed—never to `default`.
5. Authority matrix: eligibility ∩ role ∩ approval ∩ runtime availability is the exact actual tool set.
6. Payload spy: every llama-bound path, including embedded prefetch and chat fast path, invokes
   `build_llama_payload()`; production import failure is typed and has no inline fallback.
7. Context/stream matrix: typed tool-call ordering, deterministic compaction, replay digests, SSE edge
   cases, UTF-8 splits, usage-only finals, disconnects and cancellation preserve stream/final parity.
8. Fallback/telemetry/recovery matrix: equivalence proofs, one redacted emitter/trace, restart and
   idempotency recovery, no orphan work and no authority-changing repair.
9. Live caller-tier × lane × task matrix plus measured TTFT, queue, canonical-driver and batch budgets.
10. Phase-0/dashboard assertions fail closed for missing or stale contract telemetry and expose no
    blank contract version, parity, lane, fallback, invalid or unauthorized fields.

## 15. Risks and stop conditions

- Stop if C0.3 or another active slice owns an overlapping file.
- Stop on profile/port/env SSOT contradiction; do not select a convenient value.
- Stop if parity requires granting chat broader authority.
- Stop if fallback silently changes from remote reasoning/coding to a weaker local capability.
- Stop if event/result provenance cannot be verified across async boundaries.
- Preserve rollback by keeping the legacy adapter until measured parity and error-rate gates pass.
- Stop if `agent_type=human`, `role=orchestrator`, `human_gate`, or any caller-controlled priority can
  self-grant clearance, tools, queue priority, or an effective role.
- Stop if the general `local-tool-calling` profile retains unconditional edit/stage/commit instructions;
  move those behaviors behind an eligible leased write profile before live cutover.
- Replace the existing static assertion that `max_tool_calls` is absent with behavioral authority-budget
  tests; it is not a compatibility invariant under this contract.

Rollback uses one governed compatibility feature flag in the consolidated policy, exposed identically
to both clients and visible in telemetry/dashboard state. It may select the legacy adapter but cannot
restore legacy authority or routing semantics. If an environment override is required, its canonical
name and sunset date must be added to `config/env-contract.yaml` in the same slice; no ad hoc
`AQ_LEGACY_LOCAL`-style variable is permitted.

## 16. Proposed implementation inventory and sequence

### L1A — frozen schemas and pure resolver/golden seam

Freeze an exact inventory in the implementation authorization from these candidate surfaces:

- `config/schemas/local-inference-request.schema.json`;
- `config/schemas/local-inference-result.schema.json`;
- `config/schemas/local-inference-event.schema.json`;
- `config/schemas/local-inference-error.schema.json`;
- `scripts/ai/lib/local_inference_contract.py` (dependency-light validation and pure resolution only);
- focused schema/resolver/golden-adapter tests under `scripts/testing/`;
- `config/validation-check-registry.json` and one Phase-0 registration;
- one existing dashboard/operator projection showing contract version, schema health, parity-fixture
  result, freshness, and typed unavailable reason—no raw prompt content.

Both legacy adapters receive pure request builders used by tests, but no live call path is cut over in
L1A. Golden vectors must prove byte-identical resolved mode/profile/model/task/effective-role/tools/
budgets/fallback/version for chat and delegation inputs. Negative fixtures cover unknown fields,
forged interactive/human/orchestrator clearance, forged approval/lease/priority, injected canonical
path escape, contradictory tool authority, and explicit unavailable profiles. Chat and delegation
fixtures retain their distinct current source shapes and use independently implemented normalizers;
expected canonical bytes are pinned so the parity assertion cannot be tautological. Filesystem
symlink resolution, TOCTOU revalidation, redaction, and deterministic compaction are deferred to L2.

### Later slices (separately authorized)

L2A builds the request/context/policy shadow kernel. L2B extracts the shared transport and removes all
raw llama payload construction; L3 moves delegation lifecycle to the coordinator; L4 migrates
`aq-chat`; L5 proves replay/recovery and retires legacy
writers. Cancellation remains lifecycle-owned—clients never map request IDs to PIDs. Rollback uses one
governed policy flag registered in `config/env-contract.yaml`, never an ad hoc environment escape.

L2A is explicitly no-writer and no-cutover, so unresolved C0.3 lifecycle ratification does not block
it. C0.3 adjudication is mandatory before L3 lifecycle migration. Descriptor-bound path enforcement,
no-follow behavior, atomic create/replace, and adversarial symlink/rename revalidation are mandatory
before any live write-capable adoption; pure `resolve()` evidence is not an execution-time TOCTOU guard.

C0.3 discovery/evidence is integrated, but C0.3 ratification remains blocked pending owner
adjudication of every split-brain row's target, transition owner, deadline, and rollback. L1A completed
at `0c171504` after exact-inventory and golden-fixture review. No L2A implementation begins until
`.agent/PROJECT-LOCAL-INFERENCE-L2A-PLAN.md` receives independent approval. The owner retained the
tracked per-authority direction without ratifying the proposed ADR and retained `local-orchestrator`
as the kernel-declared CLI front door; L2A does not revise either declaration.
