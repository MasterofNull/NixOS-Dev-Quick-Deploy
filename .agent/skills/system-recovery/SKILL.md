# Skill: System Recovery

- **Purpose**: Autonomously diagnose and remediate system health failures detected by `aq-qa` or internal telemetry.
- **Variables**:
  - `alert_file`: Path to the JSON/log file containing the health failure details.
- **Instructions**:
  1. Read the `alert_file` to identify the failing service, check, or metric.
  2. Use `run_shell_command` with `journalctl -u <service> -n 50 --no-pager` to gather runtime logs.
  3. Formulate a remediation plan (e.g., restart service, rollback config, clear corrupted cache).
  4. If the fix requires a code change, use `replace` or `write_file` and trigger a `nixos-rebuild switch`.
  5. If the fix is operational, use `systemctl restart <service>`.
  6. Re-run `aq-qa 0` or the specific failing check to verify the remediation succeeded.
- **Workflow**:
  1. `read_file` (alert_file)
  2. `run_shell_command` (journalctl)
  3. Remediation actions (code or systemctl)
  4. `run_shell_command` (aq-qa to verify)
- **Report**: A post-mortem detailing the root cause, the applied fix, and the final verified health status.
