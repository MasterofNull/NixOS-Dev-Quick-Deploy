# Legacy Systemd Templates (Archived)

These templates were moved out of `templates/systemd/` during the Phase 26.6.2
placeholder-pruning audit.

Reason:
- They are no longer part of active deploy/render paths.
- Keeping them under `templates/` inflated placeholder-lint surface area.
- Active workflows use direct scripts/modules instead (for example,
  `scripts/setup-claude-proxy.sh` writes the service file directly).

Files retained for reference:
- `ai-stack-cleanup.service`
- `ai-stack-runtime-recovery.service`
- `ai-stack-resume-recovery.sh`
- `claude-api-proxy.service`
