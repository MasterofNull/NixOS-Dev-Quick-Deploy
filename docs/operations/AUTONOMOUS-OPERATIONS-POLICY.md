Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-09

# Autonomous Operations Policy

Purpose: allow long unattended improvement loops while keeping destructive actions approval-gated.

## Default Autonomy

Agents may proceed without pausing the user for:
- non-destructive repo edits
- tests, lint, QA, and health checks
- `nixos-quick-deploy.sh` runs
- service restarts and status inspection
- log inspection, diagnostics, and runtime verification
- non-destructive commits

## Approval-Gated Actions

Agents must stop for explicit approval before:
- deleting repo files or directories
- removing system packages or services
- destructive git operations
  - `git reset --hard`
  - force-push
  - branch deletion
  - history rewrite
- rollback execution
- disk, bootloader, partition, or filesystem-destructive actions
- credential/account actions outside local secret storage

## Sudo Model

Recommended mode:
1. user authenticates `sudo` in the current terminal session
2. agent runs bounded deploy, restart, verification, and diagnostics loops
3. agent still treats destructive actions as approval-gated even if `sudo` is available

Not recommended:
- blanket unrestricted destructive root access
- passwordless deletion authority

## Stop Conditions

Agents must stop and ask the user when:
- a requested change implies deletion or irreversible removal
- runtime behavior is ambiguous and multiple architectural choices are plausible
- an external provider/account decision is required
- rollback is the safest next step
- the system enters a degraded boot, shutdown, or repeated restart state

## Required Handoff

For each unattended slice, report:
- files changed
- commands run
- tests run
- evidence output
- rollback note

## Safe Rollback References

System:
```bash
sudo nixos-rebuild switch --rollback
```

Deploy:
```bash
sudo systemctl status ai-hybrid-coordinator.service
sudo journalctl -u ai-hybrid-coordinator.service -n 100 --no-pager
```

Repo:
- use `git revert <commit>` for accepted commits instead of destructive history edits
