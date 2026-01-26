# Run This First (K3s-only)

```bash
./nixos-quick-deploy.sh
kubectl get pods -n ai-stack
```

If needed:

```bash
kubectl rollout restart -n ai-stack deployment/aidb
```

