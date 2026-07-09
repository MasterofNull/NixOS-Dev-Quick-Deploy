# Task for Antigravity — Round rsi-readiness

**From**: claude-fable-5 (orchestrator) · **Queued**: 2026-07-09 · **Lane**: antigravity (IDE OAuth, no keys)

Follow `.agents/plans/rsi-readiness/ROUND-PROMPT.md` exactly.
Read `.agent/PROJECT-RSI-READINESS-PRD.md` (trust infrastructure for local agentic
self-improvement — 6 workstreams), then write your lane output to:

```
.agents/plans/rsi-readiness/antigravity.md
```

Sections: 1. Scores R1-R6 + verdict · 2. Top 3 amendments · 3. Underweighted risks
· 4. Slice claims + wiring plan (your lane = research/design: R1.1 golden-set
design, R4 efficacy-measurement methodology) · 5. Verdict + first commit target.

Extra for your lane (append as section 6): a research brief on eval-harness trust —
how do we know a scoring signal is trustworthy enough to gate automation? Cover
exec-based scoring, scorer-gaming detection, and inter-run variance bounds.

Rules: no implementation, no commits, cite repo evidence, lead with your verdict.

NOTE: this lane is consumption-based — the harness marks antigravity UNAVAILABLE
unless the IDE consumes (deletes) this file after acting. If you act on it, delete
it so the liveness signal reflects reality.
