# Deep Technical Analysis: Pi Harness & Agentic Engineering Benchmarks

**Date:** 2026-05-25
**Subject:** Granular Tactics and Architectural Patterns for Agentic Advancement

---

## I. Pi Harness: The Minimalist High-Integrity Runtime
The `earendil-works/pi` harness (and its `@pi-coding-agent` ecosystem) provides a blueprint for transparent, extensible agentic environments.

### 1. Hierarchical Context Loading (`AGENTS.md`)
*   **Logic:** Pi traverses the file system from the CWD upwards to the root, loading `AGENTS.md` (or `CLAUDE.md`) files at each level.
*   **Tactical Advantage:** This allows for "layered instructions." Root-level rules govern security/formatting, while directory-level rules govern specific library conventions (e.g., `src/api/AGENTS.md` enforcing FastAPI patterns).
*   **Implementation Path:** We can implement a similar `aq-load-context` utility that builds a composite system prompt based on directory depth.

### 2. Branchable Session Trees (JSONL)
*   **Logic:** Sessions are not linear logs but JSONL-based trees. Every turn is an entry with a parent ID.
*   **Tactical Advantage:** Enables the `/checkout` command to "branch" a conversation. If an agent goes down a rabbit hole, the user can reset to a specific state without losing the alternate path's data.
*   **Implementation Path:** Refactor `hybrid-coordinator` session management to use a DAG (Directed Acyclic Graph) structure instead of a linear array.

### 3. Runtime Extensions via `jiti`
*   **Logic:** Pi uses `jiti` to load TypeScript extensions at runtime without a compilation step.
*   **Tactical Advantage:** Agents can "self-extend" by writing their own hooks for `session`, `tool`, or `compact` events.
*   **Implementation Path:** For our Python-based stack, we can use `importlib` and a dedicated `plugins/` directory to allow agents to register new tool logic dynamically.

---

## II. Agentic Engineering: Advanced Tactics (IndyDevDan)
The shift from "vibe coding" to engineering requires formalizing the agent's interaction surface.

### 1. The "Gherkin" Intent Schema
*   **Tactic:** Define tasks using a standardized structure: **Purpose → Variables → Instructions → Workflow → Expected Output.**
*   **Why:** This reduces model "hallucination" by providing a strict logical cage for the reasoning engine.
*   **Implementation Path:** Update our `.agent/workflows/` templates to strictly follow this 5-point schema.

### 2. Dual-Layer Evaluation (Selection vs. Execution)
*   **Tactic:** Separate the success metric into two distinct gates.
    *   **Gate A (Selection):** Did the agent choose the correct tool with the correct arguments?
    *   **Gate B (Execution):** Did the tool produce the expected side effect (code change, test pass)?
*   **Implementation Path:** Update `aq-qa` to include a "synthetic task" suite where the agent's *selection* logic is benchmarked against a known-good tool trace.

### 3. Token Arbitrage & Model Tiering
*   **Tactic:** Use "Haiku-class" models for triage and "Sonnet-class" for implementation.
*   **Why:** Maximize context efficiency and reduce latency/cost.
*   **Implementation Path:** Configure the `switchboard` to auto-route `ls`, `grep`, and `read_file` calls to a smaller local model (e.g., Llama-3-8B), reserving Qwen3-35B for `replace` and `write_file` implementation steps.

### 4. Software Factory: The Description is the Lever
*   **Tactic:** The single most influential part of a tool is its natural language description.
*   **Implementation Path:** Implement a "Tool Auditor" that uses a local model to critique tool descriptions for ambiguity before they are registered in AIDB.

---

## III. System Integration: Supply-Chain Hardening
*   **Pi-ism:** `.npmrc` enforcement of `min-release-age` to mitigate protestware.
*   **NixOS Implementation:** Create a custom Nix overlay/check that verifies the `lastModified` timestamp of all flake inputs. Block `nixos-rebuild` if any input is less than 48 hours old (unless overridden).

---

## IV. Summary of Parity Gaps
| Feature | Our Current State | Benchmark Target |
|---|---|---|
| **Context Loading** | Single root `AGENTS.md` | Hierarchical recursive `AGENTS.md` |
| **Session Model** | Linear history | Branchable JSONL trees |
| **Tool Eval** | Functional testing only | Selection vs. Execution dual-eval |
| **Hardening** | Dependency pinning | Temporal "min-release-age" gating |
| **UI/UX** | Scrolling logs | Differential TUI progress tracking |
