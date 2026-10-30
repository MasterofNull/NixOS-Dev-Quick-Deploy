# Harness-First Task Evidence

Date: 2026-10-30
Task ID: HF-20261030-runtime-logs-out-of-flake

## Objective
- The 2026-10-30 deploy of 1e121747 was recorded as `-dirty` because tracked files that agents/services append to in the primary checkout make the git flake tree dirty.
- Findings:
  - (a) A `git+file` flake is dirty if any tracked file differs from HEAD; Nix then sets `dirtyRev` and `self.rev` is absent. Confirmed live: the same checkout gives `dirtyRevision: 1e121747...-dirty` for `git+file:///repo` and a clean `rev: 1e121747...` for `git+file:///repo?rev=<HEAD>`.
  - (b) A flake cannot exclude tracked files from dirtiness (no ignore mechanism); only untracked/gitignored files are invisible.
  - (c) PULSE.log is NOT the cause: it, RESUME.json, HANDOFF.md, PENDING.json and a2a spools are already gitignored (.gitignore ~l.179-182), so the 0.152.3 PULSE-format check, aq-resume etc. are untouched. The tracked, live-written files are: `.agent/memory/issues-backlog.md` (appended by the 15-min RSI sweep via `rsi_lifecycle._BACKLOG`, plus agents per Rule 11), `.agent/collaboration/rsi-incidents.json` (rewritten by `rsi_lifecycle`/`rsi_sweep`; read by prsi-orchestrator, approval_inbox, aq-rsi, aq-rsi-pending, delegate-to-antigravity, ai_coordination, prsi_handlers, and a systemd `PathChanged` unit in nix/modules/roles/ai-stack.nix:2554), `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` (agent-edited, reviewed content). `check-checkout-fresh.sh` already special-cases the backlog (pure-append reapply) and deliberately excludes rsi-incidents.json.
  - (d) `check-deploy-source.sh` `inert_re` treats `.agent/ .agents/ docs/ *.md` outside `nix/` as inert: dirty inert files only WARN, and `aq-deploy-current` skips them. The existing design therefore already intends that inert dirt must not block deploys. The gap is that the *recorded revision* still goes `-dirty`, so aq-deploy-current's step 8 verification (`!= *-dirty`) fails even though everything else passed.
- Options:
  1. Move rsi-incidents.json (and backlog appends) to a gitignored runtime dir. `RSI_RUNTIME_DIR` / `RSI_BACKLOG_FILE` / `PRSI_INCIDENTS_FILE` overrides exist, but about 8 readers hardcode the path, plus the nix PathChanged unit and tests; the backlog is reviewed content that Rule 11 requires to be tracked. Larger, touches nix, and risks Rule 16/canon edits. Not recommended as the first fix.
  2. (Chosen) Pin the deploy to committed HEAD: `--flake "git+file://$REPO?rev=$(git rev-parse HEAD)#..."` in aq-deploy-current. Works for any inert dirt, requires no data moves, and is safe because build-affecting dirt already STOPs earlier in the script.
- Follow-ups (not done): move rsi-incidents.json to a runtime dir only if the flake-pin approach proves insufficient; `nrs` (ad hoc `--flake .`) still records dirty and should be pointed at aq-deploy-current; the check-deploy-source.sh WARN text ("flake will record dirtyRev") is now only true for non-aq-deploy-current paths.

## Workflow/Session IDs
- Worktree: .agents/delegation/worktrees/runtime-logs-out-of-flake, branch chore/flake-source-runtime-logs. Session ID: n/a (delegated Claude sub-agent).

## Delegation Decision
- Bounded investigation plus a ~15-line script change by a Sonnet sub-agent; no canon or agent instruction files touched (no Rule 16 parity needed).

## Commands Executed
```bash
git status -s --untracked-files=no
git ls-files / git check-ignore -v (PULSE.log, RESUME.json)
nix flake metadata --json "git+file://<repo>?rev=<HEAD>"   # clean rev
nix flake metadata --json "git+file://<repo>"              # dirtyRevision
bash -n scripts/maintenance/aq-deploy-current
```

## Validation Evidence
- Metadata probe on the dirty primary checkout: unpinned ref reports `1e121747...-dirty`; `?rev=HEAD` ref reports locked `rev` 1e121747 with no dirty suffix.
- `bash -n` passes. No rebuild was run (out of scope); the real proof is the next owner run of `scripts/maintenance/aq-deploy-current`, whose step 8 should now print PASS.

## Rollback Plan
- Revert the aq-deploy-current change; deploys return to `--flake .`.

## Residual Risk
- `?rev=` builds the committed tree, so a deliberately dirty build-affecting file would be ignored; but the script STOPs on those before this point. Working-tree-backed services (repoPath) still read the live checkout regardless.
- Quoting assumes no `?`/`#` in the repo path.

## Hint Feedback
- None.
