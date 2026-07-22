# Agent catch-up queue (model/agent-agnostic)

**Purpose:** durable record of agent inputs that were SOLICITED but MISSED because an agent was
unavailable, so a returning agent can fold in its input (confirmatory audit / additional findings /
post-commit follow-up) on the exact subject it missed — without ever blocking the pipeline while it
was down. Owner directive 2026-07-22 ("model/agent-agnostic factory + catch-up cache/queue").
Generalizes the former `CODEX-REVIEW-QUEUE.md` to ALL agents. SSOT principle:
`memory/feedback-agent-agnostic-roles-and-catchup.md`.

## How it works

- **Roles are agnostic.** Every role instance (orchestrator/architect/implementer/reviewer/binding-
  acceptance) is routed at dispatch time to whichever agent is available + eligible + independent +
  cheapest — never hardcoded to one agent. If the first-choice lane is down, the orchestrator routes
  to the next eligible lane, proceeds, and files a catch-up entry here for the down lane.
- **Catch-up, not block.** A slice does not wait for a specific agent. When an eligible agent is
  unavailable, its intended contribution is recorded here (subject + exact hashes/commit + role it
  would have filled). On return, that agent processes its catch-up entries: confirmatory audit of an
  already-committed slice, or additional findings that become a follow-up slice if they warrant it.
- **A commit made while an agent was down is not permanently unreviewed by it** — it's queued for that
  agent's catch-up (advisory/confirmatory unless it surfaces a real defect → follow-up).

## Entry format

| # | Slice / subject | Exact subject (hashes / commit) | Role the missed agent would fill | Missed agent(s) + why down | Status |
|---|---|---|---|---|---|

## Live entries

| # | Slice / subject | Exact subject | Missed role | Missed agent(s) | Status |
|---|-----------------|---------------|-------------|-----------------|--------|
| C1 | B3-C1 canon compiler (committed d1c8e55b/90a55e06) | commit `90a55e06`+`d1c8e55b` | confirmatory acceptance | Antigravity (Gemini) — design-only reviewed, no code confirm; local Qwen — slow | open — fold Gemini/local confirmatory audit on availability |
| C2 | L2B-B payload normalization (committed 99364942) + AM4 reconciliation (pending) | commit `99364942`; AM4 cand `e42fb548`… | confirmatory acceptance | Antigravity, local Qwen | open |
| C3 | VF-7 evidence collector (committed e5578e5c) | commit `e5578e5c` | confirmatory acceptance | Antigravity, local Qwen | open |

## Notes for a returning agent

- Verify each subject's on-disk/commit hashes against this queue before reviewing; a mismatch means
  the tree advanced — treat as a fresh confirmatory pass on the current bytes, not a stale replay.
- A confirmatory PASS closes the entry. A defect found post-commit opens a bounded follow-up slice
  (do NOT silently rewrite committed history).
- Superseded lane-specific note: the earlier `CODEX-REVIEW-QUEUE.md` is retained as history; Codex is
  now one eligible lane among several, not the sole acceptance authority.
