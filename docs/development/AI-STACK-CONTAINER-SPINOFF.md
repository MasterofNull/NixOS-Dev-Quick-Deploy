# AI Stack Container Spin-off Guide
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

This document provides the technical foundation for spinning off the AI stack
into a standalone containerized deployment that works across Linux, Windows
(WSL2), and macOS.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI Stack Container Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  llama-server   │  │  llama-embed    │  │   open-webui    │             │
│  │    (Inference)  │  │  (Embeddings)   │  │  (Web Interface)│             │
│  │     :8080       │  │     :8081       │  │     :3000       │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┴────────────────────┘                       │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────┐             │
│  │              Hardware Abstraction Layer                    │             │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ │             │
│  │  │  CUDA   │ │ Vulkan  │ │  ROCm   │ │  Metal  │ │ CPU  │ │             │
│  │  │(NVIDIA) │ │(AMD/Intel)│ │ (AMD)  │ │(Apple) │ │      │ │             │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────┘ │             │
│  └───────────────────────────────────────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Portable Components

### 1. Hardware Profiles (JSON)

**Source:** `config/ai-stack-hardware-profiles.json`

Portable configuration defining:
- Accelerator capabilities (CUDA, Vulkan, ROCm, Metal, CPU)
- Platform-specific detection commands
- Environment variables for each accelerator
- CMake build flags for llama.cpp
- Container dependencies

This JSON can be copied directly to the container project and parsed by any
language (Python, Node.js, Go, etc.).

### 2. Hardware Abstraction Library (Nix)

**Source:** `nix/lib/ai-stack-hardware.nix`

Functions for:
- `resolveAcceleration` — Auto-detect best GPU backend
- `getEnvironment` — Generate environment variables
- `getRuntimeArgs` — Get llama.cpp command-line arguments
- `exportForContainer` — Generate container deployment config
- `generateEnvFile` — Create `.env` file content

For the container project, port these functions to:
- Python (for docker-compose generation)
- Shell script (for runtime detection)

### 3. Export Script

**Source:** `scripts/ai/export-container-config`

Generates container-ready configuration:
- `ai-stack.env` — Environment variables
- `docker-compose.yml` — Compose configuration
- `README.md` — Deployment instructions

## Platform Support Matrix

| Platform | Architecture | CUDA | Vulkan | ROCm | Metal | CPU |
|----------|--------------|------|--------|------|-------|-----|
| Linux x86_64 | x86_64 | ✅ | ✅ | ⚠️ | ❌ | ✅ |
| Linux ARM64 | aarch64 | ✅ | ✅ | ❌ | ❌ | ✅ |
| Windows WSL2 | x86_64 | ✅ | ✅ | ❌ | ❌ | ✅ |
| macOS Intel | x86_64 | ❌ | ❌ | ❌ | ✅ | ✅ |
| macOS Apple Silicon | aarch64 | ❌ | ❌ | ❌ | ✅ | ✅ |

Legend: ✅ Supported | ⚠️ Deprecated | ❌ Not available

## Container Images

### Recommended Base Images

```yaml
# CUDA (NVIDIA)
image: ghcr.io/ggml-org/llama.cpp:server-cuda

# Vulkan (AMD/Intel)
image: ghcr.io/ggml-org/llama.cpp:server

# CPU Only
image: ghcr.io/ggml-org/llama.cpp:server

# ROCm (AMD discrete - deprecated)
image: ghcr.io/ggml-org/llama.cpp:server-rocm
```

### Custom Build (if needed)

```dockerfile
FROM ubuntu:22.04 AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake git \
    libvulkan-dev vulkan-tools \
    && rm -rf /var/lib/apt/lists/*

# Clone and build llama.cpp
RUN git clone https://github.com/ggml-org/llama.cpp.git /llama.cpp
WORKDIR /llama.cpp

# Apply patches (copy from NixOS repo)
COPY patches/llama-cpp/*.patch ./
RUN for p in *.patch; do patch -p1 < "$p"; done

# Build with Vulkan
RUN cmake -B build \
    -DGGML_VULKAN=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DBUILD_SHARED_LIBS=ON \
    && cmake --build build --target llama-server -j$(nproc)

# Runtime image
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    libvulkan1 mesa-vulkan-drivers \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /llama.cpp/build/bin/llama-server /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/llama-server"]
```

## Environment Variables Reference

### Common Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_STACK_ACCELERATOR` | GPU backend: cuda/vulkan/rocm/metal/cpu | auto |
| `AI_STACK_GPU_VENDOR` | GPU vendor: nvidia/amd/intel/apple/none | auto |
| `AI_STACK_INFERENCE_PORT` | Inference API port | 8080 |
| `AI_STACK_EMBEDDING_PORT` | Embedding API port | 8081 |
| `AI_STACK_WEBUI_PORT` | Web UI port | 3000 |
| `AI_STACK_CPU_THREADS` | CPU thread count | 8 |
| `AI_STACK_CTX_SIZE` | Context window size | 16384 |

### CUDA-Specific

| Variable | Description |
|----------|-------------|
| `CUDA_VISIBLE_DEVICES` | GPU device index |
| `CUDA_CACHE_PATH` | Kernel cache directory |

### Vulkan-Specific

| Variable | Description |
|----------|-------------|
| `VK_ICD_FILENAMES` | Vulkan ICD manifest path |
| `VK_DRIVER_FILES` | Vulkan driver files path |
| `GGML_VK_VISIBLE_DEVICES` | Vulkan device index |

### ROCm-Specific (Deprecated)

| Variable | Description |
|----------|-------------|
| `HSA_OVERRIDE_GFX_VERSION` | GFX version override |
| `HSA_ENABLE_SDMA` | SDMA enable (0 for APUs) |
| `GGML_HIP_UMA` | Unified memory access |

## Spin-off Project Structure

```
ai-stack-container/
├── docker-compose.yml          # Main compose file
├── docker-compose.cuda.yml     # CUDA overlay
├── docker-compose.vulkan.yml   # Vulkan overlay
├── .env.example                # Example environment
├── config/
│   └── hardware-profiles.json  # Copied from NixOS repo
├── scripts/
│   ├── detect-gpu.sh          # GPU detection script
│   ├── setup.sh               # Initial setup
│   └── update-models.sh       # Model download helper
├── patches/
│   └── llama-cpp/             # Patches from NixOS repo
│       └── allow-vulkan-igpu-offload.patch
├── docs/
│   ├── quick-start.md
│   ├── gpu-setup.md
│   └── troubleshooting.md
└── README.md
```

## Migration Checklist

When creating the spin-off project:

1. **Copy portable files:**
   - [ ] `config/ai-stack-hardware-profiles.json`
   - [ ] `nix/patches/llama-cpp/*.patch`
   - [ ] `scripts/ai/export-container-config` (as reference)

2. **Port detection logic:**
   - [ ] Create `detect-gpu.sh` from hardware abstraction
   - [ ] Support Linux, macOS, Windows (WSL2)
   - [ ] Auto-select best accelerator

3. **Create compose files:**
   - [ ] Base compose with service definitions
   - [ ] Platform-specific overlays
   - [ ] GPU passthrough configurations

4. **Documentation:**
   - [ ] Quick start guide per platform
   - [ ] GPU setup instructions
   - [ ] Model download guide
   - [ ] Troubleshooting guide

5. **CI/CD:**
   - [ ] Multi-arch image builds (amd64, arm64)
   - [ ] GPU-specific image variants
   - [ ] Automated testing

## Testing Checklist

Before release, test on:

- [ ] Ubuntu 22.04 (NVIDIA GPU)
- [ ] Ubuntu 22.04 (AMD GPU - Vulkan)
- [ ] Ubuntu 22.04 (Intel GPU - Vulkan)
- [ ] Ubuntu 22.04 (CPU only)
- [ ] Fedora 39 (NVIDIA/AMD)
- [ ] Windows 11 WSL2 (NVIDIA)
- [ ] macOS 14 Apple Silicon
- [ ] Raspberry Pi 5 (ARM64 CPU)

## Version Compatibility

| Component | Minimum Version | Recommended |
|-----------|-----------------|-------------|
| Docker | 20.10 | 24.0+ |
| Docker Compose | 2.0 | 2.20+ |
| NVIDIA Container Toolkit | 1.13 | Latest |
| Vulkan | 1.2 | 1.3+ |
| llama.cpp | b8219 | Latest |

## References

- [llama.cpp Repository](https://github.com/ggml-org/llama.cpp)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Mesa Vulkan Drivers](https://docs.mesa3d.org/vulkan-drivers.html)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)
