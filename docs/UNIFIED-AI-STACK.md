# Unified AI Stack (K3s-only)

**Single source of truth:** `ai-stack/kubernetes/` (kustomize + kompose output).

All runtime operations are Kubernetes-native:

```bash
kubectl apply -k ai-stack/kubernetes
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
```

Legacy compose paths are retired and kept only for historical reference.

