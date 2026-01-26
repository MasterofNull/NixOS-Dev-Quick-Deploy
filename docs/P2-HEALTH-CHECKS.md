# Health Checks (K3s-only)

Health checks are handled via Kubernetes probes in `ai-stack/kubernetes/`.

Use:

```bash
kubectl get pods -n ai-stack
kubectl describe pod -n ai-stack <pod>
```

