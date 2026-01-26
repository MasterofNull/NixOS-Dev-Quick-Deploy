# TLS Setup (K3s-only)

TLS termination is handled by the Kubernetes ingress or service layer. Update manifests under `ai-stack/kubernetes/` and apply:

```bash
kubectl apply -k ai-stack/kubernetes
```

