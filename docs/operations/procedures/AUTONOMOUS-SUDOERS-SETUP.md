Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-09

# Autonomous Sudoers Setup

Purpose: enable unattended deploy, restart, and verification loops without sharing a sudo password or granting destructive root authority.

## Goal

Allow passwordless execution only for the narrow command set needed by the unattended improvement loop:
- `nixos-quick-deploy.sh`
- `nixos-rebuild`
- `systemctl`
- `journalctl`

Do not allow:
- `NOPASSWD: ALL`
- generic root shells
- destructive git commands
- arbitrary file deletion tools

## Recommended Template

Reference file:
- `templates/agentic-workflow/autonomous-ops-sudoers.example`

Copy it into sudoers safely:

```bash
sudo install -m 0440 templates/agentic-workflow/autonomous-ops-sudoers.example /etc/sudoers.d/nixos-quick-deploy-agent
sudo visudo -cf /etc/sudoers.d/nixos-quick-deploy-agent
```

## Expected Capability

After installation, unattended loops can run:

```bash
./nixos-quick-deploy.sh --host nixos --profile ai-dev
sudo systemctl restart ai-hybrid-coordinator.service
sudo journalctl -u ai-hybrid-coordinator.service -n 100 --no-pager
```

without prompting for a password in each new exec session.

## Scope Notes

The template is intentionally broad enough for deploy and verification loops, but still bounded:
- allows `systemctl` inspection and restart flows
- allows `nixos-rebuild`
- does not grant arbitrary shell execution

Agent policy still blocks:
- repo/system deletions without approval
- rollback execution without approval
- destructive git/history rewrite
- boot/disk destructive actions

## Validation

```bash
sudo -l
sudo -n /run/current-system/sw/bin/systemctl status ai-hybrid-coordinator.service --no-pager
sudo -n /run/current-system/sw/bin/journalctl -u ai-hybrid-coordinator.service -n 20 --no-pager
sudo -n /run/current-system/sw/bin/nixos-rebuild dry-run --flake .#nixos
```

## Rollback

Remove the sudoers drop-in:

```bash
sudo rm /etc/sudoers.d/nixos-quick-deploy-agent
sudo visudo -c
```

If deploy state is bad:

```bash
sudo nixos-rebuild switch --rollback
```
