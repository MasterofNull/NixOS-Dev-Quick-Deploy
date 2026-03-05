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

## Structure Contract (Agent-Facing)
- Keep command behavior specs in `.claude/commands/` only.
- Keep PRD/rules/workflow state in `.agent/` only.
- Keep phased plans in `.agents/plans/` only.
- Do not create new top-level files for workflow artifacts.
- Validate staged changes with:
```bash
scripts/governance/repo-structure-lint.sh --staged
```

## Project Layout Snapshot
```text
repo/
├── .agent/
│   ├── PROJECT-PRD.md
│   ├── GLOBAL-RULES.md
│   └── workflows/
├── .claude/
│   └── commands/
└── .agents/
    └── plans/
```

## Explore The Harness (quick)
```bash
scripts/ai/aqd workflows list
scripts/ai/aqd workflows primer --target . --objective "explore harness"
scripts/ai/aqd workflows brownfield --target . --objective "map current harness capabilities"
```
