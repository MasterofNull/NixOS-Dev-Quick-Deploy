---
doc_type: prd
id: security-systems-prd
title: Security Systems Domain PRD
status: active
owner: AI Stack Maintainers
last_updated: "2026-05-31"
---

# Security Systems Domain — PRD

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-31

## Purpose

This PRD governs the security-systems capability domain on the NixOS AI stack.
It covers AppArmor policy management, audit trail integrity, credential isolation,
OWASP compliance gate, and agent-facing security automation.

## Capabilities

| Capability | Status | Owner |
|------------|--------|-------|
| AppArmor profile enforcement | Active | AI Stack Maintainers |
| AppArmor auto-fix agent | Active | Phase 80 |
| Audit log integrity (hybrid-events.jsonl) | Active | Phase 90 |
| Pre-commit OWASP gate (tier0) | Active | tier0-validation-gate.sh |
| Credential isolation (env vars, gitignore) | Active | Architecture constraint |
| Agent capability lifecycle registry | Active | config/capability-lifecycle-registry.json |

## Non-Goals

- Penetration testing / red-team exercises (separate domain)
- Network firewall rules (managed by NixOS networking options)
- Certificate management (delegated to systemd credentials)

## Architecture

Security enforcement uses a layered model:

1. **Compile-time**: Nix flake — no runtime `pip install`, reproducible store
2. **Boot-time**: AppArmor profiles loaded via `security.apparmor.policies`
3. **Commit-time**: tier0 gate — OWASP check, no hardcoded secrets/ports
4. **Runtime**: Audit trail in `.agents/telemetry/hybrid-events.jsonl`

## References

- `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md`
- `nix/modules/services/mcp-servers.nix` (AppArmor rules)
- `scripts/automation/apparmor-fix-agent.py`
- `scripts/governance/tier0-validation-gate.sh`
- `config/capability-lifecycle-registry.json`
- `AGENTS.md §Security Gate`
