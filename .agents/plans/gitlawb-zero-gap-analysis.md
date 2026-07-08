# Parity Gap Analysis: Gitlawb/zero vs NixOS-Dev-Quick-Deploy

This analysis provides a feature-by-feature comparison and extracts actionable lessons from the Go-based [Gitlawb/zero](https://github.com/Gitlawb/zero) repository to optimize the local NixOS AI harness.

---

## 1. Philosophical Comparison & Tech Stack

| Metric/Dimension | Gitlawb/zero | NixOS-Dev-Quick-Deploy |
| :--- | :--- | :--- |
| **Language & Build** | Go (Single Compiled Binary, no external runtime) | Python (FastAPI/Aiohttp) + Node.js (Dashboard UI) |
| **Target Runtime** | Cross-platform local machine (npm global, Go bin) | NixOS-declarative flake services & local llama.cpp |
| **Integrations** | 25+ API backends + Ollama/LM Studio | Local Qwen3-35B/8B warm pools + OpenRouter fallback |
| **Process Footprint** | Extremely low (cold start <300ms, RAM <256MB RSS) | Medium-High (FastAPI overhead + server pools) |
| **Agent Paradigm** | Terminal-native, single-loop execution | Collaborative multi-agent fan-out (A2A loops) |

---

## 2. Feature-by-Feature Parity Grid

### A. Context & Token Optimization
* **Gitlawb/zero (`internal/minify`)**: Implements strict token-minimization views. 
  - For Go files, it uses the official Go AST (`go/parser` and `go/printer`) to guarantee comment/whitespace stripping without syntax breakage.
  - For other languages, it uses string-aware comment strippers (safely escaping quotes/f-strings) falling back to whitespace-only compaction on complex/unsupported syntax.
* **NixOS-Dev-Quick-Deploy**: Uses standard file outlines (`mcp_ctx_outline`) and full reads (`mcp_ctx_read`). While outlining saves tokens on structural exploration, we lack an automated code-aware minification pipeline for direct file analysis, meaning we frequently pass unnecessary verbose comments/formatting to local inference slots.

### B. Workspace Isolation & Sandboxing
* **Gitlawb/zero (`internal/worktrees`)**: Dynamically utilizes `git worktree` structures. Whenever an agent performs destructive code edits or validations, it spins up temporary, clean git worktrees under local directories. This prevents polluting or corrupting the main working tree during execution.
* **NixOS-Dev-Quick-Deploy**: Relies on host-level bubblewrap (`bwrap`) / AppArmor sandboxing (declared in Slice 2) and git status tracking with rollback routines in the main workspace. We carry risk of file locking and lock pollution when running concurrently.

### C. Headless Integration Interfaces
* **Gitlawb/zero (`docs/STREAM_JSON_PROTOCOL.md`)**: Defines a rigid, versioned line-delimited stream-json protocol (`zero exec --input-format stream-json --output-format stream-json`). This permits editor plugins (VS Code, NeoVim) or automation cascades to pipe structured payloads via stdin/stdout seamlessly, preventing JSON truncation/drift issues.
* **NixOS-Dev-Quick-Deploy**: Streams live agent states via state delta WebSockets (`/ws/agent-state`) and reads structured JSON records (`RESUME.json` / `PULSE.log`).

### D. Offline Quality & System Evlatuations
* **Gitlawb/zero (`docs/AGENT_EVALS.md`)**: Integrates local-first offline evaluation fixtures (`agenteval` suite under `testdata/`). These define task prompts, expected/forbidden modified files, trace telemetry checks, and output command criteria. It evaluates prompt and model generation changes locally and deterministically.
* **NixOS-Dev-Quick-Deploy**: Relies on programmatic Tier 0 validation gates and unittest-focused QA test phases. We lack a model-focused prompt-to-diff offline rating system.

---

## 3. Actionable Lessons for NixOS AI Harness

### Lesson 1: Implement Token-Aware Comment/Whitespace Minification (Context View)
* **Gap**: We burn slot VRAM/context processing comments and verbose spaces.
* **Action**: Introduce a `minify` view pipeline inside our MCP context engine (`lean-ctx`). Before importing entire file contents for planning prompts, pass the content through python's `ast` parser (for `.py` files) or comment removal regexes (for `.js` or `.nix`), ensuring the model sees a condensed, syntactically-valid version.

### Lesson 2: Transition from Main Tree to Git Worktrees for Execution Sandbox
* **Gap**: Concurrent local agent loops can collide, dirty git states, or write temporary tracking files in place.
* **Action**: Integrate a temp-worktree command wrapper in our `scripts/testing` and execution runner. When starting a sub-agent slice task (e.g. yolo edit mode), check out a temporary workspace tree (`git worktree add .git/worktrees/agent-task-...`) inside system temp directories, run output validations there, commit if successful, and merge back to main.

### Lesson 3: Introduce Prompt & Diff Offline Eval Fixtures
* **Gap**: When changing core system prompts, templates, or GBNF rules, it is difficult to determine if they degrade task execution without testing a live iteration.
* **Action**: Build an offline evaluation runner (`scripts/testing/run-agent-fixtures.py`) inspired by zero's `agenteval`. Maintain a tiny suite of 10 static tasks with golden prompts and expected files, and test new prompt profiles against this suite periodically.

### Lesson 4: Adopt Line-Delimited Stderr/Stdout Stream JSON Protocol
* **Gap**: Our CLI tool wrapper outputs are parsed by command output grepping which is sensitive to formatting changes.
* **Action**: Standardize a clean `--jsonl` or `--stream-json` flag for our harness orchestration scripts (`delegate-to-antigravity`, `aq-prime`), outputting line-separated JSON events containing `type`, `runId`, `delta`, and `tool_call` data.
