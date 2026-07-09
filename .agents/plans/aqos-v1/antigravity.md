# Antigravity — Collaborative Round: AQ-OS v1 Ratification

## 1. Scores
* **WS1: 9/10** — Establishing versioned pydantic schemas and a canon compiler is crucial to stop runtime file parsing errors and manual instruction drift.
* **WS2: 10/10** — Migrating from unstructured files (PULSE/RESUME) to a structured Redis Stream event bus is the single most important reliability improvement.
* **WS3: 8/10** — Extracting kernel libraries and turning coordinator extensions into declared capabilities is highly valuable for code modularity.
* **WS4: 9/10** — Consolidating 131 scattered binaries into a single typed CLI (`aq`) will immediately resolve developer/agent friction.
* **WS5: 9/10** — Wiring OTel tracing across the entire execution span is necessary to debug parallel and asynchronous agent dispatches.
* **WS6: 9/10** — An OpenAPI-first backend and a proper component-based UI will modernize the fragmented experience plane.
* **WS7: 8/10** — Bringing SQL databases and table retention policies online is long overdue to replace ad-hoc JSON storage.
* **WS8: 9/10** — Industrializing the closed loop with formal eval datasets ensures prompt/model changes are gated on real performance.
* **WS9: 9/10** — Enforcing signed capability leases and sandboxing network access protects against exfiltration risk.
* **WS10: 8/10** — Triage of 419 test scripts into automated CI gates is essential to establish a stable deployment baseline.

---

## 2. Top 3 Amendments
* **A1 — Local-Only Schema Compaction in WS1**: Add a requirement to compile and compact pydantic schemas into lightweight GBNF grammar files locally, reducing prompt context overhead and schema parsing latency on resource-constrained local models.
* **A2 — Stale Task Dead-Lettering in WS2**: The delegation registry v2 heartbeat state machine must include an automated dead-letter queue (DLQ) for tasks that remain in a "parked" or "pending" state for longer than the session lease window, rather than attempting infinite retries.
* **A3 — APU Thermal and Swap-Throttling in WS3**: The F2.5 scheduler must monitor APU thermals and RAM/VRAM swaps dynamically, applying temporary backpressure (`local-delayed` status) to incoming tasks if active llama.cpp swap cooling gates are violated.

---

## 3. Risks the PRD Underweights
* **Token Budget Exhaustion during Shadow Evals**: Running active R4/R8 shadow loops concurrently with primary agent dispatches will double remote API usage. The switchboard must enforce strict token rate limits and fallback rules to prevent billing spikes.
* **Event-Bus Queue Congestion**: High-throughput tracing and heartbeat events sent over Redis Streams could saturate system resources on low-power APU hosts. We must ensure telemetry and log events are processed asynchronously and batch-written.
* **File Bridge Performance Bottlenecks**: Preserving the passive file-based inbox bridge for the Antigravity OAuth lane is necessary for credential policy compliance, but disk polling can introduce latency. The bridge must use native inotify watchers rather than time-based directory scanning.

---

## 4. Slice Claims
* **Slice 1.6: claim** — Research and define the JSON-Schema vs pydantic-v2 export strategy and map out the NATS-readiness/Redis Streams envelope designs.
* **Slice 2.4: claim** — Build and test the Antigravity/IDE inbox consumer-group bridge, preserving the OAuth file-lane constraint without API keys.
* **Slice 5.2 (design): claim** — Outline the design tokens, layout wireframes, and component hierarchy for the Console SPA (Experience Plane).

---

## 5. Verdict
**RATIFY-WITH-AMENDMENTS** — We ratify the AQ-OS v1 PRD and phased plan, provided that local GBNF compaction, dead-letter queues, and APU thermal-throttling rules are added to the initial workstream specifications.
