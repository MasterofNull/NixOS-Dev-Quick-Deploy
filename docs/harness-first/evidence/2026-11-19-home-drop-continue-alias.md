# Home: drop the `continue` shell alias (shadowed the shell keyword)

## Objective
Stop interactive shell loops from launching the Continue CLI. While syncing the delegation worktrees,
the owner ran a `for` loop that used `[ -n "$b" ] || continue`. Every directory without a branch
started the interactive Continue CLI (`cn`, v1.5.45) instead of skipping to the next entry.

## Workflow/Session IDs
- Claude Code session 0b56dbd9 (Simurg@claude/opus-5.5), branch `fix/home-drop-continue-alias`.
- Backlog: `GIT-LOOP-LAUNCHED-CONTINUE-CLI` in `.agent/memory/issues-backlog.md`.

## Delegation Decision
Done by the orchestrator: a one-line declarative change, diagnosed in the same session from the
owner's terminal output.

## Commands Executed
- Owner ran: `git config --show-origin --get-all core.editor; echo $GIT_EDITOR $EDITOR $VISUAL; type git; type cn`. Result: no core.editor, EDITOR/VISUAL=micro, `git` is the Nix profile binary, `cn` is `~/.npm-global/bin/cn`. That ruled out editor and git-wrapper causes.
- Searched the repo for cn invocations: `.githooks/post-merge` and `post-checkout` do not call it. The only reference is `nix/home/base.nix` `shellAliases.continue = "cn"`.

## Validation Evidence
Root cause: zsh expands aliases on command words in interactive shells, and `continue` (a shell
keyword) was aliased to `cn`. The `|| continue` in the loop expanded to `|| cn` exactly on the
non-worktree directories, which matches every `cn` launch in the owner's output. Fix: remove the
alias. The Continue CLI stays available as `cn`. Applies at the next home-manager switch
(`aq-deploy-current`). In an already-open shell, `unalias continue` clears it now.

## Rollback Plan
Revert this commit and re-run home-manager.

## Residual Risk
Anyone who typed `continue` to start the CLI must now type `cn`. No other alias in `shellAliases`
shadows a shell keyword or builtin (checked by eye: ls/git/rebuild/agentic tool shortcuts).

## Hint Feedback
Do not alias shell keywords or builtins (`continue`, `break`, `return`, `exit`, `test`, `cd`). A small
lint in tier0 over `shellAliases` names could guard this.
