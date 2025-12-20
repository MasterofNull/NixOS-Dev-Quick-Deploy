# Container Management - Podman Operations

**Purpose**: Manage AI stack containers and troubleshoot issues

---

## Quick Commands

### List Containers

```bash
# All AI stack containers
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# All containers (including stopped)
podman ps -a

# With custom format
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Start/Stop/Restart

```bash
# Using helper script (recommended)
./scripts/hybrid-ai-stack.sh up
./scripts/hybrid-ai-stack.sh down
./scripts/hybrid-ai-stack.sh restart

# Individual container
podman start local-ai-qdrant
podman stop local-ai-qdrant
podman restart local-ai-qdrant

# All AI stack containers
podman restart $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")
```

### View Logs

```bash
# All services
./scripts/hybrid-ai-stack.sh logs

# Specific service
podman logs local-ai-lemonade

# Follow logs (real-time)
podman logs -f local-ai-qdrant

# Last 50 lines
podman logs local-ai-ollama --tail 50

# With timestamps
podman logs -t local-ai-postgres
```

---

## Container Operations

### Execute Commands in Container

```bash
# PostgreSQL
podman exec local-ai-postgres psql -U mcp -d mcp

# Redis
podman exec local-ai-redis redis-cli

# Ollama
podman exec local-ai-ollama ollama list

# Shell access
podman exec -it local-ai-qdrant /bin/sh
```

### Inspect Container

```bash
# Full details
podman inspect local-ai-lemonade | jq

# Specific field
podman inspect local-ai-qdrant --format '{{.State.Status}}'

# Environment variables
podman inspect local-ai-ollama --format '{{.Config.Env}}'

# Volume mounts
podman inspect local-ai-postgres --format '{{.Mounts}}'
```

### Resource Usage

```bash
# Real-time stats
podman stats

# One-time snapshot
podman stats --no-stream

# Specific container
podman stats local-ai-lemonade
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check exit code and error
podman logs local-ai-SERVICE 2>&1

# Inspect state
podman inspect local-ai-SERVICE | jq '.[0].State'

# Remove and recreate
podman rm -f local-ai-SERVICE
./scripts/hybrid-ai-stack.sh up
```

### Port Conflicts

```bash
# Find what's using port
ss -tlnp | grep 6333

# Change port in docker-compose.yml
vim ai-stack/compose/docker-compose.yml

# Restart stack
./scripts/hybrid-ai-stack.sh restart
```

### Permission Errors

```bash
# Fix data directory ownership
sudo chown -R $USER:$USER ~/.local/share/nixos-ai-stack/

# SELinux context (if applicable)
restorecon -R ~/.local/share/nixos-ai-stack/
```

### Out of Disk Space

```bash
# Clean up unused images
podman image prune -a

# Clean up volumes
podman volume prune

# Check disk usage
podman system df

# Full cleanup (keeps running containers)
podman system prune -a
```

---

## Maintenance

### Update Images

```bash
# Pull latest images
cd ai-stack/compose
podman-compose pull

# Recreate containers with new images
./scripts/hybrid-ai-stack.sh down
./scripts/hybrid-ai-stack.sh up
```

### Backup Data

```bash
# Backup AI stack data
tar -czf ai-stack-backup-$(date +%Y%m%d).tar.gz \
  ~/.local/share/nixos-ai-stack/
```

### Clean Restart

```bash
# Stop and remove containers (keeps data)
./scripts/hybrid-ai-stack.sh down

# Start fresh
./scripts/hybrid-ai-stack.sh up

# Verify
./scripts/hybrid-ai-stack.sh status
```

---

## Next Steps

- [Debugging Guide](12-DEBUGGING.md)
- [Service Status](02-SERVICE-STATUS.md)
- [NixOS Configuration](10-NIXOS-CONFIG.md)
