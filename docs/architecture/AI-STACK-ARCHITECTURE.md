# AI Stack Architecture

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

## Overview

This document describes the architecture of the NixOS-Dev-Quick-Deploy AI Stack, a local-first inference and orchestration system.

## System Architecture Diagram

```mermaid
flowchart TB
    subgraph Desktop["COSMIC Desktop Layer"]
        cosmic-greeter[cosmic-greeter]
        cosmic-session[cosmic-session]
        xdg-portal[XDG Portals]
    end

    subgraph Inference["Inference Layer"]
        llama-chat["llama-server :8080<br/>(Chat Model)"]
        llama-embed["llama-server :8081<br/>(Embedding Model)"]
        switchboard["Switchboard :8085<br/>(Local/Remote Routing)"]
    end

    subgraph MCP["MCP Orchestration Layer"]
        hybrid["Hybrid Coordinator :8003"]
        aidb["AIDB :8002"]

        subgraph HybridComponents["Hybrid Components"]
            hints[Hints Engine]
            disclosure[Progressive Disclosure]
            harness[Harness Eval]
            workflow[Workflow Manager]
            multiturn[Multi-Turn Manager]
        end
    end

    subgraph Persistence["Persistence Layer"]
        postgres[(PostgreSQL :5432)]
        redis[(Redis :6379)]
        qdrant[(Qdrant :6333)]
    end

    subgraph Observability["Observability"]
        prometheus[Prometheus Metrics]
        circuit[Circuit Breakers]
    end

    %% Connections
    cosmic-session --> xdg-portal
    switchboard --> llama-chat
    switchboard --> |Remote API| external([External LLM APIs])

    hybrid --> switchboard
    hybrid --> aidb
    hybrid --> qdrant

    aidb --> qdrant
    aidb --> postgres

    hybrid --> hints
    hybrid --> disclosure
    hybrid --> harness
    hybrid --> workflow
    hybrid --> multiturn

    llama-embed --> qdrant

    hybrid --> prometheus
    hybrid --> circuit

    redis --> hybrid
```

## Component Descriptions

### Inference Layer

| Component | Port | Purpose |
|-----------|------|---------|
| llama-server (chat) | 8080 | OpenAI-compatible chat completions |
| llama-server (embed) | 8081 | Text embeddings for RAG |
| Switchboard | 8085 | Routes queries to local or remote LLM |

### MCP Orchestration Layer

| Component | Port | Purpose |
|-----------|------|---------|
| Hybrid Coordinator | 8003 | Workflow orchestration, hints, harness eval |
| AIDB | 8002 | Knowledge base, tool discovery, RAG pipeline |

### Persistence Layer

| Component | Port | Purpose |
|-----------|------|---------|
| PostgreSQL | 5432 | Relational data, interaction history |
| Redis | 6379 | Session cache, rate limiting state |
| Qdrant | 6333 | Vector database for semantic search |

## Data Flow Diagrams

### Query Flow

```mermaid
sequenceDiagram
    participant Agent
    participant Hybrid as Hybrid Coordinator
    participant Switch as Switchboard
    participant LLM as llama-server
    participant Qdrant
    participant AIDB

    Agent->>Hybrid: POST /query
    Hybrid->>Qdrant: Semantic search
    Qdrant-->>Hybrid: Relevant contexts
    Hybrid->>AIDB: Augment with knowledge
    AIDB-->>Hybrid: Enriched context
    Hybrid->>Switch: Route query + context
    Switch->>LLM: Generate completion
    LLM-->>Switch: Response
    Switch-->>Hybrid: Response
    Hybrid-->>Agent: Augmented response
```

### Workflow Execution Flow

```mermaid
sequenceDiagram
    participant Agent
    participant Hybrid as Hybrid Coordinator
    participant Hints as Hints Engine
    participant Harness as Harness Eval
    participant Workflow as Workflow Manager

    Agent->>Hybrid: POST /workflow/plan
    Hybrid->>Hints: Get relevant hints
    Hints-->>Hybrid: Ranked hints
    Hybrid->>Workflow: Generate plan
    Workflow-->>Hybrid: Execution plan
    Hybrid-->>Agent: Plan + hints

    Agent->>Hybrid: POST /workflow/run/start
    Hybrid->>Workflow: Start execution

    loop Execution Steps
        Workflow->>Harness: Validate step
        Harness-->>Workflow: Scorecard
        Workflow->>Agent: Step result
    end

    Workflow-->>Hybrid: Execution complete
    Hybrid-->>Agent: Final result
```

### PRSI Loop

```mermaid
flowchart LR
    subgraph PRSI["Pessimistic Recursive Self-Improvement"]
        plan[1. PLAN<br/>Generate proposals]
        validate[2. VALIDATE<br/>Check safety envelope]
        execute[3. EXECUTE<br/>Apply within isolation]
        measure[4. MEASURE<br/>Capture scorecard]
        feedback[5. FEEDBACK<br/>Update hint bandit]
        compress[6. COMPRESS<br/>Flush context]
    end

    plan --> validate
    validate --> execute
    execute --> measure
    measure --> feedback
    feedback --> compress
    compress --> plan
```

## Service Dependencies

```mermaid
graph TD
    A[llama-cpp] --> B[llama-cpp-model-fetch]
    C[llama-cpp-embed] --> D[llama-cpp-embed-model-fetch]
    E[ai-hybrid-coordinator] --> F[qdrant]
    E --> G[ai-aidb]
    G --> F
    G --> H[postgresql]
    E --> I[redis]

    J[ai-stack.target] --> A
    J --> C
    J --> E
    J --> G
```

## Memory Architecture

```mermaid
flowchart TB
    subgraph Working["Working Context (Ephemeral)"]
        current[Current task slice]
        tools[Tool results]
    end

    subgraph Episodic["Episodic Memory (PostgreSQL + Qdrant)"]
        interactions[Interaction outcomes]
        patterns[Successful patterns]
    end

    subgraph Semantic["Semantic Memory (Qdrant Collections)"]
        errors[error-solutions]
        practices[best-practices]
        codebase[codebase-context]
    end

    subgraph Procedural["Procedural Memory (Static + Hints)"]
        rules[Workflow rules]
        hardening[Hardening patterns]
    end

    Working --> |Flush| Episodic
    Episodic --> |Recall| Working
    Semantic --> |RAG| Working
    Procedural --> |Hints| Working
```

## Security Boundaries

```mermaid
flowchart TB
    subgraph External["External Boundary"]
        internet([Internet])
    end

    subgraph DMZ["Rate-Limited Zone"]
        hybrid["Hybrid Coordinator<br/>(rate limiting, input validation)"]
    end

    subgraph Internal["Internal Services"]
        llama["llama-server<br/>(IPAddressDeny: any)"]
        qdrant["Qdrant<br/>(localhost only)"]
        postgres["PostgreSQL<br/>(localhost only)"]
    end

    subgraph Confined["AppArmor Confined"]
        llama
    end

    internet --> |SSRF Protected| hybrid
    hybrid --> llama
    hybrid --> qdrant
    hybrid --> postgres
```

## Port Reference

| Service | Port | Protocol | Exposure |
|---------|------|----------|----------|
| llama-server (chat) | 8080 | HTTP | localhost |
| llama-server (embed) | 8081 | HTTP | localhost |
| Switchboard | 8085 | HTTP | localhost |
| AIDB | 8002 | HTTP | localhost |
| Hybrid Coordinator | 8003 | HTTP | localhost* |
| Qdrant HTTP | 6333 | HTTP | localhost |
| Qdrant gRPC | 6334 | gRPC | localhost |
| PostgreSQL | 5432 | TCP | localhost |
| Redis | 6379 | TCP | localhost |
| Open WebUI | 3000 | HTTP | LAN (optional) |

*LAN exposure controlled by `mySystem.aiStack.listenOnLan`

---

*See also: [docs/api/hybrid-openapi.yaml](../api/hybrid-openapi.yaml) for API specification*
