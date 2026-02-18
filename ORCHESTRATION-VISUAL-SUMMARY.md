# AI Stack Orchestration - Visual Summary
**Quick Reference Guide**

---

## The Three Orchestrators (One Page)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          YOUR AI STACK                               │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Ralph Wiggum    │  │ Hybrid-Coordinator│  │      AIDB        │  │
│  │  🔄 Loop Engine  │  │  🔀 Smart Router  │  │  📚 Knowledge    │  │
│  │                  │  │                   │  │     Base         │  │
│  │  Port: 8090/8098│  │   Port: 8092      │  │  Port: 8091      │  │
│  │                  │  │                   │  │                  │  │
│  │  "Keep trying    │  │  "Local or cloud? │  │  "Find answers"  │  │
│  │   until done"    │  │   Learn from it"  │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│           │                      │                      │            │
│           │                      │                      │            │
│           └──────────────────────┴──────────────────────┘            │
│                                  │                                   │
│                     ┌────────────┴────────────┐                     │
│                     │                         │                     │
│           ┌─────────▼──────┐      ┌──────────▼─────────┐           │
│           │   PostgreSQL   │      │      Qdrant        │           │
│           │   + pgvector   │      │   (Vector DB)      │           │
│           │                │      │                    │           │
│           │  • tool_registry│     │  • skills-patterns │           │
│           │  • telemetry   │      │  • error-solutions │           │
│           │  • embeddings  │      │  • nixos-docs      │           │
│           └────────────────┘      └────────────────────┘           │
│                                                                      │
│           ┌─────────────────────────────────────┐                   │
│           │             Redis                   │                   │
│           │           (Cache + State)           │                   │
│           │                                      │                   │
│           │  • Query cache (24h TTL)            │                   │
│           │  • Embedding cache                  │                   │
│           │  • Session state                    │                   │
│           │  • Rate limiter state               │                   │
│           └─────────────────────────────────────┘                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## When to Use Which

### Ralph Wiggum 🔄
```
┌────────────────────────────────┐
│ USE FOR:                       │
│ • Code generation with retry   │
│ • Multi-file refactoring       │
│ • Iterative bug fixing         │
│ • Autonomous development       │
│                                │
│ EXAMPLES:                      │
│ ✓ "Implement feature X"        │
│ ✓ "Refactor module Y"          │
│ ✓ "Fix bug Z (keep trying)"    │
│                                │
│ KEY FEATURE:                   │
│ Never gives up (exit code 2)   │
└────────────────────────────────┘
```

### Hybrid Coordinator 🔀
```
┌────────────────────────────────┐
│ USE FOR:                       │
│ • Smart query routing          │
│ • Cost optimization            │
│ • Continuous learning          │
│ • Context augmentation         │
│                                │
│ EXAMPLES:                      │
│ ✓ "How to configure X?"        │
│ ✓ "Explain Y"                  │
│ ✓ "Help me with Z"             │
│                                │
│ KEY FEATURE:                   │
│ Learns from every interaction  │
└────────────────────────────────┘
```

### AIDB 📚
```
┌────────────────────────────────┐
│ USE FOR:                       │
│ • Knowledge base queries       │
│ • Tool discovery               │
│ • Health monitoring            │
│ • Issue tracking               │
│                                │
│ EXAMPLES:                      │
│ ✓ "Search docs about X"        │
│ ✓ "List available tools"       │
│ ✓ "Report issue Y"             │
│                                │
│ KEY FEATURE:                   │
│ Central entry point for all    │
└────────────────────────────────┘
```

---

## Typical Workflows

### Workflow 1: Simple Question
```
User: "How to enable SSH?"
  ↓
AIDB → Hybrid → llama.cpp (local)
  ↓       ↓         ↓
Check   Score   Execute (200ms, $0)
cache   0.88
  ↓       ↓         ↓
Cache → Learn → Return answer
miss    pattern
```

### Workflow 2: Complex Question
```
User: "Design HA deployment"
  ↓
AIDB → Hybrid → Claude API (remote)
  ↓       ↓         ↓
Get     Score   Execute (2s, $0.05)
context 0.62
  ↓       ↓         ↓
Augment → Learn → Return answer
         3 patterns
```

### Workflow 3: Code Task
```
User: "Add authentication"
  ↓
Ralph Wiggum Loop:
  ↓
Iteration 1: Create auth.py
Iteration 2: Add tests (exit blocked!)
Iteration 3: Fix tests ✓
  ↓
Done after 3 iterations
```

---

## Data Flow

```
WRITE FLOW (Telemetry):

User Action
    ↓
Service Execution
    ↓
Write to JSONL
    ├─ ralph-events.jsonl
    ├─ aidb-events.jsonl
    ├─ hybrid-events.jsonl
    └─ vscode-events.jsonl
    ↓
Continuous Learning Daemon
    ↓
Process & Extract Patterns
    ↓
Store Results:
    ├─ PostgreSQL (structured)
    ├─ Qdrant (vectors)
    └─ dataset.jsonl (training)


READ FLOW (Query):

User Query
    ↓
AIDB Entry Point
    ↓
Check Cache (Redis)
    ├─ Hit? → Return (fast!)
    └─ Miss? → Continue
    ↓
Search Context (Qdrant)
    ↓
Route via Hybrid Coordinator
    ├─ Local? → llama.cpp
    └─ Remote? → Claude/GPT
    ↓
Return Result
    ↓
Cache for Future (Redis)
    ↓
Learn from Interaction
```

---

## Port Reference

```
INTERNAL (Container Network):
┌──────────────────────────────┐
│ 5432  PostgreSQL             │
│ 6379  Redis                  │
│ 6333  Qdrant                 │
│ 8080  llama.cpp              │
│ 8081  Embeddings             │
│ 8091  AIDB                   │
│ 8092  Hybrid-Coordinator     │
│ 8090  Ralph Wiggum (MCP)     │
│ 8098  Ralph Wiggum (FastAPI) │
└──────────────────────────────┘

EXTERNAL (Host Access):
┌──────────────────────────────┐
│ 8443  nginx (HTTPS)          │
│ 8888  Dashboard              │
│ 3001  Open-WebUI             │
│ 3002  Grafana                │
│ 9090  Prometheus             │
│ 16686 Jaeger                 │
│ 47334 MindsDB                │
└──────────────────────────────┘

VIA NGINX:
https://localhost:8443/aidb/
https://localhost:8443/hybrid/
https://localhost:8443/ralph/
```

---

## Learning Pipeline

```
AUTOMATIC (24/7):

Every Hour:
    ↓
Read Telemetry Files
    ↓
Compute Value Scores
    ↓
Filter High-Value (≥0.7)
    ↓
Extract Patterns (LLM)
    ↓
Store in Qdrant
    ↓
Generate Training Data
    ↓
Append to dataset.jsonl
    ↓
[Repeat Forever]


VALUE SCORE:
┌─────────────────────────────┐
│ Outcome Quality     40%     │
│ User Feedback       20%     │
│ Reusability         20%     │
│ Complexity          10%     │
│ Novelty             10%     │
├─────────────────────────────┤
│ TOTAL = 0-1.0               │
│ Learn if ≥ 0.7              │
└─────────────────────────────┘
```

---

## Quick Troubleshooting

```
PROBLEM: Service won't start
→ Check: podman logs <service>
→ Check: Dependencies healthy?

PROBLEM: Query slow
→ Check: Cache hit rate
→ Check: Local vs remote ratio
→ Check: Database connections

PROBLEM: Learning not working
→ Check: Telemetry files exist?
→ Check: Daemon running?
→ Check: Dataset growing?

PROBLEM: High costs
→ Check: Routing stats
→ Check: Confidence thresholds
→ Check: Local model quality
```

---

## Key Commands

```bash
# Check all services
podman ps --format "table {{.Names}}\t{{.Status}}"

# Query AIDB
curl -X POST http://localhost:8091/query \
  -d '{"query": "How to...?"}'

# Check hybrid stats
curl http://localhost:8092/stats

# Submit task to Ralph
curl -X POST http://localhost:8090/submit \
  -d '{"task": "Implement X"}'

# Check learning progress
wc -l ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl

# View telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/*.jsonl

# Dashboard
open http://localhost:8888/dashboard.html
```

---

## Architecture Layers

```
┌─────────────────────────────────────┐
│   USER INTERFACE LAYER              │
│   • Dashboard (8888)                │
│   • Open-WebUI (3001)               │
│   • Grafana (3002)                  │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│   ORCHESTRATION LAYER               │
│   • Ralph Wiggum (iteration)        │
│   • Hybrid-Coordinator (routing)    │
│   • AIDB (knowledge)                │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│   EXECUTION LAYER                   │
│   • llama.cpp (local LLM)           │
│   • Aider/Continue/Goose (agents)   │
│   • Cloud APIs (remote LLM)         │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│   DATA LAYER                        │
│   • PostgreSQL (structured)         │
│   • Qdrant (vectors)                │
│   • Redis (cache)                   │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│   OBSERVABILITY LAYER               │
│   • Telemetry (JSONL)               │
│   • Prometheus (metrics)            │
│   • Jaeger (tracing)                │
└─────────────────────────────────────┘
```

---

## Success Metrics

```
RALPH WIGGUM:
✓ Task completion rate > 80%
✓ Average iterations < 5
✓ Exit code 2 blocking working

HYBRID COORDINATOR:
✓ Local routing > 70%
✓ Average latency < 500ms
✓ Cost savings > $50/month

CONTINUOUS LEARNING:
✓ Dataset growth > 50/week
✓ Patterns extracted > 10/day
✓ Value score avg > 0.65

OVERALL SYSTEM:
✓ Query success rate > 90%
✓ System uptime > 99%
✓ All health checks passing
```

---

## Configuration Checklist

```
✓ PostgreSQL password set
✓ Redis configured
✓ Qdrant collections created
✓ Embeddings model loaded
✓ llama.cpp model downloaded
✓ Telemetry paths writable
✓ Fine-tuning directory exists
✓ All health checks passing
✓ Dashboard accessible
✓ nginx routing working
```

---

**REFERENCE STATUS: COMPLETE**

*Three orchestrators, clear roles, seamless integration*
*Ralph iterates, Hybrid routes, AIDB knows*
*All working together to make AI easy*
