# Security Exceptions & Triage
**Updated:** 2026-01-09

## Scope

This file records temporary security exceptions and triage decisions based on
`archive/data/security-scan-2026-01-07.txt`. Exceptions must have owners, expiry, and a
remediation plan.

## Triage Summary (Latest Scan)

| Image | HIGH | CRITICAL | Decision |
| --- | --- | --- | --- |
| `docker.io/library/nginx:1.27-alpine` | 7 | 2 | Remediate (core entrypoint) |
| `localhost:5000/ai-stack-aidb:dev` | 0 | 1 | Remediate (core) |
| `docker.io/pgvector/pgvector:0.8.1-pg18` | 2 | 0 | Remediate (core) |
| `docker.io/prom/prometheus:v2.54.0` | 7 | 2 | Remediate (observability) |
| `docker.io/jaegertracing/all-in-one:1.60` | 5 | 1 | Remediate (observability) |
| `docker.io/grafana/grafana:11.2.0` | 4 | 0 | Remediate (observability) |
| `ghcr.io/open-webui/open-webui:main` | 1 | 1 | Exempt in dev only (optional) |
| `docker.io/mindsdb/mindsdb:latest` | 5 | 1 | Exempt in dev only (optional) |
| `docker.io/paulgauthier/aider:latest` | 8 | 0 | Exempt in dev only (optional) |
| `docker.io/significantgravitas/auto-gpt:latest` | 27 | 3 | Exempt in dev only (optional) |
| `localhost:5000/ai-stack-nixos-docs:dev` | 2 | 1 | Remediate (optional but recommended) |
| `localhost:5000/ai-stack-aider-wrapper:dev` | 1 | 0 | Exempt in dev only (optional) |
| `localhost:5000/ai-stack-ralph-wiggum:dev` | 5 | 0 | Exempt in dev only (optional) |

## Exceptions (Temporary)

| Service | Owner | Expiry | Justification | Remediation Plan |
| --- | --- | --- | --- | --- |
| open-webui | TBD | 30 days | Optional dev UI | Pin to stable release or remove from prod |
| mindsdb | TBD | 30 days | Optional analytics | Pin to stable release or remove from prod |
| aider | TBD | 30 days | Optional dev agent | Pin to stable release or remove from prod |
| auto-gpt | TBD | 30 days | Optional dev agent | Pin to stable release or remove from prod |
| aider-wrapper | TBD | 30 days | Optional agent backend | Pin to stable release or remove from prod |
| ralph-wiggum | TBD | 30 days | Optional agent loop | Pin to stable release or remove from prod |

## Notes

- Core services must reach **CRITICAL = 0** before production.
- Re-run `scripts/security-scan.sh` after upgrades and refresh this file.
