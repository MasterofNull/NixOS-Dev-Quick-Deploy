# AIDB Setup (K3s-only)

AIDB is deployed via Kubernetes.

```bash
kubectl apply -k ai-stack/kubernetes
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
```

For secrets and full deployment steps, see `DEPLOYMENT.md`.

