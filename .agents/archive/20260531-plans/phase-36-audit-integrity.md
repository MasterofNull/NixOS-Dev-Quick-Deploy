# Phase 36: Security Hardening — Audit Log Integrity & Permissions

## Objective
Enforce strict audit log ownership and implement integrity checks as part of the Hospital/Classified security baseline. This slice addresses findings from the recent `aq-report` and `Permission denied` crashes.

## Scope Lock
- **In Scope**: `scripts/security/hospital-classified-gate.sh`, `nix/modules/services/mcp-servers.nix`, `nix/modules/roles/ai-stack.nix`.
- **Out of Scope**: Changing log formats, implementing remote log shipping.

## Workstreams
1. **Permission Hardening**: Refactor Nix configuration to ensure `/var/log/nixos-ai-stack` and its contents are owned by the `ai-stack` group with appropriate service-level write access.
2. **Integrity Check Implementation**: Create a script to verify that audit logs are active, recently updated, and have not been truncated or tampered with.
3. **Gate Integration**: Add the audit integrity check as a mandatory block in the `hospital-classified-gate.sh`.

## Step Plan
1. **[ ] Audit Current Permissions**:
   - Check `/var/log/nixos-ai-stack` ownership.
2. **[ ] Update Nix Module**:
   - Ensure the directory is managed declaratively with the correct group.
   - Adjust `commonServiceConfig` to handle log permissions correctly.
3. **[ ] Create `scripts/security/check-audit-integrity.sh`**:
   - Check if `tool-audit.jsonl` exists.
   - Verify last modification time is within a reasonable window (e.g., last 24h).
   - Check for log continuity (no sudden size drops suggesting truncation).
4. **[ ] Integrate into Gate**:
   - Add a call to `check-audit-integrity.sh` in `hospital-classified-gate.sh`.
5. **[ ] Validation**:
   - Run `deploy system`.
   - Run `scripts/security/hospital-classified-gate.sh`.

## Acceptance Criteria
- `hospital-classified-gate.sh` passes the "Audit Integrity" check.
- All AI services start without `Permission denied` errors on log/telemetry files.
- Audit logs are owned by `root:ai-stack` (or similar service-scoped group).

## Rollback
- Revert Nix changes and run `deploy system`.
