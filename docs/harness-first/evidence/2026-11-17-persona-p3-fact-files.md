# Persona P3 Shared Fact-File Governance & Delegate Lane Attribution

Date: 2026-11-17
Task ID: HF-20261117-PERSONA-P3-FACT-FILES

## Objective
- Enforce Persona P3 shared fact-file schema, privacy/secret scanning, and cross-lane `owner_reply` attribution in `scripts/governance/tier0.d/check-fact-files.py`, list recent fact subjects at `aq-session-start`, and pin `AQ_INSTANCE_LANE` unconditionally in each `delegate-to-*` lane launcher.
- Delivered: `scripts/governance/tier0.d/check-fact-files.py`, `scripts/ai/lib/fact_subjects.py`, `scripts/ai/aq-session-start`, `scripts/ai/delegate-to-{claude,codex,gemini,local}`, `scripts/testing/test-persona-fact-files.py`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@gemini/gemini-4-argon#78d98033

## Delegation Decision
- Implemented and hardened in isolated worktree `.agents/delegation/worktrees/persona-p3` incorporating all Codex review findings through round 7.

## Commands Executed
```bash
FACT_CHECK_NO_FETCH=1 python3 scripts/testing/test-persona-fact-files.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Root causes addressed:
  1. `REPLY_LINE_RE` used `\s*` which could match across a newline onto `Co-Authored-By:` when `owner_reply:` was blank; fixed to `[ \t]*`.
  2. `_actor_lane` checked `new_fms` first and fell back to the validator's ambient `AQ_INSTANCE_LANE` even on committed units; fixed so committed units derive actor strictly from `instance:` message line or `Co-Authored-By:` trailer (`allow_env=(label == "staged")`).
  3. `delegate-to-{claude,codex,gemini,local}` now set `export AQ_INSTANCE_LANE="<lane>"` unconditionally so a parent lane's `AQ_INSTANCE_LANE` is never inherited by a child lane.
- Tests: `scripts/testing/test-persona-fact-files.py` (`48/48` pass, including conflicting inherited lane execution test and validator-lane invariance test for committed unattributed edits/deletes).

## Rollback Plan
- `git revert <sha>`. Trigger: false-positive pre-commit block on valid fact files.

## Residual Risk
- Interactive commits touching `.agent/memory/facts/*.md` without `Co-Authored-By:` or `instance:` lines must set `AQ_INSTANCE_LANE` at pre-commit time; once committed, branch commits must carry `Co-Authored-By:` or `instance:` when editing or deleting an existing fact.

## Hint Feedback
- Codex review handoff (`AGENT-CATCHUP-QUEUE.md:1361`) identified the committed-unit `AQ_INSTANCE_LANE` fallback and parent-lane inheritance edge cases.
