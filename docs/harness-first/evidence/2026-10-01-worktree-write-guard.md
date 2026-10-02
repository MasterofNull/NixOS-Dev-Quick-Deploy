# Evidence — worktree write guard (2026-10-01)

## Objective
Close RSI incident 30f7979b: isolated-worktree sub-agents could edit the main checkout by absolute path (a backlog bookkeeping agent did).

## Root cause
Claude Code worktree isolation is cwd-only; Write/Edit (and lean-ctx ctx_edit) accept any absolute path.

## Change
`scripts/ai/aq-worktree-write-guard` (stdlib only) as a project PreToolUse hook (`.claude/settings.json`, matcher Write|Edit|MultiEdit|NotebookEdit|mcp__lean-ctx__ctx_edit). When cwd is inside `.claude/worktrees/<name>/`, targets are realpath-resolved and denied outside that worktree, except `/tmp/claude-*/` scratch and `~/.claude/projects/*/memory/`. Non-worktree sessions are unaffected. Malformed input fails open with a stderr log.

## Validation
test-worktree-write-guard 8/8 (in-worktree allow, main-checkout deny for all five tools, ../ traversal, symlink escape, scratch/memory allow, non-worktree allow, malformed input). Live: deny from a worktree cwd, allow from the main checkout.

## Limits
Shell writes (Bash/ctx_shell) are not covered by this hook; agent briefs still use cwd-relative paths only.

## Rollback
Remove the hooks block from `.claude/settings.json`.

## Agents
Implementer: Claude Sonnet (worktree). Review: Claude Opus.
