# Port Management Procedures

## Source of Truth

Use these declarative sources:
- `nix/modules/core/options.nix` (`mySystem.ports.*`)
- `config/settings.sh` (script-facing defaults)
- `config/service-endpoints.sh` (URL derivation from ports)

Do not hardcode service ports in runtime code.

## Validation

Run:
```bash
scripts/testing/validate-config-settings.sh
scripts/testing/validate-runtime-declarative.sh
```

## Conflict Checks

- Ensure no duplicate assignments across active services.
- Confirm endpoint URLs derive from port variables, not literals.
- Use health checks after changes:
```bash
scripts/testing/check-mcp-health.sh
```
