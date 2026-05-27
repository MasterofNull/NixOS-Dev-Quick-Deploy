# Skill: security-audit

- **Purpose**: Automate the identification of security vulnerabilities, insecure coding patterns, and compliance regressions in the codebase.
- **Variables**:
  - `target_path`: The file or directory path to scan.
- **Instructions**:
  - Rule 1: Use `scripts/security/security-audit.sh` for comprehensive scans.
  - Rule 2: Prioritize High/Critical CVEs and AppArmor policy violations.
  - Rule 3: Only suggest actionable fixes; do not just report vulnerabilities.
- **Workflow**:
  1. Initialize target environment.
  2. Run security scanner.
  3. Analyze report for High/Critical findings.
  4. Compare findings against known allowlist in `.gitleaks.toml`.
  5. Generate remediation plan.
- **Report**: A JSON security report and a list of actionable remediation steps or JIRA/task tickets.
