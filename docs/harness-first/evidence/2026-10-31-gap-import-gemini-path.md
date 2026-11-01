# Evidence: ai-gap-import stale gemini CLI preflight

## Objective
Fix ai-gap-import.service failing with "gemini CLI not found in PATH" (live 2026-10-31 11:08).

## Workflow/Session IDs
Bounded fix slice, branch fix/gap-import-gemini-path, worktree .agents/delegation/worktrees/gap-import-path. No workflow run ID.

## Delegation Decision
Implemented directly by the delegated Claude Sonnet sub-agent (assigned slice, single-file change). No further delegation.

## Commands Executed
- rg -n 'gap-import' nix/ -> unit at nix/modules/roles/ai-stack.nix (ai-gap-import, ExecStart scripts/ai/aq-gap-import)
- rg gemini in scripts/ai/aq-gap-import and scripts/ai/aq-knowledge-import.sh
- journalctl -u ai-gap-import --no-pager -n 8; systemctl show ai-gap-import -p Environment -p OnFailure
- bash -n scripts/ai/aq-gap-import
- env -i PATH=/run/current-system/sw/bin HOME=/home/hyperd GAPS_JSONL=<empty file> bash scripts/ai/aq-gap-import

## Validation Evidence
Root cause: scripts/ai/aq-gap-import carried a preflight `command -v gemini` (plus `PATH=$HOME/.npm-global/bin`) left from the retired npm gemini-cli. The job never executes a gemini binary: content generation goes aq-gap-import -> aq-knowledge-import.sh -> scripts/ai/delegate-to-antigravity (HTTP via switchboard / inbox). The unit PATH (Nix store tools only) cannot contain a user-installed CLI, so the stale check always failed.
Because the CLI is not a dependency, no Nix option or PATH change is needed; adding a gemini path option would create a dead second source. nix/ is unchanged, so no nix eval applies.
Fix: replaced the gemini preflight with a check that delegate-to-antigravity is executable (the real dependency); removed the npm-global PATH export; corrected the header comment; added exit 1 when every selected gap import fails (previously the job would exit 0 with 0 imported, a silent green).
Results: bash -n ok. Run with a minimal PATH lacking any gemini binary and an empty gaps file: "INFO No gaps with occurrences >= 3 - nothing to import", rc=0 (preflight passed).
Design decision: the job is not made "skip when gemini unavailable" because gemini is not used; real generation failures still fail the unit.
Alerting: ai-gap-import has no OnFailure= handler (systemctl show), so failure surfaces only as a failed unit; not changed in this slice.

## Rollback Plan
git checkout -- scripts/ai/aq-gap-import (or revert the commit). No Nix or runtime state changed.

## Residual Risk
- With the preflight gone, the first live run exercises delegate-to-antigravity for real; its header states the keyed switchboard route is non-functional under the no-API-key policy and falls back to local Qwen, so per-topic imports may fail or be slow (90s timeout in aq-knowledge-import.sh). The new all-failed exit 1 will then fail the unit honestly. Whether this job should use aq-collab-round or local Qwen is a separate design question.
- Script is read from the repo checkout (repoPath), so it takes effect without rebuild once merged and checked out; a rebuild is not required.
- No OnFailure alerting on the unit.

## Hint Feedback
No aq-hints consulted; discovery done via rg and journal. A hint pointing at "consumers of retired npm gemini-cli" would have located this immediately.
