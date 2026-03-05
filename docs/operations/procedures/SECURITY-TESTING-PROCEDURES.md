# Security Testing Procedures
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


## Automated Security Suite

Run:
```bash
scripts/security/run-security-penetration-suite.sh
```

Artifacts:
- `artifacts/security-tests/latest.json`
- `artifacts/security-tests/latest.md`
- per-step logs in `artifacts/security-tests/*.log`

## Included Checks

- API authentication hardening
- Harness chaos smoke (input and workflow guardrails)
- PRSI high-risk approval rubric
- PRSI quarantine workflow
- npm security monitor smoke checks

## Required Follow-up

- Any failing step blocks release promotion.
- Open issues with log evidence and remediation owner.
- Re-run the suite after fixes and attach updated report artifacts.
