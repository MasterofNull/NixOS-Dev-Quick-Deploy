# AI Agent Setup (K3s-only)

This stack runs on **K3s + containerd**. Use Kubernetes-native commands.

## Deploy / Update

```bash
kubectl apply -k ai-stack/kubernetes
kubectl rollout restart -n ai-stack deployment/aidb
```

## Verify

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
```

For full deployment steps and secrets workflow, see `DEPLOYMENT.md` and `SECRETS-MANAGEMENT-GUIDE.md`.

