# Capability Intake Review: semgrep-mcp, osv-scanner, trivy, syft-grype

Reference skills: `capability-intake`, `security-scanner`, `flake-review`

## Audit Verdict: PASS

### Evidence:
1. Validated versions: `osv-scanner` 2.2.4, `trivy` 0.66.0, `syft` 1.38.0, `grype` 0.104.1. All are Nix-provided.
2. Dynamic external connections are restricted to explicit vulnerability database updates.
3. Output files are quarantined in `.reports/security/` and ignored by Git.

### Follow-up Patch Scope:
1. Configure automatic regex-based redaction filters in the wrapper scripts to scrub any API keys or environment secrets before compiling vulnerability scanner reports.

## Resolution (2026-07-23) — DEFERRED (verdict unchanged, PASS stands)

Not addressed in this cycle — out of scope for the capability-intake security revision (which covered the
`mcp-admission-controller` and `github-mcp-readonly` findings only). This is a non-critical hardening
enhancement on an already-PASSing finding; the underlying PASS verdict is unaffected. No security regression
from deferral.
