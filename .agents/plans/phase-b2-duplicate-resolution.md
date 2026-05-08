# Phase B.2 Duplicate Module Investigation

Date: 2026-05-08
Scope: `ai-stack/mcp-servers/hybrid-coordinator/`
Constraint: Investigation only. No files deleted in this phase.

## Objective

Determine which duplicate or near-duplicate modules are actually used by the live hybrid-coordinator service, which are wrappers or packaging artifacts, and which are safe candidates for later removal or merge.

## Evidence Collected

Harness/bootstrap:
- `aq-prime`
- `aq-session-zero`
- `aq-hints "Phase B.2 duplicate module investigation in hybrid-coordinator" --format=json --agent=codex`
- `aq-context-bootstrap --task "Phase B.2 duplicate module investigation in hybrid-coordinator"`
- `curl -sS -X POST http://127.0.0.1:8003/workflow/plan ...`

Required duplicate checks:
- `diff ai-stack/mcp-servers/hybrid-coordinator/garbage_collection.py ai-stack/mcp-servers/hybrid-coordinator/garbage_collector.py | head -40`
- `grep -rn 'from garbage_collect\|import garbage_collect' ai-stack/mcp-servers/hybrid-coordinator/*.py | grep -v test`
- `grep -rn 'from continuous_learning\|import continuous_learning\|from continuous_learning_daemon\|import continuous_learning_daemon' ai-stack/mcp-servers/hybrid-coordinator/*.py | grep -v test`
- `grep -c 'def ' ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py ai-stack/mcp-servers/hybrid-coordinator/continuous_learning_daemon.py ai-stack/mcp-servers/hybrid-coordinator/real_time_learning_engine.py`
- `grep -rn 'from agentic_memory_journal\|import agentic_memory_journal\|from memory_context_handlers\|import memory_context_handlers' ai-stack/mcp-servers/hybrid-coordinator/*.py | grep -v test`
- `ls ai-stack/mcp-servers/hybrid-coordinator/harness_sdk*`
- `grep -rl 'harness_sdk' ai-stack/ --include='*.ts' --include='*.js' | head -5`
- `grep -rl 'from harness_sdk\|import harness_sdk' ai-stack/mcp-servers/hybrid-coordinator/ --include='*.py' | grep -v test | head -5`

Follow-up caller/packaging inspection:
- `rg -n "garbage_collection|garbage_collector" ...`
- `rg -n "continuous_learning|continuous_learning_daemon|real_time_learning_engine" ...`
- `rg -n "agentic_memory_journal|memory_context_handlers|memory_manager" ...`
- `rg -n "harness_sdk(\\.ts|\\.js|\\.d\\.ts|\\.py)?" ...`
- targeted `sed`/`tail` reads of `server.py`, `http_server.py`, `ops_handlers.py`, `ai_coordinator_handlers.py`, `Dockerfile`, `start_with_learning.sh`, `package.json`, `pyproject.toml`, `README.sdk.md`, and the candidate modules.

## Findings By Duplicate Group

### 1. Garbage Collection Duplicates

Files:
- `garbage_collection.py`
- `garbage_collector.py`

Observed usage:
- No live Python imports matched either module in `ai-stack/mcp-servers/hybrid-coordinator/*.py`.
- Repo-wide references to `garbage_collector.py` are documentation-heavy.
- Repo-wide code references found only:
  - `garbage_collection.py`: standalone CLI entrypoint in its own `__main__`
  - `garbage_collector.py`: standalone `run_gc_scheduler(...)` helper plus its own `__main__` banner

Behavioral difference:
- `garbage_collection.py` is a lightweight filesystem telemetry cleanup script.
- `garbage_collector.py` is a richer DB/Qdrant garbage collector with Prometheus metrics, deduplication, pruning, orphan cleanup, and scheduler support.
- They are not line-for-line duplicates; they are overlapping implementations for the same concern with different scope and maturity.

Resolution:
- KEEP: `garbage_collector.py`
- REMOVE/MERGE: `garbage_collection.py`
- Exact reason: `garbage_collector.py` is the more complete implementation and the only one that exposes reusable scheduler functionality. Neither file is currently imported by the live service, so later cleanup should consolidate on the richer module rather than preserve both.

Caller updates needed if removal happens:
- No live Python callers in `hybrid-coordinator` need import changes.
- Documentation references will need updates:
  - `docs/P1-DEPLOYMENT-GUIDE.md`
  - `docs/development/TESTING_PLAN.md`
  - any other docs still naming `garbage_collection.py`

Confidence:
- High that neither file is imported by the running Python service today.
- Medium on whether some external operator workflow still invokes `garbage_collection.py` manually; I found docs references, not live code references.

### 2. Continuous Learning "Duplicates"

Files:
- `continuous_learning.py`
- `continuous_learning_daemon.py`
- `real_time_learning_engine.py`

Observed imports:
- `continuous_learning.py` is imported by:
  - `continuous_learning_daemon.py`
  - `server.py`
  - `ops_handlers.py`
- `continuous_learning_daemon.py` is not imported by other Python modules; it is executed as a process entrypoint from:
  - `start_with_learning.sh`
  - Docker packaging via `Dockerfile`
- `real_time_learning_engine.py` is imported by:
  - `http_server.py`
  - `ai_coordinator_handlers.py`

What each module exports in practice:
- `continuous_learning.py`
  - core `ContinuousLearningPipeline`
  - data models such as `InteractionPattern`, `FinetuningExample`, `PerformanceMetric`, `OptimizationProposal`
  - pipeline lifecycle (`start`, `stop`) and telemetry/dataset/statistics logic
- `continuous_learning_daemon.py`
  - wrapper entrypoint with `Settings` and `main()`
  - constructs `ContinuousLearningPipeline`
  - handles PID locking, env bootstrap, optional Qdrant/Postgres wiring, and long-running process supervision
- `real_time_learning_engine.py`
  - real-time gap remediation and online/meta-learning singletons and helpers
  - exports `_GAP_DETECTOR`, remediation planning/status helpers, `_apply_real_time_learning`, `_apply_meta_learning`

Running-service determination:
- The main running service (`server.py`) imports and starts `ContinuousLearningPipeline` directly from `continuous_learning.py`.
- The sidecar/daemon path (`start_with_learning.sh`) separately launches `continuous_learning_daemon.py`, which also imports `ContinuousLearningPipeline` from `continuous_learning.py`.
- `real_time_learning_engine.py` is live, but it serves a different runtime concern from the batch/telemetry pipeline.

Important anomaly:
- `ops_handlers.py` contains `from continuous_learning import learning_pipeline` inside `handle_health(...)`.
- `continuous_learning.py` does not define a module-level `learning_pipeline`.
- `ops_handlers.py` also already receives an injected `_learning_pipeline` from `server.py`.
- This looks like a stale import path, not evidence that `continuous_learning_daemon.py` or `real_time_learning_engine.py` are duplicates.

Resolution:
- KEEP: `continuous_learning.py`
- KEEP: `continuous_learning_daemon.py`
- KEEP: `real_time_learning_engine.py`
- REMOVE/MERGE: none in this group, based on current evidence
- Exact reason: these files are adjacent but not duplicates. `continuous_learning.py` is the reusable pipeline, `continuous_learning_daemon.py` is a process wrapper/entrypoint, and `real_time_learning_engine.py` implements a separate real-time remediation/online-learning subsystem.

Caller updates needed:
- No import migration is recommended for this group as part of duplicate cleanup.
- Separate hardening follow-up recommended:
  - replace the stale `from continuous_learning import learning_pipeline` in `ops_handlers.py` with the already injected `_learning_pipeline` path

Confidence:
- High that `continuous_learning.py` is the module imported by the live service.
- High that `continuous_learning_daemon.py` is a wrapper entrypoint, not a reusable imported module.
- High that `real_time_learning_engine.py` is separate functionality, not a duplicate.
- High that the `ops_handlers.py` import is stale or incorrect.

### 3. Agentic Memory Journal vs Memory Context / Memory Manager

Files examined:
- `agentic_memory_journal.py`
- `memory_context_handlers.py`
- `memory_manager.py` (follow-up inspection, because the task wording mentions memory manager)

Observed imports:
- `agentic_memory_journal.py` is imported by:
  - `http_server.py`
  - `ai_coordinator_handlers.py`
- `memory_context_handlers.py` is imported by:
  - `http_server.py`
- `memory_context_handlers.py` itself imports from `memory_manager.py`
- `memory_manager.py` is imported directly by:
  - `server.py`
  - `http_server.py`
  - `mcp_handlers.py`
  - `memory_context_handlers.py`

Relationship:
- `agentic_memory_journal.py` is an audit log/journal backend for delegation/model interaction provenance.
- `memory_manager.py` is the actual store/recall implementation for agent memory backed by Qdrant.
- `memory_context_handlers.py` is an HTTP handler layer that wraps injected `memory_manager` operations plus harness/session/discovery routes.

Resolution:
- KEEP: `agentic_memory_journal.py`
- KEEP: `memory_context_handlers.py`
- KEEP: `memory_manager.py`
- REMOVE/MERGE: none in this group
- Exact reason: these modules are independently imported and serve different layers of the stack. `memory_context_handlers.py` wraps `memory_manager.py`; `agentic_memory_journal.py` does not wrap either and is a separate audit subsystem.

Caller updates needed:
- None for duplicate cleanup.

Confidence:
- High.

### 4. Harness SDK Non-Python Files

Files:
- `harness_sdk.py`
- `harness_sdk.ts`
- `harness_sdk.js`
- `harness_sdk.d.ts`

Observed usage:
- Python code usage:
  - `tooling_manifest.py` emits `from harness_sdk import HarnessClient`
- JS/TS repo search only found `harness_sdk.js` referencing itself directly; no live service TS/JS caller was found elsewhere in `ai-stack/`.
- Packaging/docs surface proves these files are publish artifacts, not dead duplicates:
  - `package.json` exports `harness_sdk.js` with `harness_sdk.d.ts`
  - `pyproject.toml` publishes `harness_sdk.py`
  - `README.sdk.md` documents both Python and TS/JS SDKs
  - `scripts/data/generate-harness-sdk-api-docs.sh` and `scripts/data/generate-harness-sdk-provenance.sh` reference them

Running-service determination:
- I found no evidence that the live hybrid-coordinator service imports the TS/JS artifacts at runtime.
- The TS/JS files are packaging/distribution artifacts for external consumers, not internal live-service dependencies.

Resolution:
- KEEP: `harness_sdk.py`
- KEEP: `harness_sdk.ts`
- KEEP: `harness_sdk.js`
- KEEP: `harness_sdk.d.ts`
- REMOVE/MERGE: none in this group
- Exact reason: these are multi-language SDK deliverables, not duplicate service modules. The JS and `.d.ts` files are the published Node package surface defined in `package.json`; the Python file is separately published via `pyproject.toml`.

Caller updates needed:
- None for live service imports.
- If future cleanup regenerates artifacts, packaging/docs/scripts would need coordinated updates:
  - `package.json`
  - `README.sdk.md`
  - `scripts/data/generate-harness-sdk-api-docs.sh`
  - `scripts/data/generate-harness-sdk-provenance.sh`

Confidence:
- High that the TS/JS files are not used by the live Python service.
- Medium-high that they are still intentionally kept for publishing/distribution rather than unused leftovers, because packaging metadata references them explicitly.

## Recommended Next Actions

1. Safe duplicate-removal candidate:
   - Consolidate garbage collection on `garbage_collector.py`.
   - Remove `garbage_collection.py` only after doc references are updated and manual operator usage is ruled out.

2. Non-duplicate groups to leave intact:
   - `continuous_learning.py`
   - `continuous_learning_daemon.py`
   - `real_time_learning_engine.py`
   - `agentic_memory_journal.py`
   - `memory_context_handlers.py`
   - `memory_manager.py`
   - `harness_sdk.py/.ts/.js/.d.ts`

3. Separate follow-up bugfix, not duplicate cleanup:
   - Fix stale `ops_handlers.py` health-path import of `learning_pipeline`.

## Not-Confident / Do-Not-Guess Flags

- I am not fully confident that `garbage_collection.py` has zero external manual usage outside repo-tracked code, because docs still reference it and no scheduler/service wiring was found in-repo.
- I did not find any live TS/JS service importing the harness SDK artifacts, but I did find explicit packaging metadata for them. They should be treated as publish artifacts unless a later phase intentionally removes multi-language SDK support.
