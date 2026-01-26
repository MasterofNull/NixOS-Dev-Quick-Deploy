# AI Model Quickstart (K3s-only)

Models are served via Kubernetes deployments (llama-cpp, embeddings, etc.).

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/llama-cpp --tail=100
kubectl logs -n ai-stack deployment/embeddings --tail=100
```

If you update models locally, re-import the image and restart the deployment:

```bash
ONLY_IMAGES="llama-cpp" FORCE_IMPORT=1 sudo -E ./scripts/import-k3s-images.sh
kubectl rollout restart -n ai-stack deployment/llama-cpp
```

