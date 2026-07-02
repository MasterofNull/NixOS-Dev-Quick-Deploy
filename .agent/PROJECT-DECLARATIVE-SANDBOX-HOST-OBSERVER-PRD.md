# Declarative Sandbox Host Observer PRD

## Goal
Reduce sandbox-related false failures by routing host-state checks through declared observer surfaces before broadening agent permissions.

## Scope
- Add shared QA helper semantics for sandbox-denied probes.
- Use the dashboard `/api/health/services/all` surface as the host observer for phase-0 service state.
- Keep direct `systemctl` checks when available; fall back only when the current sandbox denies systemd access.
- Preserve real failures when both direct and observer checks report unhealthy state.

## Out of Scope
- Broad filesystem or system bus access grants for interactive agents.
- Replacing every `systemctl`, `ss`, and `journalctl` probe in one slice.
- NixOS service rewiring unless validation shows the observer surface lacks required permissions.

## Acceptance
- Unit coverage proves sandbox-denied text classification and observer service extraction.
- `aq-qa 0 --json` no longer reports service-state skips solely because direct systemd is denied when the dashboard observer has live data.
- Tier0 passes with the changed files.
