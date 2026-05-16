# Repository Library

This document tracks all repositories mentioned, borrowed from, or recommended for the NixOS-Dev-Quick-Deploy system. It serves as a reference for parity checks and update triggers.

## Core Dependencies (Flake Inputs)

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| nixpkgs | [github:NixOS/nixpkgs](https://github.com/NixOS/nixpkgs) | NixOS Package Collection | Primary package source. |
| home-manager | [github:nix-community/home-manager](https://github.com/nix-community/home-manager) | User Environment Manager | Manages user-specific configuration. |
| nixos-hardware | [github:NixOS/nixos-hardware](https://github.com/NixOS/nixos-hardware) | Hardware Modules | Optimizations for specific hardware. |
| disko | [github:nix-community/disko](https://github.com/nix-community/disko) | Disk Partitioning | Declarative disk management. |
| lanzaboote | [github:nix-community/lanzaboote](https://github.com/nix-community/lanzaboote) | Secure Boot | UEFI Secure Boot support. |
| sops-nix | [github:Mic92/sops-nix](https://github.com/Mic92/sops-nix) | Secret Management | Integration with SOPS for secrets. |

## Integrated Tools & MCP Servers

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| mcp-nixos | [github:utensils/mcp-nixos](https://github.com/utensils/mcp-nixos) | MCP for NixOS | Provides NixOS-specific tools via MCP. |
| SecureMCP | [github:makalin/SecureMCP](https://github.com/makalin/SecureMCP) | Security for MCP | Security layers for MCP interactions. |
| nix-ai-tools | [github:numtide/nix-ai-tools](https://github.com/numtide/nix-ai-tools) | AI Tools for Nix | Specialized AI development tools. |
| context-mode | [github:mksglu/context-mode](https://github.com/mksglu/context-mode) | Context Management | Enhanced context handling for agents. |

## Specialized Modules

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| nixos-apple-silicon | [github:tpwrules/nixos-apple-silicon](https://github.com/tpwrules/nixos-apple-silicon) | Asahi Linux Support | Support for M1/M2 Apple Silicon. |
| nix-flatpak | [github:gmodena/nix-flatpak](https://github.com/gmodena/nix-flatpak) | Flatpak Integration | Declarative Flatpak management. |
| nix-vscode-extensions | [github:nix-community/nix-vscode-extensions](https://github.com/nix-community/nix-vscode-extensions) | VSCode Extensions | Managed VSCode extensions. |

## Recommended Repositories (For Evaluation)

| Repo Name | URL | Description | Potential Use Case |
|-----------|-----|-------------|--------------------|
| nixified-ai | [github:nixified-ai/flake](https://github.com/nixified-ai/flake) | AI Infra Flake | Pre-configured local LLMs and AI tools with hardware acceleration. |
| Agentix | [github:Beach-Bum/Agentix](https://github.com/Beach-Bum/Agentix) | Safety Control Layer | Safety-first system modification proposals for agents. |
| uv2nix | [github:pyproject-nix/uv2nix](https://github.com/pyproject-nix/uv2nix) | Python-Nix Integration | Modern, fast dependency management for Python-based AI agents. |
| devenv | [devenv.sh](https://devenv.sh) | Dev Environments | Simplified development shells with built-in service support. |
| deploy-rs | [github:serokell/deploy-rs](https://github.com/serokell/deploy-rs) | Deployment Tool | Simple, multi-node NixOS deployment tool. |
| colmena | [github:zhaofengli/colmena](https://github.com/zhaofengli/colmena) | Deployment Tool | Scalable NixOS deployment and management. |
| nixos-rocm | [github:nixos-rocm/nixos-rocm](https://github.com/nixos-rocm/nixos-rocm) | ROCm Support | Optimized AMD GPU acceleration for AI workloads. |
| Flox | [github:flox/flox](https://github.com/flox/flox) | Env Management | Official CUDA binary caches and environment isolation. |

## Agent Frameworks & Stateful Orchestration

These repositories provide the high-level logic for managing complex, multi-turn agentic workflows and state.

| Repo Name | URL | Description | Potential Use Case |
|-----------|-----|-------------|--------------------|
| LangGraph | [github:langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | Stateful Graph Orchestration | Durable, cyclic agent workflows with human-in-the-loop. |
| CrewAI | [github:crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | Role-Based Multi-Agent Teams | Orchestrating teams of agents with specific SOPs. |
| Agno | [github:agno-agi/agno](https://github.com/agno-agi/agno) | Agent Runtime & MCP Engine | Session management and deep Model Context Protocol support. |
| Dify | [github:langgenius/dify](https://github.com/langgenius/dify) | Agentic Toolchain | Production-grade LLM app development and orchestration. |
| PydanticAI | [github:pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | Type-Safe Agent Framework | Strict I/O and validation for agentic interfaces. |
| DSPy | [github:stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | Retrieval-Model Optimization | Programmatically optimizing retrieval and prompt steps. |

## NixOS Developer Experience (DX)

Highly rated flakes and tools for modernizing the Nix development environment.

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| devenv | [github:cachix/devenv](https://github.com/cachix/devenv) | Declarative Dev Shells | Managing developer environments with background services. |
| nh | [github:viperML/nh](https://github.com/viperML/nh) | Nix Helper CLI | Cleaner UI and improved diffing for Nix operations. |
| flake-parts | [github:hercules-ci/flake-parts](https://github.com/hercules-ci/flake-parts) | Flake Modularization | Standardizing complex, multi-system flake outputs. |
| nix-direnv | [github:nix-community/nix-direnv](https://github.com/nix-community/nix-direnv) | Automatic Env Loading | Instant activation of Nix flakes upon directory entry. |
| nix-starter-configs | [github:Misterio77/nix-starter-configs](https://github.com/Misterio77/nix-starter-configs) | System Templates | Reference for advanced NixOS/Home Manager patterns. |

## RAG, Memory & Vector Databases

Infrastructure for managing agentic knowledge and long-term memory at scale.

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| LlamaIndex | [github:run-llama/llama_index](https://github.com/run-llama/llama_index) | Data Framework for LLMs | Advanced RAG patterns and data connector suite. |
| Qdrant | [github:qdrant/qdrant](https://github.com/qdrant/qdrant) | Vector Search Engine | High-performance vector database (primary target). |
| Weaviate | [github:weaviate/weaviate](https://github.com/weaviate/weaviate) | Hybrid Search Database | Native vector + keyword + graph retrieval. |
| Ragas | [github:explodinggradients/ragas](https://github.com/explodinggradients/ragas) | RAG Evaluation Framework | Automated metrics for retrieval and generation quality. |
| Arize Phoenix | [github:Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | AI Observability | Tracing and evaluation for RAG and agentic traces. |

## Specialized MCP Servers (High Signal)

| Repo Name | URL | Description | Role in System |
|-----------|-----|-------------|----------------|
| Context7 | [github:upstash/context7](https://github.com/upstash/context7) | Dynamic Docs MCP | Real-time fetching of version-accurate documentation. |
| Firecrawl | [github:mendableai/firecrawl](https://github.com/mendableai/firecrawl) | Web-to-Markdown MCP | Converting URLs into LLM-ready structured data. |
| Playwright MCP | [github:microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | Browser Automation | Navigating and interacting with web applications. |
| Blink Plugin | [github:blink-new/blink-plugin](https://github.com/blink-new/blink-plugin) | Infrastructure MCP integration | Managed deployment, auth, and storage tools. |
| Terraform MCP | [github:hashicorp/terraform-mcp-server](https://github.com/hashicorp/terraform-mcp-server) | Infrastructure-as-Code MCP | Querying and managing cloud infrastructure via agents. |

## Tool Aggregators & MCP Directories

These are the primary sources for discovering and "borrowing" new agentic tools and server implementations.

| Repo/Site Name | URL | Description | Role in System |
|----------------|-----|-------------|----------------|
| Official MCP Servers | [github:modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | Official reference implementations. | Reference for core MCP tools and examples. |
| Awesome MCP Servers | [github:punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | Community-curated list of MCP servers. | Primary discovery source for specialized tools. |
| All MCP Servers | [allmcpservers.com](https://www.allmcpservers.com/) | Web directory of MCP servers. | Backend for the `all-mcp-directory` skill. |
| Awesome MCP Servers (alt) | [github:wong2/awesome-mcp-servers](https://github.com/wong2/awesome-mcp-servers) | Another curated directory/listing. | Secondary discovery source. |
| Model Context Protocol | [modelcontextprotocol.io](https://modelcontextprotocol.io/) | Official MCP Specification. | Standards reference for all tool development. |

## Internal AI Stack Modules (The Harness)

These are the locally implemented components that form the core of the NixOS AI Harness.

| Module Name | Path | Description | Role in System |
|-------------|------|-------------|----------------|
| hybrid-coordinator | `ai-stack/mcp-servers/hybrid-coordinator` | UAG & Lifecycle Orchestrator | The "brain" that plans, delegates, and validates workflows. |
| AIDB | `ai-stack/aidb` & `ai-stack/mcp-servers/aidb` | Agentic Knowledge Base | RAG engine, memory store, and tool registry. |
| switchboard | `ai-stack/switchboard` | LLM Proxy & Router | Handles local/remote model routing and loop detection. |
| identity-kernel | `ai-stack/identity-kernel` | Persistent System Identity | Maintains system-wide agent identity and journals. |
| autonomous-improvement | `ai-stack/autonomous-improvement` | PRSI & Self-Optimization | Drives the closed-loop improvement of the stack itself. |
| aider-wrapper | `ai-stack/mcp-servers/aider-wrapper` | Aider Integration | Bridges the Aider coding agent into the harness. |
| ralph-wiggum | `ai-stack/mcp-servers/ralph-wiggum` | Diagnostic & Learning Agent | Specialized in system-wide diagnosis and knowledge ingestion. |
| affective-engine | `ai-stack/affective-engine` | Behavioral Modulator | Injects values and affective signals into agent behavior. |
| world-model | `ai-stack/world-model` | Predictive Context Engine | Forecasts intent and pre-warms context. |

## Strive to Implement (Roadmap)

The following features are actively being developed or are planned to reach world-class agentic status.

### Phase 1: Advanced Memory (P0)
*   **Temporal Facts**: Implement `valid_from` and `valid_until` for knowledge to handle stale information.
*   **Metadata Filtering**: High-accuracy retrieval using project/topic/type filters.
*   **L0-L3 Loading**: Progressive context disclosure to reduce token usage by 50%+.
*   **Agent Diaries**: Private expertise accumulation for individual agents (qwen, claude, etc.).

### Phase 2: Workflow DSL & Engine (P0)
*   **Workflow DSL**: A YAML-based declarative language for complex multi-agent tasks.
*   **Durable Execution**: Checkpoint and resume support for long-running workflows.
*   **Fresh Context Loops**: Automatic context reset per iteration to prevent model drift.

### Phase 3: Isolation & Performance (P1)
*   **Worktree Isolation**: Parallelize agent runs using isolated git worktrees.
*   **Multi-tenant Runtimes**: Secure, scoped execution environments for untrusted tools.

### Phase 5: Essential GUI (P0)
*   **Workflow DAG Viz**: Interactive visualization of agent execution graphs.
*   **Real-Time Log Stream**: WebSocket-based centralized logging dashboard.
*   **Memory Browser**: UI for searching and managing the AIDB knowledge base.

## Discovery & Search Patterns

Agents should use these patterns to orient themselves within the stack:

*   **Search for active modules**: `ls ai-stack/mcp-servers`
*   **Search for roadmaps**: `grep -r "PHASE" .agents/plans/`
*   **Search for parity gaps**: `cat docs/AGENT-PARITY-MATRIX.md`
*   **Search for recent decisions**: `aq-memory search "decision" --limit 10`
*   **Identify running services**: `systemctl list-units "ai-*"`

## Parity Checks & Update Triggers
... (rest of the file) ...

### Parity tooling semantics

The repo library intentionally mixes several kinds of repositories:

- **Core Dependencies (Flake Inputs)** are expected to appear in `flake.nix` / `flake.lock`.
- All other sections are **reference-only** inputs for discovery, benchmarking, or future evaluation.

`scripts/maintenance/repo-parity-check.py` only treats the core dependency section as a hard flake-input parity contract.  
`scripts/maintenance/update-repo-parity.py` still refreshes upstream metadata for the wider library, but records whether each entry is a `core_flake_input` or `reference_only` repo so operators do not mistake a benchmark/reference repo for a missing flake input. Historical rows removed from the active library are retained as `retired_reference`, and transient upstream failures can be retried immediately with:

```bash
python3 scripts/maintenance/update-repo-parity.py --retry-problematic
```

These repositories have directly influenced the design of this system or are used as benchmarks for feature parity.

| Repo Name | URL | Influence / Parity Target |
|-----------|-----|---------------------------|
| Codebuff | [github:CodebuffAI/codebuff](https://github.com/CodebuffAI/codebuff) | Staged workflow (plan/edit/review) and planner stage. |
| pi coding-agent | [github:badlogic/pi-mono](https://github.com/badlogic/pi-mono) | Session branching, tree navigation, and RPC ergonomics. |
| Claude Code | [github:anthropics/claude-code](https://github.com/anthropics/claude-code) | Professional CLI loops, agentic tools, and evidence contracts. |
| Aider | [github:Aider-AI/aider](https://github.com/Aider-AI/aider) | Best-in-class multi-file editing and repo-map generation. |
| TaskWeaver | [github:microsoft/TaskWeaver](https://github.com/microsoft/TaskWeaver) | Planning and task-oriented agent orchestration. |
| Google ADK | [github:google/adk-python](https://google.github.io/adk-docs/) | Standards for A2A communication and MCP interoperability. |
| SWE-agent | [github:princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent) | Software engineering benchmark standards and agent-computer interface. |
| OpenCode | [github:anomalyco/opencode](https://github.com/anomalyco/opencode) | Planner/executor separation and safety mode enforcement. |
| Cline | [github:cline/cline](https://github.com/cline/cline) | Guarded tool execution and interactive safety gates. |
| Goose | [github:block/goose](https://github.com/block/goose) | Composable agentic toolkit and MCP implementation. |
| Tracecat | [github:TracecatHQ/tracecat](https://github.com/TracecatHQ/tracecat) | Secure enterprise agent orchestration patterns. |

## Agentic Capabilities & Safety Guards

| Feature | implementation Path | Reference Tooling |
|---------|---------------------|-------------------|
| PRSI Loop | `ai-stack/self-improvement` | Pessimistic Recursive Self-Improvement logic. |
| RAG Augmentor | `ai-stack/progressive-disclosure` | Active context injection via AIDB. |
| Safety Gate | `scripts/governance/tier0-validation-gate.sh` | Runtime enforcement and security checklist. |
| Tool Auditor | `ai-stack/mcp-servers/shared/tool_security_auditor.py` | First-use scan and safe-cache metadata. |
| Loop Guard | `switchboard` logic | Similarity-based self-correction detection. |
| Reviewer Gate | `hybrid-coordinator` (`/review/acceptance`) | Deterministic evidence-based acceptance criteria. |
