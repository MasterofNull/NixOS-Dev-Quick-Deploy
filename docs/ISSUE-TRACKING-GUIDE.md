# Issue Tracking Guide (K3s-only)

Use Kubernetes-native commands in incident reports:

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/<service> --tail=100
```

