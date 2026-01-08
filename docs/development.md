# Development Environment Setup
**Updated:** 2026-01-09

## Prerequisites

- Podman + podman-compose
- Python 3.11+ (only for local tooling and scripts)

## Start the Stack

```bash
make up
```

Full profile (agents + optional services):

```bash
make up-full
```

## Dev Overrides

Use the dev compose overrides (sets `STACK_ENV=dev` for core services):

```bash
make dev-up
```

## Resource Limits

`deploy.resources` in `ai-stack/compose/docker-compose.yml` is advisory under podman-compose. For enforced limits, use systemd units or `podman run --cpus/--memory` overrides.

## Common Commands

```bash
make ps
make logs
make health
make metrics
make security-audit
make security-scan
make down
```

## Pre-commit Hooks

Install hooks (optional but recommended):

```bash
pip install pre-commit
pre-commit install
```

## Debugging Tips

- Check health: `make health`
- Inspect logs: `make logs`
- Service-specific logs: `podman logs <container>`
- Prometheus/Grafana URLs are in `ai-stack/README.md`
- `health-monitor` runs privileged with access to the podman socket in the `self-heal` profile; only enable it if you need self-healing.
