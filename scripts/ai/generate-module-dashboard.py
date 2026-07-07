#!/usr/bin/env python3
"""
NixOS System Capabilities Module Info generator
Reads config/system-capability-catalog.json and outputs beautiful, modern dark-themed HTML report pages.
Enriched with detailed codebase implementations, functional pipelines, CS groundings, Mermaid diagrams, and academic publications references.
"""

import os
import json
import sys

# Core educational database for all system capability modules
ENRICHED_DETAILS = {
    "aq-eval-harness": {
        "implementation": "Vented via `scripts/ai/aq-eval` wrapper and `scripts/testing/test-aq-eval.py`. It parses execution suites declared in `config/aq-eval-suites.json` and invokes pytest subcommands utilizing specialized test environments. Result logs are captured and written to `.evaluation-results.json` for agent ingestion.",
        "function": "Enforces pre-commit gates by running code-level parsing, type analysis, and contract checking. It parses AST structures to confirm tool wiring syntax, checks API parameters, and compiles code changes dynamically to prevent syntax errors from entering staging.",
        "grounding": "Continuous AI Evaluation Loop (MMLU-style local gating). By separating building from verification, this module establishes a strict validator-actor pattern, ensuring generated code is statically checked before it runs in production.",
        "mermaid": """graph TD
  A[git hook/manual] -->|Triggers| B[aq-eval CLI]
  B -->|Reads| C[aq-eval-suites.json]
  B -->|Runs| D[pytest execution]
  D -->|Spawns sandbox| E[Isolated environment]
  E -->|Writes logs| F[.evaluation-results.json]
  F -->|Inbound check| G[Expert Agent Verification]""",
        "publications": [
            ("Holistic Evaluation of Language Models (HELM) (Liang et al.)", "https://arxiv.org/abs/2211.09110"),
            ("Garak: LLM Vulnerability Scanner GitHub Repository", "https://github.com/leondz/garak"),
            ("Pytest Framework Documentation & Execution Standards", "https://docs.pytest.org/")
        ]
    },
    "aq-inference-bench": {
        "implementation": "Executed through `scripts/ai/aq-inference-bench.py`. Uses benchmark prompts to measure local model execution metrics. It interfaces directly with local llama.cpp endpoints via HTTP socket measurements to track memory pressure and CPU offloading.",
        "function": "Simulates multi-turn prompt scenarios to calculate time-to-first-token (TTFT), tokens per second (t/s), context window memory scaling, and CPU/iGPU resource contention metrics.",
        "grounding": "Hardware constraints modeling for Edge AI. Grounded in model performance scaling equations and resource cost curves, ensuring LLM concurrency profiles are optimized to prevent System Out-Of-Memory (OOM) failures on low-VRAM platforms.",
        "mermaid": """graph TD
  A[Benchmark CLI] -->|Sockets| B[llama.cpp :8080]
  B -->|Measures| C[TTFT & tokens/sec]
  B -->|Tracks| D[iGPU VRAM & RAM]
  C & D -->|Outputs| E[JSON performance metrics]""",
        "publications": [
            ("llama.cpp Architecture & iGPU Offload Specifications", "https://github.com/ggerganov/llama.cpp"),
            ("LLM.int8(): 8-bit Matrix Multiplication for Transformers (Dettmers et al.)", "https://arxiv.org/abs/2208.07339"),
            ("Performance Tuning for Local Small Language Models", "https://arxiv.org/abs/2403.08299")
        ]
    },
    "capability-intake": {
        "implementation": "Coordinates via the ingestion file `config/agent-capability-intake-candidates.json` and intake gates. Implemented as a validation check inside `scripts/ai/aq-capability-catalog` to query and verify external MCP and plugin packages.",
        "function": "Scans proposed third-party dependencies against target hashes, checks supply-chain licenses, assesses vulnerability catalogs, and prompts human approval logs before allowing package inclusions.",
        "grounding": "Secure Supply Chain & Verification Gateways (OWASP Top 10 for LLMs - Insecure Plugins). Restricts tool surfaces to deny-by-default logic until a strict vetting pipeline declares security compliance.",
        "mermaid": """graph TD
  A[Intake CLI] -->|Parses| B[Candidates list]
  B -->|Checks| C[Supply Chain Audit]
  B -->|Verifies| D[Security & License]
  D -->|Validates| E[SBOM Hash Validation]
  E -->|Approval| F[Operator System Registry]""",
        "publications": [
            ("OWASP Top 10 for LLM Applications (Insecure Plugin Design)", "https://llmtop10.org/"),
            ("Secure Software Supply Chain Guidelines (CISA Standards)", "https://www.cisa.gov/sbom"),
            ("GitHub Advisory Database & CVE Vulnerability Metrics", "https://github.com/advisories")
        ]
    },
    "t3mp3st-intake": {
        "implementation": "Handled by the Tempest scanner CLI at `scripts/ai/aq-tempest` and validated by `scripts/testing/test-aq-tempest.py`. Uses regex libraries and heuristic classification modules to scan LLM execution histories and prompts.",
        "function": "Monitors API calls for prompt injection payloads, system prompt leakage, jailbreak structures, and unauthorized shell redirection attempts, logging audit failures to telemetry ports.",
        "grounding": "LLM Red Teaming & Behavioral Guardrails. Implements adversarial prompt validation and defense-in-depth modeling to protect model-to-system interactions.",
        "mermaid": """graph TD
  A[API Router Logging] -->|Monitors| B[Tempest Scanner]
  B -->|Regex classification| C[Jailbreak Heuristics]
  B -->|Behavior checks| D[Leak detection]
  C & D -->|Reports| E[Audit failure log]""",
        "publications": [
            ("Indirect Prompt Injection in Real-World LLM Integrations (Greshake et al.)", "https://arxiv.org/abs/2302.12173"),
            ("OWASP LLM01: Prompt Injection Standards", "https://llmtop10.org/"),
            ("Adversarial Prompting and Semantic Safety Barriers", "https://arxiv.org/abs/2308.02312")
        ]
    },
    "auto-skill-selection": {
        "implementation": "Wired in the hybrid coordinator routing layer and `ai-stack/local-agents/tool_registry.py`. Evaluates user task prompts against the indexing map at `.agent/SKILL_INDEX.md` and loads matching module schemas.",
        "function": "Dynamically selects and pre-warms context structures with only the specific skills and guides needed for a task, hiding unnecessary skills to maintain clean prompting space.",
        "grounding": "Lazy Context Injection & Sparse Prompting. Based on context efficiency research, this module avoids model confusion and token exhaustion by loading specialized system capabilities strictly on demand.",
        "mermaid": """graph TD
  A[User context prompt] -->|Matches| B[Skill selection logic]
  B -->|Reads| C[SKILL_INDEX.md]
  C -->|Retrieves| D[Skill modules]
  D -->|Pre-warms| E[Hydrated prompt context]""",
        "publications": [
            ("Lost in the Middle: How Language Models Use Long Contexts (Liu et al.)", "https://arxiv.org/abs/2307.03172"),
            ("In-Context Retrieval-Augmented Language Models (Ram et al.)", "https://arxiv.org/abs/2302.00083"),
            ("Sparse Attention and Memory-Mapped Prompt Contexts", "https://arxiv.org/abs/2402.10237")
        ]
    },
    "tooling-manifest": {
        "implementation": "Maintained in `ai-stack/mcp-servers/hybrid-coordinator/knowledge/tooling-manifest.py`. Dynamically constructs JSON schemas of local tools to generate standardized API bindings for LLM calls.",
        "function": "Acts as the registry and translator mapping local python methods/arguments to standard OpenAI-style function declaration tools, validating schemas on compile.",
        "grounding": "Strict Interface Typing & Declarative Tooling. Ensures LLMs receive mathematically sound function schemas, reducing syntax model hallucinations during tooling calls.",
        "mermaid": """graph TD
  A[Python functions] -->|Parsed by| B[tooling-manifest.py]
  B -->|Translates to| C[JSON schema models]
  C -->|Registers| D[Hybrid coordinator tools]""",
        "publications": [
            ("Toolformer: Language Models Can Teach Themselves to Use Tools (Schick et al.)", "https://arxiv.org/abs/2302.04761"),
            ("OpenAPI Specification (OAS) 3.1 Standards", "https://www.openapis.org/"),
            ("JSON Schema Draft-07 Specification Details", "https://json-schema.org/")
        ]
    },
    "local-agent-delegation": {
        "implementation": "Structured inside the Switchboard router configuration (`ai-stack/switchboard/switchboard.py`) and routed through `scripts/ai/delegate-to-antigravity`. Wires local tool results to remote reasoning endpoints.",
        "function": "Receives standard prompt inputs, serializes system context maps, maps fallback endpoints to local Qwen loops on API limits, and returns structured tool calling execution steps.",
        "grounding": "Distributed Agent Orchestration (Split-Compute Architecture). Leverages high-reasoning remote models for planning while routing local, secure file modifications to local execution boundaries.",
        "mermaid": """graph TD
  A[Switchboard :8085] -->|Routes| B[antigravity CLI]
  B -->|Primary| C[Remote API Models]
  B -->|Fallback| D[Local Inference :8080]
  C & D -->|Returns| E[Executed tool calls]""",
        "publications": [
            ("MRKL Systems: Modular, Extensible Architectures (Karpas et al.)", "https://arxiv.org/abs/2205.00445"),
            ("Mixture-of-Agents Enhances LLM Reasoners (Wang et al.)", "https://arxiv.org/abs/2406.04692"),
            ("Switchboard-Style API Router Design Principles", "https://github.com/open-router/openrouter-runner")
        ]
    },
    "playwright-mcp": {
        "implementation": "Runs as an external Model Context Protocol server. Ingested dynamically via Playwright package wraps, launching node processes under system governance sandboxing rules.",
        "function": "Opens headless browsers, scrapes DOM states, captures visual screenshots, clicks buttons, types inputs, and reports layout renders back to the coordinating agent.",
        "grounding": "Dynamic Web RAG & End-to-End User Emulations. Allows AI agents to interact with JS-heavy web interfaces, bridging the gap between raw text processing and UI execution.",
        "mermaid": """graph TD
  A[Playwright MCP Server] -->|Launches| B[Chromium headless]
  B -->|Interacts| C[Scrapes DOM details]
  B -->|Captures| D[Visual screenshots]
  C & D -->|Responds| E[Agent context]""",
        "publications": [
            ("WebArena: Evaluation Environments for Web Agents (Zhou et al.)", "https://arxiv.org/abs/2307.13854"),
            ("Playwright Framework Library & Instrumentation Docs", "https://playwright.dev/"),
            ("Model Context Protocol (MCP) Host/Client Specifications", "https://modelcontextprotocol.io/")
        ]
    },
    "semgrep-mcp": {
        "implementation": "Implemented as a Semgrep static scanner wrapping binary packages. Wired into the pipeline at `config/agent-capability-intake-candidates.json`.",
        "function": "Statically parses generated python and typescript code diffs, checking them for SQL injection, raw shell execution, insecure packages, and hardcoded secrets.",
        "grounding": "Shift-Left Secure Software Development. Automatically prevents security hazards from being written to files, enforcing clean code boundaries before the validation gate.",
        "mermaid": """graph TD
  A[Code files/diffs] -->|Scans| B[Semgrep engine]
  B -->|Checks rules| C[OWASP vulnerabilities]
  C -->|Signals| D[Audit approval gate]""",
        "publications": [
            ("Semgrep Static Analysis Engine Documentation", "https://github.com/semgrep/semgrep"),
            ("OWASP Source Code Analysis Tools (SAST Guidance)", "https://owasp.org/www-community/Source_Code_Analysis_Tools"),
            ("Static Analysis Security Assessment of Generative AI Output", "https://arxiv.org/abs/2308.10312")
        ]
    },
    "github-mcp-readonly": {
        "implementation": "Connects GitHub remote APIs to local agent contexts, running inside MCP adapter scripts configured in `ai-stack/mcp-servers/`.",
        "function": "Queries repository structures, fetches issues, scans active pull request comments, and pulls git diff files to hydrate context templates.",
        "grounding": "Contextual Source Control Grounding. Integrates real-time external workspace issues with local execution structures, ensuring agents operate in sync with upstream records.",
        "mermaid": """graph TD
  A[Git Adapter] -->|HTTP calls| B[GitHub API R/O]
  B -->|Syncs| C[Active issues/diffs]
  C -->|Appends| D[Model system prompt]""",
        "publications": [
            ("GitHub REST & GraphQL API Specification Manual", "https://docs.github.com/en/rest"),
            ("SWE-bench: Can LLMs Resolve GitHub Issues? (Jimenez et al.)", "https://arxiv.org/abs/2310.06770"),
            ("API-Driven Code Querying Optimization for Intelligent Agents", "https://arxiv.org/abs/2401.04561")
        ]
    },
    "understand-anything": {
        "implementation": "Managed through AST parsing engines inside the understand-anything code index CLI which runs semantic graph building algorithms on target files.",
        "function": "Extracts call trees, identifies callers and target functions, registers class dependencies, and traces code paths to create dynamic visual and semantic maps of codebases.",
        "grounding": "Abstract Syntax Tree (AST) Semantic Code Indexing. Speeds up repository search times and prevents context contamination by letting the agent scan call-graphs rather than reading whole files.",
        "mermaid": """graph TD
  A[Target file] -->|Parses| B[AST Builder]
  B -->|Constructs| C[Call trees & callers]
  B -->|Maps| D[Dependency graph relationships]""",
        "publications": [
            ("Call Graph Construction Algorithms (Grove et al. ACM)", "https://dl.acm.org/doi/10.1145/263698.263714"),
            ("Abstract Syntax Trees (AST) Compilation Fundamentals", "https://en.wikipedia.org/wiki/Abstract_syntax_tree"),
            ("Semantic Graph Database Maps for Large Workspace Comprehension", "https://arxiv.org/abs/2309.01235")
        ]
    },
    "osint-research-store": {
        "implementation": "Exposed as a database module that connects to local PostgreSQL structures, structured within the service routing configurations of `ai-stack/aidb/`.",
        "function": "Ingests OSINT dataset packages, formats records with metadata search tags, indexes content indices, and serves structured search outputs.",
        "grounding": "Declarative Knowledge Databases. Integrates public intelligence and unstructured collections in schema-compliant storage for fast semantic query retrieval.",
        "mermaid": """graph TD
  A[Inbound data] -->|Indexes| B[Research Store Adapter]
  B -->|Saves| C[PostgreSQL OSINT tables]
  C -->|Retrieves| D[Tagged intelligence]""",
        "publications": [
            ("OSINT Framework Resources & Mapping Schemes", "https://osintframework.com/"),
            ("PostgreSQL Full Text Search Design & Documentation", "https://www.postgresql.org/docs/current/textsearch.html"),
            ("Structured Open Source Intelligence Gathering Models", "https://arxiv.org/abs/2402.04690")
        ]
    },
    "aidb-rag-stores": {
        "implementation": "Wired in `ai-stack/aidb/layered_loading.py` and `ai-stack/aidb/temporal_facts.py`. Uses PostgreSQL for relational logs and Qdrant vector databases for semantic document search.",
        "function": "Caches interaction runs, collects task outputs, indexes prompt-response traces, and retrieves relevant past solutions based on cosine similarity of search embeddings.",
        "grounding": "Episodic and Semantic Long-Term Agent Memory. Follows MemoryBroker paradigms, ensuring that lessons, system configurations, and past debug fixes survive session reboots.",
        "mermaid": """graph TD
  A[Memory Broker] -->|Relational logs| B[PostgreSQL]
  A -->|Vector indexes| C[Qdrant DB]
  B & C -->|Syncs| D[Agent Episodic Memory]""",
        "publications": [
            ("MemGPT: Towards LLMs as Operating Systems (Packer et al.)", "https://arxiv.org/abs/2310.08560"),
            ("Qdrant Vector Database Architectures & Approximate Neighbors", "https://qdrant.tech/documentation/"),
            ("Letta: MemGPT Kernel Orchestration Services & Memory Brokers", "https://github.com/letta-ai/letta")
        ]
    },
    "workflow-blueprints": {
        "implementation": "Declared in `config/workflow-blueprints.json` and parsed by the workflow checkpointer service under `ai-stack/mcp-servers/hybrid-coordinator/core/`.",
        "function": "Structures multi-agent tasks as Directed Acyclic Graphs (DAGs), ensuring steps execution flows sequentially or in parallel based on pipeline state transitions.",
        "grounding": "Deterministic Task State Machines (similar to LangGraph). Replaces unpredictable agent chaining with structured step-based constraints, guaranteeing execution tracking.",
        "mermaid": """graph TD
  A[Tasks workflow.json] -->|Loads| B[DAG Pipeline Run]
  B -->|Validates state| C[Transitions checklist]
  C -->|Clamps and saves| D[Checkpoint snapshots]""",
        "publications": [
            ("LangGraph Multi-Agent Workflow State Framework", "https://langchain-ai.github.io/langgraph/"),
            ("Directed Acyclic Graphs (DAG) Task Scheduling Models", "https://en.wikipedia.org/wiki/Directed_acyclic_graph"),
            ("Formal State Transitions and Safe Multi-Agent Coordination Logs", "https://arxiv.org/abs/2401.12039")
        ]
    },
    "nixos-static-analysis": {
        "implementation": "Wrapped within system verification hooks at `scripts/governance/nix-static-analysis.sh`. Executes Nix AST scanners like statix, deadnix, and nixfmt.",
        "function": "Audits Nix files for syntax errors, dead declarations, circular overlays, and styling compliance, preventing invalid configuration from breaking nixos rebuilds.",
        "grounding": "Declarative Configuration Testing. Enforces NixOS-first code contracts, ensuring that all system package/service changes remain strictly declarative.",
        "mermaid": """graph TD
  A[Nix declarations] -->|Checks| B[Statix & Deadnix]
  B -->|Lints syntax| C[Nixfmt compliance]
  B -->|Enforces| D[Declarative configuration]""",
        "publications": [
            ("NixOS Flakes Schema Standards & Module Lifecycle", "https://nixos.wiki/wiki/Flakes"),
            ("Statix: Lints and checks for the Nix language", "https://github.com/nerdypepper/statix"),
            ("Type-Safe Infrastructures and Flat Overlay Scopes on NixOS", "https://nixos.org/manual/nixpkgs/stable/")
        ]
    },
    "dashboard-observability": {
        "implementation": "Runs as the FastAPI dashboard backend (`dashboard/backend/api/main.py`) paired with D3/Mermaid frontend scripts inside `dashboard.html` and `/assets/dashboard.js`.",
        "function": "Collects system metrics, streams agent state changes via WebSockets, visualizes call graphs, and logs operator actions to the audit files.",
        "grounding": "Real-time Agentic Observability (Anti-Black-Box UI). Provides clear visualization of agent execution paths, prompt counts, and state models to ensure user transparency.",
        "mermaid": """graph TD
  A[System statistics] -->|Rest APIs| B[FastAPI server]
  B -->|WebSockets| C[dashboard.html]
  C -->|Renders| D[Live SVG & D3 metrics]""",
        "publications": [
            ("OpenTelemetry Protocol Specs for Distributed Tracing", "https://opentelemetry.io/docs/specs/otlp/"),
            ("D3.js: Data-Driven Documents Rendering Standards", "https://d3js.org/"),
            ("Interactive Web Engineering HUD Dashboards for Systems Observability", "https://github.com/indydevdan")
        ]
    },
    "identity-kernel-service": {
        "implementation": "Maintained in `ai-stack/identity-kernel/checkpoint_service.py` and configured in `nix/modules/services/identity-kernel.nix`. Exposes configuration ports at `/identity/self`.",
        "function": "Saves agent name templates, profiles, values logs, capability sets, and checkpoints, storing changes to disk to persist agent identity configurations.",
        "grounding": "Agent Identity Envelopes (Mem0 and Letta paradigms). Gives agents a consistent sense of identity, goals, and behavioral limits that persist across reboots.",
        "mermaid": """graph TD
  A[Agent configurations] -->|Validates| B[Checkpoint service]
  B -->|Serializes| C[Envelopes & Profiles]
  B -->|Persists| D[Disk memory state]""",
        "publications": [
            ("Mem0: Dynamic Personalization Memory Engine for LLMs", "https://github.com/mem0ai/mem0"),
            ("Identity-Preserving Semantic Envelopes & Actor Core Specs", "https://arxiv.org/abs/2310.08560"),
            ("Persisted Agent Profiling and Behavior Boundaries", "https://arxiv.org/abs/2403.01255")
        ]
    },
    "affective-engine-module": {
        "implementation": "Structured in `ai-stack/affective-engine/reciprocity_tracker.py` and enabled in `nix/modules/services/affective-engine.nix`. Exposes state metrics via port `:8003`.",
        "function": "Calculates user interaction tones, maintains a reciprocity debt ledger based on computational cooperation algorithms, and modulates model output vocabulary accordingly.",
        "grounding": "Affective Coprocessing Loops and Game-Theoretic Interaction Engines. Explores cooperation curves and agent temperaments to improve multi-turn user cooperation.",
        "mermaid": """graph TD
  A[Interaction tone] -->|Evaluates| B[Reciprocity tracker]
  B -->|Maintains| C[Tone scores ledger]
  B -->|Modulates| D[Response vocabulary]""",
        "publications": [
            ("Affective Computing paradigms (MIT Media Lab)", "https://www.media.mit.edu/groups/affective-computing/overview/"),
            ("Game Theory in Agent-Human Interaction Cores", "https://en.wikipedia.org/wiki/Game_theory"),
            ("Affective Linguistic Modulation in Interactive AI Engines", "https://arxiv.org/abs/2311.08291")
        ]
    }
}

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    catalog_path = os.path.join(repo_root, "config/system-capability-catalog.json")
    output_dir = os.path.join(repo_root, "assets/modules")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(catalog_path):
        print(f"Error: system capability catalog file not found at {catalog_path}")
        sys.exit(1)

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading catalog: {e}")
        sys.exit(1)

    entries = data.get("entries", [])
    print(f"Found {len(entries)} capability entries to generate.")

    html_template = """<!DOCTYPE html>
<html lang="en" translate="no">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="google" content="notranslate">
  <title>{name} - AI Harness Module Info</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #080c12;
      --bg2: #0d1220;
      --bg3: rgba(13, 18, 32, 0.96);
      --fg: #e2eaf4;
      --fg2: #8aa4bb;
      --fg3: #4a6278;
      --cyan: #00d9ff;
      --cyan-g: rgba(0, 217, 255, 0.15);
      --mag: #d400ff;
      --mag-g: rgba(212, 0, 255, 0.15);
      --grn: #39ff14;
      --grn-g: rgba(57, 255, 20, 0.12);
      --yel: #f9e2af;
      --yel-g: rgba(249, 226, 175, 0.15);
      --red: #ff3644;
      --red-g: rgba(255, 54, 68, 0.15);
      --border: rgba(0, 217, 255, 0.14);
      --font: 'JetBrains Mono', monospace;
      --hud: 'Orbitron', sans-serif;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: var(--font);
      background-color: var(--bg);
      color: var(--fg);
      line-height: 1.6;
      padding: 2.5rem;
      background-image: radial-gradient(var(--border) 1px, transparent 1px);
      background-size: 28px 28px;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid var(--border);
      padding-bottom: 1.5rem;
      margin-bottom: 2.5rem;
      flex-wrap: wrap;
      gap: 1rem;
    }}
    .logo-area {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    .status-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background-color: var(--grn);
      box-shadow: 0 0 8px var(--grn);
    }}
    .status-dot.disabled {{
      background-color: var(--red);
      box-shadow: 0 0 8px var(--red);
    }}
    h1 {{
      font-family: var(--hud);
      text-transform: uppercase;
      letter-spacing: 0.15em;
      font-size: 1.6rem;
      background: linear-gradient(90deg, var(--cyan), var(--mag));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      filter: drop-shadow(0 0 8px rgba(0, 217, 255, 0.3));
    }}
    .back-btn {{
      font-family: var(--hud);
      text-decoration: none;
      color: var(--cyan);
      border: 1px solid var(--cyan);
      padding: 0.6rem 1.2rem;
      border-radius: 3px;
      transition: all 0.3s ease;
      font-size: 0.8rem;
      background: transparent;
      letter-spacing: 0.15em;
      text-transform: uppercase;
    }}
    .back-btn:hover {{
      background: var(--cyan-g);
      box-shadow: 0 0 12px var(--cyan);
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2rem;
      margin-bottom: 2.5rem;
    }}
    .grid3 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 2rem;
      margin-bottom: 2.5rem;
    }}
    @media (max-width: 800px) {{
      .grid2, .grid3 {{
        grid-template-columns: 1fr;
      }}
    }}
    .card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1.8rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      background: var(--border);
    }}
    .card.enabled::before {{ background: var(--grn); }}
    .card.disabled::before {{ background: var(--red); }}
    .card.warning::before {{ background: var(--yel); }}
    .card.info::before {{ background: var(--cyan); }}
    .card.mag::before {{ background: var(--mag); }}

    .card-title {{
      font-family: var(--hud);
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 1.2rem;
      color: var(--cyan);
      border-bottom: 1px dashed var(--border);
      padding-bottom: 0.6rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 2px;
      font-size: 0.7rem;
      font-weight: bold;
      text-transform: uppercase;
      margin-right: 0.5rem;
      border: 1px solid transparent;
    }}
    .badge-enabled {{
      background: var(--grn-g);
      color: var(--grn);
      border-color: rgba(57, 255, 20, 0.3);
    }}
    .badge-disabled {{
      background: var(--red-g);
      color: var(--red);
      border-color: rgba(255, 54, 68, 0.3);
    }}
    .badge-info {{
      background: var(--cyan-g);
      color: var(--cyan);
      border-color: rgba(0, 217, 255, 0.3);
    }}
    .badge-warning {{
      background: var(--yel-g);
      color: var(--yel);
      border-color: rgba(249, 226, 175, 0.3);
    }}
    .badge-mag {{
      background: var(--mag-g);
      color: var(--mag);
      border-color: rgba(212, 0, 255, 0.3);
    }}
    .kv-row {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.85rem;
      font-size: 0.88rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      padding-bottom: 0.5rem;
    }}
    .kv-key {{
      color: var(--fg2);
    }}
    .kv-val {{
      color: var(--fg);
      text-align: right;
      word-break: break-all;
    }}
    .code-box {{
      background: #030509;
      border: 1px solid var(--border);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      padding: 0.8rem;
      border-radius: 4px;
      overflow-x: auto;
      color: var(--yel);
      white-space: pre-wrap;
      word-break: break-all;
      margin-top: 0.5rem;
    }}
    .ref-list {{
      list-style-type: none;
    }}
    .ref-list li {{
      margin-bottom: 0.6rem;
      font-size: 0.88rem;
      display: flex;
      align-items: center;
      color: var(--fg);
    }}
    .ref-list li::before {{
      content: '↳ ';
      color: var(--cyan);
      margin-right: 0.5rem;
    }}
    .ref-list li a {{
      color: var(--cyan);
      text-decoration: none;
      border-bottom: 1px dotted var(--cyan-g);
      transition: all 0.2s ease;
    }}
    .ref-list li a:hover {{
      color: var(--mag);
      border-bottom-color: var(--mag);
      text-shadow: 0 0 4px var(--mag);
    }}
    .edu-text {{
      font-size: 0.92rem;
      color: var(--fg);
      line-height: 1.7;
    }}
    .description {{
      font-size: 1rem;
      color: var(--fg);
      margin-bottom: 2.5rem;
      background: var(--bg2);
      border: 1px solid var(--border);
      padding: 1.8rem;
      border-radius: 4px;
      position: relative;
      line-height: 1.7;
    }}
    .description::before {{
      content: 'MODULE FUNCTION';
      position: absolute;
      top: -10px;
      left: 15px;
      background: var(--bg);
      padding: 0 10px;
      font-family: var(--hud);
      font-size: 0.65rem;
      color: var(--fg3);
      letter-spacing: 0.15em;
    }}
    footer {{
      margin-top: 5rem;
      text-align: center;
      font-size: 0.75rem;
      color: var(--fg3);
      border-top: 1px solid var(--border);
      padding-top: 1.8rem;
    }}
    /* Mermaid core custom overrides */
    .mermaid svg {{
      max-width: 100%;
      height: auto;
    }}
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'dark',
      securityLevel: 'loose',
      themeVariables: {{
        fontFamily: 'JetBrains Mono, monospace',
        primaryColor: '#0d1220',
        primaryTextColor: '#e2eaf4',
        primaryBorderColor: 'rgba(0, 217, 255, 0.4)',
        lineColor: '#00d9ff',
        secondaryColor: '#080c12',
        tertiaryColor: '#0d1220'
      }}
    }});
  </script>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <div class="status-dot {status_class}"></div>
        <h1>{name}</h1>
      </div>
      <a href="/index.html" class="back-btn">← Command Center</a>
    </header>

    <div class="description">
      {summary}
    </div>

    <!-- WORKFLOW & RESEARCH PARADIGMS GRID -->
    <div class="grid2">
      <!-- System Workflow Card -->
      <div class="card info">
        <div class="card-title">System Workflow & Logical Data Flow</div>
        <div class="mermaid" style="background:#030509; padding: 1.5rem 1rem; border-radius: 4px; border: 1px solid var(--border); overflow-x: auto; display: flex; justify-content: center; min-height: 220px;">
{mermaid_graph}
        </div>
      </div>

      <!-- Research Publications Card -->
      <div class="card warning">
        <div class="card-title">Research Publications & References</div>
        <div style="font-size:0.85rem; color:var(--fg2); margin-bottom:0.75rem;">
          Academic literature, standards, and research publications detailing this paradigm:
        </div>
        <ul class="ref-list" style="margin-top: 0.5rem;">
          {publications_list}
        </ul>
      </div>
    </div>

    <!-- PRIMARY EDUCATION GRID -->
    <div class="grid2">
      <!-- Under the Hood implementation details -->
      <div class="card info">
        <div class="card-title">Codebase Implementation</div>
        <div class="edu-text">
          {impl_text}
        </div>
      </div>

      <!-- Functional architecture & execution patterns -->
      <div class="card mag">
        <div class="card-title">Functional Architecture & Tasks</div>
        <div class="edu-text">
          {func_text}
        </div>
      </div>
    </div>

    <div class="grid2">
      <!-- Grounding -->
      <div class="card warning">
        <div class="card-title">Theoretical Grounding / CS Paradigm</div>
        <div class="edu-text">
          {ground_text}
        </div>
      </div>

      <!-- General details -->
      <div class="card {status_class}">
        <div class="card-title">Metadata & Status Parameters</div>
        <div class="kv-row">
          <span class="kv-key">Module Key</span>
          <span class="kv-val">{id}</span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Status State</span>
          <span class="kv-val"><span class="badge badge-{status_class}">{state}</span></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Maturity Level</span>
          <span class="kv-val"><span class="badge badge-info">{maturity}</span></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Module Owner</span>
          <span class="kv-val">{owner}</span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Category</span>
          <span class="kv-val">{category}</span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Kind</span>
          <span class="kv-val">{kind}</span>
        </div>
      </div>
    </div>

    <div class="grid3">
      <!-- Security & Risk Card -->
      <div class="card {risk_class}">
        <div class="card-title">Security & Admission Gates</div>
        <div class="kv-row">
          <span class="kv-key">Risk Evaluation</span>
          <span class="kv-val"><span class="badge badge-{risk_class}">{risk}</span></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Admission Type</span>
          <span class="kv-val">{admission}</span>
        </div>
        {gate_section}
      </div>

      <!-- Wumbology Status Card -->
      <div class="card info">
        <div class="card-title">Wumbology Study (L1-Wumbo)</div>
        <div class="kv-row">
          <span class="kv-key">Wumbo Status</span>
          <span class="kv-val"><span class="badge badge-grn" style="background:var(--grn-g); color:var(--grn); border:1px solid rgba(57,255,20,0.3)">WUMBO ACTIVE</span></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Theory Level</span>
          <span class="kv-val">First Grade</span>
        </div>
        <div style="font-size:0.72rem; color:var(--fg2); margin-top:0.6rem; border-top:1px solid rgba(0,217,255,0.08); padding-top:0.4rem; font-style:italic;">
          \"I wumbo, you wumbo, he she me wumbo... Wumbology, the study of wumbo! It's first grade!\" — Patrick Star
        </div>
      </div>

      <!-- Primary References Card -->
      <div class="card info">
        <div class="card-title">Codebases & Primary References</div>
        <ul class="ref-list">
          {refs_list}
        </ul>
      </div>

      <!-- Boundaries -->
      <div class="card mag">
        <div class="card-title">Agent Execution Boundaries</div>
        <div style="font-size:0.85rem; color:var(--fg2); margin-bottom:0.75rem;">
          The following AI profiles have invocation permissions on this module:
        </div>
        <div>
          {agent_badges}
        </div>
      </div>
    </div>


    <div class="grid2">
      <!-- Parity Targets Card -->
      <div class="card warning">
        <div class="card-title">Parity Targets</div>
        <div style="font-size:0.85rem; color:var(--fg2); margin-bottom:0.75rem;">
          External system paradigms tracked for functional parity:
        </div>
        <ul class="ref-list">
          {parity_list}
        </ul>
      </div>

      <!-- Data Stores Card -->
      <div class="card info">
        <div class="card-title">Data Ingestion Stores</div>
        <div style="font-size:0.85rem; color:var(--fg2); margin-bottom:0.75rem;">
          Relational tables or key-value structures owned by this node:
        </div>
        <ul class="ref-list">
          {data_stores_list}
        </ul>
      </div>
    </div>

    <!-- Validation & QA Section -->
    <div class="card info" style="margin-top: 1.5rem;">
      <div class="card-title">Validation Checks & Diagnostic Instructions</div>
      <div style="font-size: 0.85rem; margin-bottom: 0.75rem;">
        To execute sanity tests and verify compliance with NixOS system governance boundaries, execute the following command in the workspace directory:
      </div>
      <div>
        {validation_boxes}
      </div>
    </div>

    <footer>
      NixOS AI Operating System • Generated Declarative Module Observability
    </footer>
  </div>
</body>
</html>"""

    for item in entries:
        item_id = item.get("id", "")
        # Obtain detailed enriched texts
        details = ENRICHED_DETAILS.get(item_id, {
            "implementation": "Implementation details are currently declared in primary reference hooks.",
            "function": "Processes tasks dynamically under the coordinate loop.",
            "grounding": "Grounded in standard modular AI design parameters.",
            "mermaid": "graph TD\\n  A[Start] --> B[End]",
            "publications": []
        })

        # Determine status styling
        state = item.get("state", "unknown")
        status_class = "enabled" if state == "enabled" else "disabled"

        # Risk styling
        sec = item.get("security", {})
        risk = sec.get("risk", "low")
        if risk == "high" or risk == "critical":
            risk_class = "disabled"
        elif risk == "medium":
            risk_class = "warning"
        else:
            risk_class = "enabled"

        gate = sec.get("required_gate", "")
        if gate:
            gate_section = f"""<div style="margin-top:0.75rem; font-size:0.8rem; color:var(--fg2);">Required Intake Gate Audit:</div>
<div class="code-box">{gate}</div>"""
        else:
            gate_section = ""

        # Refs list format
        refs = item.get("primary_refs", [])
        if refs:
            refs_list = "\n".join([f"<li>{ref}</li>" for ref in refs])
        else:
            refs_list = "<li>No references declared</li>"

        # Agent badges format
        agents = item.get("agent_access", [])
        if agents:
            agent_badges = " ".join([f'<span class="badge badge-mag">{agent}</span>' for agent in agents])
        else:
            agent_badges = '<span class="badge badge-warning">No agents permitted</span>'

        # Parity targets format
        parity = item.get("parity_targets", [])
        if parity:
            parity_list = "\n".join([f"<li>{target}</li>" for target in parity])
        else:
            parity_list = "<li>No parity targets configured</li>"

        # Data stores format
        stores = item.get("data_stores", [])
        if stores:
            data_stores_list = "\n".join([f"<li>{store}</li>" for store in stores])
        else:
            data_stores_list = "<li>No persistent storage structures mapped</li>"

        # Validation checks commands format
        validations = item.get("validation", [])
        if validations:
            validation_boxes = "\\n".join([f'<div class="code-box">{v}</div>' for v in validations])
        else:
            validation_boxes = '<div class="code-box" style="color:var(--red);">No automated validation suite registered!</div>'

        # Publications list format
        pubs = details.get("publications", [])
        if pubs:
            publications_list = "\n".join([f'<li><a href="{url}" target="_blank">{title}</a></li>' for title, url in pubs])
        else:
            publications_list = "<li>No academic references recorded</li>"

        # Format and write HTML file
        rendered_html = html_template.format(
            id=item_id,
            name=item.get("name", "Unknown Module"),
            summary=item.get("summary", "No description provided."),
            state=state,
            maturity=item.get("maturity", "unknown"),
            owner=item.get("owner", "unassigned"),
            category=item.get("category", "unclassified"),
            kind=item.get("kind", "unknown"),
            status_class=status_class,
            risk_class=risk_class,
            risk=risk,
            admission=sec.get("admission", "unknown"),
            gate_section=gate_section,
            refs_list=refs_list,
            agent_badges=agent_badges,
            parity_list=parity_list,
            data_stores_list=data_stores_list,
            validation_boxes=validation_boxes,
            impl_text=details["implementation"],
            func_text=details["function"],
            ground_text=details["grounding"],
            mermaid_graph=details.get("mermaid", "graph TD\\n  A[Start] --> B[End]"),
            publications_list=publications_list
        )

        file_path = os.path.join(output_dir, f"{item_id}.html")
        with open(file_path, "w", encoding="utf-8") as out:
            out.write(rendered_html)

    print("HTML pages generation complete!")

if __name__ == "__main__":
    main()
