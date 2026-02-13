# Deprecated Scripts

These scripts were deprecated as part of the migration from Podman-based container runtime to Kubernetes (K3s). They have been replaced by Kubernetes-native commands.

## Replacement Guide

| Deprecated Script | Replacement |
|---|---|
| `ai-stack-manage.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `ai-stack-startup.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `ai-stack-full-test.sh` | `scripts/ai-stack-e2e-test.sh` |
| `hybrid-ai-stack.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `podman-ai-stack.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `podman-ai-stack-monitor.sh` | `scripts/ai-stack-health.sh` |
| `container-lifecycle.sh` | `kubectl` commands |
| `enable-podman-containers.sh` | K3s handles containers natively |
| `enable-podman-tcp.sh` | Not needed with K3s |
| `initialize-ai-stack.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `local-ai-starter.sh` | `kubectl apply -k ai-stack/kubernetes/` |
| `setup-podman-api.sh` | Not needed with K3s |
| `swap-embeddings-model.sh` | Edit `ai-stack/kubernetes/kompose/embeddings-deployment.yaml` |
| `swap-llama-cpp-model.sh` | Edit `ai-stack/kubernetes/kompose/llama-cpp-deployment.yaml` |
| `verify-nixos-docs.sh` | `kubectl logs -n ai-stack deploy/nixos-docs` |
| `verify-upgrades.sh` | `kubectl get pods -n ai-stack` |
| `reset-ai-volumes.sh` | `kubectl delete pvc -n ai-stack --all` |
| `deploy-jan2026-updates-optionA.sh` | One-time migration script, no longer needed |
| `ai-stack-monitor.sh` | `scripts/ai-stack-health.sh` |

## Common Kubernetes Commands

```bash
# Start AI stack
kubectl apply -k ai-stack/kubernetes/

# Check status
kubectl get pods -n ai-stack

# View logs
kubectl logs -n ai-stack deploy/<service-name>

# Restart a service
kubectl rollout restart -n ai-stack deploy/<service-name>

# Stop AI stack
kubectl delete -k ai-stack/kubernetes/
```

## Date Archived

2026-02-05
