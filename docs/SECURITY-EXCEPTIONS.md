# Security Exceptions & Triage
**Updated:** 2026-03-23

## Scope

This file records temporary security exceptions and triage decisions based on
`archive/data/security-scan-2026-01-07.txt`. Exceptions must have owners, expiry, and a
remediation plan.

## Triage Summary (Latest Scan)

| Image | HIGH | CRITICAL | Decision |
| --- | --- | --- | --- |
| `docker.io/library/nginx:1.28.2-alpine` | pending | pending | Remediate (core entrypoint) |
| `docker.io/library/postgres:17.9-alpine3.23` | pending | pending | Remediate (`gosu` hotspot family) |
| `docker.io/library/redis:7.4.8-alpine3.21` | pending | pending | Remediate (`gosu` hotspot family) |
| `localhost:5000/ai-stack-aidb:dev` | 0 | 1 | Remediate (core) |
| `docker.io/pgvector/pgvector:0.8.1-pg18` | 2 | 0 | Remediate (core) |
| `docker.io/prom/prometheus:v3.10.0` | pending | pending | Remediate (observability) |
| `cr.jaegertracing.io/jaegertracing/jaeger:2.16.0` | pending | pending | Remediate (observability) |
| `docker.io/grafana/grafana:12.4.1` | pending | pending | Remediate (observability) |
| `docker.io/qdrant/qdrant:v1.17.0` | pending | pending | Remediate (vector store) |
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
- Re-run `scripts/security/security-scan.sh` after upgrades and refresh this file.
- Hosted backlog intake now comes from `scripts/security/export-github-code-scanning-alerts.sh`.
- Current open hosted backlog is dominated by Trivy image findings rather than repo-local secret findings.
- Current `gosu` hotspot family maps to the hosted `postgres` and `redis` Trivy scan categories.
