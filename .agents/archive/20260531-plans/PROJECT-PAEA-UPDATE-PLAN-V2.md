# Advanced System Update Plan: P.A.E.A Implementation

---

## Phase 1: The Context & Session Engine (HCE + BSM)
**Goal:** Upgrade the fundamental data structures of the harness.

1.  **Hierarchical Context:** Write `scripts/ai/lib/context_merger.py` to handle recursive `AGENTS.md` loading.
2.  **DAG Session Storage:** Refactor `ai-stack/agent-memory/session_manager.py` to support parent-child relationships in turn IDs.
3.  **CLI Tooling:** Add `aq-branch <turn_id>` to the CLI.
4.  **Validation:** Demonstrate an agent following directory-specific rules in `src/api/` that contradict root rules.

---

## Phase 2: Intent Modeling & Dual-Layer Eval (GIT + DLV)
**Goal:** Precision and Measurement.

1.  **PVIWR Schema Migration:** Refactor all 50+ tool descriptions in the harness to follow the Gherkin-style schema.
2.  **Tool Selection Benchmark:** Create `tests/benchmarks/tool_selection.json` with 100+ natural language prompts and expected tool calls.
3.  **QA Gate Integration:** Add `aq-qa --bench tool-selection` to the core diagnostic loop.
4.  **Validation:** Achieve >85% selection accuracy on the benchmark suite using the local Qwen3-35B.

---

## Phase 3: Token Arbitrage & Switchboard 2.0
**Goal:** Efficiency and specialized model usage.

1.  **Model Tiering Config:** Update `config/switchboard/profiles.yaml` to define `l1-triage` and `l2-reasoning` model mappings.
2.  **Route Intelligence:** Implement a "Complexity Estimator" in the switchboard that analyzes the length and depth of the request to select the model tier.
3.  **Local Model Optimization:** Ensure the `l1` model is quantized for maximum speed (e.g., Llama-3-8B-Q4_K_M).
4.  **Validation:** Measure a >30% reduction in end-to-end latency for "Research" phases.

---

## Phase 4: Temporal Hardening & A-TUI
**Goal:** Security and Observability.

1.  **Nix Temporal Check:** Implement `scripts/governance/check-flake-age.sh` and wire it into `tier0-validation-gate.sh`.
2.  **Textual TUI Integration:** Refactor `aq-qa` output to use a rich terminal dashboard.
3.  **Live Diff Previews:** Add a TUI component that shows the proposed `replace` side-by-side with the current file content.
4.  **Validation:** Attempt to update a flake input to a "zero-day" release and verify the build gate blocks it.

---

## Phase 5: Autonomous Software Factory (AFK)
**Goal:** Self-extensibility and "Always-On" operations.

1.  **Skill Scaffold:** Create `scripts/ai/aq-factory --type skill` to generate new agent workflow modules.
2.  **Daemon Task Handover:** Implement the `aq-daemon` task queue for long-running "Software Factory" jobs.
3.  **Final Integration:** Wired background agents to the dashboard with live DAG visualization.
4.  **Validation:** Run a "Phase 1-4 Complete" system audit using a backgrounded agent and verify the signed-off report on the dashboard.
