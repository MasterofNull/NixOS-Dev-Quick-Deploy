# Antigravity — Collaborative Round: RSI Readiness

## 1. Scores + Ratification
* **R1: 9/10** — Establishing a robust, non-gaming eval harness is the single most critical dependency for all downstream self-improvement work.
* **R2: 8/10** — A local write-execution reliability layer is sorely needed; local models frequently hallucinate or narrate file writes that never hit the filesystem.
* **R3: 9/10** — The `SMALL_RESIDENT` model (phi-4-mini) provides an excellent opportunity to offload simple verification/routing tasks, saving significant CPU/memory slots.
* **R4: 10/10** — A shadow-mode run with strict sandbox evaluation is the only correct way to measure proposal efficacy before granting any real autonomy.
* **R5: 8/10** — Trace seeding using unique IDs will connect asynchronous delegation and loop runs to a single, observable span.
* **R6: 8/10** — A flagship app focusing on the harness's own issues-backlog is a great dogfooding strategy.
* **R7: 9/10** — Git lock and index serialization are crucial; racing parallel agents clobbering each other's staging areas represents a major system reliability risk.
* **R8: 9/10** — A durable delegation queue that can park and resume tasks across transient or long quota limits is key to scaling remote-heavy workflows.

**Verdict:** **RATIFY** — We approve the PRD as-is. The focus on trust infrastructure and shadow-mode safety before autonomy matches our design philosophy.

---

## 2. Top Amendments
* **A1 — Dynamic Timeout Scaling in R1**: Ensure the Golden Task evaluation harness dynamically scales test timeouts based on system load/contention (e.g. promoting the prompt-5 infra contention classification) to prevent false-negative regressions during hardware bottlenecks.
* **A2 — Isolation of Shadow Workspaces in R4**: Shadow evaluation of self-improvement proposals must occur in strict, ephemeral git worktrees (e.g. `isolation: worktree`) rather than the primary workspace directory, avoiding dirty git states for parallel runners.
* **A3 — Attendant circuit-breaker metrics in R8**: The durable delegation queue must expose trace-linked latency/park metrics to the dashboard, ensuring "parked" queues do not turn into silent task blackholes.

---

## 3. Risks the PRD Underweights
* **KV-Cache Eviction Bottlenecks**: As parallel shadow agents run concurrently, the resident models will experience heavy prompt-context swapping. We must cache compiled prefix KV-caches to prevent heavy TTFT (Time to First Token) overhead.
* **Eval Gaming via Prompt Leaks**: Local models might overfit to the golden task set by reading the test definitions in the workspace. The golden test suite files must be excluded from the agent's read/search paths via `.gitignore` or a dedicated system-level path filter.
* **Quota Starvation on Remote Cascade**: Since remote Cascade calls are heavy, a high volume of shadow evaluations could trigger sustained remote rate-limits, locking up the system despite the durable queue. A token-budget rate limiter must be enforced at the switchboard level.

---

## 4. Slice Claims + Wiring Plan
* **R1: claim** — Research and compile the capability golden task set (focusing on code edits and schema validation) and design the evaluation scoring engine.
* **R4: claim** — Design the shadow proposal ledger and the sandbox run/validation evaluation pipeline.
* **R8: pass** — Bounded for Codex/local implementation to wire the queue state machine into the event bus.

---

## 5. Verdict + First Commit Target
**VERDICT:** **RATIFY**

**First Commit Target:**
`feat(eval): define golden task schema and validation criteria`
Co-Authored-By: Antigravity <noreply@harness.local>
