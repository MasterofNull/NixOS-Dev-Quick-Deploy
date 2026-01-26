# AI System Usage Guide (K3s-only)

```bash
kubectl apply -k ai-stack/kubernetes
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
```

