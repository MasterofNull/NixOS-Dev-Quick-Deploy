# System Dashboard Guide (K3s-only)

The system dashboard now pulls **Kubernetes** metrics and service health.

## Quick Checks

```bash
kubectl get pods -n ai-stack
kubectl get svc -n ai-stack
kubectl logs -n ai-stack deployment/dashboard-api --tail=100
```

## Data Sources

- Prometheus (targets via `kubectl get svc -n ai-stack prometheus`)
- Grafana (dashboard UI)
- AIDB + Hybrid Coordinator (health endpoints)

For full deployment steps, see `DEPLOYMENT.md`.

