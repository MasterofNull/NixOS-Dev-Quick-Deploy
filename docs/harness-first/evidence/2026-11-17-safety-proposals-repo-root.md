# Safety control layer proposals path anchored to REPO_ROOT

Date: 2026-11-17
Task ID: HF-20261117-SAFETY-PROPOSALS-ROOT

## Objective
- Resolve `PROPOSALS_DIR` in `ai-stack/mcp-servers/hybrid-coordinator/workflow/safety_control_layer.py` relative to `REPO_ROOT` (via `REPO_ROOT` env var or ancestor `CLAUDE.md` discovery) instead of the caller's arbitrary working directory.
- Delivered: `ai-stack/mcp-servers/hybrid-coordinator/workflow/safety_control_layer.py` and `scripts/testing/test-safety-proposals-repo-root.py`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@gemini/gemini-4-argon#78d98033; design input from local-20261114-093246-iswn6k

## Delegation Decision
- Design produced by local Qwen (`local-20261114-093246-iswn6k`); packaged in isolated worktree `.agents/delegation/worktrees/safety-proposals-repo-root` for independent review via `aq-land`.

## Commands Executed
```bash
python3 scripts/testing/test-safety-proposals-repo-root.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Root cause: `SafetyControlLayer.PROPOSALS_DIR` was defined as `Path(".agent/proposals")`, which resolved relative to the process `cwd` and wrote proposal artifacts outside the repository when invoked from another directory.
- Fix: Added `_resolve_repo_root()` checking `os.environ.get("REPO_ROOT")` first and walking parent directories for `CLAUDE.md` before falling back to `Path.cwd()`. Removed unused `hashlib` and `typing.List` imports.
- Tests: `scripts/testing/test-safety-proposals-repo-root.py` verifies both ancestor `CLAUDE.md` walk-up and `REPO_ROOT` env override (`2/2` pass).

## Rollback Plan
- `git revert <sha>`. Trigger: proposal files failing to write under `.agent/proposals`.

## Residual Risk
- If `REPO_ROOT` is set to a non-existent path and no ancestor contains `CLAUDE.md`, `_resolve_repo_root()` falls back to `Path.cwd()`.

## Hint Feedback
- `aq-hints` and `local-20261114-093246-iswn6k` design output pinpointed line 19 of `safety_control_layer.py`.
