# Collaborative Round — aqos-v1

Opened: 2026-07-09T11:42:40Z
Target artifact (if a review round): .agents/plans/aqos-v1

## Task
# Round: aqos-v1 — PRD Ratification & Slice Claiming

You are one expert lane in a 4-agent flat collaborative round (claude, codex, antigravity, local).

## Inputs (read in this order)
1. `.agent/PROJECT-AQOS-PRD.md` — the redesign PRD (workstreams WS1-WS10)
2. `.agents/plans/aqos-v1/PLAN.md` — beats, slices, delegation matrix
3. `.agent/FABLE-PARITY-CONTRACT.md` — behavioral contract you operate under

## Your task (bounded — produce ONE markdown file)
Write your lane output to `.agents/plans/aqos-v1/<your-lane>.md` with exactly these sections:

### 1. Scores
One line per workstream: `WS<n>: <1-10> — <one-sentence reason>`

### 2. Top 3 amendments
The three highest-impact changes/additions/deletions to the PRD, each with: what, why, which workstream.

### 3. Risks the PRD underweights
Max 3, one paragraph each.

### 4. Slice claims
Which PLAN.md slices you claim for your lane in Beats 1-3, honoring the delegation defaults and your measured capability envelope. One line per slice: `<slice-id>: <claim|pass> — <reason>`

### 5. Verdict
`RATIFY` / `RATIFY-WITH-AMENDMENTS` / `REJECT` + one sentence.

## Rules
- Ground every claim in the PRD/plan text or repo evidence — no invented features.
- Lead with the outcome; final answer self-contained (Fable-parity).
- Local lane: if budget-constrained, sections 1 and 5 are mandatory, 2-4 best-effort.
- Do NOT implement anything in this round. Do NOT commit. Orchestrator aggregates.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/aqos-v1.md` and writes `antigravity.md`. No API keys.
