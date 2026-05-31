# PRD: Senior Staff Software Engineer / Codex - Multi-Agent Edge AI Harness
> Author: Codex - Role: Senior Staff Software Engineer
> Date: 2026-05-19 - Version: 1.0
> Exercise: Greenfield design independent of the current NixOS-Dev-Quick-Deploy system

---

## 1. Executive Summary

This PRD defines a greenfield implementation architecture for a multi-agent edge AI harness that treats local LLM inference as an OS-managed resource. The Staff Engineer lens is concrete: API surfaces, interface contracts, data models, testability, upgrade paths, failure semantics, OpenTelemetry integration, MCP/A2A compliance, and security boundaries at every code interface.

The proposed system is an edge-first runtime composed of:

- A protocol gateway exposing OpenAI-compatible APIs, A2A agent coordination, and MCP tool access.
- An AI kernel with scheduler, context manager, memory manager, storage manager, tool manager, access manager, model lifecycle manager, and observability manager.
- A hardware abstraction layer for llama.cpp/GGUF first, with pluggable CUDA/AWQ/GPTQ/EXL2 and NPU backends.
- A model lifecycle service supporting background pre-download, verified staging, atomic promotion, rollback, and dashboard progress.
- A developer experience centered on one CLI, reproducible NixOS packaging, local-first traces, stable JSON schemas, and fast integration tests.

The design intentionally avoids bespoke protocols where standards exist. MCP is the tool boundary. A2A is the inter-agent boundary. OpenAI-compatible HTTP is the application compatibility boundary. OpenTelemetry GenAI Semantic Conventions are the observability boundary. Internal modules communicate through explicit, versioned event and state schemas rather than ad hoc Python dictionaries or shell-formatted text.

The core engineering thesis: a local edge harness fails less often from weak model intelligence than from weak runtime contracts. The primary deliverable is therefore a boring, typed, observable, recoverable control plane around constrained inference.

---

## 2. Problem Statement (from your role's lens)

Edge multi-agent systems are difficult to build because local model inference is simultaneously scarce, stateful, slow to restart, security-sensitive, and difficult to observe. From an API and implementation architecture perspective, the main failure modes are:

1. Unstable boundaries. Existing harnesses often mix CLI output, daemon control, scheduler state, and tool execution in loosely structured formats. This makes clients brittle and tests shallow.
2. Unmanaged concurrency. Multiple agents submit work to a single model backend without admission control, priority, cancellation, context ownership, or zombie reaping.
3. Slow model lifecycle. Downloading and loading a model is treated as a blocking maintenance operation rather than a background, state-machine-driven workflow.
4. Poor recovery semantics. Agent tasks, tool calls, model swaps, and context eviction often lack durable checkpoints and precise retry behavior.
5. Incomplete protocol compliance. Tool execution, agent coordination, and model inference are commonly exposed through custom wire protocols, creating integration drag.
6. Weak observability. Token usage, TTFT, decode latency, queue latency, tool latency, cache hits, model swap phases, thermal throttling, and rollback decisions are not emitted as one trace.
7. Security at the wrong layer. Agentic systems frequently validate prompt text but under-specify the code boundary: path access, command execution, tool authorization, model file provenance, and memory read/write policy.

This PRD proposes an implementation architecture where every boundary is explicit, typed, cancellable, observable, and testable.

---

## 3. Goals & Non-Goals

### Goals

- Provide a stable local API surface:
  - OpenAI-compatible `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/models`.
  - A2A JSON-RPC 2.0 endpoints for agent discovery, task lifecycle, delegation, and context handoff.
  - MCP Streamable HTTP client/server integration for tool access.
- Implement an AI kernel with explicit resource managers:
  - Scheduler: MLFQ, admission control, cancellation, zombie reaping, token budgets, priority inheritance.
  - Context manager: per-agent context slots, compaction, hibernation, and KV cache ownership.
  - Memory manager: tiered agent memory with value-based eviction.
  - Storage manager: verified model artifacts, durable checkpoints, Q4 KV cache persistence.
  - Access manager: agent identity, policy checks, per-action authorization, audit events.
- Support background model pre-download and atomic hot-swap:
  - Zero new-request downtime by queueing new requests during the flip.
  - Drain or checkpoint in-flight requests.
  - Target <5s swap window on supported hardware.
  - Automatic rollback after failed health checks.
- Make implementation portable and reproducible:
  - NixOS-first packages and systemd units.
  - Hardware backend abstraction for CPU/iGPU first, dGPU/NPU later.
  - No hardcoded ports, URLs, or secrets; all runtime config comes from files, environment, or secret paths.
- Build a developer-friendly system:
  - Single CLI: `edgeai`.
  - Hot-reloadable model registry and agent cards.
  - Local dashboard backed by the same public API as the CLI.
  - Contract tests and local smoke tests that run without internet.
- Emit standard observability:
  - OTLP traces, metrics, and logs.
  - OpenTelemetry GenAI attributes for model calls and agent/tool spans.
  - Correlated scheduler, model lifecycle, hardware, and safety events.

### Non-Goals

- Training platform. Federated fine-tuning and DP-FedLoRA are future extensions, not v1.
- Kubernetes replacement. This is a single-device and small-edge-mesh runtime, not a general cluster scheduler.
- Cloud dependency. Remote model fallback may exist, but all critical control-plane operations must work offline.
- Proprietary agent protocol. We will not invent a new inter-agent protocol where A2A is sufficient.
- Full POSIX agent runtime. Quine-style POSIX mapping is useful inspiration, but v1 uses process isolation only where it simplifies safety and lifecycle.
- Browser-only administration. The dashboard is not the control plane; it is a client of the same typed APIs as CLI and automation.

---

## 4. Architecture Proposal

### 4.1 Core Modules / Components

```
Clients
  CLI / Dashboard / IDE / OpenAI SDK / A2A peers / MCP hosts
    |
Protocol Gateway
  OpenAI Compat API | A2A Gateway | MCP Tool Gateway | Admin API
    |
AI Kernel
  Scheduler | Context Manager | Memory Manager | Storage Manager
  Tool Manager | Access Manager | Model Lifecycle Manager | Observability Manager
    |
Execution Backends
  llama.cpp/GGUF | CUDA/AWQ/GPTQ | EXL2 | NPU adapters | Split inference peers
    |
OS / Hardware
  NixOS systemd | cgroups | filesystem | network | thermal/DVFS sensors
```

#### Protocol Gateway

The gateway is the only public ingress. It owns request authentication, request IDs, trace context extraction, protocol adaptation, input size limits, schema validation, and error normalization.

Public endpoint groups:

- `/v1/*`: OpenAI-compatible inference API.
- `/a2a/*`: A2A JSON-RPC 2.0 endpoint and Agent Card discovery.
- `/mcp/*`: MCP Streamable HTTP bridge and local MCP server registry.
- `/admin/*`: local authenticated admin API for model lifecycle, scheduler state, dashboard data, and health.
- `/metrics`: Prometheus-compatible metrics for local scraping.
- `/healthz`, `/readyz`: health and readiness probes.

#### Scheduler

The scheduler manages inference work as kernel jobs, not raw HTTP requests. It uses MLFQ inspired by AgentRM, admission control and backpressure inspired by HiveMind, and state-aware request lifecycle ideas from Astraea.

Queue classes:

| Queue | Workload | Example | Default Budget |
|---|---|---|---|
| `interactive` | human-facing reactive work | chat, IDE completion | low latency, short max queue wait |
| `agentic` | delegated agent tasks | code review, research DAG node | balanced |
| `background` | proactive maintenance | indexing, evals, summarization | best effort |
| `batch` | non-urgent long jobs | benchmark, re-embed, model eval | preemptible |

Scheduler job schema:

```json
{
  "job_id": "job_01HY...",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "agent_id": "agent.codex.staff",
  "tenant_id": "local",
  "queue": "interactive",
  "priority": 80,
  "deadline_ms": 30000,
  "token_budget": {
    "input_max": 32768,
    "output_max": 4096,
    "total_max": 36864
  },
  "capabilities_required": ["chat", "tool_use", "code"],
  "model_hint": "qwen3.6-coder-35b",
  "cancellable": true,
  "created_at": "2026-05-19T16:00:00Z"
}
```

Required behavior:

- Admission control rejects or queues based on memory pressure, thermal state, active model state, and per-agent budgets.
- Cancellation is cooperative for decode loops and mandatory for queued work.
- Zombie reaping marks a job as `stalled` when no progress event occurs before `stall_timeout_ms`.
- Priority inheritance propagates A2A task priority through delegated subtasks.
- Every state transition emits an event and OTel span event.

#### Context Manager

The context manager owns agent context slots and maps them to KV cache, memory references, tool outputs, and prompt assembly.

Context states:

```text
new -> active -> io_wait -> compacting -> hibernated -> evicted
                 |                         |
                 +-------------------------+
```

Context slot schema:

```json
{
  "context_id": "ctx_01HY...",
  "agent_id": "agent.codex.staff",
  "model_id": "qwen3.6-coder-35b.gguf:q4_k_m",
  "state": "active",
  "window_tokens": 32768,
  "used_tokens": 18420,
  "kv_cache_ref": "kv://agent.codex.staff/qwen3.6/ctx_01HY.q4kv",
  "memory_refs": [
    "mem://semantic/project-architecture/abc123",
    "mem://episodic/agent.codex.staff/session456"
  ],
  "last_accessed_at": "2026-05-19T16:00:00Z",
  "utility_score": 0.82
}
```

Implementation requirements:

- Tool calls are context invalidation points unless the backend supports structured continuation.
- Tool outputs are stored as immutable artifacts with content hash, not appended as unbounded text.
- Compaction produces a signed summary object with provenance references.
- Context reads across agents require explicit policy grants.

#### Memory Manager

The memory manager separates memory type from storage technology. It implements value-driven tiering inspired by AMV-L rather than simple TTL or LRU.

Memory item schema:

```json
{
  "memory_id": "mem_01HY...",
  "owner_agent_id": "agent.codex.staff",
  "scope": "private",
  "type": "semantic",
  "tier": "warm",
  "content_ref": "blob://sha256/...",
  "embedding_ref": "vec://local/...",
  "utility": {
    "score": 0.71,
    "last_used_at": "2026-05-19T15:59:00Z",
    "reuse_count": 12,
    "decay_policy": "amv_l_default"
  },
  "acl": {
    "read": ["agent.codex.staff"],
    "write": ["agent.codex.staff"]
  }
}
```

Memory tiers:

- `hot`: request-path working set in RAM.
- `warm`: local vector store and recent artifacts.
- `cold`: compressed disk archive.
- `shared`: signed semantic facts available to multiple agents.

#### Storage Manager

The storage manager owns artifact integrity and atomic filesystem operations.

Responsibilities:

- Model artifact staging and verification.
- Q4 KV cache persistence and restore scheduling.
- Immutable tool output blobs.
- Context checkpoints.
- Registry snapshots and rollback metadata.

All writable artifacts must use a two-phase write:

1. Write to temporary content-addressed path.
2. fsync and verify hash.
3. Atomically move or update registry pointer.

#### Tool Manager

MCP is the only supported tool protocol. Local shell, filesystem, browser, database, and device tools are MCP servers behind the access manager.

Tool invocation schema:

```json
{
  "tool_call_id": "tool_01HY...",
  "agent_id": "agent.codex.staff",
  "server_id": "mcp.filesystem.local",
  "tool_name": "read_file",
  "resource_indicators": ["file:///workspace/project/README.md"],
  "arguments": {
    "path": "/workspace/project/README.md",
    "start_line": 1,
    "end_line": 80
  },
  "limits": {
    "timeout_ms": 10000,
    "max_output_bytes": 65536
  },
  "approval": {
    "mode": "policy",
    "decision": "allow",
    "policy_id": "local-readonly-workspace"
  }
}
```

Boundary rules:

- Tool arguments are validated against JSON Schema before execution.
- Tool outputs are treated as untrusted and escaped before prompt insertion.
- Each tool call runs with explicit timeout, output cap, and resource indicators.
- Shell tools require argv arrays; shell-string execution is not part of the public contract.
- Path tools must reject traversal outside granted roots after canonicalization.

#### Access Manager

The access manager enforces identity, capability, authorization, and audit.

Identity model:

- Local agents have stable `agent_id`.
- A2A peers publish signed Agent Cards.
- Human users authenticate to local admin APIs with local auth or API key.
- Network-exposed endpoints require TLS or a trusted local mesh tunnel.

Policy decision schema:

```json
{
  "decision_id": "dec_01HY...",
  "subject": "agent.codex.staff",
  "action": "tool.invoke",
  "resource": "mcp.filesystem.local/read_file",
  "context": {
    "request_id": "req_01HY...",
    "trace_id": "4bf92f..."
  },
  "decision": "allow",
  "reason": "workspace_read_grant",
  "expires_at": "2026-05-19T17:00:00Z"
}
```

#### Model Lifecycle Manager

The model lifecycle manager is a first-class kernel service. It is not a shell script wrapped by a dashboard.

Model states:

```text
cataloged -> downloading -> downloaded -> verified -> staged -> warming
          -> candidate -> active -> retired -> archived
          -> failed
```

Lifecycle events:

```json
{
  "event_type": "model.stage.progress",
  "event_version": "v1",
  "model_id": "qwen3.6-coder-35b.gguf:q4_k_m",
  "operation_id": "op_01HY...",
  "progress": {
    "bytes_total": 21474836480,
    "bytes_completed": 6442450944,
    "eta_seconds": 920,
    "hash_verified": false
  },
  "timestamp": "2026-05-19T16:00:00Z"
}
```

#### Observability Manager

The observability manager exports:

- Traces: OTLP HTTP/gRPC.
- Metrics: Prometheus and OTLP metrics.
- Logs: structured JSON logs with trace and span IDs.
- Events: append-only local event log for offline debugging.

All requests must include or create:

- `request_id`
- `trace_id`
- `agent_id`
- `model_id`
- `job_id` when scheduled

### 4.2 Data Flows

#### Chat / Inference Flow

1. Client calls `/v1/chat/completions`.
2. Gateway authenticates request, validates schema, creates trace.
3. Gateway resolves model request through model router.
4. Scheduler admits job or returns structured retryable error.
5. Context manager restores or creates context slot.
6. Storage manager schedules KV cache restore when available.
7. Backend streams tokens.
8. Tool calls are routed through MCP Tool Manager and Access Manager.
9. Observability emits model, scheduler, context, tool, and hardware spans.
10. Context and KV state are checkpointed according to policy.

#### Agent Delegation Flow

1. Agent submits A2A `tasks/send` to local or peer Agent Card endpoint.
2. A2A gateway validates task, requested capabilities, and priority.
3. Access manager checks delegation grant.
4. Scheduler creates a job with inherited priority and parent trace context.
5. Task state is streamed through A2A task lifecycle events.
6. Result includes artifact references, not large inline blobs by default.

#### Model Promotion Flow

1. Admin or policy marks a verified model as `candidate`.
2. Model lifecycle manager prewarms candidate backend where hardware allows.
3. Scheduler stops admitting new jobs to the old active model and queues compatible new jobs.
4. In-flight jobs are drained, checkpointed, or continued according to request policy.
5. Active model pointer is atomically swapped.
6. Health checks run against the candidate.
7. If health checks pass, candidate becomes `active`; old active becomes `retired`.
8. If health checks fail, pointer reverts and candidate becomes `failed`.

### 4.3 Interface Contracts

#### OpenAI-Compatible API

Required endpoints:

```http
GET  /v1/models
POST /v1/chat/completions
POST /v1/responses
POST /v1/embeddings
```

Compatibility requirements:

- Accept standard OpenAI SDK request shapes where feasible.
- Support streaming via server-sent events.
- Preserve OpenAI-style error fields while adding local details under `error.details`.
- Do not expose internal stack traces.

Error shape:

```json
{
  "error": {
    "message": "Model qwen3.6-coder-35b is warming; retry after 2 seconds.",
    "type": "model_not_ready",
    "param": "model",
    "code": "MODEL_WARMING",
    "details": {
      "retry_after_ms": 2000,
      "active_model_id": "qwen3.6-coder-14b.gguf:q4_k_m",
      "operation_id": "op_01HY..."
    }
  }
}
```

#### A2A Gateway

Required endpoints:

```http
GET  /.well-known/agent-card.json
POST /a2a/jsonrpc
GET  /a2a/tasks/{task_id}/events
```

Agent Card minimum:

```json
{
  "schema_version": "a2a.agent_card.v1",
  "agent_id": "agent.codex.staff",
  "name": "Codex Staff Engineer",
  "description": "Implementation, API design, testing, and review agent.",
  "capabilities": [
    {
      "name": "code_review",
      "input_modes": ["text", "diff"],
      "output_modes": ["markdown", "json"],
      "max_context_tokens": 32768
    }
  ],
  "endpoints": {
    "jsonrpc": "http://127.0.0.1:${EDGEAI_A2A_PORT}/a2a/jsonrpc"
  },
  "auth": {
    "type": "local_api_key"
  },
  "signature": {
    "alg": "ed25519",
    "key_id": "local-agent-card-key",
    "value": "base64..."
  }
}
```

Task lifecycle states:

```text
submitted -> accepted -> working -> waiting_on_tool -> completed
                         |             |
                         |             -> failed
                         -> cancelled
```

#### MCP Integration

MCP requirements:

- Streamable HTTP support for local and remote MCP servers.
- OAuth Resource Server semantics when network exposed.
- RFC 8707 Resource Indicators for scoped resource access.
- Gateway-level audit event for every tool list, tool call, resource read, and prompt/template access.

MCP server registry:

```json
{
  "server_id": "mcp.filesystem.local",
  "transport": "streamable_http",
  "base_url": "http://127.0.0.1:${EDGEAI_MCP_FS_PORT}/mcp",
  "capabilities": ["tools", "resources"],
  "policy_ref": "policy.workspace_readwrite",
  "health": {
    "path": "/healthz",
    "timeout_ms": 1000
  }
}
```

#### Admin API

Admin endpoints:

```http
GET  /admin/v1/models
POST /admin/v1/models/{model_id}/download
POST /admin/v1/models/{model_id}/stage
POST /admin/v1/models/{model_id}/promote
POST /admin/v1/models/{model_id}/rollback
GET  /admin/v1/models/{model_id}/events
GET  /admin/v1/scheduler/queues
GET  /admin/v1/agents
GET  /admin/v1/traces/{trace_id}
```

Admin APIs must be local-authenticated by default and disabled on non-loopback interfaces unless explicitly configured.

### 4.4 Data Models

#### Model Registry

The model registry is JSON-driven, hot-reloadable, and schema-versioned.

```json
{
  "schema_version": "edgeai.model_registry.v1",
  "models": [
    {
      "model_id": "qwen3.6-coder-35b.gguf:q4_k_m",
      "display_name": "Qwen3.6 Coder 35B Q4_K_M",
      "family": "qwen",
      "version": "3.6",
      "format": "gguf",
      "quantization": "Q4_K_M",
      "artifact": {
        "uri": "https://models.example.invalid/qwen3.6-coder-35b-q4_k_m.gguf",
        "size_bytes": 21474836480,
        "sha256": "hex...",
        "license": "model-license-id"
      },
      "hardware_targets": [
        {
          "target": "cpu_igpu",
          "runtime": "llama_cpp",
          "recommended_ram_gb": 48,
          "min_ram_gb": 32,
          "gpu_layers_default": 28
        }
      ],
      "capabilities": ["chat", "code", "tool_use", "long_context"],
      "benchmarks": {
        "tokens_per_second_decode": 12.4,
        "ttft_ms_p50": 850,
        "quality_score": 0.83
      },
      "safety": {
        "allow_tool_use": true,
        "max_context_tokens": 32768
      },
      "lifecycle": {
        "state": "cataloged",
        "active_since": null,
        "retire_after": null
      }
    }
  ]
}
```

Registry rules:

- Registry changes are schema-validated before hot reload.
- Artifact hash is mandatory.
- Hardware targets are advisory until measured locally, then enriched with local benchmark metadata.
- Capability tags drive routing but must not bypass access checks.

#### Agent Registry

Agent registry entries are A2A Agent Cards plus local policy overlays.

```json
{
  "agent_id": "agent.codex.staff",
  "card_ref": "agent-card://agent.codex.staff/v1",
  "enabled": true,
  "default_queue": "agentic",
  "budgets": {
    "tokens_per_hour": 200000,
    "tool_calls_per_hour": 500,
    "max_concurrent_jobs": 2
  },
  "policy_refs": [
    "policy.workspace_readwrite",
    "policy.network_denied_by_default"
  ]
}
```

#### Event Envelope

All internal events use one envelope:

```json
{
  "event_id": "evt_01HY...",
  "event_type": "scheduler.job.started",
  "event_version": "v1",
  "timestamp": "2026-05-19T16:00:00Z",
  "trace_id": "4bf92f...",
  "span_id": "00f067aa0ba902b7",
  "actor": {
    "type": "agent",
    "id": "agent.codex.staff"
  },
  "subject": {
    "type": "job",
    "id": "job_01HY..."
  },
  "payload": {}
}
```

Events are append-only and suitable for offline replay in tests.

### 4.5 Implementation Architecture

Recommended service split:

| Service | Language | Why |
|---|---|---|
| `edgeai-gateway` | Go or Rust | stable HTTP, low memory, streaming, single binary |
| `edgeai-kernel` | Rust or Go | scheduler, lifecycle, event bus, strong concurrency guarantees |
| `edgeai-backend-llamacpp` | C++/Go wrapper | direct integration with llama.cpp |
| `edgeai-tool-runner` | Rust/Go | sandboxing, process control, resource limits |
| `edgeai-dashboard` | TypeScript | client of public Admin API |
| `edgeai-cli` | Go/Rust | same API as dashboard, scriptable JSON output |

Python is acceptable for eval harnesses and research workflows, but the always-on gateway/kernel path should avoid a heavy Python runtime on constrained devices.

Persistent stores:

- SQLite for local control-plane state and event log in v1.
- Filesystem content-addressed store for large artifacts.
- Optional vector store adapter for semantic memory.
- No external database dependency for single-node mode.

Internal dependency rule:

- Gateway depends on kernel API.
- Kernel depends on storage/access/observability interfaces.
- Backends implement inference adapter interfaces.
- Tools never call kernel internals directly.
- Dashboard and CLI call public APIs only.

---

## 5. Model Management (Pre-download + Hot-Swap)

### 5.1 Staging, Promotion, Retirement

Model lifecycle is a durable state machine.

States:

| State | Meaning | Allowed Next States |
|---|---|---|
| `cataloged` | Registry knows model, artifact absent | `downloading`, `archived` |
| `downloading` | Background fetch active | `downloaded`, `failed` |
| `downloaded` | Artifact exists, not verified | `verified`, `failed` |
| `verified` | Hash and metadata verified | `staged`, `archived` |
| `staged` | Ready on disk for prewarm | `warming`, `archived` |
| `warming` | Backend loading or mmap warming | `candidate`, `failed` |
| `candidate` | Eligible for promotion | `active`, `failed` |
| `active` | Current model for one or more routes | `retired`, `failed` |
| `retired` | Previously active, rollback eligible | `active`, `archived` |
| `archived` | Removed from active lifecycle | `cataloged` |
| `failed` | Failed download, verify, warm, promote, or health | `cataloged`, `archived` |

### 5.2 Pre-download

Requirements:

- Runs at `background` queue priority.
- Supports pause/resume.
- Emits progress events at least every 1s or every 64 MiB, whichever is less frequent.
- Verifies size and SHA256 before staging.
- Never mutates the active model pointer.
- Uses bandwidth and disk budgets from config.
- Stores incomplete artifacts under a non-routable temporary path.

Dashboard data:

```json
{
  "operation_id": "op_01HY...",
  "model_id": "qwen3.6-coder-35b.gguf:q4_k_m",
  "phase": "downloading",
  "bytes_total": 21474836480,
  "bytes_completed": 6442450944,
  "progress_pct": 30.0,
  "eta_seconds": 920,
  "throughput_bytes_per_second": 15728640,
  "hash": {
    "algorithm": "sha256",
    "expected": "hex...",
    "verified": false
  }
}
```

### 5.3 Hot-Swap

Target: less than 5s new-request interruption on supported edge hardware.

Swap phases:

1. `prepare`: ensure candidate is staged, verified, and warm enough.
2. `freeze_admission`: queue compatible new requests; reject only if queue deadline cannot be met.
3. `drain_or_checkpoint`: allow short in-flight requests to finish; checkpoint long-running requests if supported.
4. `flip_pointer`: atomically update route pointer from old backend to candidate backend.
5. `probe`: run health checks against candidate.
6. `resume_admission`: release queued requests.
7. `commit_or_rollback`: mark active on pass, revert on fail.

Swap policy schema:

```json
{
  "swap_policy": {
    "max_new_request_pause_ms": 5000,
    "inflight_drain_timeout_ms": 3000,
    "checkpoint_long_running": true,
    "health_check_timeout_ms": 60000,
    "rollback_on": [
      "health_check_failed",
      "p95_latency_regression",
      "backend_crash",
      "tool_call_regression"
    ]
  }
}
```

Implementation notes:

- Use llama-swap-style proxy routing as the portable v1 baseline.
- Use SwapServeLLM-style checkpoint/restore when backend and hardware support it.
- CPU-only GGUF systems may not meet the <5s full backend swap target unless prewarmed through mmap and route pointer flip; document per-hardware capability honestly.
- New-request downtime is measured at the gateway. In-flight streaming requests may continue on the old backend if resources permit.

### 5.4 Rollback

Rollback is automatic when:

- Candidate health endpoint fails.
- Smoke prompt output cannot be parsed.
- TTFT or error rate exceeds configured threshold.
- Backend crashes during probe.
- Safety guard refuses candidate model metadata or license.

Rollback event:

```json
{
  "event_type": "model.rollback.completed",
  "event_version": "v1",
  "from_model_id": "qwen3.6-coder-35b.gguf:q4_k_m",
  "to_model_id": "qwen3.6-coder-14b.gguf:q4_k_m",
  "reason": "health_check_failed",
  "swap_pause_ms": 1820,
  "timestamp": "2026-05-19T16:00:00Z"
}
```

### 5.5 Dashboard Integration

The dashboard must be a thin client of Admin API:

- Model catalog table: version, quantization, size, state, capability tags, local benchmark score.
- Download detail: progress, ETA, hash verification, current bandwidth.
- Staging detail: disk path, verification status, warm status.
- Promotion panel: current active model, candidate, estimated swap impact, rollback target.
- Event stream: lifecycle events and trace links.
- Guardrails: promotion requires explicit confirmation unless an automatic policy is configured.

---

## 6. Key Design Decisions (with rationale)

### Decision 1: Standard protocols at all external boundaries

Use OpenAI-compatible APIs for application clients, A2A for agent coordination, MCP for tool access, and OTLP/OpenTelemetry for observability.

Rationale: The 2026 agent protocol stack is converging around MCP plus A2A. Custom protocols create integration cost without adding edge-specific value.

### Decision 2: Local AI kernel instead of direct backend proxying

Do not let clients call llama.cpp, Ollama, or vLLM directly. All requests enter through the gateway and scheduler.

Rationale: Direct calls bypass admission control, context ownership, cancellation, budgets, audit, and hot-swap safety. AIOS and AgentRM show that OS-style management materially improves multi-agent serving.

### Decision 3: GGUF Q4_K_M / Q4_K_XL first for CPU+iGPU edge

Default to GGUF for v1 edge hardware, with AWQ/GPTQ/EXL2 as backend-specific extensions.

Rationale: GGUF is the most portable format for CPU-primary and hybrid iGPU systems. Q4_K_M and Q5_K_M are strong tradeoff points according to llama.cpp quantization evaluations. GPU-native formats are important, but they should not define the baseline.

### Decision 4: Durable state machines for lifecycle operations

Downloads, staging, promotion, rollback, task execution, and context checkpointing must be durable state machines.

Rationale: Edge devices power cycle, lose network, and run out of disk. A restart-safe state machine is simpler to test and safer than imperative scripts.

### Decision 5: Event-sourced debugging, not log scraping

Every kernel state transition emits a structured event. Logs are for humans; events are for replay, tests, dashboard, and automation.

Rationale: Multi-agent failures are distributed across scheduler, tools, model backend, and memory. Replayable event streams make failures inspectable.

### Decision 6: Tool outputs are untrusted artifacts

Tool outputs must be stored as immutable artifacts and selectively summarized or inserted into prompts.

Rationale: MCP tools can return prompt injection payloads, huge outputs, malformed JSON, or sensitive data. Treating outputs as untrusted artifacts makes escaping, truncation, provenance, and audit enforceable.

### Decision 7: Scheduler owns thermal and memory admission

The scheduler must consider thermal state, memory pressure, KV cache pressure, and model lifecycle state before admitting work.

Rationale: Edge performance collapses under thermal throttling. Sustainable inference studies show thermal constraints are a primary limiter on mobile and APU hardware.

### Decision 8: Dashboard cannot be privileged magic

The dashboard uses public Admin API endpoints and has no direct filesystem or daemon access.

Rationale: This keeps automation, CLI, and UI behavior consistent and testable.

### Decision 9: Split inference is an adapter, not a v1 dependency

The execution backend interface should support split inference and FedAttn later, but single-node offline inference remains the v1 critical path.

Rationale: Adaptive split inference is promising for edge meshes, but it adds network, privacy, and scheduling complexity. The baseline must be reliable offline.

### Decision 10: Security policy at code boundary

Policy enforcement belongs at tool invocation, file access, model artifact ingestion, network calls, and memory sharing boundaries, not only at prompt moderation.

Rationale: Agentic systems fail through actions, not just generated text.

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hot-swap exceeds <5s on CPU-only devices | User-visible pause | Report per-hardware capability; prewarm with mmap; queue new requests; keep old backend serving streams when possible |
| KV cache corruption or incompatible cache after model change | Wrong outputs or crashes | Include model hash, tokenizer hash, quantization, and context schema in KV cache header; reject incompatible restores |
| Tool prompt injection through MCP output | Data exfiltration, unsafe actions | Treat tool output as untrusted; provenance tagging; output caps; policy checks before follow-up tool calls |
| Agent Card spoofing on edge mesh | Malicious delegation | Signed Agent Cards; trust roots; local allowlist; gossip quarantine for unsigned peers |
| Model artifact supply-chain compromise | Unsafe or malicious model | Mandatory hash verification, signatures where available, license metadata, offline allowlist |
| Scheduler starvation of background tasks | Maintenance never completes | MLFQ aging and reserved background slots under low pressure |
| Event volume overwhelms disk | Device fills storage | Bounded retention, compression, event sampling for high-frequency decode events, critical events never sampled |
| OTel semantic conventions change | Instrumentation churn | Isolate OTel mapping in adapter layer; keep internal event schema stable |
| Split inference leaks sensitive activations | Privacy violation | Disabled by default; policy gate; FedAttn or encrypted transport for approved deployments |
| NixOS-first becomes NixOS-only | Reduced adoption | Keep service binaries portable; Nix modules are packaging, not architecture |
| Dashboard promotion misuse | Bad model promoted | Health probes, confirmation gates, policy-based auto-rollback, audit log |
| Long-running streams during swap | Resource contention | Per-request swap policy: drain, continue on old backend, or checkpoint/cancel |

---

## 8. Research Citations Used

- AIOS: LLM Agent Operating System, arXiv:2403.16971. Used for the application/kernel/hardware layering and core kernel components: scheduler, context manager, memory manager, storage manager, tool manager, access manager.
- AgentRM: OS-Inspired Resource Manager, arXiv:2603.13110. Used for MLFQ scheduling, zombie reaping, rate-limit-aware admission control, and context lifecycle management.
- HiveMind: OS-Inspired Scheduling Proxy, arXiv:2604.17111. Used for admission control, AIMD backpressure, priority queues, token budgets, and proxy-compatible deployment.
- Astraea: State-Aware Scheduling Engine, arXiv:2512.14142. Used for request lifecycle awareness and adaptive KV cache decisions during I/O waits.
- Agent.xpu: Heterogeneous SoC Scheduling, arXiv:2506.24045. Used for reactive/proactive workload split and heterogeneous CPU/iGPU/NPU scheduling.
- Agent Persistent Q4 KV Cache, arXiv:2603.04428. Used for per-agent Q4 KV cache persistence and reload hidden behind decode phases.
- AMV-L Lifecycle-Managed Agent Memory, arXiv:2603.04443. Used for value-driven memory tiering rather than TTL/LRU-only policies.
- SwapServeLLM, ACM SC 2025. Used for hot-swap design, checkpoint/restore concepts, and sub-5s swap ambition.
- llama-swap, mostlygeek/llama-swap. Used as the practical proxy model for OpenAI-compatible local backend swapping, preloading, and dashboard/log streaming.
- Tangram, arXiv:2512.01357. Used for memory mapping, model loading, and cold-start reduction concepts.
- Adaptive Split Inference Orchestration, arXiv:2504.03668. Used for future split-inference backend adapter design.
- Federated Attention, arXiv:2511.02647. Used as a future privacy-preserving distributed attention option.
- Gossip Protocols for Agentic AI, arXiv:2508.01531, and Edge General Intelligence, arXiv:2508.18725. Used for decentralized edge peer discovery and sparse message passing.
- 3D Guard-Layer, arXiv:2511.08842, and SoK Security and Safety of Edge AI, arXiv:2410.05349. Used for local safety monitoring and edge attack-surface framing.
- A2A Protocol, Google/Linux Foundation, 2025-2026. Used for Agent Cards, JSON-RPC 2.0 task lifecycle, and inter-agent context sharing.
- MCP, Linux Foundation Agentic AI Foundation roadmap 2026. Used for Streamable HTTP, OAuth resource server semantics, audit trails, and tool access.
- OpenTelemetry GenAI Semantic Conventions, 2025-2026. Used for model, agent, tool, token, cost, and latency instrumentation.
- Dynamic Model Routing and Cascading, arXiv:2603.04445. Used for complexity-aware routing and Agreement-Based Cascading.
- Sustainable LLM Inference Energy Study, arXiv:2504.03360. Used for thermal-aware scheduling and dynamic quantization decisions.
- Unified Evaluation of llama.cpp Quantizations, arXiv:2601.14277. Used for GGUF Q4_K_M/Q5_K_M edge quantization defaults.
- OpenHarness, HKUDS. Used for the implementation principle separating intelligence layer from execution layer, plus tools/skills/plugins/permissions/hooks/memory/coordinator modularity.

---

## 9. Comparison Hooks

Because this is a greenfield reference design, these hooks are phrased against a typical current local AI harness, including systems that resemble the current NixOS-Dev-Quick-Deploy stack.

### Where current system is AHEAD

- NixOS-first reproducibility is already a strong foundation. Many current stacks already have declarative services, flake-based environments, and repeatable local deployment, which should be preserved.
- CLI-first workflows are often more mature than greenfield dashboards. Existing command-line automation, health checks, validation gates, and local reports are valuable.
- Existing systems may already have practical agent workflows, skill registries, prompt templates, and project memory that are more complete than a greenfield kernel.
- Local operational knowledge is ahead of theory. Current scripts often encode real hardware quirks, service restart behavior, and model-specific workarounds that a clean design does not yet know.
- If a system already has CI-style validation gates and agent collaboration handoff files, that is an operational maturity advantage.

### Where current system SHOULD CHANGE

- Replace ad hoc internal contracts with versioned schemas for jobs, events, model registry, agent registry, tool calls, memory items, and lifecycle operations.
- Move model lifecycle from manual service operations to a durable model lifecycle manager with background download, staging, promotion, rollback, and dashboard-visible events.
- Make scheduler/admission control a central kernel service rather than incidental queueing around HTTP calls.
- Adopt A2A Agent Cards for agent discovery and capability advertisement instead of static, local-only skill registries.
- Enforce MCP as the tool boundary, including resource indicators, schema validation, output caps, and tool-call audit.
- Emit OTel GenAI traces across gateway, scheduler, model backend, tools, memory, and hardware, rather than fragmented logs and per-script reports.
- Treat KV cache and context as managed resources with ownership and compatibility metadata.
- Add thermal and memory pressure to admission decisions, especially for APU/iGPU hardware.
- Make the dashboard a client of Admin API rather than a privileged process with direct state access.

### Where current system can be PRESERVED

- NixOS modules, flake shells, systemd service wiring, and reproducible local deployment approach.
- Existing CLI culture and validation discipline, provided commands are backed by stable JSON APIs where automation depends on them.
- Existing project memory and document corpus, migrated behind a typed memory manager rather than discarded.
- Existing health checks and tiered validation gates, extended with contract tests, event replay tests, and model lifecycle simulation.
- Existing local model backends where they can be wrapped by the gateway/backend adapter contract.
- Existing agent role definitions, mapped into A2A Agent Cards and policy overlays.

---

## 10. Open Questions for Combined PRD

1. Which implementation language should own the always-on kernel: Go for operational simplicity, Rust for type and memory safety, or a mixed approach?
2. What is the exact v1 hardware floor: 8 GB RAM CPU-only, 16 GB APU, or 32 GB hybrid iGPU?
3. Is the <5s hot-swap target required for all hardware classes, or should the SLA be capability-tiered?
4. Should llama-swap be adopted directly as the v1 proxy baseline, forked, or reimplemented behind the gateway contract?
5. What is the minimal A2A subset required for v1: Agent Cards and task lifecycle only, or context sharing and UX negotiation too?
6. How strict should MCP-only tool access be for local development escape hatches?
7. What trust model should edge mesh use: local allowlist, shared CA, WebAuthn/device identity, or signed Agent Cards only?
8. Should split inference be included in v1 architecture tests, or deferred entirely until single-node lifecycle and scheduler are stable?
9. Which OTel backend is the default local developer experience: Jaeger, Grafana/Tempo, Phoenix, or file-backed traces with optional export?
10. What model quality and safety health checks are sufficient to auto-promote or auto-rollback a model without human review?
11. How should long-running in-flight streaming requests behave during hot-swap: always drain, continue on old backend, or checkpoint/cancel based on request policy?
12. What is the policy for memory sharing between agents: explicit grant only, project-level shared semantic memory, or signed fact publication?
13. Should model registry entries be locally authored JSON, signed remote catalogs, or both?
14. How much dashboard functionality belongs in v1 versus CLI-only Admin API plus event stream?
15. What compatibility guarantees should be made for OpenAI API deviations, especially tool calling and `/v1/responses` behavior?

---

## Appendix A: Test Strategy

### Contract Tests

- OpenAI compatibility tests using official SDK request shapes.
- A2A Agent Card schema and JSON-RPC task lifecycle tests.
- MCP Streamable HTTP tool list/call/resource tests.
- Admin API schema tests for model lifecycle and scheduler endpoints.
- Event envelope schema tests for every emitted event type.

### Scheduler Tests

- MLFQ priority ordering.
- Priority inheritance through delegated A2A tasks.
- Admission rejection under memory pressure.
- Queueing under model warming.
- Cancellation of queued and active jobs.
- Zombie reaping after stalled progress.
- Background task aging to prevent starvation.

### Model Lifecycle Tests

- Download resume after process restart.
- Hash mismatch marks model `failed`.
- Staged model cannot become active without verification.
- Promotion queues new requests during pointer flip.
- Failed health check triggers rollback.
- Rollback restores previous route pointer.
- Event replay reconstructs final lifecycle state.

### Context and Memory Tests

- KV cache restore rejects incompatible model/tokenizer/context schema.
- Tool-call context invalidation produces expected checkpoint.
- Compaction preserves provenance references.
- Memory ACL denies cross-agent private read.
- AMV-L-style utility scoring demotes low-value items under pressure.

### Security Tests

- Path traversal rejection after canonicalization.
- Shell-string execution is rejected at API boundary.
- Tool outputs containing prompt injection text are stored as untrusted artifacts.
- Unsigned Agent Card is rejected or quarantined in mesh mode.
- Network-exposed admin API refuses unauthenticated calls.
- Model artifact without hash cannot be staged.
- Resource indicators are required for scoped MCP resources.

### Observability Tests

- Every inference request produces gateway, scheduler, model, and response spans.
- Tool calls are children of the agent task span.
- Model swap emits phase events with shared operation ID.
- Errors include trace ID and stable error code.
- Metrics include TTFT, decode tokens/sec, queue wait, active model, cache hit rate, and thermal state.

### Local Smoke Tests

```text
edgeai doctor
edgeai models list --json
edgeai models download <small-test-model>
edgeai models promote <small-test-model>
edgeai chat --model <small-test-model> "Say pong"
edgeai a2a card validate
edgeai mcp tools list
edgeai traces tail --last 1
```

### Acceptance Criteria

- A developer can install the harness, start it, list models, download a small model, promote it, and issue an OpenAI-compatible chat request with no manual service edits.
- A model promotion either completes within the configured hardware SLA or emits a structured SLA miss event and leaves the previous active model serving.
- A failed candidate health check automatically rolls back.
- A2A Agent Card validation passes for local agents.
- MCP tool calls are schema-validated, policy-checked, audited, and trace-linked.
- All public APIs have JSON Schema or OpenAPI coverage.
- Event replay can reconstruct scheduler and model lifecycle state for the last 24 hours.
- No default configuration exposes admin or tool endpoints beyond loopback.
