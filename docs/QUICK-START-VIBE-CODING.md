# Quick Start (K3s-only)

## Status

```bash
kubectl get pods -n ai-stack
```

## Logs

```bash
kubectl logs -n ai-stack deployment/aidb --tail=100
kubectl logs -n ai-stack deployment/hybrid-coordinator --tail=100
kubectl logs -n ai-stack deployment/ralph-wiggum --tail=100
```

## Restart a Service

```bash
kubectl rollout restart -n ai-stack deployment/aidb
```

## Port-forward

```bash
kubectl port-forward -n ai-stack svc/aidb 8091:8091
```

