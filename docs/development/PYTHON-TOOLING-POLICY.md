# Python Tooling Policy
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-24

## Decision

Use `uv` as the default Python workflow tool for:
- local development environments
- CI/bootstrap dependency installation
- project-scoped Python tool execution

Do not mass-convert runtime-sensitive Nix or container install paths without service-specific validation.

## Why

- `uv` is faster and more reproducible for virtualenv creation, dependency sync, and tool execution.
- This repo already prefers `uv` in templates and capability hints.
- Some runtime/container paths in this repo have ordering-sensitive installs, especially CPU-only PyTorch layers, and should be migrated only after explicit validation.

## Default Rules

1. Prefer `uv venv`, `uv sync`, `uv pip`, and `uv tool run` over ad hoc `pip install` in developer and CI workflows.
2. Keep Nix declarative packaging as the source of truth for system/runtime dependencies.
3. Treat Dockerfiles and service runtime install steps as exception-based until migrated and validated individually.
4. New bare `pip install` usage in `scripts/` and GitHub Actions must be explicitly allowlisted with a documented reason.

## Approved Exceptions

Current approved exceptions are tracked in [python-tooling-policy-allowlist.txt](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/python-tooling-policy-allowlist.txt).

These exceptions exist because they are either:
- runtime/container-specific install paths
- transitional GitHub workflow bootstrap paths
- compatibility/error-message strings rather than executable policy

## Migration Order

1. Dev and CI bootstrap scripts
2. GitHub Actions Python setup steps
3. Standalone Python tooling helpers
4. Service Dockerfiles, one service at a time

## Validation

Run:

```bash
bash scripts/governance/check-python-tooling-policy.sh
```

This check is included in quick deploy lint.
