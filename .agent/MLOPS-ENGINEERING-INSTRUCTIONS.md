# MLOPS-ENGINEERING Domain — Agent Instruction Surface

**Domain tag:** `mlops-engineering`
**State:** proposed
**Upstream authority:** `.agent/PROJECT-MLOPS-ENGINEERING-PRD.md`

## 1. Domain Mandate
Maintain the health, speed, and contextual efficiency of the AI harness and its local models.

## 2. Methodology
- **Memory Compression:** Proactively identify overgrown context windows and use semantic compression tools to summarize and archive them.
- **Performance Tuning:** Monitor local LLM KV cache and restart/flush the server if degradation is detected.

## 3. Safety Guardrails
- **NO DESTRUCTIVE GC:** Never permanently delete operational memory. Always compress and move to archive.
- Ensure model restarts are coordinated so as not to interrupt active orchestrator sessions.

## 4. AIDB Interaction
- **Namespace:** `mlops-patterns`
- Store telemetry baselines and prompt-optimization successes here.
