# AI Stack Quick Reference - December 2025 Upgrades

## 🚀 Enable Vulkan GPU (2-5x Faster!)

```bash
# 1. Copy environment template
cp ai-stack/compose/.env.example ai-stack/compose/.env

# 2. Edit .env and uncomment:
LLAMA_VULKAN_ENABLE=1
LLAMA_GPU_LAYERS=33

# 3. Restart llama.cpp
cd ai-stack/compose
podman-compose restart llama-cpp

# 4. Verify (should see "using Vulkan")
podman logs local-ai-llama-cpp | grep -i vulkan
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
podman exec local-ai-llama-cpp ls -l /dev/dri
```

## ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| `ai-stack/compose/.env` | Environment variables |
| `ai-stack/compose/docker-compose.yml` | Service definitions (updated!) |
| `ai-stack/UPGRADES-2025.md` | Full upgrade documentation |

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
podman exec local-ai-llama-cpp ls -l /dev/dri
```

**Still using CPU?**
```bash
# Verify environment
podman exec local-ai-llama-cpp env | grep VULKAN

# Check logs
podman logs local-ai-llama-cpp --tail 50
```

## 📚 Full Docs

- [Complete Upgrade Guide](./UPGRADES-2025.md)
- [Main AI Stack README](../README.md)
- [Docker Model Runner Comparison](./UPGRADES-2025.md#comparison)
