# Evidence — delegate wrapper shell safety + transactional registry helpers (2026-10-01)

## Objective
Close backlog generated-background-shell-loses-errors-and-reparses-prompts (critical) for delegate-to-codex and delegate-to-gemini.

## Root cause
Background launch built a double-quoted `bash -c "..."` with raw `$prompt`/`$_prompt_brief`/`$id` (shell re-parse: injection + mangling) and ended `> /dev/null 2>&1 &` (launch errors lost); registry updates were inline heredoc `open(rf,'w')` rewrites with no lock.

## Change
`lib/codex-background-worker.sh` / `lib/gemini-background-worker.sh` receive all dynamic values as argv (`nohup bash <worker> ARGS -- "${cmd[@]}" >> "$output_file"`); `lib/registry-update.py set|append` (argv values) over new public `TaskRegistry.update_fields_atomic` / `append_row_atomic`, thin wrappers on the committed shared-lock + atomic-replace primitives. Integration fixes by the orchestrator: `_update_registry` no longer drops unparseable rows on rewrite (verbatim preservation); delegate-to-claude background launch logs to the task file and its worker appends instead of truncating; test-delegate-codex-quota-precheck no longer hardcodes 2026-07-25 (parser correctly resolves the NEXT Jul 25 — a date time bomb).
The implementer also rewrote task_registry.py and delegate-to-claude out of scope; those versions were not taken (already fixed in 8e142926 / d68e12de).

## Validation
test-delegate-wrapper-shell-safety (prompt with $(...), backticks, quotes, newlines reaches the stub byte-identical, nothing executed; launch errors kept; no truncation under concurrent reader; legacy lines kept; static checks); claude lifecycle/model-routing/payload-safety; antigravity stdio; headless budget; registry transactional/heartbeat; local-delegation-artifact; agent-ops-projection; worktree isolation; concurrent dispatch; codex shared-writable; quota-precheck 15/15.

## Rollback
Revert the commit.

## Agents
Implementer: Claude Sonnet (worktree). Integration/review: Claude Opus.
