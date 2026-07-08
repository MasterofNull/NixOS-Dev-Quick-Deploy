# Antigravity — F3 Design: CapabilityLease Contract + OTel Observability + Signed Envelope

## 1. Top 3 Design Decisions

1. **Monotonic CapabilityLease Attenuation**: Instead of ad-hoc feature flags and env variables, every capability (MCP servers, system capabilities, model lanes) is governed by a unified `CapabilityLease` contract. When executing under `zero_trust`, the lease contract statically restricts the write scope and disables unsafe shell access, making least-privilege compile-time guaranteed.
2. **OTel Semantic Span Correlation**: Turn boundaries and tool-calls are modeled as OpenTelemetry parent/child spans. This enables standard tracer exporters (Jaeger, OpenTelemetry Collector) to collect latency, parameters, and tokens automatically, rendering the live dashboard events panel instantly compliant with Grafana dashboards.
3. **Workspace Isolation via Git Worktrees (Zero-Risk Writing)**: Before any execution lane writes to files, a temporary git worktree is spawned (`.git/worktrees/agent-task-...`). On success (validation gate GREEN), changes are merged into the main development branch. On failure or lease timeout, the worktree is deleted, ensuring the main workspace remains pristine.

---

## 2. CapabilityLease Contract Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "3.0",
  "lease_id": "string (UUID)",
  "lease_version": "1.0",
  "issued_to": "string (agent_role or session_id)",
  "issued_at": "string (ISO8601)",
  "expires_at": "string (ISO8601)",
  "source": "mcp_server|tool|skill|model|remote_lane",
  "permissions": {
    "actions": ["read_file", "search", "write_file", "execute_command"],
    "paths": ["/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/*"],
    "network": {
      "allowed_domains": [],
      "blocked_domains": ["*"]
    }
  },
  "constraints": {
    "max_execution_sec": 30,
    "max_token_budget": 5000,
    "zero_trust": true
  },
  "signature": "string (ecdsa/ed25519 hash of the token)"
}
```

---

## 3. OpenTelemetry Observability Model

We define the following OpenTelemetry span mappings:
- **Parent Span (`agent_turn`)**: Triggered at the entry of the agent loop.
  - Attributes: `agent.role`, `agent.model`, `session.id`, `round.id`, `tokens.input`, `tokens.output`.
- **Child Span (`tool_execution`)**: Spanned during tool execution.
  - Attributes: `tool.name`, `tool.lease_id`, `tool.arguments`, `tool.exit_code`, `zero_trust.mode`.
- **Child Span (`validation_check`)**: Spanned during pre-commit gates.
  - Attributes: `check.name`, `check.status` (PASS/FAIL), `check.duration_ms`.

Exporters write JSON-lines span records to a locally mounted OTEL daemon endpoint, feeding Grafana and the Dashboard telemetry panel in real-time.

---

## 4. Signed A2A Envelope & Heartbeat

To securely bridge remote agents (like Antigravity IDE) and the local coordinator node:
- **Task Envelope**: The coordinator drops a signed JSON task packet:
  ```json
  {
    "round_id": "f3-capability-otel",
    "task_prompt": "string",
    "deadline": "string",
    "idempotency_key": "string",
    "expected_output_path": "string",
    "signature": "string (signed by coordinator key)"
  }
  ```
- **Liveness Heartbeat**: While working on a long compilation, the Antigravity agent daemon touches `/tmp/antigravity-liveness` every 20 seconds. If a heartbeat is missed for 60 seconds, the coordinator transitions the lane in `round.json` to `pending-late` or `failed`.

---

## 5. Automatic Worktree-Scoped Rollback

1. **Snapshot Stage**: Executor detects a write-capable action. Spawns an isolated git worktree:
   `git worktree add -d <worktree_dir> <branch>`
2. **Execute Stage**: The agent changes code exclusively in the worktree workspace.
3. **Validate Stage**: Run `scripts/governance/tier0-validation-gate.sh` inside the worktree environment.
4. **Assert Outcome**:
   - **On Green**: Merge the worktree branch into the active workspace branch and prune:
     `git worktree remove <worktree_dir>`
   - **On Red/Timeout**: Instantly drop the worktree, restoring the system state with zero risk to untracked files or concurrent runs.
