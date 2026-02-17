# Configuration Reference

This document is the source of truth for deployment configuration in the clean flake-first path.

## Configuration Surfaces

- `config/settings.sh`: centralized runtime settings (timeouts, retries, ports, namespaces, paths).
- `config/defaults.sh`: deploy defaults and baseline behavior flags.
- `config/variables.sh`: additional script-scoped variables used by phased deploy flow.
- `nix/hosts/<host>/facts.nix`: declarative host facts discovered by `scripts/discover-system-facts.sh`.
- `nix/modules/core/options.nix`: typed schema for `mySystem.*` options consumed by NixOS modules.

## Common Parameters

### Runtime and Retry

- `KUBECTL_TIMEOUT`
- `CURL_TIMEOUT`
- `NIXOS_REBUILD_TIMEOUT`
- `MAX_RETRY_ATTEMPTS`
- `RETRY_BASE_DELAY`

### Namespaces and Paths

- `AI_STACK_NAMESPACE`
- `BACKUPS_NAMESPACE`
- `LOGGING_NAMESPACE`
- `AI_STACK_CONFIG_DIR`
- `AI_STACK_ENV_FILE`

### Service Ports

- `AIDB_PORT`
- `HYBRID_COORDINATOR_PORT`
- `EMBEDDINGS_PORT`
- `QDRANT_PORT`
- `POSTGRES_PORT`
- `REDIS_PORT`

## Example Overrides

Use one-off overrides:

```bash
AI_STACK_NAMESPACE=ai-stack-dev KUBECTL_TIMEOUT=90 ./nixos-quick-deploy.sh
```

Or validate a custom env file before deploy:

```bash
./scripts/validate-config-settings.sh --env-file ./my-overrides.env
```

## Best Practices

- Keep all runtime overrides in environment files, not inline edits across multiple scripts.
- Change ports only through `config/settings.sh` or explicit env overrides.
- Keep host hardware and profile facts in `nix/hosts/<host>/facts.nix`.
- Run config validation before deploy and in CI.

## Troubleshooting

### Validation fails with namespace errors

- Symptom: invalid namespace message.
- Fix: use RFC1123-compatible values (`lowercase`, `digits`, `-` only, max 63 chars).

### Validation fails with port range errors

- Symptom: port must be `1-65535`.
- Fix: adjust out-of-range overrides in env file or shell exports.

### Validation fails on path settings

- Symptom: invalid path for `AI_STACK_CONFIG_DIR` or `AI_STACK_ENV_FILE`.
- Fix: remove shell metacharacters and path traversal segments (`..`), then re-run validation.

### Drift between expected and actual package counts

- Symptom: CI fails in package count drift check.
- Fix:
  1. Review flake/module changes.
  2. Regenerate baseline:
     `./scripts/check-package-count-drift.sh --write-baseline`
  3. Commit updated `config/package-count-baseline.json` with rationale.
