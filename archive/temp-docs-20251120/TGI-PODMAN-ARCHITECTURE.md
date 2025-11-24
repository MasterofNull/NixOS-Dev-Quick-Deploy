# TGI Podman Architecture Documentation

## Overview

**TGI (Text Generation Inference) is already running in Podman containers**, managed by NixOS systemd services. You don't need to "place TGI in Podman" - it's already there!

This document explains the architecture and how everything works together.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      NixOS System                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Systemd Services                          │ │
│  │                                                        │ │
│  │  ┌─────────────────────┐  ┌─────────────────────┐    │ │
│  │  │ huggingface-tgi     │  │ huggingface-tgi-    │    │ │
│  │  │ .service            │  │ scout.service       │    │ │
│  │  │                     │  │                     │    │ │
│  │  │ Type: simple        │  │ Type: simple        │    │ │
│  │  │ Port: 8080          │  │ Port: 8085          │    │ │
│  │  └──────────┬──────────┘  └──────────┬──────────┘    │ │
│  │             │                        │               │ │
│  │             │ ExecStart (podman run) │               │ │
│  │             ▼                        ▼               │ │
│  └─────────────────────────────────────────────────────┘ │
│                │                        │                 │
│  ┌─────────────▼────────────┐  ┌───────▼──────────────┐  │
│  │     Podman Runtime       │  │  Podman Runtime      │  │
│  │                          │  │                      │  │
│  │  ┌────────────────────┐  │  │  ┌────────────────┐ │  │
│  │  │ TGI Container      │  │  │  │ TGI Container  │ │  │
│  │  │                    │  │  │  │                │ │  │
│  │  │ Image:             │  │  │  │ Image:         │ │  │
│  │  │ ghcr.io/hugging    │  │  │  │ ghcr.io/hugging│ │  │
│  │  │ face/text-         │  │  │  │ face/text-     │ │  │
│  │  │ generation-        │  │  │  │ generation-    │ │  │
│  │  │ inference:latest   │  │  │  │ inference:2.5.1│ │  │
│  │  │                    │  │  │  │                │ │  │
│  │  │ Model:             │  │  │  │ Model:         │ │  │
│  │  │ DeepSeek-R1        │  │  │  │ Llama-4-Scout  │ │  │
│  │  │ -Distill-Qwen-7B   │  │  │  │ -17B-16E       │ │  │
│  │  │                    │  │  │  │                │ │  │
│  │  │ Volumes:           │  │  │  │ Volumes:       │ │  │
│  │  │ - Cache mounted    │  │  │  │ - Cache mounted│ │  │
│  │  │ - Env secrets      │  │  │  │ - Env secrets  │ │  │
│  │  └────────────────────┘  │  │  └────────────────┘ │  │
│  └──────────────────────────┘  └─────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │           Host Filesystem                          │  │
│  │                                                    │  │
│  │  /var/lib/huggingface/                            │  │
│  │  ├── cache/  ← DeepSeek model cache               │  │
│  │                                                    │  │
│  │  /var/lib/huggingface-scout/                      │  │
│  │  ├── cache/  ← Scout model cache                  │  │
│  │                                                    │  │
│  │  /var/lib/nixos-quick-deploy/secrets/             │  │
│  │  ├── huggingface-tgi.env  ← HF_TOKEN              │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Systemd Service Layer

Each TGI instance is a **systemd service** defined in [configuration.nix](templates/configuration.nix):

- `huggingface-tgi.service` - DeepSeek model on port 8080
- `huggingface-tgi-scout.service` - Llama 4 Scout model on port 8085

**Lifecycle Management:**
```bash
# Start/stop services
sudo systemctl start huggingface-tgi.service
sudo systemctl stop huggingface-tgi.service

# Enable on boot
sudo systemctl enable huggingface-tgi.service

# Check status
sudo systemctl status huggingface-tgi.service

# View logs
journalctl -u huggingface-tgi.service -f
```

### 2. Podman Container Layer

When the systemd service starts, it runs a **Podman container** with the TGI Docker image.

**Example from DeepSeek service:**
```nix
ExecStart = ''
  ${pkgs.podman}/bin/podman run \
    --rm \
    --name huggingface-tgi \
    --network=slirp4netns:port_handler=slirp4netns \
    --publish 127.0.0.1:8080:8080 \
    --env-file=/var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env \
    --volume /var/lib/huggingface/cache:/data:rw \
    --device nvidia.com/gpu=all \
    ghcr.io/huggingface/text-generation-inference:latest \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
    --port 8080 \
    --max-concurrent-requests 128
'';
```

**Key Container Settings:**
- `--rm`: Auto-remove container on stop
- `--name`: Container name for identification
- `--network=slirp4netns`: Rootless networking (no root required)
- `--publish`: Map container port to host (127.0.0.1:8080 → container:8080)
- `--env-file`: HuggingFace API token for model downloads
- `--volume`: Persistent cache for downloaded models
- `--device`: GPU access (if available)

### 3. Container Image

**Official TGI Images:**
- `ghcr.io/huggingface/text-generation-inference:latest` (DeepSeek)
- `ghcr.io/huggingface/text-generation-inference:2.5.1` (Scout - pinned version)

**Image Contains:**
- Rust-based TGI server
- CUDA/ROCm support for GPU acceleration
- Model loader and inference engine
- OpenAI-compatible API server

### 4. Model Storage

Models are downloaded to **host volumes** and mounted into containers:

**DeepSeek:**
```
Host: /var/lib/huggingface/cache
Container: /data
```

**Scout:**
```
Host: /var/lib/huggingface-scout/cache
Container: /data
```

**Cache Structure:**
```
/var/lib/huggingface/cache/
├── models--deepseek-ai--DeepSeek-R1-Distill-Qwen-7B/
│   ├── blobs/              ← Actual model weights
│   ├── snapshots/          ← Symlinks to specific versions
│   └── refs/               ← Version references
└── tmp*/                   ← Download temp files
```

### 5. Security Configuration

**Service Hardening:**
```nix
# From configuration.nix
ProtectSystem = "strict";
ProtectHome = true;
PrivateTmp = true;
NoNewPrivileges = true;
ReadWritePaths = [ "/var/lib/huggingface/cache" ];

# IMPORTANT: ProcSubset must be "all" for Podman
ProcSubset = "all";  # Allows access to /proc/sys for capabilities
ProtectProc = "default";
```

**Why `ProcSubset = "all"`?**
- Podman needs to read `/proc/sys/kernel/cap_last_cap` to check container capabilities
- Previous value `"pid"` blocked this, causing startup failures
- This was fixed in [configuration.nix:743-746](templates/configuration.nix#L743-L746)

### 6. Environment Variables

**Required Environment File:**
```bash
# /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HUGGINGFACEHUB_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Get Your Token:**
1. Visit https://huggingface.co/settings/tokens
2. Create a new token with "Read" permissions
3. Add to env file:
   ```bash
   sudo install -m600 /dev/null /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env
   echo "HF_TOKEN=hf_xxx" | sudo tee -a /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env
   echo "HUGGINGFACEHUB_API_TOKEN=hf_xxx" | sudo tee -a /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env
   ```

## Why This Architecture?

### Benefits of Systemd + Podman:

1. **No Docker Daemon**: Podman is daemonless, more secure
2. **Rootless Containers**: Services run as system user, not root
3. **Native Systemd Integration**: Standard systemd commands work
4. **Automatic Restarts**: Systemd handles crash recovery
5. **Logging Integration**: `journalctl` for all logs
6. **Boot Integration**: Services start automatically on boot
7. **Resource Limits**: Systemd cgroup controls

### Benefits Over User-Level Containers:

The deployment uses **system-level services** instead of user Podman:

**System-Level (Current):**
- Start on boot automatically
- Run even when user not logged in
- Managed with `sudo systemctl`
- Services in `/etc/systemd/system/`
- Accessible to all users

**User-Level (Alternative):**
- Start only when user logs in
- Stop when user logs out
- Managed with `systemctl --user`
- Services in `~/.config/systemd/user/`
- Accessible only to that user

For AI inference services that should always be available, **system-level is the right choice**.

## Verification Commands

### Check Services:
```bash
# Service status
systemctl status huggingface-tgi.service
systemctl status huggingface-tgi-scout.service

# Service logs (live)
journalctl -u huggingface-tgi.service -f
```

### Check Containers:
```bash
# List running containers
podman ps

# Filter for TGI containers
podman ps --filter name=huggingface

# Container logs (alternative to journalctl)
podman logs huggingface-tgi
podman logs huggingface-tgi-scout
```

### Check APIs:
```bash
# Health checks
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8085/health

# Test inference
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}'
```

### Check Model Cache:
```bash
# DeepSeek cache
du -sh /var/lib/huggingface/cache/
ls -la /var/lib/huggingface/cache/

# Scout cache
du -sh /var/lib/huggingface-scout/cache/
ls -la /var/lib/huggingface-scout/cache/
```

## Troubleshooting

### Service Won't Start:

1. **Check service status:**
   ```bash
   systemctl status huggingface-tgi.service
   ```

2. **Check recent logs:**
   ```bash
   journalctl -u huggingface-tgi.service -n 50
   ```

3. **Common issues:**
   - Missing HF_TOKEN: Add to `/var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env`
   - Port conflict: Check if another service using port 8080/8085
   - Missing directories: Should be created by systemd tmpfiles
   - GPU access: Check `nvidia-smi` or GPU drivers

### Container Won't Run:

1. **Try running manually:**
   ```bash
   sudo podman run --rm \
     -p 127.0.0.1:8080:8080 \
     -v /var/lib/huggingface/cache:/data:rw \
     -e HF_TOKEN=hf_xxx \
     ghcr.io/huggingface/text-generation-inference:latest \
     --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
     --port 8080
   ```

2. **Check Podman network:**
   ```bash
   podman network ls
   podman network inspect slirp4netns
   ```

### Model Download Stuck:

1. **Check disk space:**
   ```bash
   df -h /var/lib/huggingface/
   ```

2. **Check download progress in logs:**
   ```bash
   journalctl -u huggingface-tgi.service -f | grep -i download
   ```

3. **Verify HF_TOKEN is valid:**
   ```bash
   # Test token
   curl -H "Authorization: Bearer hf_xxx" \
     https://huggingface.co/api/whoami
   ```

### API Not Responding:

1. **Model still loading** (normal for first start):
   - DeepSeek: ~5-10 minutes for 15GB model
   - Scout: ~10-20 minutes for 35GB model
   - Check logs for "Connected" message

2. **Check health endpoint:**
   ```bash
   curl -v http://127.0.0.1:8080/health
   ```

3. **Check container is running:**
   ```bash
   podman ps | grep huggingface
   ```

## Integration with Other Services

### Open WebUI Integration:

Open WebUI can access TGI endpoints directly:

1. Add TGI endpoints in Open WebUI settings
2. Use OpenAI-compatible API format:
   - Base URL: `http://127.0.0.1:8080/v1`
   - Model: `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`

### Direct API Usage:

```python
import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="dummy"  # TGI doesn't require API key for local use
)

response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=100
)
print(response.choices[0].message.content)
```

## Summary

**TGI is already running in Podman!** The architecture uses:

- ✅ Systemd services for lifecycle management
- ✅ Podman containers for isolation
- ✅ Host volume mounts for model persistence
- ✅ Rootless mode for security
- ✅ OpenAI-compatible API endpoints
- ✅ Automatic model downloading and caching
- ✅ GPU acceleration support

No additional setup needed - it's a complete, production-ready deployment.
