# Ralph Wiggum Quick Start (K3s-only)

```bash
kubectl get pods -n ai-stack -l io.kompose.service=ralph-wiggum
kubectl logs -n ai-stack deployment/ralph-wiggum --tail=100
kubectl rollout restart -n ai-stack deployment/ralph-wiggum
```

