# Agent Collaboration & Handoff Rules (AC-1)

These rules ensure state continuity across multiple agents (Gemini, Codex, Qwen) and resilience against API rate limits or context resets.

## 0. The Atomic Resume (AR) — NEW
**Mandatory at the start of every session and every phase transition.**
- **Action:** Write/Update `.agent/collaboration/RESUME.json`.
- **Content:** `{"session_id": "...", "objective": "...", "phase": "...", "next_steps": ["..."], "last_update": "ISO-8601"}`
- **Purpose:** Surrounding Claude Code compaction failures (401/Lossy). Claude reads this file FIRST on every wake-up to reconstruct its brain state in 1 tool call.

## 1. The Intent Lock (IL)
**Mandatory before any multi-file edit or complex `replace`.**
- **Action:** Write the intended change set to `.agent/collaboration/PENDING.json`.
- **Content:** List of files, specific functions being touched, and the "Goal State".
- **Purpose:** If the agent "goes dark" (429 error), the successor knows exactly where the surgical incision was about to be made.

## 2. The Atomic Pulse (AP)
**Mandatory after every successful tool execution that modifies the state.**
- **Action:** Append a one-line entry to `.agent/collaboration/PULSE.log`.
- **Format:** `[TIMESTAMP] [AGENT_ID] [write/exec/commit]: <target> — <brief_summary>`
- **Purpose:** Provides a "Black Box" flight recorder. Teammates read the last 5 lines of this file to orient themselves instantly without scraping verbose session logs.

## 3. The Handoff Memo (HM)
**Mandatory when an agent finishes a slice or hits a non-fatal constraint.**
- **Action:** Write/Update `.agent/collaboration/HANDOFF.md`.
- **Content:**
  - **Status:** (Partial / Complete / Blocked)
  - **Last Action:** Exactly what was just finished.
  - **Next Step:** The immediate next tool call the successor should make.
  - **Context Bloat:** (Low / Med / High) - Signal to teammate if they should reset context.

## 4. The Rate-Limit Pivot (RLP)
If a `429` or `Invalid Content` error is detected:
1. **DO NOT** retry blindly.
2. **DO** attempt a 1-turn emergency write to `.agent/collaboration/RECOVERY.md`.
3. **DO** include the exact `old_string` and `new_string` that failed to commit.

---

## Tooling Integration
- **aq-resume:** Reads `RESUME.json` + `PULSE.log` + `HANDOFF.md` to reconstruct state.
- **aq-prime:** Must call `aq-resume` during initialization.
- **aq-session-stop:** Must verify `HANDOFF.md` and `RESUME.json` are current.
