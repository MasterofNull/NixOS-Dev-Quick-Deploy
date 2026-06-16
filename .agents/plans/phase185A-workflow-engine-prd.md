---
doc_type: prd
id: phase185A-workflow-engine-prd
title: "Phase 185A — Workflow Execution Engine: Implement Runtime, Wire Agent Loop, Enable Parallel Decomposition"
status: draft
owner: architect
phase: "Phase 185A"
priority: P1-high
evidence_required: delegate-to-local --mode agent with multi-step workflow prompt executes ≥2 steps in parallel; workflow_execution events appear in telemetry; aq-qa workflow check passes
---

# Phase 185A — Workflow Execution Engine

## 1. Problem Statement

### Current State

The workflow execution layer is architecturally hollow. Every call to `execute_workflow()` in
`ai-stack/workflows/coordinator.py` routes through one of two methods:

- `_execute_sync()` (line 149–186): sets `status = "completed"` and returns
  `{"result": "Workflow execution not yet implemented"}`.
- `_execute_async()` (line 188–220): transitions to `"running"`, calls `asyncio.sleep(1)`,
  then sets `status = "completed"` with the same stub string.

This means no YAML workflow has ever actually executed through the harness. Every invocation
since `WorkflowCoordinator` was introduced has silently short-circuited.

### Downstream Impact

1. **No parallel decomposition is possible.** The architecture was designed around multi-step
   task decomposition with parallelization strategies (see `config/workflow-automation.yaml`
   `executor.max_parallel_tasks: 5`), but nothing dispatches parallel sub-agents.

2. **All agent delegation is serial single-step.** `aq-agent-loop` calls `delegate_to_remote`
   or local llama.cpp for individual tasks; there is no mechanism to decompose a prompt into
   N sub-tasks and gather results.

3. **`workflow_executor.py` in the coordinator's `workflow/` directory is an orphan.**
   `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py` (`WorkflowExecutor`,
   `WorkflowPhaseExecutor`) has full retry logic, polling, and session file management, but is
   never instantiated or called from `agent_executor.py`, `aq-agent-loop`, or any coordinator
   HTTP handler path.

4. **`yaml_workflow_handlers.py` is reachable via HTTP but executes nothing.**
   `POST /api/workflows/execute` delegates to `WorkflowCoordinator.execute_workflow()`, which
   hits the stub.

5. **The hot-swap keyword map in `agent_executor.py` (line 100) can inject
   `get_workflow_status` into a running agent turn**, but there is no corresponding
   `execute_workflow` tool — only status polling of already-dead executions.

### Evidence

| Location | Line | Stub Text |
|---|---|---|
| `ai-stack/workflows/coordinator.py` | 162 | `"Workflow execution not yet implemented"` |
| `ai-stack/workflows/coordinator.py` | 205 | `"Workflow execution not yet implemented"` |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py` | exists, 706L | Never instantiated from coordinator entry points |
| `ai-stack/local-agents/agent_executor.py` | 100 | `_AEXEC_WORKFLOW_KW` hot-swap injects `get_workflow_status` only, no execute |

---

## 2. Architecture Overview

The intended end-to-end flow, showing where each existing file fits:

```
aq-agent-loop / delegate-to-local --mode agent
  │
  │  Task contains workflow keyword (line 89-100, agent_executor.py)
  │  OR task prefix is "workflow:" / explicit YAML file provided
  │
  ▼
LocalAgentExecutor._run_agent_loop()        [agent_executor.py]
  │
  │  Detects workflow trigger condition
  │  Calls new tool: execute_workflow(yaml_file, inputs)
  │
  ▼
WorkflowTriggerTool                         [NEW — local-agents/workflow_trigger_tool.py]
  │  Validates YAML path, builds inputs dict from task context
  │
  ▼
WorkflowCoordinator.execute_workflow()      [ai-stack/workflows/coordinator.py]
  │  parse_file()  →  WorkflowParser        [ai-stack/workflows/parser.py]        COMPLETE
  │  validate_all()  →  WorkflowValidator   [ai-stack/workflows/validator.py]      COMPLETE
  │  state_store.save()  →  WorkflowStateStore [ai-stack/workflows/persistence.py] COMPLETE
  │
  ├─► _execute_sync()   ─────────────────── [STUB — Phase 185A.A fills this]
  │     │
  │     │  Reads workflow.nodes, builds DependencyGraph
  │     │  DependencyGraph.get_parallel_batches() → List[List[WorkflowNode]]
  │     │
  │     ▼
  │   WorkflowNodeDispatcher                [NEW — ai-stack/workflows/node_dispatcher.py]
  │     │
  │     │  For each parallel batch:
  │     │  asyncio.gather(*[_dispatch_node(node) for node in batch])
  │     │
  │     ▼
  │   _dispatch_node(node)
  │     │
  │     │  Selects agent lane based on node.agent / node.capabilities
  │     │  Emits telemetry: workflow_step_dispatched
  │     │  Routes to ONE of:
  │     │
  │     ├─► /control/agents/spawn           [WorkflowPhaseExecutor — workflow_executor.py L537]
  │     │     (local harness sub-agent via coordinator REST, already implemented)
  │     │
  │     ├─► delegate_to_remote              [ai_coordination.py — delegate_to_remote_handler]
  │     │     (remote Codex/Gemini delegation)
  │     │
  │     └─► Local llama.cpp direct call     [build_llama_payload — shared/llm_config.py]
  │           (for bounded, fast local tasks)
  │
  │   Collect asyncio.gather results
  │   Map node outputs → next batch inputs (dependency injection)
  │   Emit: workflow_step_complete per node
  │
  ▼
WorkflowCoordinator._aggregate_results()   [NEW method]
  │  Merges per-node outputs into final result dict
  │  Emits: workflow_aggregated
  │
  ▼
Telemetry sink                             [.agents/telemetry/hybrid-events.jsonl]
  │
  ▼
Dashboard panels                           [dashboard/backend/api/routes/aistack.py]
```

Key observation: `WorkflowPhaseExecutor._delegate_phase_execution()` (line 537 of
`workflow_executor.py`) already builds a correct REST call to
`/control/agents/spawn`. The gap is upstream — `WorkflowCoordinator._execute_sync()` never
calls any of this.

---

## 3. What Exists vs What's Missing

| Component | File Path | Status |
|---|---|---|
| Workflow YAML parser | `ai-stack/workflows/parser.py` | Complete |
| Workflow YAML validator | `ai-stack/workflows/validator.py` | Complete |
| Workflow models (`Workflow`, `WorkflowNode`, etc.) | `ai-stack/workflows/models.py` | Complete |
| Dependency graph (`DependencyGraph`) | `ai-stack/workflows/graph.py` | Complete (has `to_mermaid`, `to_visualization_payload`) |
| State persistence (`WorkflowStateStore`) | `ai-stack/workflows/persistence.py` | Complete |
| `WorkflowCoordinator` skeleton | `ai-stack/workflows/coordinator.py` | Stub — `_execute_sync` L149, `_execute_async` L188 |
| Phase-level executor with retry | `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py` | Complete but unwired — never instantiated |
| YAML workflow HTTP handlers | `ai-stack/mcp-servers/hybrid-coordinator/workflow/yaml_workflow_handlers.py` | Routes wired, calls coordinator stub |
| Orchestration HTTP handlers | `ai-stack/mcp-servers/hybrid-coordinator/workflow/orchestration_handlers.py` | Complete (agent spawn, delegation API) |
| Runtime manager / policy loading | `ai-stack/mcp-servers/hybrid-coordinator/workflow/runtime_manager.py` | Complete |
| Workflow config | `config/workflow-automation.yaml` | Complete (max_parallel_tasks=5, retry, timeouts) |
| Workflow examples + templates | `ai-stack/workflows/examples/`, `ai-stack/workflows/templates/` | 18 YAML files — complete |
| `execute_workflow` agent tool | NOT YET CREATED | Missing |
| `WorkflowTriggerTool` wire-up | NOT YET CREATED | Missing |
| `_execute_sync` / `_execute_async` bodies | `ai-stack/workflows/coordinator.py` L149, L188 | Stub → must implement |
| `WorkflowNodeDispatcher` (parallel batch runner) | NOT YET CREATED | Missing |
| `_aggregate_results()` coordinator method | NOT YET CREATED | Missing |
| Telemetry events (`workflow_started`, etc.) | NOT YET CREATED | Missing |
| Agent loop workflow trigger detection | `ai-stack/local-agents/agent_executor.py` | Partially stubbed (keyword hot-swap L89-100 adds `get_workflow_status` only) |
| ralph-wiggum loop engine | `ai-stack/mcp-servers/ralph-wiggum/loop_engine.py` | Complete loop mechanics, no workflow awareness |
| `aq-auto-remediate.py` PRSI integration | `scripts/ai/aq-auto-remediate.py` | TODO placeholder — deferred |
| `meta_optimizer.analyze_tool_discovery()` | `ai-stack/meta-optimization/meta_optimizer.py` L486 | Returns None — deferred |
| Dashboard workflow panels | `dashboard/backend/api/routes/aistack.py` | Missing (no workflow routes) |

---

## 4. Relationship to Agentic Mind Standardization PRD

`PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md` (Phase 148) defines 7 PR items. The following
overlap directly with Phase 185A:

| PR Item | Title | Overlap with 185A |
|---|---|---|
| **PR-1** | Canonical Agent Task Envelope | **Direct dependency.** Every workflow node dispatched as a sub-agent must carry the versioned task envelope (`task_id`, `agent_type`, `role`, `workflow_phase`, `output_contract`). The `WorkflowNodeDispatcher` must emit PR-1-compliant envelopes to `/control/agents/spawn` and `delegate_to_remote`. |
| **PR-4** | Output Guardrails Before Acceptance | **Direct dependency.** Node results aggregated by `_aggregate_results()` must pass PR-4 output validators before they are accepted as step outputs. JSON nodes must parse; implementation nodes must name changed files. |
| **PR-5** | Unified Trace Path | **Direct dependency.** Workflow telemetry events (`workflow_started`, `workflow_step_dispatched`, `workflow_step_complete`, `workflow_aggregated`) must carry the same `gen_ai.*` trace attributes defined in PR-5 so cross-node runs are replayable. |
| **PR-2** | Workflow Adherence Evaluator | **Indirect dependency.** The evaluator added in PR-2 should score per-node agent responses inside the workflow execution loop, feeding the `workflow_step_complete` event. Phase 185A should emit the raw response + acceptance criteria to make PR-2 scoring possible without re-running the workflow. |
| **PR-7** | Agent Interop Scorecard | **Indirect.** Parallel speedup ratio and per-node first-pass contract score are natural inputs to the PR-7 scorecard. Phase 185A should write these as structured fields on `workflow_aggregated` events so PR-7 can read them without re-parsing logs. |

**PRs NOT touched by 185A:** PR-3 (local model re-probe gate), PR-6 (prompt assembly SSOT audit).

**Dependency ordering:** PR-1 task envelope must be available before Phase 185A Phase B wires
the agent loop. PR-4 output validators should be available before Phase 185A Phase C parallel
dispatch, but can be stubbed with a passthrough gate initially.

---

## 5. Goals and Success Criteria

### Goals

1. Replace the stub bodies in `WorkflowCoordinator._execute_sync()` and `_execute_async()`
   with real node-level execution.
2. Enable parallel execution of independent workflow nodes in the same topological batch.
3. Wire the agent loop (`aq-agent-loop` / `agent_executor.py`) to trigger workflow execution
   when task input signals a multi-step plan.
4. Emit structured telemetry for all workflow lifecycle events.
5. Provide dashboard panels for live workflow monitoring.

### Success Criteria (Measurable)

| Criterion | Target | How Measured |
|---|---|---|
| Parallel step execution | `delegate-to-local --mode agent` with a 4-node parallel workflow executes nodes in ≥2 concurrent batches | `workflow_step_dispatched` events with same `batch_id` appear within 2 s of each other in telemetry |
| Workflow latency reduction vs serial | Parallel path completes in ≤60% of the time a sequential path would take for the same 4-node workflow | Computed `parallel_speedup_ratio` field on `workflow_aggregated` event ≥1.4 |
| Success rate | ≥80% of triggered workflows reach `status=completed` in a clean environment | `aq-qa` workflow check reports success_rate ≥0.80 over last 24 h |
| Telemetry coverage | All 4 event types appear in `hybrid-events.jsonl` after one workflow run | `grep workflow_started .agents/telemetry/hybrid-events.jsonl` returns ≥1 result |
| Agent loop integration | `aq-agent-loop --task "run workflow ai-stack/workflows/examples/parallel-tasks.yaml"` triggers and completes without error | Exit code 0, JSON output contains `workflow_execution_id` |
| aq-qa gate | `aq-qa 0` workflow section reports pass | `aq-qa 0 | grep workflow` shows green |

---

## 6. Scope

### In Scope

- Implement `_execute_sync()` body: node traversal, dependency-ordered batch dispatch, result
  collection, state persistence, telemetry emission.
- Implement `_execute_async()` body: same as sync, wrapped in background thread with status
  transitions.
- Create `WorkflowNodeDispatcher` to manage parallel batch execution via `asyncio.gather`.
- Add `_aggregate_results()` method to `WorkflowCoordinator`.
- Add `execute_workflow` tool to `ToolRegistry` (agent_executor tool registration).
- Wire `_AEXEC_WORKFLOW_KW` hot-swap in `agent_executor.py` to inject `execute_workflow` tool
  (not just `get_workflow_status`).
- Add explicit workflow trigger in `aq-agent-loop` for `--workflow` flag or `workflow:` task
  prefix.
- Emit 4 new telemetry events: `workflow_started`, `workflow_step_dispatched`,
  `workflow_step_complete`, `workflow_aggregated`.
- 5 new dashboard panels (see Section 10).
- `aq-qa` checks for workflow execution (see Section 11).
- `WorkflowPhaseExecutor` instantiation from within `_execute_sync()` (it already exists at
  `workflow_executor.py` — just needs to be imported and called).

### Out of Scope (Deferred)

- `ralph-wiggum/loop_engine.py` loop control TODOs — loop engine is a separate runtime; its
  integration with workflow sessions is a future phase.
- `aq-auto-remediate.py` PRSI integration TODO — requires PRSI event bus to be implemented.
- `meta_optimizer.analyze_tool_discovery()` returning None — meta-optimizer is a separate
  system; its null return does not block workflow execution.
- Distributed execution (feature flag `features.experimental.distributed_execution` in
  `workflow-automation.yaml` is `false` — stays false).
- ML success prediction (`ml_success_prediction: false` in config — stays false).
- WorkflowCoordinator sub-workflow recursion (`examples/sub-workflow.yaml`) — valid in the
  model but not wired in Phase 185A.
- Template manager storage path fix (`templates.storage_path: "/tmp/workflow-templates"` is
  blocked by AppArmor — see issue backlog — deferred to separate NixOS service hardening task).

---

## 7. Technical Approach

### 7.1 `_execute_sync()` Implementation

**File:** `ai-stack/workflows/coordinator.py`, method `_execute_sync` starting at line 149.

Replace the TODO block with the following logic:

```python
async def _execute_sync(self, execution_id, workflow, inputs):
    execution_state = self.active_executions[execution_id]
    execution_state["status"] = "running"
    await self.state_store.save(execution_id, execution_state)
    _emit_telemetry("workflow_started", execution_id, workflow.name, node_count=len(workflow.nodes))

    graph = DependencyGraph(workflow)
    batches = graph.get_parallel_batches()          # topological sort → List[List[WorkflowNode]]
    dispatcher = WorkflowNodeDispatcher(
        execution_id=execution_id,
        coordinator_url=self._coordinator_url(),    # reads COORDINATOR_URL env or default
        config=_load_executor_config(),             # reads config/workflow-automation.yaml executor block
    )
    node_outputs: Dict[str, Any] = dict(inputs)    # seed with workflow inputs
    failed_nodes = []

    for batch_index, batch in enumerate(batches):
        batch_id = f"{execution_id[:8]}-b{batch_index}"
        results = await dispatcher.dispatch_batch(batch, node_outputs, batch_id)
        for node_id, result in results.items():
            if result.get("status") == "failed":
                failed_nodes.append(node_id)
                if not _executor_config().get("allow_partial_completion", False):
                    raise WorkflowStepError(f"Node {node_id} failed: {result.get('error')}")
            node_outputs[node_id] = result.get("output", "")

    aggregated = _aggregate_results(workflow, node_outputs)
    _emit_telemetry("workflow_aggregated", execution_id, workflow.name,
                    node_count=len(workflow.nodes), failed_count=len(failed_nodes),
                    parallel_speedup_ratio=dispatcher.speedup_ratio())

    execution_state["status"] = "completed"
    execution_state["completed_at"] = datetime.now(timezone.utc).isoformat()
    execution_state["outputs"] = aggregated
    await self.state_store.save(execution_id, execution_state)
    return {"status": "completed", "execution_id": execution_id,
            "workflow": workflow.name, "outputs": aggregated}
```

`DependencyGraph.get_parallel_batches()` must be verified or added to `graph.py`. The existing
`DependencyGraph` already has `to_mermaid()` and a visualization payload — it likely has
topological ordering. Confirm by reading `ai-stack/workflows/graph.py` at implementation time.
If missing, add `get_parallel_batches() → List[List[WorkflowNode]]` using Kahn's algorithm on
`node.dependencies`.

### 7.2 `WorkflowNodeDispatcher`

**New file:** `ai-stack/workflows/node_dispatcher.py`

Responsibilities:
- Accept a batch of `WorkflowNode` objects and current `node_outputs` dict.
- Build a PR-1-compliant task envelope for each node (agent_type, role, workflow_phase,
  output_contract derived from `node.output_format` if set, else `"text"`).
- Dispatch all nodes in the batch concurrently via `asyncio.gather(timeout=per_node_timeout)`.
- Each node dispatched to one of three routes based on `node.agent` field:
  - `"local"` or unset → `WorkflowPhaseExecutor._delegate_phase_execution()` via
    `/control/agents/spawn` (already implemented in `workflow_executor.py` line ~537).
  - `"remote-codex"` / `"remote-gemini"` → `delegate_to_remote_handler` HTTP call to
    `/control/agents/delegate` or coordinator tool endpoint.
  - `"local-llm"` → direct `build_llama_payload()` + llama.cpp call (shared/llm_config.py).
- Emit `workflow_step_dispatched` on each node start; `workflow_step_complete` on each node
  result (both success and failure).
- Track wall-clock time per batch to compute `speedup_ratio = sum(node_durations) / batch_duration`.
- Respect `executor.max_parallel_tasks: 5` from `config/workflow-automation.yaml` —
  semaphore-guard concurrent dispatches.

### 7.3 `_execute_async()` Implementation

**File:** `ai-stack/workflows/coordinator.py`, method `_execute_async` starting at line 188.

Same logic as `_execute_sync()` but:
- Already wrapped in a background thread in `execute_workflow()` (line 127-132 — `threading.Thread`).
- Transitions `status → "running"` before calling the shared dispatcher.
- On exception: transitions `status → "failed"` and saves state.
- No return value (callers poll via `get_execution_status()`).

To avoid code duplication, extract the core execution logic into a private
`_run_execution_pipeline(execution_id, workflow, inputs)` coroutine called by both sync and
async variants.

### 7.4 Agent Loop Trigger

**Files:**
- `ai-stack/local-agents/agent_executor.py` — add `execute_workflow` to `_AEXEC_HOTSWAP_MAP`
  alongside `get_workflow_status`.
- `scripts/ai/aq-agent-loop` — add `--workflow YAML_FILE` flag that bypasses the free-text
  task path and directly calls `WorkflowCoordinator.execute_workflow()`.

**Detection heuristic in agent_executor** (add to `_AEXEC_WORKFLOW_KW` handling at line 100):
When a tool result or task prompt contains workflow keywords AND names a `.yaml` file path,
inject `execute_workflow` tool into the active tool set alongside `get_workflow_status`. The
`execute_workflow` tool definition must be added to the ToolRegistry in `tool_registry.py` with:
- `name: "execute_workflow"`
- `description`: concise (fits in 512-token context).
- `parameters`: `{yaml_file: str, inputs: dict, async_mode: bool = false}`.

**Explicit flag path in `aq-agent-loop`** (simpler, higher-priority for Phase B):
```
aq-agent-loop --workflow ai-stack/workflows/examples/parallel-tasks.yaml \
              --inputs '{"target": "foo"}'
```
This path calls `WorkflowCoordinator.execute_workflow()` directly, skipping the agent loop
and providing a clean integration test surface.

### 7.5 Result Aggregation

**New method `_aggregate_results()` on `WorkflowCoordinator`:**

```python
def _aggregate_results(workflow: Workflow, node_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge per-node outputs into the workflow result dict."""
    # Identify terminal nodes (no other node depends on them)
    all_dependencies = {dep for node in workflow.nodes for dep in node.dependencies}
    terminal_node_ids = [n.id for n in workflow.nodes if n.id not in all_dependencies]
    return {
        "terminal_outputs": {nid: node_outputs[nid] for nid in terminal_node_ids if nid in node_outputs},
        "all_outputs": node_outputs,
        "node_count": len(workflow.nodes),
    }
```

### 7.6 WorkflowPhaseExecutor Instantiation

`WorkflowPhaseExecutor` exists at `workflow_executor.py` and is functional. It must be imported
into `coordinator.py` (or `node_dispatcher.py`) rather than re-implemented. The import path is:

```python
# In ai-stack/workflows/coordinator.py or node_dispatcher.py
import sys, os
_COORDINATOR_WORKFLOW_PATH = str(Path(__file__).resolve().parents[2]
    / "mcp-servers" / "hybrid-coordinator" / "workflow")
if _COORDINATOR_WORKFLOW_PATH not in sys.path:
    sys.path.insert(0, _COORDINATOR_WORKFLOW_PATH)
from workflow_executor import WorkflowPhaseExecutor
```

The `coordinator_url` for `WorkflowPhaseExecutor` must be read from
`os.getenv("COORDINATOR_URL", "http://127.0.0.1:8003")` — never hardcoded, per architecture
constraints.

---

## 8. Implementation Plan

### Phase A — Implement Executor Body (no agent loop changes)

**Target:** `_execute_sync()` and `_execute_async()` call real code; sync execution with serial
node dispatch works end-to-end.

1. **A.1** — Audit `ai-stack/workflows/graph.py` for `get_parallel_batches()`. Add if missing.
2. **A.2** — Create `ai-stack/workflows/node_dispatcher.py` (`WorkflowNodeDispatcher`) with
   serial-first implementation (batch size 1, `asyncio.gather` with single element). Tests pass.
3. **A.3** — Replace `_execute_sync()` body in `coordinator.py` lines 153-162. Remove
   `"Workflow execution not yet implemented"` string. Wire `WorkflowNodeDispatcher`.
4. **A.4** — Replace `_execute_async()` body in `coordinator.py` lines 198-205. Same dispatcher.
5. **A.5** — Add `_aggregate_results()` to `WorkflowCoordinator`.
6. **A.6** — Emit 4 telemetry events to `_HYBRID_EVENTS` JSONL using the async-safe writer
   pattern already established in `agent_executor.py` line 75-98.
7. **A.7** — Run `ai-stack/workflows/tests/test_e2e_integration.py` — all tests must pass.
8. **A.8** — Manual smoke: `curl -X POST http://127.0.0.1:8003/api/workflows/execute -d
   '{"workflow_file":"ai-stack/workflows/examples/simple-sequential.yaml","inputs":{}}'` —
   verify non-stub response.

### Phase B — Wire Agent Loop

**Target:** `aq-agent-loop --workflow` flag works; keyword detection injects `execute_workflow` tool.

1. **B.1** — Add `execute_workflow` tool definition to `tool_registry.py` tool catalog.
2. **B.2** — Add `--workflow YAML_FILE` and `--inputs JSON` flags to `scripts/ai/aq-agent-loop`.
   The explicit flag path calls `WorkflowCoordinator.execute_workflow()` directly (no LLM turn).
3. **B.3** — Update `_AEXEC_HOTSWAP_MAP` in `agent_executor.py` line 98-103: add
   `execute_workflow` to `_AEXEC_WORKFLOW_KW` candidates alongside `get_workflow_status`.
4. **B.4** — Smoke test: `aq-agent-loop --workflow ai-stack/workflows/examples/parallel-tasks.yaml`.
5. **B.5** — Verify `workflow_started` event appears in `.agents/telemetry/hybrid-events.jsonl`.

### Phase C — Enable Parallelism

**Target:** `asyncio.gather` dispatches ≥2 nodes concurrently; speedup ratio metric is non-trivial.

1. **C.1** — Expand `WorkflowNodeDispatcher.dispatch_batch()` to concurrent dispatch:
   `asyncio.gather(*[_dispatch_node(n) for n in batch], return_exceptions=True)`.
2. **C.2** — Add `asyncio.Semaphore(max_parallel_tasks)` guard, reading
   `executor.max_parallel_tasks` from `config/workflow-automation.yaml`.
3. **C.3** — Compute `speedup_ratio = sum(serial_durations) / actual_batch_duration`. Attach
   to `workflow_aggregated` event.
4. **C.4** — Integration test with `examples/parallel-tasks.yaml` — confirm ≥2 nodes run
   concurrently (check that `workflow_step_dispatched` events for different nodes in the same
   batch have `ts` values within 2 s of each other).
5. **C.5** — Add PR-1 task envelope to each node dispatch payload (see Section 4).
6. **C.6** — `aq-qa` workflow check: see Section 11.

---

## 9. Monitoring and Observability

### New Telemetry Events

All events written to `.agents/telemetry/hybrid-events.jsonl` (same sink as agent_executor
events, same async-safe writer pattern). Event schema follows existing conventions in
`agent_executor.py` lines 86-98.

| Event | When Emitted | Key Fields |
|---|---|---|
| `workflow_started` | `_execute_sync()` / `_execute_async()` entry, after state transitions to `running` | `execution_id`, `workflow_name`, `node_count`, `async_mode` |
| `workflow_step_dispatched` | Per node, before sub-agent call | `execution_id`, `workflow_name`, `node_id`, `node_agent`, `batch_id`, `batch_index`, `batch_size` |
| `workflow_step_complete` | Per node, after sub-agent returns | `execution_id`, `workflow_name`, `node_id`, `status` (`completed`/`failed`), `duration_ms`, `output_length` |
| `workflow_aggregated` | After all batches complete | `execution_id`, `workflow_name`, `node_count`, `failed_count`, `total_duration_ms`, `parallel_speedup_ratio`, `batch_count` |

### Metric Keys (for Prometheus / dashboard polling)

| Metric | Type | Description |
|---|---|---|
| `workflow_success_rate` | Gauge | `completed / (completed + failed)` over rolling 24 h |
| `workflow_step_count_p50`, `_p95` | Histogram | Step count distribution per completed workflow |
| `workflow_parallel_speedup_ratio` | Gauge | Rolling average of `parallel_speedup_ratio` from `workflow_aggregated` events |
| `workflow_active_count` | Gauge | Count of executions with `status=running` in `WorkflowStateStore` |
| `workflow_type_breakdown` | Counter vec by `workflow_name` | Tracks which workflow templates are triggered most |

These metrics are computed by the dashboard backend reading `hybrid-events.jsonl` and the
`WorkflowStateStore` SQLite DB (`config/workflow-automation.yaml store.db_path`).

---

## 10. Dashboard Visualizations

All panels added to the existing AI stack dashboard. Backend route additions go in
`dashboard/backend/api/routes/aistack.py`.

### New API Routes Required

```
GET /api/workflows/active          → active execution count + list
GET /api/workflows/stats           → success/failure rates, step distributions
GET /api/workflows/speedup         → parallel speedup ratio time series
GET /api/workflows/breakdown       → workflow type breakdown counts
```

### Panel Specifications

| Panel | Type | Data Source | Update Interval |
|---|---|---|---|
| **Active Workflows** | Single-value gauge | `/api/workflows/active` count | 2 s (matches `dashboard.refresh_intervals.execution_status`) |
| **Workflow Success/Failure Rate** | Time series line chart (success% green, failure% red) | `/api/workflows/stats` rolling 24 h | 5 s |
| **Steps per Workflow** | Histogram bar chart (x=step_count buckets 1-2, 3-5, 6-10, 11+) | `/api/workflows/stats` step_count_distribution | 10 s |
| **Parallel Speedup Ratio** | Single-value gauge with sparkline | `/api/workflows/speedup` rolling 10 executions | 5 s |
| **Workflow Type Breakdown** | Horizontal bar chart | `/api/workflows/breakdown` | 30 s |

Implementation note: dashboard backend must read `WorkflowStateStore` (the SQLite DB at
`config/workflow-automation.yaml store.db_path`) and `hybrid-events.jsonl` using
`asyncio.to_thread()` to avoid blocking — mandatory per the async-blocking bug pattern in
MEMORY.md.

---

## 11. Validation Plan

### aq-qa Checks (add to aq-qa section "workflow")

```bash
# Check 1: WorkflowCoordinator stub string is gone
aq-qa workflow stub_removed
  → rg "Workflow execution not yet implemented" ai-stack/workflows/coordinator.py
  → PASS if no matches

# Check 2: workflow_started event appears in telemetry after smoke run
aq-qa workflow telemetry_present
  → grep -c "workflow_started" .agents/telemetry/hybrid-events.jsonl
  → PASS if count >= 1

# Check 3: WorkflowStateStore has at least one completed execution
aq-qa workflow completed_execution
  → sqlite3 <db_path> "SELECT COUNT(*) FROM executions WHERE status='completed'"
  → PASS if count >= 1

# Check 4: parallel speedup ratio > 1.0 (at least one batch ran parallel)
aq-qa workflow parallel_speedup
  → grep "workflow_aggregated" .agents/telemetry/hybrid-events.jsonl | python3 -c
    "import sys,json; data=[json.loads(l) for l in sys.stdin];
     ratios=[d.get('parallel_speedup_ratio',1.0) for d in data if d.get('parallel_speedup_ratio')];
     print(max(ratios) if ratios else 0)"
  → PASS if result > 1.0

# Check 5: execute_workflow tool registered in ToolRegistry
aq-qa workflow tool_registered
  → python3 -c "from tool_registry import get_registry; r=get_registry(); print('execute_workflow' in r.tools)"
  → PASS if True
```

### Manual Smoke Tests

1. Serial execution: `curl POST /api/workflows/execute` with
   `ai-stack/workflows/examples/simple-sequential.yaml` — verify `status=completed`, non-stub output.
2. Parallel execution: same with `ai-stack/workflows/examples/parallel-tasks.yaml` — verify
   `workflow_step_dispatched` events show concurrent batch dispatch.
3. Failure handling: submit a workflow with a node that calls a non-existent tool — verify
   `status=failed`, `error` field populated, state persisted.
4. Async mode: `POST /api/workflows/execute` with `async_mode=true` — verify `status=started`
   returned immediately, poll `GET /api/workflows/{execution_id}/status` until `completed`.
5. Agent loop integration: `aq-agent-loop --workflow ai-stack/workflows/examples/parallel-tasks.yaml
   --inputs '{}'` — verify exit 0 and JSON output with `workflow_execution_id`.

---

## 12. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **`DependencyGraph.get_parallel_batches()` missing** | Medium | Blocks Phase A | Read `graph.py` first; implement Kahn's algorithm if absent. Simple addition. |
| **Parallel dispatch race on shared `node_outputs` dict** | Medium | Data corruption in result aggregation | Use `asyncio.Lock` around `node_outputs` writes; each node writes to its own key (node_id) so in practice race is only on dict insertion — CPython GIL protects this, but add explicit lock for clarity. |
| **Sub-agent quota exhaustion under parallel dispatch** | Medium | All nodes fail simultaneously | `asyncio.Semaphore(max_parallel_tasks=5)` from config. Monitor `workflow_step_dispatched` event rate vs coordinator capacity. |
| **`/control/agents/spawn` blocked by AppArmor under ai-hybrid service user** | High | Phase A blocked at first real dispatch | `WorkflowPhaseExecutor` calls coordinator REST (loopback), not exec. Loopback calls are AppArmor-permitted. Verify with manual curl before wiring. |
| **`workflow_executor.py` import path collision** | Low | `sys.path` pollution | Use explicit path insertion pattern already established in `agent_executor.py` line 31-33. |
| **`asyncio.gather` exception from one node masks others** | Medium | Partial results lost | Use `return_exceptions=True`; inspect each result for `isinstance(r, Exception)`. |
| **State persistence (SQLite) blocking event loop** | High | Dashboard lag, coordinator timeouts | All `state_store.save()` calls must use `asyncio.to_thread()`. Check `persistence.py` implementation at Phase A start. |
| **Template storage path `/tmp/workflow-templates` blocked by AppArmor** | High | `TemplateManager` init crash | Deferred to scope. Phase 185A does not use `TemplateManager`. Set `templates.storage_path` to `/var/lib/ai-stack/hybrid/workflow-templates` in a future NixOS module change. |

---

## 13. Dependencies

### Hard Prerequisites (must be complete before Phase B wiring)

| Dependency | Status | Notes |
|---|---|---|
| **Delegation working end-to-end (Phase 184A equivalent)** | Assumed complete per recent commits | `/control/agents/spawn` and `delegate_to_remote_handler` must return real results, not 404/500. Verify with `curl http://127.0.0.1:8003/control/agents/spawn` before starting Phase A. |
| **PR-1 Canonical Task Envelope** | Partial (Phase 148 PRD drafted, implementation status unknown) | Phase A can start without PR-1 by building a minimal envelope inline. Phase C.5 requires PR-1 to be importable. |
| **`WorkflowStateStore` SQLite** | Complete per `persistence.py` existence | Verify SQLite tables exist: `sqlite3 <db_path> ".tables"` before Phase A.3. |
| **llama.cpp running on port 8080** | Runtime prerequisite | Node dispatch via `"local-llm"` route requires llama.cpp active. Smoke tests should use `"local"` route (coordinator spawn) to avoid hard dependency. |

### Rebuild Requirements

| Change | Rebuild Needed |
|---|---|
| New Python files in `ai-stack/workflows/` or `ai-stack/local-agents/` | No NixOS rebuild — Python files are loaded at runtime from repo path. `REPO_ROOT` env var must be set. |
| New dashboard backend routes in `dashboard/backend/api/routes/aistack.py` | Dashboard service restart only: `systemctl restart ai-dashboard.service` |
| New aq-qa checks added to aq-qa script | No rebuild — script is a Python file in `scripts/ai/` |
| Changes to `ai-stack/mcp-servers/hybrid-coordinator/` | `nixos-rebuild switch` required (coordinator is a NixOS service with `repoSource` copy) |
| AppArmor profile changes (if needed for new paths) | `nixos-rebuild switch` required |

### PENDING-REBUILD Items Already in Queue

The following PENDING-REBUILD items from MEMORY.md are NOT blocking Phase 185A but must be
applied before final Phase C validation to ensure the coordinator is running the latest code:

- AppArmor BPF consolidation (35438312) — must rebuild before Phase C parallel dispatch runs
  under the coordinator service user, or AppArmor OOM may block sub-agent spawns.
- Switchboard useful_ratio (ebeae5ab) — no direct impact on workflow execution.
- health-spider osi_layered_running (d501b1e8) — no direct impact.

---

## Appendix A — File Reference Map

| File | Role in Phase 185A |
|---|---|
| `ai-stack/workflows/coordinator.py` | Primary edit target — implement `_execute_sync`, `_execute_async`, add `_aggregate_results` |
| `ai-stack/workflows/graph.py` | Audit for `get_parallel_batches()`; add if missing |
| `ai-stack/workflows/node_dispatcher.py` | New file — `WorkflowNodeDispatcher` |
| `ai-stack/workflows/models.py` | Read-only — `WorkflowNode.dependencies`, `WorkflowNode.agent` fields |
| `ai-stack/workflows/persistence.py` | Read-only (verify async-safe) |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py` | Import `WorkflowPhaseExecutor` from here — do not re-implement |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/yaml_workflow_handlers.py` | No change needed — routes already call `WorkflowCoordinator.execute_workflow()` |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/orchestration_handlers.py` | No change — `handle_orchestration_delegate` already usable for remote node dispatch |
| `ai-stack/local-agents/agent_executor.py` | Phase B — add `execute_workflow` to hot-swap map (line 98-103) |
| `ai-stack/local-agents/tool_registry.py` | Phase B — register `execute_workflow` tool definition |
| `scripts/ai/aq-agent-loop` | Phase B — add `--workflow` flag |
| `dashboard/backend/api/routes/aistack.py` | Phase C — add 4 new workflow API routes |
| `config/workflow-automation.yaml` | Read-only config source — `executor.max_parallel_tasks`, `executor.default_timeout_seconds`, `store.db_path` |
