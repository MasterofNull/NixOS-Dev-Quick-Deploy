# Antigravity — Foundation Critique of the Flat-Collaborative Factory Core

## 1. Is it too ad-hoc? — YES, in specific, structural areas
1. **Ad-hoc state propagation via file-system polling**: Relying on periodic directory polls (`.agents/plans/...` and `antigravity-inbox/...`) introduces high latency and lack of event-driven capability. We need a lightweight **State and Event Broker** (such as a local SQLite or Redis instance) that records task states and dispatches jobs asynchronously.
2. **Unstructured prose inputs**: `<agent>.md` files containing freeform critiques cannot be aggregated programmatically. Aggregation is restricted to manual operator intervention or fragile LLM parsing. We must transition to a standardized JSON schema for agent critiques and votes (declaring `verdict`, `required_changes[]`, `risks_identified[]`, and `cons_voted`).
3. **No security/token scope limits on execution**: The sub-agent running in `edit` or `yolo` mode currently has read access to the general home directory structure and key storage files. We need to tie active tool access to signed capability tokens issued per task.

## 2. Where to improve + what is MISSING (papers/systems/logic)
- **Stateful orchestration**: Study **LangGraph** (stateful multi-agent DAGs) and **Temporal / Durable Task** engines (durable execution for long-running workflows with sagas and automatic recovery).
- **Inference cascades**: Study **FrugalGPT** (LLM routing cascade — escalating from low-cost resident models to high-cost models only when tests fail) and **RouteLLM** (predictive complexity-based routing).
- **Consensus & debate protocols**: Study **Mixture-of-Agents** (Wang et al. — layered fan-out of sub-agents feeding an aggregator model for consensus) and **Multi-Agent Debate** frameworks.
- **OTel Mapped Telemetry**: Implement OpenTelemetry tracing spans encompassing the entire multi-agent loop, logging token footprints, latency, and tool execution failures to standard Grafana/Jaeger setups.

## 3. Highest Operability Target
- **Idempotency & Resumability**: Every agent dispatch must carry a unique transaction/idempotency key. If a sub-agent crashes or is interrupted by system OOM, the scheduler must resume from the last successful checkpoint instead of re-running the entire delegation.
- **Automatic Rollbacks**: Before executing files with write access, snapshot the workspace structure (e.g. via git stash or worktree isolation) to allow instant state reversion when tests or validation checks fail.
- **Metadata Provenance Trails**: Log the precise execution telemetry for every contribution: hardware context, model tag, input/output tokens, and latency metrics.

## 4. Local-agent stacking/scheduling (the utilization fix)
1. **Resident Low-Latency Models**: Run a lightweight model (e.g., `phi-4-mini` or `Qwen2.5-4B`) warm in memory for classification, JSON validation, GBNF schema parsing, and simple unit test failures, reserving the 35B model exclusively for multi-file planning sessions.
2. **VRAM Pool Manager**: Implement a priority queue that unloads/swaps model slots in llama.cpp gracefully only if memory headroom is exceeded, gating swaps with a 30-second throttle period.
3. **GBNF Cache**: Cache compiled GBNF grammar strings by schema signature hash to mitigate conversion latency on local models.

## 5. Top 3 changes (ranked)
1. **Durable, typed round state machine**: Write `round.json` with strict validation schemas.
2. **Local model-stacking + Slot Scheduler**: Introduce a warm-small / cold-large model pool with queued concurrency and VRAM tracking.
3. **Traceable execution & consensus**: Wire OpenTelemetry tracing and voting protocols for reproducibility.
