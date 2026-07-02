---
name: context-efficiency
description: "Context Efficiency Skill"
---

# Context Efficiency Skill
## Tags
context, tokens, compaction, RESUME, PULSE, sub-agent, slicing, grep_search, scoping, budget, MEMORY
## When to Use
Approaching context limits; writing RESUME.json; slicing context for sub-agents; choosing between
full-file reads vs targeted searches; deciding what to include in a delegation prompt.

---

## 1. The Core Principle: Pay Only for What You Need

Every token loaded that isn't used is waste. For large-codebase agents, context fill causes:
- Earlier conversation turns to be summarized/dropped (compaction)
- Sub-agents receiving irrelevant noise that degrades quality
- Slower inference on local models (KV cache pressure)

Rule: **load by address, not by content**. Pass file paths to sub-agents; let them read what they need.

---

## 2. RESUME.json — The Compaction Anchor

Write RESUME.json at two mandatory triggers:
1. When starting a new user task
2. After each completed todo item

This is the state that survives a 401 summarization failure. If it's not in RESUME.json, it's at
risk of being lost.

```json
{
  "current_objective": "One sentence: what are we building right now",
  "phase": "Phase 86",
  "todo_snapshot": [
    "done: slice 1 — attention_queue.py",
    "in-progress: slice 2 — aq-alerts CLI",
    "pending: slice 3 — dashboard endpoint"
  ],
  "uncommitted_changes": [
    "scripts/ai/lib/attention_queue.py",
    "scripts/ai/aq-alerts"
  ],
  "resume_hint": "Next: implement /api/aistack/alerts/status in aistack.py"
}
```

Path: `.agent/collaboration/RESUME.json`

---

## 3. PULSE.log — Atomic Event Log

Append one line after every successful write or commit:
```
[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]
```

Example:
```
2026-05-30T14:22:11Z [claude] [write]: scripts/ai/lib/attention_queue.py — added priority queue
2026-05-30T14:25:03Z [claude] [commit]: feat(phase-86) — HITL attention queue v1
```

PULSE.log is the durable audit trail. RESUME.json is the point-in-time snapshot.
Do not duplicate between them — PULSE records history, RESUME records current state.

---

## 4. Sub-Agent Context Slicing

Pass ONLY what the sub-agent needs for its slice. Never pass full history.

**Include:**
```
- slice_objective (1-2 sentences)
- relevant_files (paths only — agent reads them)
- acceptance_criteria (explicit pass/fail conditions)
- constraints (ports, security rules, existing patterns)
- reference_skills (skill names only: ["apparmor-rules", "python-async"])
```

**Exclude:**
- Full HANDOFF.md (pass path, not content)
- Previous agent outputs
- Unrelated file contents
- Full AGENTS.md (reference specific sections)

Estimated token savings per delegation: 2000–8000 tokens depending on history depth.

---

## 5. Search Scoping

Order of preference (cheapest to most expensive):

| Task | Tool | Why |
|------|------|-----|
| Find files by name | Glob | Single index scan |
| Find pattern in known directory | Grep with `path=` | Bounded scope |
| Understand a specific function | Read with `offset+limit` | Skip header boilerplate |
| Broad codebase discovery | Grep without path | Full scan — use sparingly |
| "What pattern does X follow?" | RAG /query via coordinator | Semantic, 0 file reads |

**For directed searches** (known file or location): use Grep/Glob directly.
**For exploratory searches**: use Agent with subagent_type=Explore to keep main context clean.

Do NOT run both `agrep` AND Grep for the same pattern — pick one.

---

## 6. Hot Memory Budget Rules

`ai-stack/agent-memory/MEMORY.md` has a 200-line hard limit (lines after 200 are truncated on load).

Degradation rules:
1. Phase complete + deployed → collapse to 1-line pointer to topic file
2. Topic file not referenced in 2+ sessions → move to archive/
3. `ai-stack/agent-memory/MEMORY.md` never grows — swap entries, don't append
4. Bug patterns promoted only if they hit in 2+ separate sessions

Writing new facts to hot memory: write to a topic file first, add a 1-line pointer to `ai-stack/agent-memory/MEMORY.md`.

---

## 7. Delegation Prompt Token Budget

Rough token costs for common context items:
```
Full HANDOFF.md:        ~800–2000 tokens
RESUME.json:            ~150–300 tokens
Single SKILL.md:        ~400–1000 tokens
Single file content:    ~100–5000 tokens (varies)
Slice prompt (lean):    ~200–500 tokens
```

For local model delegation (Qwen3-35B): hard ceiling is 180 output tokens (coordinator enforces).
Input context budget: 3500 tokens for `local-agent` profile.

Keep delegation prompts under 1500 tokens total (prompt + context). For Gemini: under 2000 tokens
to avoid routing classifier failure (429).

---

## 8. Context Recovery After Compaction

When resuming after a 401 / context overflow:
```bash
aq-resume        # outputs RESUME.json state
cat .agent/collaboration/HANDOFF.md  # last agent's work record
```

Do NOT re-read files that were already read in the session (CLAUDE.md rule).
Do NOT re-run discovery searches that completed before compaction.
RESUME.json tells you exactly where to pick up.

---

## 9. File Reads — Bounded by Default

When reading files in handlers or agent code, always bound the read:

```python
# WRONG — loads entire 50K line log into context:
content = Path("/var/lib/ai-stack/tool-audit.jsonl").read_text()

# CORRECT — tail only what you need:
lines = Path("/var/lib/ai-stack/tool-audit.jsonl").read_text().splitlines()[-200:]
```

Same for Grep: use `limit=` and specific path when possible.

For Read tool: always pass `offset` + `limit` for files > 200 lines unless you need the full file.
