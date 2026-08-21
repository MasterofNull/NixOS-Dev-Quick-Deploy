---
doc_type: design
title: Local Context Supply Chain — front-loaded retrieval-gated context for local agents
status: in-progress
owner: hyperd
date: 2026-08-17
---

# Local Context Supply Chain (Phase 0)

## Problem (owner-confirmed, in-situ validated)
Qwen on the APU re-prefills fully every call and is single-slot. Two compounding wastes:
1. The agent reads **whole files** (17KB / ~4.3K tokens) into context → huge prefill → slow first token.
2. The system's **knowledge base is read-starved**: 15+ populated Qdrant collections
   (`codebase-context`, `error-solutions` 63+ patterns, `best-practices`, `skills-patterns`,
   `wiki-sections`, `agent-memory-*`) are reachable only by **in-loop tool calls** (`query_aidb`,
   `get_hint`) — each an extra slow prefill, and the anti-stagnation guard *aborts* the agent for
   making them without an interleaved action. So local starts most tasks **cold**, re-deriving fixes
   the base already holds and reading files already indexed in `codebase-context`.

## Decision (the framework we enforce)
**Invariant:** *A local task's context is assembled ONCE at dispatch by the embed model — code span
+ prior fixes + skill + best-practice + docs + memory, token-budgeted — and Qwen reasons over that
small, complete prompt. In-loop retrieval is a bounded fallback, not the primary path.*

Rationale (the round-trip insight): on a re-prefill-every-call model, minimizing prompt SIZE while
increasing the NUMBER of prefills is a net loss. Front-loading pays the breadth cost ONCE (cheap on
bge-m3), then Qwen runs with **fewest steps, fewest prefills, fewest failure points** — the right
target for an unsupervised bulk lane (throughput/reliability, not latency).

## Slice 0.1 — the assembler (this slice)
**New:** `ai-stack/local-agents/context_assembler.py`
```
assemble_context(task_text: str, *, task_id: str, token_budget: int = 3500,
                 collections: list[str] | None = None) -> AssembledContext
# .text (labeled block to prepend), .sources [{collection,score,citation}], .tokens, .stats
```
- Embed `task_text` ONCE via bge-m3 (:8081); search each collection (:6333) top-k.
- Default ranked sources w/ per-source caps (so no source dominates):
  codebase-context k=4, error-solutions k=3, best-practices k=2, skills-patterns k=2,
  wiki-sections k=2, agent-memory-semantic k=2.
- Merge → sort by score → greedy-fill under `token_budget` with per-source caps.
- Format a labeled block: `## Relevant prior knowledge (front-loaded — do NOT re-fetch)` with a
  subsection per source and `[file:line]` / id citations.
- **Fail-open** (mirror `context_cache.py`): any embed/Qdrant/collection error → skip that source,
  never raise. Missing collection = skipped, not fatal.
- Reuse `context_cache.embed_text` + a thin Qdrant search helper. Minimal-code — no new deps.

**Wire:** in `scripts/ai/lib/dispatch.py` (local dispatch path), before assembling the agent prompt,
call `assemble_context(task_objective)` and PREPEND `.text` to the system/first-user context.
Gate behind env `AQ_CONTEXT_ASSEMBLER` (default `1`; kill switch `0`). Log `.tokens` + source count
to the task's progress/ledger so we can PROVE it fired.

**Test:** `scripts/testing/test-context-assembler.py` — dual-mode (real :8081/:6333 + offline stub).
Assert: (a) a code task pulls from ≥2 collections; (b) output respects `token_budget`;
(c) fail-open when a collection is absent/embed down; (d) citations present.

## Slice 0.2 (follow-on, NOT this dispatch) — enforcement hardening
- `read_file` backstop gate in `agent_executor.py`: files > ~1500 tok return outline + top chunks,
  not raw bytes. Front-loading is primary; this is the in-loop backstop.
- Remove `git_add`/`git_commit` from local's tool set → no-commit becomes STRUCTURAL, not prompt-hoped.

## Validation / Definition of Done (Rule 15)
- integrated: assembler called on the live local dispatch path (behind default-on flag).
- ON: `AQ_CONTEXT_ASSEMBLER=1` in the running system.
- real-world: a real backlog slice runs with front-loaded context; prefill/steps measured vs the
  `dogfood-01` slow-path baseline (before/after tokens + first-token latency + steps-per-task).
- observable: assembled-tokens + source-count logged to progress.json + dogfood-ledger.
- intervenable: kill switch `AQ_CONTEXT_ASSEMBLER=0`.

## Guardrails (in force)
Local NEVER commits (orchestrator commits on remote-APPROVE + tier0). Fail-open everywhere.
Sequential local only. `dogfood-01` (slow path) finishes untouched as the baseline.

## BASELINE (slow path, dogfood-01, 2026-08-18T04:19:41Z)
- Task: router-role-route-exclude-lane-granularity (bounded single-file edit on aq-role-route, 449L/17KB).
- Result: **FAILED** at 1540.9s (25.7 min), 8 tool calls, NO edit landed.
- Failure: repeated-read stagnation ("read 4x without progress, abort at call 8").
- Root cause: whole-file read ~4.3K tok near 5200 budget → context prune evicts needed span → re-read loop.
- Model capability CONFIRMED: located _matches_exclude (L270-285) + drafted correct fix; the HARNESS defeated it, not the model.
- => The assembler's target metric: this SAME task should complete in <=2 steps once the exclude-handling span is front-loaded. That before/after is the proof.

## AFTER-run 1 (Slice 0.1 only, 2026-08-18T04:49:52Z) — VALIDATES that 0.2 is load-bearing
- Same task, assembler ON. Assembler fired correctly (1213 tok, aq-role-route spans + relevant best-practice).
- Result: FAILED at 427s (7 min), 2 tool calls, no edit.
- Cause: agent STILL read the whole 17KB file on top of the front-loaded spans → 25920 chars > 24000 LLAMA_MAX_PROMPT_CHARS → char-guard REFUSED (correctly — no slot wedge).
- LESSON: Slice 0.1 (front-load) is ADDITIVE; without Slice 0.2 (read_file gate + suppress redundant in-loop retrieval) it can make total context WORSE. The two halves are not separable. Building 0.2 now.
- Guard working: LLAMA_MAX_PROMPT_CHARS=24000 correctly refused an oversized prefill instead of wedging (contrast run 1's slot wedge).
