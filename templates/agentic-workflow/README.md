# Agentic Workflow Templates

Source-of-truth templates used by:
- `scripts/ai/aqd workflows project-init`
- `scripts/ai/aqd workflows retrofit`

Design goals:
- KISS always-read core
- progressive disclosure for deep context
- command-oriented workflow structure
- strict file placement contract for agent artifacts
- delegation-first orchestration with explicit non-orchestrator sub-agent rules

Template tokens:
- `@PROJECT_NAME@`
- `@GOAL@`
- `@STACK@`
- `@OWNER@`

Generated layout contract:
- `.agent/` for PRD, rules, workflow evidence
- `.claude/commands/` for slash-command specs
- `.agents/plans/` for phased plans
- `.vscode/tasks.json` for ready-to-run harness/hints workflow tasks
