# Credential Management Procedures

## Principle

- Load credentials from secret files/environment only.
- Never hardcode API keys, passwords, or tokens in code or docs.

## Secret Sources

Primary runtime location:
- `/run/secrets/*`

Common examples:
- `/run/secrets/hybrid_coordinator_api_key`
- `/run/secrets/aider_wrapper_api_key`
- `/run/secrets/postgres_password`

## Rotation and Validation

- Rotate credentials on compromise or periodic policy cadence.
- Validate key presence before runtime startup.
- Re-run smoke checks after rotation:
```bash
scripts/testing/check-mcp-health.sh
scripts/testing/check-api-auth-hardening.sh
```

## Auditing

- Use security workflow and reports for ongoing scanning.
- Ensure generated reports do not include secret plaintext.
