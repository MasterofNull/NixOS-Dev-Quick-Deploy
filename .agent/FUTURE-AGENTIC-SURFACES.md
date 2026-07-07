# Technical Briefing — Unlocking High-Speed Agentic Execution on Local NixOS Staging

To scale local multi-agent layouts to fully autonomous speeds under APU hardware allocations, we propose these five strategic engineering targets:

## 1. Dynamic Model Multiplexing & Context Offload Swapper
*   **Problem**: Ryzen Ryzen 7 iGPU context is limited to 12 layers (4GB memory partition). If multiple agents are running local Qwen3-35B and Llama-70B models concurrently, they clash on resources, forcing paging and throttling speed below 1 tok/s.
*   **Target**: Implement a systemd-bound model swapper that monitors the Switchboard queue. The manager actively swaps weights inside llama.cpp slot partitions when active targets shift.

## 2. GBNF Schema Compliance Verification Gate (Grammar Proxy)
*   **Problem**: Local inference fails to yield valid JSON arguments for MCP tools on ~15% of outputs, prompting agent tool-repair loops that waste tokens and cycles.
*   **Target**: Wire GBNF (GGML BNF Grammar) constraint files directly into Switchboard API boundaries. It coerces agent outputs into syntactically valid JSON tool parameters before execution.

## 3. Declarative AppArmor sandboxes for Sub-Agents
*   **Problem**: Allowing sub-agents to execute arbitrary scripts risks host path contamination outside the workspace `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy`.
*   **Target**: Declarative AppArmor files embedded in the system services configuration Nix modules restricting script executors strictly to read-only Nix store routes and workspace folders.

## 4. Episodic RAG recency decay and cache drift monitors
*   **Problem**: Stale codebase snippets contaminate RAG vector similarity searches, loading outdated files into context.
*   **Target**: A systemd timer checking workspace hashes and applying cosine distance decay penalties to old vector segments.

## 5. Agent-to-Agent Shared State Ledger (A2A Shared Cache)
*   **Problem**: Sub-agents issue duplicate `read_file` or `grep_search` tasks for identical configuration files, multiplying tokens.
*   **Target**: Establish a shared context cache (`headroom` proxy) allowing agents to read pre-warm configurations instead of executing duplicate storage file reads.

---

### Academic Links & Reference Resources
*   *Grammar-based Coercion in Small Quantized LLMs* (GGML specifications)
*   *Active Vector Search Decay and Codebase Recency Limits* (ACM digital library)
*   *Declarative sandboxing with Bubblewrap constraints* (NixOS security guides)

---

## 6. Remote Agent Orchestrations & Hybrid Boundaries
*   **Switchboard Cascade Routing**: Realized via custom routing profiles (`remote-reasoning`, `lifecycle-delegate`, `continue-local`). High-value planning tasks leverage remote OpenRouter endpoints (`llama-3.3-70b-instruct:free`, `gemini-2.5-flash-lite`), while routine edits route to the local APU-bound Qwen model.
*   **Dynamic Tool Sanitization (Zero-Trust)**: Routing policy maps enforce restricted tool catalogs. Any task processing credentials, secrets, or keys triggers a lock denying execution-level capabilities like `reload-model` or `proposals/apply` to remote actors.
*   **Decoupled Intelligence, Bound Verification**: While remote models drive complex architectural formulation, all files, modifications, and validation steps run strictly within the local host's POSIX DAC namespace via local-bound MCP servers.

## 7. Current System Goals for Modules & Tools
*   **Strict Declarative Alignment**: Guaranteeing that all packages, python dependencies, and system configurations are declared in Nix flake modules. Runtime workarounds are treated, as code smells and auto-flagged on the integrity dashboard.
*   **Maturity-Tier Progression**: Capability advancement from `backlog` -> `ready-for-prd` -> `promoted`. The dashboard observably represents candidate health, alerting manual operators when a module deviates from system SLAs.
*   **Episodic Memory Parity**: Ensuring local memory vector embeddings are mirrored to remote context frames uniformly, minimizing context length while matching prompt requirements.

## 8. Agentic Monitoring & Dashboard Observabilities
*   **Visualizing Trace Chains**: Implementing graphical node graphs directly on the dashboard depicting agent-to-agent command propagation (e.g. tracking switchboard redirects, tool outputs, and LLMFQ wait levels).
*   **Real-time Cost & Compression Counters**: Dynamically graphing local vs remote token ingestion, cost metrics, and exact cache compression savings (via lean-ctx metrics) to help human operators profile performance spikes.
*   **Error Loop Warnings**: Elevating warnings on the dashboard when a sub-agent spends more than 2 consecutive turns retry-looping on the same file path or tool type.

## 9. Continual Evaluation & Training Lifecycle
*   **Fine-Tuning Harvest Pipeline**: Capturing rejected runs, syntax crash traces, and tool-parsing failure events, automatically redacting secrets, and saving them into standard JSONL training files for Qwen/Llama custom quants.
*   **Automated Regression Testing**: Running a local Pytest matrix validating model responses against historical golden task records (from `.agent/memory/solved_tasks.json`) before permitting new models or weights to scale system-wide.
*   **State-Delta Assertions**: Wrapping evaluations around isolated workspace environments, comparing actual disk changed states with expected final actions to verify correctness.
