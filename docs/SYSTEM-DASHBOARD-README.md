# System Dashboard (K3s-only)

The dashboard reads live Kubernetes state. Compose-based commands are retired.

Quick checks:

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/dashboard-api --tail=100
```

Access options:
- Dashboard UI: `http://localhost:8888/dashboard.html`
- Dashboard API (dev NodePort): `http://localhost:31889/api/health`
- Remote UI with NodePort API: `http://<host>:8888/dashboard.html?apiPort=31889`

For troubleshooting and data sources, see `docs/SYSTEM-DASHBOARD-GUIDE.md` and `DEPLOYMENT.md`.
