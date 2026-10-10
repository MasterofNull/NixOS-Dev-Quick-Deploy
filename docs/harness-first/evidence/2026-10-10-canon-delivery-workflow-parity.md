# Canonical delivery workflow for all lanes + Sonnet 5.5 balanced tier (2026-10-10)

## Why
Owner: "all agents/models should follow and use the same workflows … so other models/agents can resume,
complete, handoff, and share work … the last codex agent was not following our SOP's."

Audit of the five always-on agent files (AGENTS.md, CLAUDE.md, .agent/CODEX.md, .agent/GEMINI.md,
.agent/LOCAL-AGENT.md) + .agent/WORKFLOW-CANON.md:
- Canon blocks (rules, Fable parity, memory SOP, RSI SOP, MVP SOP, headless delegate) were in parity
  (`check-agent-instruction-parity.py` OK).
- The delivery mechanics — worktree per slice, never commit in the main checkout, `tier0 && commit`,
  PR-only, resumable trail, exact owner commands, no rebuild during DB jobs, enabled≠done, discover via
  capability index / knowledge graph — lived only in the Claude lane's private auto-memory. Codex never
  saw them, which is how a Codex session committed straight into the main checkout.
- None of the agent files named the discovery tools added this cycle (`aq-graph-query`,
  `aq-capability-index`, `aq-wiki --section`, `aq-rsi report`).
- `config/model-coordinator.json` balanced tier was `claude-sonnet-5`; Rule 17 named Haiku as the Claude
  implementer default, while Haiku repeatedly escaped its worktree / wrote vacuous tests this cycle.

## What changed
- New canon block `canon/blocks/delivery-workflow.md` (+ `.summary.md`), registered in `canon/canon.yaml`
  with the same targets as `mvp-delivery-sop` and compiled into all six files.
- Rule 17 (`canon/blocks/behavioral-rules.md`): Claude-lane default implementer = `sonnet` (Sonnet 5.5,
  balanced); `haiku` only for mechanical single-file edits with a checkable result. Codex/local still first
  when eligible.
- `config/model-coordinator.json` balanced → `claude-sonnet-5-5`; `aq-role-route` allowlist accepts it
  (old id kept for back-compat); `.agent/FABLE-PARITY-CONTRACT.md` wording.
- `scripts/ai/delegate-to-codex` preamble item 11 points delegated Codex runs at the delivery workflow.
- Budget held at 24000 bytes (not raised): lane regions condensed; every trimmed passage preserved verbatim
  in `.agent/lanes/{agents,claude,codex,local}-reference.md` under "moved from lane region".

## Validation
- `canon-compile.py --check`: OK, no drift. `check-agent-instruction-parity.py`: OK within budget.
- `test-agent-instruction-parity.py` 6 OK; `test-aq-canon-compiler.py` 13 OK;
  `test-delegate-claude-model-routing.py` 4 OK; `test-model-tiering-health.py`, `test-model-budget.py` pass.
- Sizes after (budget 24000): AGENTS 23606, CLAUDE 23973, CODEX 23956, LOCAL-AGENT 23992, GEMINI 22997.

## Not done / limits
- Agent files are within ~50 bytes of budget; the next canonical addition needs a structural change
  (e.g. move more lane detail to references) rather than more trimming.
- `delegate-to-antigravity` mentions worktrees but not PR/tier0; Antigravity reads its own file
  (.agent/GEMINI.md), which now carries the block. Local runs get it via LOCAL-AGENT.md; the local MICRO
  payload is behaviour-only and `config/local-agent-grounding.md` was not changed.
- Instruction text is not enforcement: main-checkout commits are still only caught by the nrs guard.
