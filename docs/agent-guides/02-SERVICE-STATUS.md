# Service Status (K3s-only)

```bash
kubectl get pods -n ai-stack
kubectl describe pod -n ai-stack <pod>
kubectl logs -n ai-stack deployment/<service> --tail=100
```

