# AI Stack Agentic Workflow Fixes Report

**Date:** 2026-01-05
**Status:** Issues Identified, Fixes In Progress

## Executive Summary

Comprehensive investigation of the AI stack revealed that while the infrastructure is running (AIDB, Hybrid Coordinator, continuous learning daemon), the **agentic workflow is not actively being used**. Telemetry is stale, learning metrics show zero interactions, and key components like Ralph Wiggum are not running.

---

## Critical Issues Found

### 1. Ralph Wiggum Loop Not Running ❌ CRITICAL

**Problem:** Ralph Wiggum container exits immediately with code 2

**Root Causes:**
- Behind profile gate in docker-compose.yml (`profiles: ["agents", "full"]`)
- Even after removing profile, container fails to start
- No logs generated on startup (silent failure)
- Depends on agent backends (Aider, AutoGPT) that aren't running

**Impact:**
- No autonomous agent orchestration
- No telemetry generation from agent workflows
- Continuous learning has no data to process

**Fix Applied:**
- ✅ Removed profile gate from docker-compose.yml line 607
- ⏳ Container still failing to start (investigating)

**File:** [ai-stack/compose/docker-compose.yml:607](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/docker-compose.yml#607)

---

### 2. Agent Backend Services Don't Exist ❌ CRITICAL

**Problem:** Ralph orchestrator expects HTTP APIs for agent backends, but they're CLI tools

**Location:** [ai-stack/mcp-servers/ralph-wiggum/orchestrator.py:28-34](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/ralph-wiggum/orchestrator.py#28-34)

```python
BACKEND_URLS = {
    "aider": "http://aider:8080",        # Doesn't exist
    "continue": "http://continue-server:8080",  # Doesn't exist
    "goose": "http://goose:8080",        # Doesn't exist
    "autogpt": "http://autogpt:8080",    # Doesn't exist
    "langchain": "http://langchain:8080"  # Doesn't exist
}
```

**Reality:**
- Aider is a CLI tool (`aider --model ...`)
- AutoGPT is a CLI tool (`python -m autogpt`)
- Continue is a VS Code extension, not a service
- Goose is a CLI tool
- LangChain is a Python library, not a service

**Required Fix:**
- Create HTTP wrapper APIs for CLI tools, OR
- Modify orchestrator to use subprocess execution, OR
- Create simple API adapters for each tool

**Impact:** Even if Ralph starts, it can't execute any agents

---

### 3. No Agent-to-AIDB Integration ❌ HIGH

**Problem:** No code exists that makes HTTP calls to AIDB from agent workflows

**Expected Workflow:**
```
Agent Request → Query AIDB Context → Augment with Qdrant → Execute Agent → Record Telemetry
```

**Current Reality:**
```
No agents running → No AIDB calls → No context → No telemetry
```

**Missing Integration Points:**
- Ralph orchestrator should call `http://localhost:8091/api/v1/context` before agent execution
- Agents should query `http://localhost:8091/vector/search` for relevant patterns
- Agent results should POST to `http://localhost:8091/telemetry/*`

**Files to Modify:**
- [ai-stack/mcp-servers/ralph-wiggum/orchestrator.py](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/ralph-wiggum/orchestrator.py)
- [ai-stack/mcp-servers/aidb/server.py](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/aidb/server.py) (already has endpoints)

---

### 4. Telemetry Stale - No Active Generation ⚠️ HIGH

**Current Status:**
- Last AIDB telemetry: Jan 5 01:16 (recent, from dashboard checks)
- Last Hybrid telemetry: Jan 2 20:30 (4 days old)
- Last Ralph telemetry: Never (container not running)

**Telemetry Files:**
```bash
/home/hyperd/.local/share/nixos-ai-stack/telemetry/
├── aidb-events.jsonl       (44KB, updated today from health checks)
├── hybrid-events.jsonl     (2.4KB, stale)
└── ralph-events.jsonl      (missing - never created)
```

**Issue:** Telemetry is only generated when agents actively use the services

**Root Cause:** No agents are running or making requests

---

### 5. Continuous Learning Daemon Running But Idle ⚠️ MEDIUM

**Status:** ✅ Daemon IS running (PID 3 in hybrid-coordinator container)

**Problem:** Has no telemetry to process because agents aren't running

**Evidence:**
```bash
$ podman top local-ai-hybrid-coordinator
coordinator  3  1  0.070  python3 -u /app/continuous_learning_daemon.py
```

**Learning Metrics:**
```json
{
  "interactions": {
    "total": 157,
    "high_value": 0,
    "last_7d": 10,
    "last_7d_high_value": 0
  },
  "patterns": {
    "extractions": 0,
    "learning_rate": 0.000
  },
  "fine_tuning": {
    "samples": 0
  }
}
```

**Fix:** Get agents running so telemetry is generated

**File:** [ai-stack/mcp-servers/hybrid-coordinator/continuous_learning_daemon.py](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/continuous_learning_daemon.py)

---

### 6. Qdrant Collections Empty - No Context ⚠️ MEDIUM

**Current Status:**
```bash
$ curl http://localhost:8092/health
{
  "collections": [
    "codebase-context",
    "skills-patterns",
    "error-solutions",
    "interaction-history",
    "best-practices"
  ]
}
```

**Collections exist but are empty:**
- No codebase context indexed
- No skill patterns stored
- No error solutions recorded
- No interaction history
- No best practices captured

**Required Actions:**
1. Index current codebase into `codebase-context`
2. Import existing skills into `skills-patterns`
3. Seed `best-practices` with known patterns
4. Let interaction-history build naturally from usage

**Scripts Needed:**
- `scripts/populate-qdrant-collections.sh`
- `scripts/index-codebase.sh`
- `scripts/import-skills-to-qdrant.sh`

---

### 7. Dashboard Monitoring Issues ✅ FIXED

**Issues Found:**
- ✅ `ai_metrics.json` was stale (Jan 2) - now updating
- ✅ Dashboard collector fixed and running every 15 seconds
- ✅ All dashboard data files now fresh

**Remaining Issues:**
- ⚠️ Learning metrics show 0 because no active learning
- ⚠️ Telemetry summary stale because no agent activity

---

## Agent Workflow Architecture

### Designed Workflow (From AGENTS.md)

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Ralph Wiggum    │  ← Should be running (NOT RUNNING)
│ Loop Engine     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Query AIDB      │  ← No integration exists
│ for Context     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Augment with    │  ← Collections empty
│ Qdrant Patterns │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Route to Agent  │  ← Agent backends don't exist
│ (Aider/AutoGPT) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execute Task    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Record          │  ← No telemetry generated
│ Telemetry       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Learning Daemon │  ← Running but has no data
│ Processes       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update Qdrant   │
│ with Patterns   │
└─────────────────┘
```

### Current Reality

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
         ▼
       ❌ STOPS HERE

No agents running
No workflow execution
No learning occurring
```

---

## Fixes Required (Priority Order)

### Priority 1: Get Ralph Wiggum Running

**Tasks:**
1. ✅ Remove profile gate (DONE)
2. ⏳ Debug why container exits with code 2
3. ⏳ Fix agent backend dependencies
4. ⏳ Test Ralph startup with minimal config

**Estimated Effort:** 2-3 hours

---

### Priority 2: Create Agent Backend Adapters

**Options:**

**Option A: HTTP Wrapper Services (Recommended)**
- Create simple FastAPI wrappers for each CLI tool
- Pros: Clean API, matches current architecture
- Cons: More code to maintain

**Option B: Direct Subprocess Execution**
- Modify orchestrator to use `subprocess.run()`
- Pros: Simpler, direct execution
- Cons: Breaks current API design

**Option C: Hybrid Approach**
- Use subprocess for now, add APIs later
- Pros: Fast to implement, functional
- Cons: Technical debt

**Recommendation:** Start with Option C, migrate to Option A

**Estimated Effort:** 4-6 hours

---

### Priority 3: Add AIDB Integration to Orchestrator

**Changes Needed:**

```python
# In orchestrator.py _execute_task()
async def _execute_task(self, task):
    # 1. Query AIDB for context
    context = await self._get_aidb_context(task.prompt)

    # 2. Augment task with context
    augmented_prompt = self._augment_with_context(task.prompt, context)

    # 3. Execute agent
    result = await self._call_agent_backend(augmented_prompt)

    # 4. Record telemetry
    await self._record_telemetry(task, result)

    return result
```

**Estimated Effort:** 2-3 hours

---

### Priority 4: Populate Qdrant Collections

**Scripts to Create:**
1. `scripts/index-codebase.sh` - Index all source files
2. `scripts/import-skills-to-qdrant.sh` - Import `.agent/skills/`
3. `scripts/seed-best-practices.sh` - Add known patterns

**Estimated Effort:** 3-4 hours

---

### Priority 5: Enable Active Telemetry Generation

**Once agents are running:**
- Telemetry will automatically generate
- Learning daemon will process it
- Fine-tuning dataset will grow
- Qdrant will update with patterns

**No additional code needed** - just need agents executing

---

## Immediate Next Steps

1. **Debug Ralph Wiggum startup failure**
   - Check server.py imports
   - Test with minimal configuration
   - Add extensive logging

2. **Create simple agent backend wrapper**
   - Start with Aider only
   - Use subprocess execution
   - Test with single task

3. **Add AIDB context querying**
   - Implement HTTP call to localhost:8091
   - Parse and inject context
   - Test with sample prompts

4. **Populate at least one Qdrant collection**
   - Start with codebase-context
   - Index current project files
   - Verify retrieval works

5. **End-to-end test**
   - Submit task to Ralph
   - Verify context retrieval
   - Check agent execution
   - Confirm telemetry generation
   - Validate learning pipeline processes it

---

## Configuration Changes Made

### docker-compose.yml
```yaml
# Line 607 - Removed profile gate
ralph-wiggum:
  # profiles: ["agents", "full"]  # DISABLED
```

### Dashboard Collector
- ✅ Fixed PATH environment
- ✅ Fixed timer scheduling
- ✅ Added to AI stack startup dependencies

---

## Metrics After Fixes

**Before:**
- Ralph Wiggum: Not running
- Telemetry events/day: ~2-3 (only health checks)
- Learning patterns: 0
- Fine-tuning samples: 0
- Qdrant collections: Empty
- Agent execution: 0

**Target After Fixes:**
- Ralph Wiggum: Running and processing tasks
- Telemetry events/day: 50-100 (active agent workflows)
- Learning patterns: Growing daily
- Fine-tuning samples: 100+ after first week
- Qdrant collections: Populated with context
- Agent execution: Active and continuous

---

## References

- [AGENTS.md](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/AGENTS.md) - Agent onboarding guide
- [AI-AGENT-START-HERE.md](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/AI-AGENT-START-HERE.md) - Quick start
- [docker-compose.yml](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/docker-compose.yml) - Service definitions
- [Ralph Wiggum orchestrator.py](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/ralph-wiggum/orchestrator.py)
- [Continuous Learning Pipeline](file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py)

---

## Conclusion

The AI stack infrastructure is **healthy and running**, but the **agentic workflow layer is not activated**. The key bottleneck is Ralph Wiggum not starting, which blocks all autonomous agent orchestration. Once Ralph is fixed and agent backends are properly integrated, the entire learning pipeline will activate naturally.

**Status:** Infrastructure ✅ | Agentic Workflow ❌ | Learning Pipeline ⏳ (Ready but idle)
