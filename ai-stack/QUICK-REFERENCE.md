# AI Stack Quick Reference - December 2025 Upgrades

## 🚀 Enable Vulkan GPU (2-5x Faster!)

```bash
# 1. Copy environment template
cp templates/local-ai-stack/.env.example ~/.config/nixos-ai-stack/.env

# 2. Edit .env and uncomment:
LLAMA_VULKAN_ENABLE=1
LLAMA_GPU_LAYERS=33

# 3. Restart llama.cpp
kubectl rollout restart deploy -n ai-stack llama-cpp

# 4. Verify (should see "using Vulkan")
kubectl logs -n ai-stack deploy/llama-cpp | grep -i vulkan
```

## 📊 New Tools

```bash
# Monitor AI stack (live dashboard)
./scripts/ai-stack-monitor.sh

# Manage models (Docker-style)
./scripts/llama-model-cli.sh list
./scripts/llama-model-cli.sh logs 100
./scripts/llama-model-cli.sh prune

# Download models (existing tool)
./scripts/ai-model-manager.sh download qwen2.5-coder-7b
```

## 🔍 Check GPU Usage

```bash
# AMD GPUs
radeontop

# Intel GPUs  
intel_gpu_top

# Verify Vulkan
vulkaninfo | grep driver

# Container GPU access
kubectl exec -n ai-stack deploy/llama-cpp -- ls -l /dev/dri
```

## ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| `~/.config/nixos-ai-stack/.env` | Environment variables |
| `ai-stack/kubernetes/kustomization.yaml` | Service definitions (updated!) |
| `docs/archive/AI-STACK-UPGRADES-2025.md` | Full upgrade documentation |

## 🔗 Dependency Order & Readiness

**Startup order (recommended):**
1) Postgres → 2) Redis → 3) Qdrant → 4) Embeddings → 5) AIDB → 6) Hybrid → 7) Ralph → 8) MindsDB → 9) llama-cpp → 10) Open WebUI

**Dependency gates (K8s initContainers):**
- `aidb` waits for Postgres/Redis/Qdrant/Embeddings.
- `hybrid-coordinator` waits for Postgres/Redis/Qdrant/Embeddings/AIDB.
- `ralph-wiggum` waits for Postgres/Redis/Hybrid/AIDB.

**Startup probes (heavy services):**
- `aidb`, `embeddings`, `mindsdb`, `llama-cpp`, `ralph-wiggum` use `startupProbe` to avoid premature restarts during cold start.

**Quick checks:**
```bash
# List deployments and confirm names
kubectl get deploy -n ai-stack

# Watch rollout readiness (replace <service> with actual deployment names)
kubectl rollout status -n ai-stack deploy/<service>

# Verify pods are healthy
kubectl get pods -n ai-stack
```

## 📈 Performance Comparison

| Mode | Speed | Use Case |
|------|-------|----------|
| CPU only | 8-12 tok/s | Baseline |
| Vulkan GPU | 20-45 tok/s | **Recommended!** |

## 🆘 Troubleshooting

**GPU not detected?**
```bash
# Check drivers
ls /dev/dri
vulkaninfo

# Check permissions
kubectl exec -n ai-stack deploy/llama-cpp -- ls -l /dev/dri
```

**Still using CPU?**
```bash
# Verify environment
kubectl exec -n ai-stack deploy/llama-cpp -- env | grep VULKAN

# Check logs
kubectl logs -n ai-stack deploy/llama-cpp --tail 50
```

## 📚 Full Docs

- [Complete Upgrade Guide](../docs/archive/AI-STACK-UPGRADES-2025.md)
- [Main AI Stack README](../README.md)
- [Docker Model Runner Comparison](./UPGRADES-2025.md#comparison)
