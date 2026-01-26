# AI Agent Start Here (K3s-only)

This system is **K3s + containerd** only. Use Kubernetes-native commands.

## Quick Health

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
kubectl logs -n ai-stack deployment/hybrid-coordinator --tail=100
```

## Service Endpoints

Expose services with port-forward when needed:

```bash
kubectl port-forward -n ai-stack svc/aidb 8091:8091
kubectl port-forward -n ai-stack svc/hybrid-coordinator 8092:8092
```

Then test:

```bash
curl http://localhost:8091/health
curl http://localhost:8092/health
```

For full deployment steps and secrets, see `DEPLOYMENT.md` and `SECRETS-MANAGEMENT-GUIDE.md`.

