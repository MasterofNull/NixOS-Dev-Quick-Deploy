# Agent work durability S0a: Claude Code temp root off tmpfs 2026-11-19

Date: 2026-11-19
Task ID: HF-20261119-003

## Objective
Stop losing subagent transcripts and task outputs on reboot. Root cause: Claude Code defaults its temp root to `os.tmpdir()`, which is `/tmp`, and `/tmp` is tmpfs here. S0a points `CLAUDE_CODE_TMPDIR` at `${xdg.stateHome}/claude-code/tmp` and creates the directories at 0700. Plan: `.agents/plans/agent-work-durability-20261119/DESIGN.md` (S0, Revision 1 F3/F4/F10, Revision 2).

## Workflow/Session IDs
Session Simurg@claude/sonnet-5.5 (slice S0a); plan agent-work-durability-20261119; branch feat/agent-work-durability.

## Delegation Decision
Bounded single-slice Nix change delegated by the orchestrator to a Sonnet implementer (Rule 17). Review is by a different lane at PR time.

## Commands Executed
- `nix eval --json .#homeConfigurations.hyperd.config.home.sessionVariables.CLAUDE_CODE_TMPDIR`
- `nix eval --json .#homeConfigurations.hyperd.config.systemd.user.sessionVariables.CLAUDE_CODE_TMPDIR`
- `nix eval --json .#homeConfigurations.hyperd.config.systemd.user.tmpfiles.rules`
- `python3 scripts/testing/test-claude-tmpdir-durable.py`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
- Both variables evaluate to `/home/hyperd/.local/state/claude-code/tmp` (no hardwired path in source; it derives from `config.xdg.stateHome`).
- tmpfiles rules: `d` entries at 0700 for `claude-code`, `claude-code/tmp` and `claude-code/archive`, with no age field (F3: retention must archive before removing, so tmpfiles never deletes).
- Regression test `scripts/testing/test-claude-tmpdir-durable.py` prints `PASS test-claude-tmpdir-durable`; it skips cleanly when `nix` is unavailable (`REQUIRE_NIX_EVAL=1` makes the skip a failure). Registered in `config/ci-checks.json` tests-misc-a-c.
- Not yet validated live: J1 (a new session after the home-manager switch writes under the new directory, and it survives a reboot).

## Rollback Plan
Remove the `CLAUDE_CODE_TMPDIR` entries (both) and the tmpfiles rules from `nix/home/base.nix`, then run home-manager switch. New sessions fall back to `os.tmpdir()`. The created directories can stay.

## Residual Risk
- Owner step: `home-manager switch`. New Claude sessions then use the new directory. The running session keeps `/tmp`.
- Whether Claude Code also honours the variable from `~/.claude/settings.json` `env` is unverified and not relied on.
- No retention yet (S0b): the directory grows until the archiver and timer land. Directory and archive are 0700; they are outside the repo and must stay out of AIDB/RAG indexing.
- Home-manager `systemd.user.tmpfiles.rules` creates the directories when the user systemd manager applies tmpfiles (at switch or next login).

## Hint Feedback
No aq-hints were consulted for this slice. Design inputs came from the PRD.

## Activation attestation (Rule 15)
- Integrated: yes, `nix/home/base.nix` (home.sessionVariables, systemd.user.sessionVariables, systemd.user.tmpfiles.rules).
- Turned ON: after the owner's home-manager switch; evaluates to the new path now.
- Validated end-to-end: J1 after the switch (new session, subagent run, reboot, outputs still present). Eval and unit test only so far; deferred until the owner switch, 2026-11-19.
- Observable: `ls -ld ~/.local/state/claude-code/tmp` (mode drwx------) and `ls ~/.local/state/claude-code/tmp` after a subagent run.
- Intervenable: unset the variable (or remove it from base.nix) and new sessions use `/tmp` again.
- PM-tracked: `.agents/plans/agent-work-durability-20261119/tracker.json` item s0a-claude-tmpdir.
