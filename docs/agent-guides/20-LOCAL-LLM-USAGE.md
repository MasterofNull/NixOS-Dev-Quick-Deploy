# Local LLM Usage (K3s-only)

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/llama-cpp --tail=100
```

Port-forward the OpenAI-compatible endpoint:

```bash
kubectl port-forward -n ai-stack svc/llama-cpp 8080:8080
```

