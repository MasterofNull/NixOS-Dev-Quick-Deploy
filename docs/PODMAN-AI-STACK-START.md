# Starting the Podman AI Stack

## Quick Start

The Podman AI stack is configured but **not started automatically**. You need to start it manually.

### Method 1: Using Systemd (Recommended)

Start all services in order:

```bash
# 1. Start the network first
systemctl --user start podman-local-ai-network.service

# 2. Wait a moment, then start all containers
systemctl --user start podman-local-ai-ollama.service \
  podman-local-ai-open-webui.service \
  podman-local-ai-qdrant.service \
  podman-local-ai-mindsdb.service
```

**Note:** On first run, containers will pull Docker images which can take several minutes. The services have timeouts, so if they appear to hang, check the logs:

```bash
# Check status
systemctl --user status podman-local-ai-ollama.service

# View logs
journalctl --user -u podman-local-ai-ollama.service -f
```

### Method 2: Using Podman Directly (If Helper Script Not Available)

If the `podman-ai-stack` helper isn't available yet, you can start containers manually:

```bash
# Ensure network exists
podman network exists local-ai || podman network create local-ai

# Start Ollama
podman run -d \
  --name local-ai-ollama \
  --network local-ai \
  --label nixos.quick-deploy.ai-stack=true \
  -p 11434:11434 \
  -v $HOME/.local/share/podman-ai-stack/ollama:/root/.ollama \
  docker.io/ollama/ollama:latest

# Start Open WebUI
podman run -d \
  --name local-ai-open-webui \
  --network local-ai \
  --label nixos.quick-deploy.ai-stack=true \
  -p 3000:8080 \
  -v $HOME/.local/share/podman-ai-stack/open-webui:/app/backend/data \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  ghcr.io/open-webui/open-webui:latest

# Start Qdrant
podman run -d \
  --name local-ai-qdrant \
  --network local-ai \
  --label nixos.quick-deploy.ai-stack=true \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $HOME/.local/share/podman-ai-stack/qdrant:/qdrant/storage \
  docker.io/qdrant/qdrant:latest

# Start MindsDB
podman run -d \
  --name local-ai-mindsdb \
  --network local-ai \
  --label nixos.quick-deploy.ai-stack=true \
  -p 47334:47334 \
  -p 7735:7735 \
  -v $HOME/.local/share/podman-ai-stack/mindsdb:/var/lib/mindsdb \
  docker.io/mindsdb/mindsdb:latest
```

## Verify Services Are Running

```bash
# Check systemd services
systemctl --user status podman-local-ai-*.service

# Check running containers
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# Check container logs
podman logs local-ai-ollama
podman logs local-ai-open-webui
```

## Access the Services

Once running, you can access:

- **Ollama API**: `http://localhost:11434`
- **Open WebUI**: `http://localhost:3000` (web interface)
- **Qdrant HTTP**: `http://localhost:6333`
- **Qdrant gRPC**: `localhost:6334`
- **MindsDB API**: `http://localhost:47334`
- **MindsDB GUI**: `http://localhost:7735`

## Troubleshooting

### Containers Timeout on First Start

This is normal! The first time you start containers, they need to pull Docker images which can take 5-10 minutes depending on your internet connection.

**Solution:** Wait for image pulls to complete, then restart the services:

```bash
# Check if images are being pulled
podman images | grep -E "ollama|open-webui|qdrant|mindsdb"

# If images are still downloading, wait and then restart
systemctl --user restart podman-local-ai-ollama.service
```

### Helper Script Not Found

If `podman-ai-stack` command is not available, rebuild Home Manager:

```bash
# Ensure preference is set
echo "LOCAL_AI_STACK_ENABLED=true" > ~/.config/nixos-quick-deploy/local-ai-stack.env

# Rebuild Home Manager
home-manager switch -b backup
```

### Rootless Podman UID/GID Issues

If you see errors like "potentially insufficient UIDs or GIDs available in user namespace":

**This is automatically configured by NixOS.** The deploy script sets `autoSubUidGidRange = true` in your NixOS configuration, which manages `/etc/subuid` and `/etc/subgid` declaratively.

**If you still see this error:**
```bash
# 1. Rebuild NixOS to apply the configuration
sudo nixos-rebuild switch

# 2. Migrate Podman storage
podman system migrate

# 3. Restart the services
systemctl --user restart podman-local-ai-*.service
```

**Verify configuration:**
```bash
# Should show your username with UID range
cat /etc/subuid
cat /etc/subgid
# Expected output: username:100000:65536
```

### Network Already Exists Error

If you see "network already exists", that's fine - the network was created successfully. You can ignore this error.

## Stopping the Stack

```bash
# Stop all containers
systemctl --user stop podman-local-ai-ollama.service \
  podman-local-ai-open-webui.service \
  podman-local-ai-qdrant.service \
  podman-local-ai-mindsdb.service

# Stop network (optional - containers can still use it)
systemctl --user stop podman-local-ai-network.service
```

Or using Podman directly:

```bash
podman stop local-ai-ollama local-ai-open-webui local-ai-qdrant local-ai-mindsdb
```

## Data Persistence

All container data is stored in `~/.local/share/podman-ai-stack/`:

- `ollama/` - Ollama model cache
- `open-webui/` - Open WebUI chat history and settings
- `qdrant/` - Qdrant vector database files
- `mindsdb/` - MindsDB database files

This data persists across container restarts and rebuilds.

