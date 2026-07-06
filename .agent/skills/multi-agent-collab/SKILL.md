---
name: multi-agent-collab
description: "Multi-Agent Collaboration Skill"
---

# Multi-Agent Collaboration Skill
## Tags
orchestrator, multi-agent, review, handoff, delegation, RESUME, PULSE, role, slice
## When to Use
Designing a review cycle; handing off between architect/implementer/reviewer; coordinating
parallel agents; signaling task completion; structuring RESUME.json for cross-agent continuity.

---

## 1. Role Matrix (summary)

| Role | Can do | Cannot do |
|------|--------|-----------|
| `orchestrator` | Assign slices, accept work, commit integration, open/close sessions | Implement code itself without reviewer |
| `architect` | Draft architecture, write PRDs, flag risks | Commit without orchestrator review |
| `implementer` | Edit files within assigned slice, validate, propose commit | Self-promote to reviewer, re-scope |
| `reviewer` | Issue pass/fail verdict against slice criteria | Review own work |

**Sub-agent non-orchestrator rule**: sub-agents execute only assigned slices. Do not re-scope,
do not route other agents, do not finalize acceptance.

---

## 2. Canonical 2-3 Agent Review Cycle

```
Orchestrator (Claude)
  ├─ 1. Write PRD + assign slice to implementer
  ├─ 2. delegate-to-gemini --role implementer --prompt-file /tmp/slice.txt
  ├─ 3. delegate-to-gemini --role reviewer --prompt "Review commit X per criteria Y"
  └─ 4. Accept or REQUEST_REVISION; commit final integration

Single-agent multi-role (when team not needed):
  └─ Single agent handles all roles sequentially, marks each role switch explicitly
```

Pass implementer exactly the slice context. Do NOT pass full HANDOFF.md — pass only:
- The slice objectives
- Relevant file paths (not content)
- Acceptance criteria
- RESUME.json checkpoint

---

## 2b. Multi-Agent Expert-Team Debate (STANDARD for PRD / plan / decision creation)

CORRECT pattern (supersedes assigning a DIFFERENT role per agent — that conflates
angle-diversity with model-diversity and under-covers each angle):

**Every agent plays the SAME expert-team baseline per PASS. Run MULTIPLE passes to
cover the different angles.**

- **angle-diversity → passes.** Each pass = ONE expert-team baseline chosen for the
  goal/task/domain (kernel roles from role-matrix + domain expertise), e.g.
  pass1=[architect+security], pass2=[implementer+systems], pass3=[reviewer+product].
- **model-diversity → agents.** Within a pass, Claude + local(Qwen) + Codex + Gemini
  ALL reason through the SAME baseline, so disagreement reflects genuine model
  reasoning, not role framing.
- Multiple same-baseline passes cover EVERY angle with EVERY model — which is what the
  old AgentType→one-role SSOT tried to approximate with per-agent roles, but couldn't.

Mechanism (per pass, via aq-collaborate):
1. orchestrator picks the pass's expert-team baseline.
2. each agent votes: `aq-collaborate review <angle-item> --agent <model>-<baseline> --verdict approve|reject --score S --feedback "..."`
3. `aq-collaborate decide <angle-item>` → weighted consensus for that angle.
4. next pass = next baseline; aggregate the passes' consensuses into the final call.

ANTI-PATTERN (do NOT): one pass where each agent gets a different role. You then
cannot tell a role artifact from a real disagreement, and only one model sees each angle.

### Engage ALL available agents (standing requirement)

Every phase — grounding, research, PRD, plans, collaborations, integrations,
validations — engages ALL available agents, not just the orchestrator. The roster is
dynamic (the local model changes; currently Qwen). Invocation paths:
- **claude** — orchestrator + participant (direct).
- **local** (currently Qwen) — `delegate-to-local --mode agent` (headless, live).
- **codex** — `delegate-to-codex --prompt` (headless CLI, live).
- **gemini** — NO headless lane (switchboard remote credential unavailable under
  current constraints); engages via file/git A2A: post the pass to `aq-collaborate` +
  PULSE.log, the Antigravity IDE agent reads + submits its vote/contribution async.

Aggregation point = `aq-collaborate` (each agent submits a `review` per pass; `decide`
computes consensus once all available agents have voted). Do not proceed on a partial
roster unless an agent is genuinely unavailable — record which agents participated.

---

## 3. RESUME.json Schema (exact format)

```json
{
  "current_objective": "One sentence: what are we building right now",
  "phase": "Phase 86",
  "todo_snapshot": [
    "done: slice 1 — attention_queue.py",
    "in-progress: slice 2 — aq-alerts CLI",
    "pending: slice 3 — dashboard endpoint",
    "pending: slice 4 — NixOS shell hook"
  ],
  "uncommitted_changes": [
    "scripts/ai/lib/attention_queue.py",
    "scripts/ai/aq-alerts"
  ],
  "resume_hint": "Next: implement dashboard /api/aistack/alerts/status route in aistack.py"
}
```

**Write RESUME.json**: when starting a new user task AND after each completed todo item.
This is the compaction anchor — it must survive a 401 summarization failure.

---

## 4. Handoff Protocol

When transferring work to another agent:
```
1. Update RESUME.json with current state
2. Append to PULSE.log: [ISO-timestamp] [agent] [handoff]: scope — target agent + objective
3. Write HANDOFF.md entry with:
   - What was completed (with commit hash)
   - What's in-progress (file + line)
   - What's pending (next slice)
   - Any blockers discovered
4. Pass HANDOFF.md path to receiving agent (not content — they read it)
```

Task completion signal (from sub-agent to orchestrator):
```
1. Update PULSE.log: [timestamp] [agent] [complete]: slice-name — outcome
2. Update RESUME.json: mark todo item as done, update resume_hint
3. If committing: run tier0 gate first
4. Output summary: "VERDICT: PASS|FAIL — [brief outcome]" as last line
```

---

## 5. File Drop Protocol (.agents/drops/)

Drop file format for async task queuing:
```yaml
# .agents/drops/<id>.drop.yaml
title: "Task title (no injection chars)"
body: "Task description — no $(), backticks, or && allowed"
severity: medium           # critical|high|medium|low
agent: gemini              # optional: preferred agent
human_gate: false          # true = require human approval before execution
rebuild_required: false    # true = task requires nixos-rebuild after completion
```

Security: DropSpec rejects `$(`, `` ` ``, `&&` in title/body. Use plain text only.

---

## 6. Context Slicing for Sub-Agents

**Rule**: Sub-agents get slice-relevant context only. Never pass full session history.

What to include per slice:
```
- slice_objective (1-2 sentences)
- relevant_files (paths only, not content — agent reads them)
- acceptance_criteria (explicit pass/fail conditions)
- constraints (ports, security rules, existing patterns to follow)
- reference_skills (list skill names to load, e.g., ["apparmor-rules", "nixos-system"])
```

What NOT to include:
- Full HANDOFF.md (link to it, don't inline it)
- Previous agent outputs
- Unrelated file contents
- Full AGENTS.md (reference specific sections)

---

## 7. Conflict Resolution

When parallel implementers produce conflicting output:
1. Orchestrator reviews both against acceptance criteria
2. Winning implementation is selected (not merged — one wins)
3. Losing agent's patterns/insights are captured in HANDOFF.md
4. Conflict fact is logged to memory/facts: `fact_type: "conflict_resolution"`
