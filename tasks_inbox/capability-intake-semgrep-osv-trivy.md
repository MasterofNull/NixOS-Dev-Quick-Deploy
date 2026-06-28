# Capability Intake Review: semgrep-mcp, osv-scanner, trivy, syft-grype

Reference skills: `capability-intake`, `security-scanner`, `flake-review`

Objective: Review the first-wave security scanner candidates and propose a consolidated import-security gate.

Required steps:
1. Run `scripts/ai/aq-capability-intake audit semgrep-mcp --json`.
2. Run `scripts/ai/aq-capability-intake audit osv-scanner --json`.
3. Run `scripts/ai/aq-capability-intake audit trivy --json`.
4. Run `scripts/ai/aq-capability-intake audit syft-grype --json`.
5. Inspect upstream install and release practices.
6. Recommend which scanner(s) should become mandatory for plugin import, which should remain optional, and where reports should live.
7. Specify redaction rules for secret-scan output.

Do not install or enable new scanners. Produce PASS/FAIL/REQUEST_REVISION with evidence and exact follow-up patch scope.
