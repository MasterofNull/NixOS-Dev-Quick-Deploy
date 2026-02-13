# AI Stack Resource Profiles

These profiles guide per-service CPU/memory requests/limits for the K3s AI stack.

## Profiles

| Profile | Requests | Limits | Typical Use |
| --- | --- | --- | --- |
| small | 100m CPU / 128Mi | 500m CPU / 512Mi | lightweight APIs, sidecars |
| medium | 200m CPU / 256Mi | 1 CPU / 1Gi | dashboards, tracing UIs |
| large | 500m CPU / 1Gi | 2 CPU / 2Gi | heavier control-plane services |

## Current Assignments (high level)

- small: nginx, container-engine
- medium: dashboard-api, grafana, jaeger
- large: prometheus (larger limits for TSDB)

Adjust per deployment if real usage indicates a different profile.
