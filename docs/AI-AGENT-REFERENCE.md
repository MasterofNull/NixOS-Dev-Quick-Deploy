# AI Agent Reference (K3s-only)

## Stack Layout

```
ai-stack/
├── kubernetes/           # Kustomize base + kompose output
├── kustomize/            # Overlays (dev/prod)
└── compose/secrets/      # Secret source-of-truth
```

## Operations

```bash
kubectl apply -k ai-stack/kubernetes
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/aidb --tail=100
```

## MCP + AIDB

AIDB is exposed in-cluster. Use port-forward for local access:

```bash
kubectl port-forward -n ai-stack svc/aidb 8091:8091
curl http://localhost:8091/health
```

