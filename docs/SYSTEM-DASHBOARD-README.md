# System Dashboard (K3s-only)

The dashboard reads live Kubernetes state. Compose-based commands are retired.

Quick checks:

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/dashboard-api --tail=100
```

For troubleshooting and data sources, see `docs/SYSTEM-DASHBOARD-GUIDE.md` and `DEPLOYMENT.md`.

