# local[Qwen] — rsi-readiness ratification

## 1. Scores + Ratification
* **R1: 9/10** — Crucial. The evaluation harness must be trustworthy and immune to model gaming or infrastructure noise.
* **R2: 8/10** — Necessary. Restoring write-reliability prevents local models from fabricating file writes.
* **R3: 7/10** — Useful. Phi-4-mini (SMALL_RESIDENT) can offload routine checks and conserve resources.
* **R4: 9/10** — Important. Sandbox-confined shadow execution is the correct methodology to test proposal safety.
* **R5: 7/10** — Good. Trace IDs will unify asynchronous delegation and loop observability.
* **R6: 8/10** — Good. Targeting the harness's own backlog is a sound integration proof.
* **R7: 9/10** — Stricter git and worktree serialization is required to prevent parallel runs from clobbering states.

**Verdict:** **RATIFY** — The PRD's focus on trust infrastructure, sandbox testing, and shadow-only loops matches local execution requirements.

## 2. Top Amendments
* **A1 — Dynamic Timeout Adaptability (R1)**: Timeout limits in the capability evaluation harness should dynamically adapt based on CPU/RAM contention.
* **A2 — Strict Tool-Level Confinement (R4)**: Implement direct tool-level guards in the executor when running shadow loop tasks to guarantee no destructive mutations can occur.

## 3. Risks the PRD Underweights
* **Model KV-Cache Thrashing**: Parallel agent executions on the local APU will lead to heavy swapping/prefill delays unless a cache pool manager is deployed.
* **Human Operator Fatigue**: High volume of shadow-loop proposals can saturate the human review queue, making the gate a rubber stamp.

## 4. Slice Claims + Wiring Plan
* **R2 training-data curation: claim** — Compile local failure traces as teacher-correctable samples to improve future model updates.
* **R6 flagship validation: pass** — Claude/Antigravity will orchestrate flagship validation.

## 5. Verdict + First Commit Target
**VERDICT:** **RATIFY**

**First Commit Target:**
`feat(local): initialize local training data collection for write reliability`
Co-Authored-By: local-qwen <noreply@harness.local>
