# Configuration Validation Procedures

## Primary Validators

- Runtime/declarative wiring:
```bash
scripts/testing/validate-runtime-declarative.sh
```
- Config/settings validation:
```bash
scripts/testing/validate-config-settings.sh
```
- Quick deploy lint bundle:
```bash
scripts/quick-deploy-lint.sh --mode fast
```

## Validation During Deployment

Preflight should run before deploy/rebuild:
1. `quick-deploy-lint --mode fast`
2. `validate-runtime-declarative.sh`
3. `check-mcp-health.sh` (post-switch smoke)

## Validation Error Reporting

- Always capture command, exit code, and failing assertion.
- Include file path/module/option when available.
- Record remediation hint and rollback command.

Recommended format:
```text
[validator] FAIL <check-name>: <reason>
  file: <path>
  remediation: <action>
  rollback: <command>
```
