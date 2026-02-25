# Debugging & Troubleshooting

**Purpose**: Find and fix issues in AI stack and NixOS system

---

## Quick Diagnostics

### Check Everything

```bash
# System status
./scripts/hybrid-ai-stack.sh status

# Service health
systemctl --failed

# Recent errors
journalctl -p err -n 50

# Container logs
./scripts/hybrid-ai-stack.sh logs | grep -i error
```

---

## Common Issues

### 1. Service Not Responding

**Symptoms**: Cannot connect to service, timeouts

```bash
# Check if running
podman ps | grep local-ai-SERVICE

# Check port listening
ss -tlnp | grep PORT

# Check logs for errors
podman logs local-ai-SERVICE --tail 100 | grep -i error

# Restart service
podman restart local-ai-SERVICE
```

### 2. Qdrant Search Not Working

**Symptoms**: Empty results, low scores, errors

```bash
# Check collections exist
curl http://localhost:6333/collections | jq

# Check collection health
curl http://localhost:6333/collections/error-solutions | jq

# Verify points in collection
curl http://localhost:6333/collections/error-solutions | jq '.result.points_count'

# Re-initialize if empty
./scripts/setup-hybrid-learning-auto.sh
```

### 3. llama.cpp Model Not Loading

**Symptoms**: Slow responses, model download errors

```bash
# Check model download progress
podman logs local-ai-llama-cpp | grep -i "download"

# Check available disk space
df -h ~/.local/share/nixos-ai-stack/llama-cpp-models/

# Model download can take 10-45 minutes on first start
# Be patient!
```

### 4. NixOS Build Failures

**Symptoms**: nixos-rebuild fails, syntax errors

```bash
# Check syntax
nix-instantiate --parse templates/configuration.nix

# Test build without switching
sudo nixos-rebuild build

# View full error
sudo nixos-rebuild switch 2>&1 | tee build.log

# Rollback if needed
sudo nixos-rebuild switch --rollback
```

### 5. Python Package Issues

**Symptoms**: ImportError, ModuleNotFoundError

```bash
# NixOS requires virtual environments
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Never use: pip install --user  # ❌ Won't work on NixOS!
```

---

## Debugging Tools

### System Logs

```bash
# All errors last hour
journalctl -p err --since "1 hour ago"

# Specific service
journalctl -u docker -n 100

# Follow live
journalctl -f

# Boot logs
journalctl -b
```

### Container Debugging

```bash
# Inspect container
podman inspect local-ai-SERVICE | jq

# Environment variables
podman inspect local-ai-SERVICE --format '{{.Config.Env}}'

# Network
podman inspect local-ai-SERVICE --format '{{.NetworkSettings.Ports}}'

# Shell access
podman exec -it local-ai-SERVICE /bin/sh
```

### Network Debugging

```bash
# Check port listening
ss -tlnp | grep PORT

# Test connection
curl -v http://localhost:6333/healthz

# DNS resolution
nslookup localhost

# Container networking
podman network inspect local-ai
```

### Database Debugging

```bash
# PostgreSQL
podman exec local-ai-postgres pg_isready -U mcp
podman exec local-ai-postgres psql -U mcp -d mcp -c '\l'

# Redis
podman exec local-ai-redis redis-cli ping
podman exec local-ai-redis redis-cli INFO

# Qdrant
curl http://localhost:6333/healthz
curl http://localhost:6333/collections | jq
```

---

## Error Patterns

### Read-only Filesystem

**Error**: `OSError: [Errno 30] Read-only file system`

**Cause**: Trying to modify /nix/store (immutable on NixOS)

**Fix**: Use virtual environment for Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install PACKAGE
```

### Port Already in Use

**Error**: `bind: address already in use`

**Cause**: Another process using the port

**Fix**: Find and stop conflicting service
```bash
lsof -i :PORT
kill -9 PID
# Or change port in docker-compose.yml
```

### Collection Not Found

**Error**: `Collection 'name' not found`

**Cause**: Qdrant collections not initialized

**Fix**: Re-run initialization
```bash
./scripts/setup-hybrid-learning-auto.sh
```

### NVIDIA Driver Issues

**Error**: `could not select device driver`

**Cause**: GPU not available or drivers not loaded

**Fix**: Check drivers and configuration
```bash
nvidia-smi  # Should show GPU
# Add to configuration.nix:
# services.xserver.videoDrivers = [ "nvidia" ];
```

---

## Performance Debugging

### Slow Queries

```bash
# Check resource usage
podman stats --no-stream

# Check disk I/O
iostat -x 1 5

# Check network
nethogs

# Profile query
time curl -X POST http://localhost:6333/search ...
```

### High Memory Usage

```bash
# Check container memory
podman stats local-ai-llama-cpp

# Redis memory
podman exec local-ai-redis redis-cli INFO memory

# Adjust limits in docker-compose.yml if needed
```

---

## Recovery Procedures

### Nuclear Option: Full Reset

```bash
# Stop everything
./scripts/hybrid-ai-stack.sh down

# Remove containers (keeps data)
podman rm -f $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")

# Start fresh
./scripts/hybrid-ai-stack.sh up
```

### Data Recovery

```bash
# Restore from backup
tar -xzf ai-stack-backup-DATE.tar.gz -C ~/.local/share/

# Restart services
./scripts/hybrid-ai-stack.sh restart
```

### System Recovery

```bash
# Rollback NixOS
sudo nixos-rebuild switch --rollback

# Home Manager rollback (activate prior generation manually)
home-manager generations
```

---

## Logging Best Practices

### Enable Debug Logging

```bash
# In .env file
LLAMA_CPP_LOG_LEVEL=debug

# Restart to apply
./scripts/hybrid-ai-stack.sh restart
```

### Centralized Logging

```bash
# Export all logs
./scripts/hybrid-ai-stack.sh logs > all-logs-$(date +%Y%m%d-%H%M%S).txt

# Search all logs
./scripts/hybrid-ai-stack.sh logs | grep "error\|fail\|exception" -i
```

---

## Next Steps

- [Service Status](02-SERVICE-STATUS.md) - Health monitoring
- [Container Management](11-CONTAINER-MGMT.md) - Container operations
- [Error Logging](32-ERROR-LOGGING.md) - Store errors for learning
