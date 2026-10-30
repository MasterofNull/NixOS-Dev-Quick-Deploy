# Coordinator query-gaps.tmp permission denied

## Objective
Stop ai-hybrid-coordinator spamming `Permission denied /var/log/nixos-ai-stack/query-gaps.tmp` every 5 minutes.

## Workflow/Session IDs
Slice fix/coordinator-query-gaps-perms (worktree .agents/delegation/worktrees/query-gaps-perms). No session id recorded.

## Delegation Decision
Bounded single-slice fix, read-only live probes, implemented directly by the delegated sub-agent (Sonnet tier, per orchestrator dispatch).

## Commands Executed
- rg query-gaps ai-stack nix: writer is `sync_query_gaps_to_jsonl` (ai-stack/mcp-servers/hybrid-coordinator/extensions/interaction_tracker.py), called from the 300s `_gap_sync_loop` in server.py. It writes `query-gaps.tmp` then renames over `query-gaps.jsonl`, so it needs write+exec on the directory.
- systemctl show ai-hybrid-coordinator: User=ai-hybrid Group=ai-stack, ReadWritePaths includes /var/log/nixos-ai-stack, no LogsDirectory.
- stat /var/log/nixos-ai-stack: root:ai-stack 770 (live, now correct); query-gaps.jsonl ai-hybrid:ai-stack 644.
- journalctl -u ai-hybrid-coordinator: 144 `sync_query_gaps_failed` entries, last 2026-10-29 20:41:56; none since; 135 `gap_sync_complete` since 2026-10-29 20:42.
- rg nixos-ai-stack /etc/tmpfiles.d/00-nixos.conf: line 91 and 167 `z ... 0770 root ai-stack` (nix/modules/services/mcp-servers.nix), line 133 `z ... 0750 hyperd users` (nix/modules/core/base.nix:356).
- python3 -m pytest tests/test_query_gaps_sync_log_once.py

## Validation Evidence
- Root cause (Rules 13/14): base.nix declares the shared log dir 0750 hyperd:users (ai-hybrid is not in `users`, so DAC denies create of the .tmp; ReadWritePaths does not bypass that). mcp-servers.nix overrides with a later `z` 0770 root:ai-stack. Both land in the same tmpfiles file as duplicate `z` lines for one path; systemd-tmpfiles keeps the first, so the winning mode depended on rule order and whether the 0770 rule was deployed. The current deployed generation (tmpfiles file linked 2026-10-30 07:33) has the 0770 rule first and the dir is 770 root:ai-stack; live failures stopped after the 2026-10-29 20:41 rebuild.
- Declarative state is already correct; no Nix change made. The duplicate base.nix `z` line remains a latent ordering hazard (see Residual Risk).
- Code change: writer now logs `sync_query_gaps_failed` once per distinct error and logs `gap_sync_recovered` when it clears, so any future perms regression produces one line, not one per 5 minutes. Behavior otherwise unchanged (still returns 0, loop keeps running).
- pytest tests/test_query_gaps_sync_log_once.py: 1 passed (3 failing syncs on a read-only dir yield exactly 1 warning; then recovery after chmod returns 1 and logs recovered).
- Producer fix (Rule 19): nix/modules/core/base.nix no longer declares the log dir (neither the 0750 hyperd:users d/z pair nor the 0750 root:root program-path pair) when `roles.aiStack.enable`; nix/modules/services/mcp-servers.nix is the single owner (`d` + `z` 0770 root:ai-stack) and its duplicate second `z` (in the lib.mkAfter block) was removed. hyperd is in ai-stack (`id hyperd`), so hyperd-owned tools keep access.
- nix-instantiate --parse on both files: ok.
- nix eval of `systemd.tmpfiles.rules` filtered to the directory itself (children excluded): hyperd-ai-dev gives `d` and `z` lines only, both `0770 root ai-stack` (before the fix: five lines with three conflicting owner/modes). hyperd-minimal gives `d` and `z` `0750 hyperd users`, the unchanged non-AI-stack case.

## Rollback Plan
Revert nix/modules/core/base.nix and nix/modules/services/mcp-servers.nix (needs owner rebuild), and revert ai-stack/mcp-servers/hybrid-coordinator/extensions/interaction_tracker.py and delete tests/test_query_gaps_sync_log_once.py (archive per Rule 12). Needs coordinator restart (owner action) to take effect.

## Residual Risk
- The Nix change is validated by eval only; not rebuilt. After owner rebuild, expect /var/log/nixos-ai-stack unchanged at root:ai-stack 770. Only the log dir was de-duplicated; the optimizer dir keeps its base.nix rule.
- Takes effect after coordinator restart; not deployed.
- The `r query-gaps.tmp` tmpfiles rule only runs at boot/activation, harmless.

## Hint Feedback
No aq-hints consulted (hybrid-coordinator MCP unavailable in this session); wiki/graph not used.
