# 62 — Agent Memory, Diaries & Long-Horizon Persistence

> **Load:** On-demand — reference when starting a continuation task, or before any
> long-horizon, multi-session, or cross-agent workflow.
> **Related:** `61-WORKFLOW-PRACTICES.md`, `45-PROGRESSIVE-DISCLOSURE.md`
> **Source:** Distilled from `docs/AGENTS.md` §8.5, `docs/memory-system/`, live harness.

---

## Overview: What the Harness Provides

The locally-hosted AI harness (hybrid-coordinator, port 8003) provides **three distinct
persistence systems** for agents:

| System | Purpose | Backend | Scope |
|---|---|---|---|
| **Qdrant memory collections** | Semantic search over stored facts | Qdrant vector DB | Shared across agents |
| **Agent diaries** | Per-agent expertise accumulation | AIDB (Postgres + Qdrant) | Agent-private, orchestrator-readable |
| **Lesson registry** | Promoted lessons injected at query time | AIDB | Shared, review-gated |
| **Semantic cache** | Avoid re-computing similar queries | In-memory + Qdrant | Session / service lifetime |
| **Delegation result cache** | Re-use high-quality delegate responses | In-memory | Service lifetime |

---

## 1. Memory Collections (Qdrant)

Three typed collections are available. Choose by **content type**, not convenience:

| Type | Qdrant Collection | Use for |
|---|---|---|
| `episodic` | `agent-memory-episodic` | Events, sessions, "what happened" — task outcomes, deployments, decisions made in context |
| `semantic` | `agent-memory-semantic` | Facts, concepts, persistent knowledge — architecture decisions, library choices, config |
| `procedural` | `agent-memory-procedural` | How-to knowledge — workflows, runbooks, repeatable patterns |

### Store a memory

**Via CLI (`aq-memory`):**
```bash
# Store a decision (semantic)
aq-memory add "Delegation routes to remote-free agent pool by default (Phase 14.2)" \
  --project ai-stack --topic delegation --type decision --tags "routing,delegation,phase14"

# Store a session outcome (episodic)
aq-memory add "Fixed corrupt prefix in ai_coordinator_handlers.py — was blocking delegation" \
  --project ai-stack --topic coordinator --type context --tags "fix,phase14"

# Store a repeatable how-to (procedural)
aq-memory add "To debug delegation: journalctl -u ai-hybrid-coordinator.service -n 50 | grep delegate" \
  --project ai-stack --topic debugging --type procedure --tags "delegation,debug"
```

**Via API (POST /memory/store):**
```bash
API_KEY=$(cat /run/secrets/hybrid_coordinator_api_key | tr -d '[:space:]')
curl -s -X POST http://127.0.0.1:8003/memory/store \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "memory_type": "episodic",
    "summary": "Phase 14 delegation fix: prefer_local now False by default",
    "content": "Detailed content here...",
    "metadata": {"project": "ai-stack", "topic": "delegation", "tags": ["phase14"]}
  }'
```

**Via MCP tool (Claude Code / hybrid-coordinator-bridge):**
```
store_memory(summary="...", memory_type="episodic", metadata={...})
```

### Recall a memory

```bash
# CLI
aq-memory search "delegation routing" --project ai-stack --topic delegation --limit 10
aq-memory list --project ai-stack --valid-now --limit 20
aq-memory list --stale   # find facts that need updating

# API
curl -s -X POST http://127.0.0.1:8003/memory/recall \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "delegation routing fix", "memory_types": ["episodic","semantic"], "limit": 5}'

# MCP tool
recall_memory(query="delegation routing", memory_types=["semantic"])
```

### Confidence levels
| Level | Meaning |
|---|---|
| 1.0 | Verified, authoritative (docs, specs) |
| 0.9 | High confidence, tested (working code) |
| 0.8 | Moderate, observed behaviour |
| 0.7 | Inferred, needs verification |
| <0.7 | Speculative — tag accordingly |

---

## 2. Agent Diaries

Each agent has a **private diary** for personal expertise accumulation across sessions.
Orchestrators can read any diary in observer mode (read-only).

### Write to your diary
```python
from aidb.agent_diary import AgentDiary

diary = AgentDiary("qwen")   # use your agent name
diary.write(
    "Phase 14.2: delegation fix — corrupt prefix removal + prefer_local=False. "
    "Root cause was previous agent prepending raw diff as string literal.",
    topic="coordinator",
    tags=["delegation", "phase14", "debugging"]
)
```

```bash
# Or via CLI
aq-memory agent-diary write "What I learned today..." --topic coding --tags "phase14"
```

### Read your diary
```bash
aq-memory agent-diary qwen --limit 20              # recent entries
aq-memory agent-diary qwen --topic auth --limit 10  # topic filter
aq-memory agent-diary qwen --since 7d              # last 7 days
```

### Orchestrator observer mode
```python
# Orchestrators only — read-only
qwen_work = AgentDiary.read_as_observer("qwen", topic="coordinator", limit=10)
```

### Diary best practices
- **Write after completing a task** — "what I learned", not just "what I did"
- **Search your diary before starting similar work** — avoids repeating mistakes
- **Tag consistently** — use phase numbers, subsystem names, and outcome type
- **Review at session start** for long-horizon tasks — `aq-memory agent-diary <name> --limit 5`

---

## 3. Lesson Registry (Promoted Lessons)

Lessons are **reviewed and approved** knowledge chunks that get injected at query time.
They represent distilled, high-confidence outcomes from past agent work.

```bash
# View active lessons
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8003/control/ai-coordinator/lessons \
  | python3 -m json.tool

# Promote a lesson for review
aq-capability-promote --lesson "lesson-key" --agent codex
```

Lessons are automatically injected (up to 2 refs) into delegate and query responses.
See `.agents/plans/` and `aq-rate` output for lesson promotion candidates.

---

## 4. Progressive Memory Loading (L0–L3)

Use layered loading to **minimise token usage** (50%+ reduction vs full load):

| Layer | Tokens | Always loaded? | Contents |
|---|---|---|---|
| L0 Identity | ~50 | ✅ Yes | Agent name, role, system context (`~/.aidb/identity.txt`) |
| L1 Critical | ~170 | ✅ Yes | Recent decisions (7d), active blockers, key preferences |
| L2 Topic | variable | On-demand | Facts relevant to current query, auto-filtered by topic |
| L3 Full | heavy | Explicit only | Complete semantic search — use sparingly |

```python
from aidb.layered_loading import LayeredMemory

memory = LayeredMemory(fact_store=store)

# L0 + L1 + L2 auto (78% token reduction vs full)
context = memory.progressive_load(
    query="How should I fix delegation routing?",
    max_tokens=500
)

# L0 + L1 only (cheapest, for quick orientation)
context = memory.progressive_load(query, max_tokens=220)
```

**CLI equivalent:**
```bash
aq-memory search "<query>" --project ai-stack --topic <topic> --limit 10   # L2 equivalent
```

---

## 5. Semantic Cache

The harness maintains a **semantic similarity cache** for query responses:
- Current hit rate: ~93.8% (see `aq-report`)
- Cache is prewarm-enabled — runs at service start
- Warm manually: `aq-cache-warm` / `aq-cache-prewarm`

Agents don't need to manage this directly — it's automatic. But be aware:
- Cache hits return in <10ms vs 100ms+ for fresh retrieval
- Cache is NOT used for delegation results (separate cache)
- To force fresh retrieval, pass `cache_bust=true` in query payload

---

## 6. When to Use Memory — Decision Tree

```
Starting a continuation task or new session?
  → aq-memory search "<task>" --project ai-stack --limit 5   (FIRST action)
  → aq-memory agent-diary <your-name> --limit 5

Made an architecture decision?
  → Store as semantic: aq-memory add "<decision>" --type decision

Completed a task / fixed a bug?
  → Store as episodic: aq-memory add "<outcome>" --type context
  → Write diary entry: aq-memory agent-diary write "<lesson>"

Discovered a repeatable pattern / runbook step?
  → Store as procedural: aq-memory add "<how-to>" --type procedure

High-value lesson to share across agents?
  → Promote to lesson registry: aq-capability-promote
```

---

## 7. Health & Validation

Ensure the memory systems are reachable and correctly indexed:

```bash
# Verify Data Store Health (Layer 1)
aq-qa 1

# Check Qdrant collections status
curl -sS http://127.0.0.1:6333/collections | jq

# Re-index AIDB (Manual trigger)
sudo systemctl start ai-aidb-reindex
```

## 8. Memory Hygiene (Monthly)

```bash
aq-memory list --stale --project ai-stack           # find outdated facts
aq-memory expire <id> --reason "superseded"         # expire stale facts
aq-memory stats --project ai-stack                  # size / health stats
aq-memory agent-diary $(whoami) --limit 100 | wc -l # diary size check
```

**Never store:**
- Passwords, API keys, tokens, secrets of any kind
- Sensitive personal data
- Large binary content
- Temporary debugging notes (use inline comments instead)

---

## 8. Performance Tips

```bash
# Use metadata filtering — 34% recall improvement
aq-memory search "auth" --project ai-stack --topic auth     # fast
aq-memory search "auth"                                      # slow (no filter)

# Set result limits — never use --limit 1000
aq-memory search "<query>" --limit 10
```

**Token budget guidance:**
- `max_tokens=220` → L0+L1 only (78% reduction)
- `max_tokens=520` → L0+L1+L2 (48% reduction)
- `max_tokens=2000+` → full L3 (use only when explicitly needed)

---

## 9. Full Documentation

| Resource | Path |
|---|---|
| User Guide | `docs/memory-system/USER-GUIDE.md` |
| API Reference | `docs/memory-system/API-REFERENCE.md` |
| Integration Examples | `docs/memory-system/INTEGRATION-EXAMPLES.md` |
| Quick Reference | `docs/memory-system/QUICK-REFERENCE.md` |
| Architecture | `docs/architecture/memory-system-design.md` |