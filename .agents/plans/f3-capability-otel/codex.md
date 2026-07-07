# F3 Codex Design: CapabilityLease + OTel + Signed A2A + Rollback

## Top 3 Priorities

1. **CapabilityLease as the single authority primitive.** All five auto-selection layers must emit or consume leases, not parallel policy hints. Deny-by-default and monotonic least-privilege only work if every tool, skill, plugin, MCP server, RAG source, DB/cache, model, and remote lane is represented as the same attenuable object.
2. **OTel traces as the operational truth.** PULSE/audit/matrix should become projections of trace data, not independent partial ledgers. Every turn and tool call gets trace identity, lease identity, zero-trust state, and validation outcome.
3. **Signed A2A envelope plus rollback snapshot before write.** Antigravity and other delegated nodes need signed local provenance, liveness, typed output, and pre-write recovery as one contract before they receive write-capable leases.

## CapabilityLease Contract

`CapabilityLease` should be an immutable, signed, short-lived contract issued by the harness policy engine after capability-intake and before selection/execution.

```yaml
id: string                    # stable capability id, not display name
lease_id: string              # unique per issuance
version: string               # capability contract version
source: local|nix|plugin|mcp|rag|db|cache|model|remote_lane
owner: string                 # owning subsystem or package identity
issued_to: string             # agent/session/workload identity
issued_at: iso8601
expires_at: iso8601
parent_lease_id: string|null
permissions:
  actions: [read|search|execute|write|network|delegate|model_call|secret_read]
  resources: [string]         # paths, routes, collections, tool ids, lanes
  constraints:
    max_calls: integer|null
    max_tokens: integer|null
    max_cost_class: low|medium|high|null
    allowed_output_paths: [string]
    sandbox_profile: string|null
input_schema: object
output_schema: object
trust_tier: internal|reviewed|sandboxed|external|quarantined
zero_trust_behavior:
  enabled: boolean
  strip_actions: [write|network|secret_read|delegate]
  require_human_review: boolean
  force_sandbox: boolean
cost_class: free|low|medium|high|bounded_external
observability_hooks:
  span_name: string
  attrs: [string]
  events: [lease_issued|lease_attenuated|lease_revoked|policy_denied]
revocation_rule:
  mode: ttl|manual|policy|validation_failure|heartbeat_miss|budget_exhausted
  revocation_epoch: integer
  reason: string|null
signature:
  alg: ed25519
  key_id: local-harness-key-id
  value: string
```

### Admission and Selection Rules

- **Deny by default:** an external plugin, MCP server, remote lane, model, or data source is unusable until capability-intake creates an admitted capability record and policy can issue a lease from it.
- **Five layers become lease evaluators:** `a2a_guard`, action policy, budget policy, capability-intake, and auto-selection/routing each either attenuate a lease or deny it. None can invent permissions absent from the admitted capability.
- **Monotonic least privilege:** within one request, permissions can only stay equal or shrink. Elevation requires a new parent policy decision, new lease id, explicit span event, and a stricter revocation epoch check.
- **Zero-trust becomes lease behavior:** Phase-0 `zero_trust` is not a separate flag passed through call chains. It is one lease mode that strips irreversible actions for that request: write, network, secret read, external delegation, and unsandboxed execution.
- **Revocation is epoch-based:** every executor checks `revocation_epoch` before use. A stale cached lease cannot revive after policy increments the capability or session epoch.
- **Property tests:** stripped actions cannot be reacquired by child leases; caller-supplied `zero_trust=false` cannot downgrade an inherited stricter lease; stale lease ids fail after revocation epoch increments; output paths outside `allowed_output_paths` are rejected even when the tool succeeds.

## OTel Span Model

Use W3C trace context across coordinator, switchboard, local executor, and antigravity envelope. Existing audit/PULSE/matrix events become trace events or views over traces.

### Spans

- `agent.turn`: root span for each user/delegated turn.
- `agent.selection`: child span for auto-selection and lease bundle assembly.
- `capability.lease.issue`: child span for each issued or attenuated lease.
- `tool.call`: child span for each tool/MCP/plugin/script invocation.
- `model.call`: child span for local or remote inference.
- `a2a.task`: child span for delegated antigravity/local/remote task.
- `validation.gate`: child span for py_compile, bash -n, tier0, aq-qa, or slice-specific checks.
- `workspace.snapshot` and `workspace.rollback`: child spans around write-capable execution.

### Core Attributes

Use stable `harness.*` attributes where OTel has no existing semantic field.

```text
service.name
service.version
trace_id
span_id
harness.round_id
harness.task_id
harness.agent.role
harness.agent.name
harness.lane
harness.model
harness.model_version
harness.tokens_in
harness.tokens_out
harness.latency_ms
harness.lease.bundle_ids
harness.lease.zero_trust
harness.lease.trust_tier
harness.capability.id
harness.capability.source
harness.tool.name
harness.output.path
harness.validation.result
harness.rollback.snapshot_id
```

### Emit Points

- **switchboard:** create `agent.turn`, `agent.selection`, and `model.call`; attach lane/model/token/latency attributes.
- **hybrid coordinator:** issue lease spans; record policy denial, attenuation, revocation, and selected bundle.
- **agent_executor/local runtime:** create `tool.call`, `validation.gate`, and `workspace.snapshot` spans; check lease before tool execution.
- **antigravity delegate path:** create `a2a.task`, heartbeat events, envelope verification result, and output verification result.
- **capability-intake:** emit admission/rejection spans with trust tier and provenance.

### Read Points

- **Matrix/live selections panel:** query recent `agent.selection`, `capability.lease.issue`, and `tool.call` spans by trace id and round id. Show selected bundle, denied capabilities, zero-trust stripping, cost class, and validation status.
- **Audit trail:** persist span summaries as append-only audit records keyed by trace id.
- **PULSE compatibility:** for human-readable collaboration logs, generate concise pulse rows from span events instead of maintaining a separate truth source.
- **Grafana/Jaeger:** use standard OTLP export. Local dev can run file/stdout exporter first, but the contract should be OTLP-compatible from day one.

## Signed A2A Task Envelope

The watched folder becomes transport only. The signed envelope is the authority.

```yaml
schema_version: a2a.task.v1
round_id: string
task_id: string
idempotency_key: string
issuer: harness-coordinator
assignee: antigravity
created_at: iso8601
deadline: iso8601
expected_output_path: .agents/plans/f3-capability-otel/antigravity.md
allowed_write_paths:
  - .agents/plans/f3-capability-otel/antigravity.md
lease_bundle: [CapabilityLease]
task:
  title: string
  instructions: string
  output_schema: object
heartbeat:
  path: .agents/heartbeats/antigravity/<task_id>.json
  interval_seconds: 30
  stale_after_seconds: 120
signature:
  alg: ed25519
  key_id: local-harness-key-id
  value: string
```

Rules:

- No API keys. The harness signs locally with an Ed25519 key stored outside tracked files, preferably via age/sops-managed local secret or host-local key path.
- The IDE OAuth identity is not a signing root. It can authenticate the IDE to its own service, but harness task authority is local signing plus admitted lease bundle.
- Antigravity verifies signature, deadline, idempotency key, lease bundle, allowed write path, and output schema before writing.
- Heartbeat includes `task_id`, `trace_id`, `agent_version`, `state`, `last_event_at`, `pid` if local, and `lease_bundle_hash`.
- Output contract includes `task_id`, `trace_id`, `status`, `artifact_path`, `summary`, `validation`, `lease_bundle_hash`, and `signature`. The coordinator rejects unsigned, stale, path-escaping, or schema-invalid outputs.

## Automatic Rollback Before Write

Every write-capable lease requires a workspace snapshot before the first write. This is enforced in the executor, not left to agent habit.

Flow:

1. Policy grants write only with `allowed_output_paths` and `sandbox_profile`.
2. Executor creates `workspace.snapshot` before write:
   - preferred: isolated git worktree under the existing worktrees dir for delegated/remote agents;
   - fallback: git stash including untracked files only for tightly scoped local writes where worktree isolation is unavailable.
3. Executor runs the write under Slice-2 bwrap with only allowed paths mounted writable.
4. Validation runs under the same trace: schema check, path check, py_compile/bash -n where relevant, then tier/slice gate.
5. On validation failure, timeout, heartbeat miss, or lease revocation, executor rolls back the worktree or stash and emits `workspace.rollback`.
6. On success, executor marks snapshot retained until orchestrator review, then garbage collection can prune it after commit or explicit acceptance.

Safety rules:

- Rollback never crosses the allowed write path set.
- Existing user changes are preserved by worktree isolation where possible. If stash fallback detects unrelated dirty files outside the lease scope, deny write lease instead of snapshotting the whole workspace.
- bwrap and CapabilityLease must agree: the lease defines allowed resources; bwrap is the kernel-level enforcement of that same set.
- Validation failure revokes the write lease for the task id so a retry needs a fresh lease and new snapshot.

## Acceptance Criteria

- One schema can represent tools, skills, plugins, MCP servers, RAG, DB/cache, models, and remote lanes.
- A zero-trust request cannot perform irreversible operations even if downstream code asks for them.
- The live matrix can answer: what was selected, why, under which lease, what was denied, what ran, and what validation proved.
- Antigravity output is accepted only when signed, fresh, schema-valid, and written to the expected path.
- Any write-capable execution has a recoverable snapshot before the first mutation.
