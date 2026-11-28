# Harness-First Task Evidence: agent hygiene rules and append-only merges

Date: 2026-11-26
Task ID: HF-20261126-AGENT-HYGIENE

## Objective
- Close recurring failures IMPLEMENTER-RG-MISSES-HIDDEN-DIRS, SUBAGENT-BARE-GIT-STASH, ORCH-PKILL-SELF-MATCH and MAIN-CHECKOUT-AUTOSTASH-POP-CONFLICT with canon rules and a union-merge attribute for append-only logs.

## Workflow/Session IDs
- Headless fix slice, worktree branch worktree-agent-a83497019ae693bee; changes staged, not committed.

## Delegation Decision
- Single bounded slice (docs, canon, one hook message); no further delegation.

## Commands Executed
- Edited `canon/blocks/headless-delegate-mode.md` and `.summary.md`; ran `canon-compile.py --write` (6 files updated: AGENTS.md, .claude/CLAUDE.md, .agent/{CODEX,GEMINI,LOCAL-AGENT,WORKFLOW-CANON}.md).
- Added hygiene section to `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`.
- Added `.agent/.gitattributes` (not at the repo root: root-file hygiene allowlist) with `merge=union` for PULSE.log, issues-backlog.md, AGENT-CATCHUP-QUEUE.md.
- Autostash producer: `.githooks/pre-push` (behind-upstream message) and `.githooks/README.md` both instructed `git pull --rebase --autostash`; changed to plain `git pull --rebase`. Autostash pop conflicts on append-only files in the main checkout came from that advice.

## Validation Evidence
- `canon-compile.py --check`: OK: no canon drift.
- `check-agent-instruction-parity.py`: OK, all required canon blocks within budget.
- `check-cross-surface-contract.py`: PASS.
- `repo-structure-lint.sh --staged`: PASS.
- No existing test home for `.agent/.gitattributes` content; no check added.

## Rollback Plan
- Revert the commit; `.agent/.gitattributes` removal restores default text merge.

## Residual Risk
- `merge=union` can duplicate lines if both sides edit an existing line; fine for append-only files. Advice is textual; nothing machine-enforces it yet. Other autostash users (user-local git config rebase.autostash) are outside the repo.

## Hint Feedback
- None recorded (headless).
