# Architecture Diagrams
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-25

## Agentic AI Operating System (AI OS) Architecture

The NixOS-Dev-Quick-Deploy stack operates as a foundational "AI Operating System," treating the LLM as the CPU, context windows as working RAM, and persistent vector/graph stores as long-term storage.

### 1. High-Level AI OS Topology

```mermaid
flowchart TD
    subgraph UI ["User Surface — COSMIC Desktop (NixOS 25.11)"]
        CLI[aq-prime / aq-* CLIs]
        Editor[Continue / Aider / Cursor]
        Dash[Command Center UI :8889]
    end

    subgraph Governance ["Governance & Gateway (Policy & Routing)"]
        SWB[ai-switchboard :8085]
    end

    subgraph Orchestration ["Orchestration (Cyclic State Machine)"]
        HC[hybrid-coordinator :8003]
        HC --"MCP (A2A)"--> HC
    end

    subgraph Compute ["Execution & Inference"]
        LLM[llama-cpp :8080\nQwen3.6-35B]
        EMB[llama-embed :8081]
        RAG[ralph-wiggum :8004]
    end

    subgraph Domains ["Functional Execution Domains"]
        D1[Systems Software]
        D2[MLOps / Opt\nscaffolded]
        D3[QA Automation\nscaffolded]
        D4[Trading / OSINT\nproposed]
    end

    subgraph Memory ["Knowledge & Persistence"]
        AIDB[(AIDB :8002\nTemporal Memory)]
        VDB[(Qdrant :6333)]
        KV[(Redis :6379)]
        PG[(Postgres :5432)]
    end

    CLI -->|execute| SWB
    Editor -->|query| SWB
    Dash -->|api| HC
    
    SWB -->|profile-execution| HC
    
    HC -->|task/intent| Domains
    HC -->|inference| LLM
    HC -->|semantic query| AIDB
    HC -->|rag orchestration| RAG
    HC -->|embedding| EMB
    
    AIDB -->|vector search| VDB
    AIDB -->|relational| PG
    RAG -->|retrieve| AIDB
```

### 2. Request Routing Flow (Cyclic DAG)

The system is migrating from a linear fallback model to a cyclic, state-driven orchestration model (Agentic Mesh) leveraging the Model Context Protocol (MCP) as the standard Agent-to-Agent (A2A) networking layer.

```mermaid
flowchart LR
    User([User / Agent]) --> SWB[Switchboard :8085]
    SWB -->|default profile| HC[Hybrid Coordinator :8003]
    SWB -->|continue-local| HC
    
    %% Cyclic Orchestration
    HC -->|evaluate state| State{Task Complete?}
    State --No--> Tool[MCP Tool Execution]
    Tool -->|feedback| HC
    State --Yes--> Result[Return Result]
    
    HC -->|prefer_local=true| LLAMA[LLaMA.cpp :8080]
    HC -->|vector search| AIDB[(AIDB :8002)]
    HC -->|rag task| RALPH[Ralph Wiggum :8004]
    HC -->|embed request| EMBED[LLaMA Embed :8081]
    
    RALPH --> AIDB
    DASHBOARD[Dashboard :8889] -->|/api/*| HC
    DASHBOARD -->|/api/logic/search| AIDB
```

### 3. Foundation Persistence (Temporal Memory)

Memory relies on "supersession logic" (temporal knowledge graphs) to manage stale facts, shifting from simple bolt-on RAG to crystalline memory.

```mermaid
flowchart TD
    Input[Incoming Context] --> Split{Memory Tier}
    Split -->|Short-term| Redis[Working Memory]
    Split -->|Episodic| Log[Event Spine / Audit]
    Split -->|Semantic| AIDB[AIDB Relational + Vector]
    
    AIDB --> Logic{Supersession Logic}
    Logic -->|Stale Fact| Deprecate[Invalidate Tag]
    Logic -->|New Fact| Embed[llama-embed :8081]
    Embed --> Qdrant[(Qdrant Vector Store)]
```

---
*Note: K3s, Podman, and linear legacy pipelines have been fully deprecated in favor of this host-local, declarative NixOS systemd-native AI OS architecture.*
