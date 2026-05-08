# Architectural Review Findings

Target: `ai-stack/mcp-servers/hybrid-coordinator/` and harness bridge surfaces  
Mode: read-only analysis of existing code; no source files modified

## DUPLICATES

- `hybrid-coordinator` currently exposes `111` Python modules at top level (`ls .../*.py | sort`), which is a very large flat surface for one service.
- `harness_sdk` exists in four language artifacts in the same directory:
  - `harness_sdk.py`
  - `harness_sdk.ts`
  - `harness_sdk.js`
  - `harness_sdk.d.ts`
- Strong overlap pairs:
  - `garbage_collection.py` vs `garbage_collector.py`
    - Both define a `GarbageCollector` class.
    - `garbage_collection.py` is file-based telemetry cleanup (`/data/telemetry`, gzip/rotate/prune).
    - `garbage_collector.py` is database/vector cleanup (`asyncpg`, `QdrantClient`, Prometheus metrics).
    - Same concept, different storage backends, zero internal imports into either module. This is naming collision plus likely abandoned split-brain evolution.
  - `continuous_learning.py` vs `continuous_learning_daemon.py`
    - `continuous_learning.py` contains the real pipeline (`ContinuousLearningPipeline`).
    - `continuous_learning_daemon.py` is a wrapper/runner that imports `ContinuousLearningPipeline`.
    - The daemon has `0` internal fan-in; `continuous_learning.py` has `3`.
    - This is not exact duplication, but it is overlapping lifecycle ownership.
  - `coordinator.py` vs `ai_coordinator.py` vs `server.py`/`http_server.py`
    - `coordinator.py` is explicitly marked `ARCHIVED — DO NOT USE`.
    - `ai_coordinator.py` is active helper logic for control/delegation surfaces.
    - `server.py` is the active runtime entrypoint and calls `http_server.run_http_mode(...)`.
    - `http_server.py` is effectively the main composition root for the live HTTP harness.
    - Result: at least four “coordinator/server” names remain in one package, but only two are active.
  - `browser_research.py` vs `web_research.py`
    - `web_research.py` is the generic bounded fetch/extract layer.
    - `browser_research.py` is the JS-heavy fallback and imports helper functions back from `web_research.py`.
    - This is a reasonable layering, but the names still read as parallel implementations.
  - `research_workflows.py` vs `workflow_planning.py`
    - `research_workflows.py` is curated source-pack research orchestration.
    - `workflow_planning.py` is task/workflow plan construction for the harness.
    - Not duplicate behavior, but both present as workflow/orchestration modules in the same flat namespace.
- `http_server.py` is highly overloaded as the aggregator for the entire package.
  - It has `84` top-level `import`/`from` lines.
  - It imports most handler modules directly and still reaches into older orchestration layers.
  - It even imports `sys` twice (`line 28` and `line 174`), which is a minor smell but consistent with overgrown composition logic.

## IMPORT_ORPHANS

- AST-based import scan across `111` Python modules found `28` modules with `0` in-package fan-in.
- Top internally imported modules:
  - `config`: `25`
  - `metrics`: `10`
  - `agent_registry`: `8`
  - `ai_coordinator`: `7`
  - `memory_manager`: `5`
  - `tooling_manifest`: `5`
  - `hints_engine`: `4`
  - `llm_router`: `4`
  - `model_optimization`: `4`
  - `orchestration_utils`: `4`
- Non-test orphan candidates with `0` internal fan-in:
  - `auth_middleware`
  - `circuit_breaker`
  - `continuous_learning_daemon`
  - `coordinator`
  - `federation_sync`
  - `garbage_collection`
  - `garbage_collector`
  - `harness_sdk`
  - `safe_command_executor`
  - `server`
  - `skill_validator`
- Important caveat:
  - `server.py` is probably an entrypoint, not dead code. It has `0` internal fan-in because nothing imports it; it launches `http_server.run_http_mode(...)`.
  - `harness_sdk.py` is not dead globally; it is referenced outside the AST in `tooling_manifest.py`, and TS/JS users may consume the non-Python copies.
  - `safe_command_executor.py` is imported by `scripts/ai/mcp-bridge-hybrid.py`, so it is orphaned only relative to the `hybrid-coordinator` package itself.
- Modules with low but non-zero package fan-in:
  - `http_server`: `1` importer (`server.py`)
  - `continuous_learning`: `3`
  - `workflow_planning`: `3`
  - `hints_engine`: `4`
  - `ai_coordinator`: `7`
- Direct evidence of active composition:
  - `server.py` imports and instantiates `ContinuousLearningPipeline`.
  - `server.py` calls `http_server.run_http_mode(...)`.
  - `http_server.py` imports `workflow_planning`, `tooling_manifest`, `mcp_handlers`, `hints_handlers`, `workflow_session_handlers`, and many others.
- Architectural takeaway:
  - The package is not “modular” in the dependency-graph sense. It is a large, flat module garden with one dominant root (`http_server.py`) and many leaf/orphan files preserved in place.

## VSCODIUM_ROOT_CAUSE

- Continue is configured to launch the harness MCP bridge through:
  - `python3 /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/mcp-bridge-hybrid.py`
- The Continue config hard-pins `aq-hints` as a context provider:
  - `"endpoint": "http://127.0.0.1:8003/hints"`
  - This means editor startup/use depends on the hybrid coordinator being responsive.
- The bridge is synchronous despite importing `asyncio`.
  - `main()` is `for line in sys.stdin: ...`
  - No `await` usage was found by `grep -n 'timeout|asyncio.wait|await|blocking'`.
  - Each tool call is handled serially in the stdin loop.
- Blocking points in the bridge path:
  - `_post(...)` uses `urllib.request.urlopen(..., timeout=30)`
  - `_get(...)` uses `urllib.request.urlopen(..., timeout=10)`
  - `_run_local(...)` uses `subprocess.run(...)` with no timeout at all
- Consequence:
  - One slow `/hints`, `/workflow/*`, or local AQD subprocess call can stall the entire MCP stdio bridge.
  - Because the bridge is single-threaded and synchronous, a blocked call stalls all further editor requests until the current request returns.
- The bridge does not show any async isolation or cancellation strategy:
  - no worker threads
  - no per-request subprocess timeout
  - no async HTTP client
  - no queue separation between fast metadata calls and slow workflow calls
- Continue config contradiction likely contributes to instability:
  - `__frozen` says `contextLength=32000` and `maxTokens=4096` for Local Agent are locked.
  - Actual `"Local Agent (Harness-Aware)"` model config is `contextLength: 16384`, `maxTokens: 1024`.
  - `"Continue Local (Compact)"` is `16384/4096`.
  - If the editor or prompts assume the frozen values, this mismatch can manifest as retries, truncation, or “hang-like” waiting.
- Most likely root-cause cluster for VSCodium/Continue hangs:
  - hard dependency on `http://127.0.0.1:8003/hints`
  - synchronous MCP bridge over stdio
  - blocking HTTP calls with `10s` and `30s` timeouts
  - unbounded `subprocess.run(...)` calls in the same request path
  - config mismatch between documented and actual context/token limits

## STORAGE_BLOAT

- JSONL file count in repo: `3`
  - `./ai-stack/snapshots/imported-documents-meta.jsonl`
  - `./ai-stack/snapshots/query-gaps.jsonl`
  - `./docs/architecture/adk-discovery-log.jsonl`
- Disk usage:
  - `.aidb/`: `2.1M`
  - `/var/lib/nixos-ai-stack/`: `4.0K`
- Accumulating-data candidates found by name probe:
  - `./.aidb/temporal_facts.json`
  - `./scripts/data/sync-learning-data.sh`
  - `./ai-stack/aidb/temporal_facts.py`
  - `./ai-stack/aidb/__pycache__/temporal_facts.cpython-313.pyc`
- Redis state:
  - `DBSIZE`: `54`
  - `INFO keyspace`: `db0:keys=54,expires=52,avg_ttl=211572594`
- Current evidence does not show severe local disk bloat yet.
  - Repo-visible JSONL volume is low.
  - `.aidb/` is modest.
  - `/var/lib/nixos-ai-stack/` is currently tiny.
- Architectural concern is still valid:
  - there are multiple learning, telemetry, memory, and session-history concepts spread across the codebase
  - both `garbage_collection.py` and `garbage_collector.py` exist but neither is clearly wired into the live package import graph
  - accumulation controls may exist on paper but not in the active runtime path

## ECHO_PATTERNS

- Files posting to or embedding `/hints` or `/workflow` paths (`head -20` sample):
  - `ai-stack/local-orchestrator/mcp_client.py`
  - `ai-stack/security/audit_trail.py`
  - `ai-stack/security/security_hardening.py`
  - `ai-stack/security/zero_trust.py`
  - `ai-stack/mcp-servers/aider-wrapper/server.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/workflow_session_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/hints_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/auth_middleware.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/openai_a2a_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/auto_tool_select_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/tooling_manifest.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/yaml_workflow_handlers.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/test_workflow_plan_optimization_watch.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`
  - `ai-stack/mcp-servers/shared/rate_limiter.py`
  - `ai-stack/platform/harness_sdk_v2.py`
  - `ai-stack/observability/metrics_middleware.py`
- `hints_engine.py` does not appear to call back to `http://127.0.0.1:8003` directly in the inspected probe.
  - `grep -n 'http.*8003|coordinator|hybrid'` returned terminology and local module references, not outbound self-HTTP calls.
  - This suggests the hints system is locally embedded rather than recursively calling its own public endpoint.
- Network-call density inside `hybrid-coordinator` is still high:
  - `grep -rn 'aiohttp|requests.get|requests.post' ... | grep -v test | wc -l` => `55`
- Architectural pattern:
  - the harness exposes `/hints` and `/workflow/*` as both internal primitives and public coordination APIs
  - multiple modules advertise or rediscover the same endpoints
  - this increases the chance of self-referential orchestration, duplicated routing metadata, and “service pings service” behavior
- Specific echo risk:
  - Continue config uses `/hints`
  - the bridge also exposes `get_hints`
  - `hints_engine`, `hints_handlers`, `tooling_manifest`, `openai_a2a_handlers`, and `auto_tool_select_handlers` all encode hints/workflow knowledge
  - that is a lot of routing/metadata duplication for one concept

## DEAD_CODE_CANDIDATES

- Lowest-reference `ai-stack/*` directories from the requested probe:
  - `0 ai-stack/agentic-patterns/`
  - `0 ai-stack/autonomous-improvement/`
  - `0 ai-stack/autonomous-orchestrator/`
  - `0 ai-stack/context_memory/`
  - `0 ai-stack/cron/`
  - `0 ai-stack/federated-learning/`
  - `0 ai-stack/meta-optimization/`
  - `0 ai-stack/sop-templates/`
  - `1 ai-stack/affective-engine/`
  - `1 ai-stack/cli-bridge/`
  - `1 ai-stack/embedding-cache/`
  - `1 ai-stack/identity-kernel/`
  - `1 ai-stack/local-agents/`
  - `1 ai-stack/local-orchestrator/`
  - `1 ai-stack/migrations/`
  - `1 ai-stack/trading-agents/`
  - `1 ai-stack/world-model/`
- Requested directory spot-checks:
  - `federated-learning`
    - Files exist: `federated_pattern_synthesis.py`, `agent_learning_aggregator.py`
    - No `__init__.py` at the scanned levels
    - References found only in `hybrid-coordinator/federated_integration.py` plus the directory’s own code
    - Looks weakly integrated and easy to strand
  - `meta-optimization`
    - Files exist: `harness_evolution_tracker.py`, `meta_optimizer.py`
    - No `__init__.py` at the scanned levels
    - Probe found only self-reference in `harness_evolution_tracker.py`
    - Strong dead-code candidate
  - `affective-engine`
    - Has `__init__.py`
    - Referenced by `hybrid-coordinator/affective_handlers.py`
    - Low-reference, but at least wired through one handler layer
  - `trading-agents`
    - Has `__init__.py` and multiple package submodules
    - Referenced by `hybrid-coordinator/trading_handlers.py`
    - Not dead, but integration appears shallow
  - `real-time-learning`
    - No `__init__.py` in the scanned levels
    - Referenced from `delegation_handlers.py`, `ai_coordinator_handlers.py`, `http_server.py`, `real_time_learning_engine.py`, and `metrics.py`
    - Active concept despite non-package-looking layout
  - `autonomous-orchestrator`
    - Has `__init__.py`
    - Probe found only `local-orchestrator/orchestrator.py` plus self-reference
    - Strong candidate for partial abandonment or one-off coupling
- Highest-confidence dead/abandoned candidates from all evidence:
  - `coordinator.py`
  - `meta-optimization/`
  - `garbage_collection.py`
  - `garbage_collector.py`
  - `continuous_learning_daemon.py`
  - `federation_sync.py`
  - `skill_validator.py`
- Lower-confidence but suspicious:
  - `auth_middleware.py`
  - `harness_sdk.py` as Python specifically, because the SDK concept is split across Python/TS/JS/d.ts and may be drifting rather than dead
  - `autonomous-orchestrator/`

## Bottom Line

- The harness architecture is carrying a large amount of overlap in one flat package namespace.
- `http_server.py` is the live choke point; most other modules radiate around it, while many older modules remain parked in place with zero in-package fan-in.
- The VSCodium/Continue hang risk is credible and likely rooted in the synchronous MCP bridge plus mandatory `/hints` dependency, not just model quality or context size.
- Storage bloat is not severe yet by current disk/key counts, but cleanup/retention code appears under-integrated relative to the number of learning/telemetry paths present.

## Codex PDR Review

### 1. VSCodium root cause

- `AGREE` on the primary diagnosis: `scripts/ai/mcp-bridge-hybrid.py` is a synchronous stdio loop and both `_post()` and `_get()` use blocking `urllib.request.urlopen(...)`. That is sufficient to stall the whole MCP bridge while one request is in flight.
- I do not think the PDR is complete enough if it names only "sync mcp-bridge, blocking urllib".
- Two additional contributors should be called out explicitly before implementation:
  - `_run_local()` uses `subprocess.run(...)` with no timeout, so local AQD-backed tools can hang the same bridge even after the HTTP path is improved.
  - Continue is hard-wired to `/hints`, so the issue is not just transport blocking; it is also that a high-frequency editor path depends on a potentially expensive coordinator path.
- Recommended wording change: treat the root cause as "single-threaded MCP bridge + blocking HTTP/local execution on a hot `/hints` path", not only blocking `urllib`.

### 2. Duplicate module list

- `DISAGREE` with treating the `garbage_collection` pair as confirmed duplicates to merge immediately.
- `garbage_collection.py` is file/telemetry retention cleanup. `garbage_collector.py` is DB/Qdrant solution-store cleanup with metrics. They are a naming collision and ownership problem, but not the same implementation. Renaming or re-homing is justified; forced merge is not yet justified.
- `DISAGREE` with treating `continuous_learning.py`, `continuous_learning_daemon.py`, and `real_time_learning_engine.py` as one duplicate set.
- `continuous_learning.py` is the pipeline. `continuous_learning_daemon.py` is its process wrapper/runner. `real_time_learning_engine.py` is a separate online-learning and gap-remediation helper module imported by handlers and `http_server.py`.
- What should change:
  - Reclassify both sets from "duplicate modules" to "overlapping lifecycle / naming / ownership surfaces".
  - Keep daemon-vs-library separation unless there is a clear operational reason to inline them.
  - Audit `real_time_learning_engine.py` as an extensions-domain dependency, not as a duplicate of the continuous learning pipeline.

### 3. Phase A plan

- `AGREE`, with amendments.
- Converting the bridge to an async request dispatcher with `run_in_executor` is a reasonable low-risk fix for the current codebase because it keeps stdlib transport and minimizes blast radius.
- I would not stop at "async event loop + run_in_executor" alone.
- Required additions:
  - add explicit timeouts to `_run_local()`;
  - separate fast-path tool budgets from slow-path tool budgets;
  - make `/hints` fail open to cached/stale data instead of blocking on fresh synthesis;
  - cap bridge concurrency so the editor cannot flood the coordinator.
- Alternative worth considering but not required for Phase A:
  - replace `urllib` with `aiohttp` or `httpx.AsyncClient` and remove the thread-pool bridge entirely.
- My recommendation is still to do the executor-based fix first because it is smaller and compatible with the current bridge shape.

### 4. Phase B domain-split risks the PDR missed

- Flat-file imports are widely assumed today. Many modules import peers with bare names (`import workflow_planning`, `from continuous_learning import ...`, `import memory_context_handlers`). A directory split will break these consumers unless imports are normalized or compatibility shims are left behind.
- The split is not only internal to `http_server.py`. CLI scripts such as `scripts/ai/aq-hints` and other modules outside the package import `hints_engine` directly today. Those external entrypoints need to be part of the migration contract.
- `server.py` and `http_server.py` still act as composition roots. Moving modules without first shrinking those roots can increase circular-import risk rather than reduce it.
- Test and fixture code uses direct file-name assumptions in places such as `Path(__file__).with_name("workflow_planning.py")`. Domain moves can break tests even if runtime imports pass.
- Removing `harness_sdk.ts/.js/.d.ts` as "unused by live service" is too narrow a criterion. They may be part of external consumer or generated-SDK workflows. Confirm repo and downstream usage before deletion.
- I recommend inserting a new Phase `B.1.5`:
  - normalize import boundaries;
  - identify external consumers of moved modules;
  - add compatibility shims or a package `__init__` export layer;
  - only then perform B.2/B.3.

### 5. Overall phase sequence

- `AGREE` with `A -> B -> C -> D -> E` at a high level.
- I would modify the internal sequencing of `B`, not the overall order.
- Recommended order:
  - `A`
  - `B.1` audit/classification
  - `B.1.5` import-contract and compatibility plan
  - `B.2` prune/rename only truly redundant modules
  - `B.3` directory split
  - `C`
  - `D`
  - `E`
- Reason: the current proposed `B.2` assumes duplicate certainty that the code does not support for all listed sets.

### 6. Acceptance-criteria amendments

- Phase A should require more than "VSCodium does not hang".
- Add:
  - bridge handles concurrent fast requests without serial 30s stalls;
  - `/hints` returns cached or degraded output when the backend is slow/unavailable;
  - local command execution has bounded timeout behavior;
  - manual or scripted verification that `get_hints`, `workflow_plan`, and one local-command-backed tool all return while another slow request is in flight.
- Phase B should verify compatibility, not just import syntax.
- Add:
  - smoke tests for `scripts/ai/aq-hints`, bridge startup, `/hints`, `/workflow/plan`, and `/workflow/run/start`;
  - assertion that `core/` has no imports from `extensions/`;
  - repo search proving no stale imports remain for moved modules;
  - explicit list of compatibility shims retained or removed.
- Final acceptance should change "No duplicate module pairs remain" to "No unowned overlapping modules remain without documented canonical ownership", because some currently listed pairs are not true duplicates.
