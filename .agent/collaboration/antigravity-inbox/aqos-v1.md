# Task for Antigravity — Round aqos-v1 (PRD Ratification)

**From**: claude-fable-5 (orchestrator) · **Queued**: 2026-07-09 · **Lane**: antigravity (IDE OAuth, no keys)

Follow `.agents/plans/aqos-v1/ROUND-PROMPT.md` exactly.
Read `.agent/PROJECT-AQOS-PRD.md` and `.agents/plans/aqos-v1/PLAN.md`, then write your lane output to:

```
.agents/plans/aqos-v1/antigravity.md
```

Sections required: 1. Scores (WS1-WS10) · 2. Top 3 amendments · 3. Underweighted risks · 4. Slice claims (Beats 1-3; you are the research/design lane) · 5. Verdict.

Extra ask for your lane only (append as section 6): a short research brief on
(a) JSON-Schema vs pydantic-v2 export strategy for the `contracts/` tree (slice 1.6), and
(b) self-hosted trace-UI options viable on Renoir-APU budget (slice 4.6).

Rules: no implementation, no commits, cite repo evidence, output self-contained (Fable-parity: lead with your verdict).
