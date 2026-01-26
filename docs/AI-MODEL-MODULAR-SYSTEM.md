# AI Model Modular System (K3s-only)

Model lifecycle is managed via Kubernetes deployments and config maps.

```bash
kubectl get deployments -n ai-stack
kubectl rollout restart -n ai-stack deployment/llama-cpp
```

For deployment flow, see `DEPLOYMENT.md`.

