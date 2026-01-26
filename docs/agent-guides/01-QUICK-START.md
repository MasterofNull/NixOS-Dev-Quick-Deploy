# Agent Quick Start (K3s-only)

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
kubectl logs -n ai-stack deployment/hybrid-coordinator --tail=100
```

Port-forward for local access:

```bash
kubectl port-forward -n ai-stack svc/aidb 8091:8091
```

