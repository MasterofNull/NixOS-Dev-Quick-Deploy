# .claude Layer

This directory follows a compact + progressive-disclosure model.

## Purpose
- Keep always-read context small.
- Store reusable command workflows under `.claude/commands/`.
- Link to deeper docs instead of embedding large policy text.

## In This Repo
- `../CLAUDE.md` is the always-read project core card.
- Generated project templates (via `aqd workflows project-init`) include:
  - `.claude/CLAUDE.md`
  - `.claude/commands/prime.md`
  - `.claude/commands/create-prd.md`
  - `.claude/commands/plan-feature.md`
  - `.claude/commands/execute.md`
  - `.claude/commands/commit.md`
  - `.claude/commands/explore-harness.md`

## Explore The Harness (quick)
```bash
scripts/ai/aqd workflows list
scripts/ai/aqd workflows primer --target . --objective "explore harness"
scripts/ai/aqd workflows brownfield --target . --objective "map current harness capabilities"
```
