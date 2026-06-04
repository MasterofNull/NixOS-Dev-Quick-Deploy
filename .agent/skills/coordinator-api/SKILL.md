---
name: coordinator-api
description: "Coordinator API Skill"
---

# Coordinator API Skill
## Tags
http, api, auth, coordinator, routes, 8003, loopback, query, memory, control, workflow
## When to Use
Calling coordinator HTTP endpoints; getting 401/403 errors; unsure which route to use; building
payloads for /query, /workflow, /control/ai-coordinator, /memory, /hints.

---

## 1. Connection

```
Base URL:  http://127.0.0.1:8003      (always use 127.0.0.1, never hostname)
Switchboard: http://127.0.0.1:8085   (LLM inference gateway — NOT the coordinator)
AIDB:      http://127.0.0.1:8002      (BLOCKED for direct access — use :8003 endpoints)
```

All coordinator calls from code: use `os.environ.get("HYBRID_URL", "http://127.0.0.1:8003")`.

---

## 2. Authentication

```python
# Read key from secrets file (never hardcode):
key_file = os.environ.get("HYBRID_API_KEY_FILE", "/run/secrets/hybrid_coordinator_api_key")
with open(key_file) as f:
    api_key = f.read().strip()

headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json",
}
```

**Loopback bypass**: Requests from `127.0.0.1` on these path prefixes skip API key auth:
```
/hints          /workflow/      /query          /v1/orchestrate   /v1/
/review/        /discovery/     /control/ai-coordinator/
/control/llm/   /control/agents/ /control/agents  /control/review/
/control/runtimes /control/runtimes/  /memory/   /memory/crystalline/
/learning/      /cache/         /harness/       /parity/
/feedback       /status         /alerts         /stats
/learning/stats /control/safety/ /agent/lifecycle/ /control/reasoning/
/qa/
```

If your route is NOT in this list and you're calling from loopback, you still need the X-API-Key.

**DUAL AUTH WARNING**: `http_server.py` has an inline `agent_prefixes` copy at ~line 1412
(`_is_loopback_agent_request`) separate from `middleware/auth.py`. When adding new loopback
routes, update **both** files or the route will get 401 on one code path.

---

## 3. Key Routes

### Query / Search
```
POST /query                          Text query → RAG response
POST /query/hybrid                   Hybrid dense+sparse search
POST /v1/orchestrate                 Full agent orchestration turn
GET  /hints?query=<text>&context=<> Contextual hints for agent prompts
GET  /hints/list                     All available hint categories
```

### Memory
```
POST /memory/facts                   Insert memory fact
POST /memory/broker/push             Push to memory broker (loopback agents only)
GET  /memory/broker/status           Broker health
POST /memory/crystalline/            Save crystallized knowledge
GET  /memory/crystalline/search      Search crystallized knowledge
```

### Agent Control
```
POST /control/ai-coordinator/delegate    Delegate task to local agent
GET  /control/ai-coordinator/status      Agent runtime status
POST /control/agents/spawn               Spawn sub-agent
GET  /control/agents/list                List active agents
GET  /control/runtimes                   Runtime availability
POST /control/llm/switch                 Switch active model
```

### Workflow
```
POST /workflow/plan                  Create workflow plan
POST /workflow/run/start             Start workflow execution
GET  /workflow/run/{id}/status       Workflow run status
POST /workflow/run/{id}/step         Advance workflow step
```

### Health + Status
```
GET  /health                         Basic health (no auth)
GET  /health/detailed                Full service health
GET  /status                         Coordinator status
GET  /stats                          Usage statistics
GET  /metrics                        Prometheus metrics
```

---

## 4. Payload Patterns

### /query
```json
{
  "query": "your search text",
  "collection": "best-practices",        // optional: target specific collection
  "n_results": 5,                        // optional: default 5
  "score_threshold": 0.45,               // optional: BGE-M3 default 0.45
  "metadata_filter": {}                  // optional: filter by metadata fields
}
```

### /control/ai-coordinator/delegate
```json
{
  "task": "your task description",
  "profile": "local-tool-calling",        // switchboard profile
  "max_tokens": 180,                     // hard ceiling for local profiles
  "role": "implementer",                 // orchestrator|architect|implementer|reviewer
  "agent_type": "human"                  // "human" = L0 interactive priority (bypasses MLFQ deprioritize)
}
```

### /memory/facts
```json
{
  "content": "fact text",
  "source": "agent-name",
  "fact_type": "observation",            // observation|decision|error|solution
  "metadata": {"phase": "86", "scope": "apparmor"}
}
```

---

## 5. Rate Limits

```
/query:        30 RPM
/hints:        60 RPM
/workflow:     30 RPM
/search/tree:  20 RPM
/harness/eval: 20 RPM
/a2a:         300 RPM
/ (root):     300 RPM
Exempt:  /health, /metrics, /health/detailed, /health/aggregate
```

---

## 6. Error Patterns

| HTTP code | Cause | Fix |
|-----------|-------|-----|
| 401 | Missing/wrong X-API-Key | Check key file path; add path to LOOPBACK_AGENT_PREFIXES if loopback |
| 429 | Rate limit hit | Implement exponential backoff; use loopback path if from 127.0.0.1 |
| 500 | Coordinator Python error | `journalctl -u ai-hybrid-coordinator -n 20` |
| 503 | LLM slot busy | Retry with backoff; SLOT_WAIT_S handles this in delegate-to-local |
| -1 / timeout | Service down or slow start | Check `systemctl is-active ai-hybrid-coordinator`; cold start = ~5s |
