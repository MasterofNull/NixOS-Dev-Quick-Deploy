# Dashboard Quickstart (K3s-only)

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/dashboard-api --tail=100
```

Access options:
- Local dashboard UI: `http://localhost:8888/dashboard.html`
- Dashboard API (dev NodePort): `http://localhost:31889/api/health`
- Remote UI with NodePort API: `http://<host>:8888/dashboard.html?apiPort=31889`
