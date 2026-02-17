# Config Directory Reference

This directory contains runtime and deployment configuration inputs.

## Core Files

- `settings.sh`: centralized runtime settings (timeouts, retries, ports, namespaces, paths).
- `defaults.sh`: deploy defaults and baseline behavior toggles.
- `variables.sh`: expanded variable catalog used by legacy phased deploy flow.

## Data and Registry Files

- `service-endpoints.sh`: canonical endpoint definitions used by scripts.
- `npm-packages.sh`: pinned npm package/version declarations.
- `edge-model-registry.json`: model registry metadata for edge/local model workflows.
- `improvement-sources.json`: curated improvement source inventory used by discovery tooling.

## Control and Utility Files

- `.gitignore`: excludes temporary editor/backup files in this directory.
- `template-placeholder-baseline.tsv`: baseline map for template placeholder lint checks.

## How to Validate

```bash
./scripts/validate-config-settings.sh
```
