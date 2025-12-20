# Service Status Checking

**Purpose**: Check what's running, troubleshoot issues, verify health

---

## Quick Status Check

```bash
# All-in-one status check
./scripts/hybrid-ai-stack.sh status
```

Output shows:
- Container status (running/stopped)
- Port mappings
- Health check results
- Quick fix suggestions

---

## Individual Service Checks

### Qdrant Vector Database

```bash
# HTTP health check
curl http://localhost:6333/healthz

# Check collections
curl http://localhost:6333/collections | jq '.result.collections[].name'

# Collection details
curl http://localhost:6333/collections/error-solutions | jq

# Container status
podman ps --filter "name=local-ai-qdrant"

# Logs
podman logs local-ai-qdrant --tail 50
```

**Expected Response**:
```json
{
  "title": "healthz OK",
  "version": "1.x.x"
}
```

### Ollama (Embeddings)

```bash
# API check
curl http://localhost:11434/api/tags

# List models
podman exec local-ai-ollama ollama list

# Test embedding generation
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "nomic-embed-text", "prompt": "test"}' | jq

# Container logs
podman logs local-ai-ollama --tail 50
```

**Expected Models**:
- nomic-embed-text (384 dimensions)

### Lemonade (GGUF Inference)

```bash
# Health check
curl http://localhost:8080/health

# Model info
curl http://localhost:8080/v1/models | jq

# Test completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-coder",
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 10
  }' | jq

# Check model download progress
podman logs local-ai-lemonade | grep -i download

# Container status
podman ps --filter "name=local-ai-lemonade"
```

**Common States**:
- `Downloading model...` - First time, wait 10-45 min
- `Model loaded` - Ready for inference
- `Health: OK` - Fully operational

### Open WebUI

```bash
# HTTP check
curl -I http://localhost:3000

# Access in browser
firefox http://localhost:3000

# Container logs
podman logs local-ai-open-webui --tail 50

# Check data directory
ls -lh ~/.local/share/nixos-ai-stack/open-webui/
```

### PostgreSQL (MCP Database)

```bash
# Connection check
podman exec local-ai-postgres pg_isready -U mcp

# List databases
podman exec local-ai-postgres psql -U mcp -c '\l'

# Connection test
podman exec local-ai-postgres psql -U mcp -d mcp -c 'SELECT version();'

# Check tables
podman exec local-ai-postgres psql -U mcp -d mcp -c '\dt'

# Container logs
podman logs local-ai-postgres --tail 50
```

### Redis (Cache)

```bash
# Ping test
podman exec local-ai-redis redis-cli ping

# Check memory usage
podman exec local-ai-redis redis-cli INFO memory | grep used_memory_human

# Check key count
podman exec local-ai-redis redis-cli DBSIZE

# Monitor operations
podman exec local-ai-redis redis-cli MONITOR

# Container logs
podman logs local-ai-redis --tail 50
```

---

## Container Management

### List All AI Stack Containers

```bash
# All containers with status
podman ps -a --filter "label=nixos.quick-deploy.ai-stack=true"

# Only running
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# With formatting
podman ps --filter "label=nixos.quick-deploy.ai-stack=true" \
  --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Resource Usage

```bash
# CPU and memory usage
podman stats --no-stream --filter "label=nixos.quick-deploy.ai-stack=true"

# Disk usage
podman system df

# Specific container stats
podman stats local-ai-lemonade --no-stream
```

### Restart Containers

```bash
# Restart all
./scripts/hybrid-ai-stack.sh restart

# Restart specific service
podman restart local-ai-qdrant

# Restart multiple
podman restart local-ai-qdrant local-ai-ollama
```

---

## Health Check Automation

### Python Health Check Script

```python
#!/usr/bin/env python3
import requests
import sys

services = {
    "Qdrant": "http://localhost:6333/healthz",
    "Ollama": "http://localhost:11434/api/tags",
    "Lemonade": "http://localhost:8080/health",
    "Open WebUI": "http://localhost:3000",
}

all_healthy = True

for name, url in services.items():
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ {name}: OK")
        else:
            print(f"✗ {name}: HTTP {response.status_code}")
            all_healthy = False
    except Exception as e:
        print(f"✗ {name}: {e}")
        all_healthy = False

sys.exit(0 if all_healthy else 1)
```

Save as `check-health.py` and run:
```bash
python3 check-health.py
```

### Bash Health Check

```bash
#!/usr/bin/env bash

check_service() {
    local name=$1
    local url=$2

    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo "✓ $name: OK"
        return 0
    else
        echo "✗ $name: FAILED"
        return 1
    fi
}

check_service "Qdrant" "http://localhost:6333/healthz"
check_service "Ollama" "http://localhost:11434/api/tags"
check_service "Lemonade" "http://localhost:8080/health"
check_service "Open WebUI" "http://localhost:3000"
```

---

## Common Issues & Diagnostics

### Service Not Responding

```bash
# Check if container is running
podman ps --filter "name=local-ai-SERVICE"

# If not running, check why it stopped
podman ps -a --filter "name=local-ai-SERVICE"

# View recent logs
podman logs local-ai-SERVICE --tail 100

# Check for port conflicts
ss -tlnp | grep PORT_NUMBER

# Restart service
podman restart local-ai-SERVICE
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :6333

# Or with ss
ss -tlnp | grep 6333

# Kill the process (if safe)
kill -9 PID

# Or change port in docker-compose.yml
```

### Container Crashes on Startup

```bash
# View full logs
podman logs local-ai-SERVICE

# Check exit code
podman inspect local-ai-SERVICE | jq '.[0].State'

# Common causes:
# - Missing volumes: Check ~/.local/share/nixos-ai-stack/
# - Permission errors: Check ownership
# - Resource limits: Check available RAM/disk

# Fix permissions
sudo chown -R $USER:$USER ~/.local/share/nixos-ai-stack/
```

### Qdrant Collections Missing

```bash
# Check what collections exist
curl http://localhost:6333/collections | jq '.result.collections[].name'

# Re-create collections (see 01-QUICK-START.md)
# Or run automated setup
./scripts/setup-hybrid-learning-auto.sh
```

### Slow Performance

```bash
# Check resource usage
podman stats --no-stream

# Check disk I/O
iostat -x 1 5

# Check if models still downloading
podman logs local-ai-lemonade | grep -i download

# Check GPU usage (if available)
nvidia-smi
```

---

## Monitoring Dashboard

Access the unified dashboard:

```bash
firefox ai-stack/dashboard/index.html
```

Dashboard provides:
- Real-time health checks (every 30s)
- Service endpoint links
- Learning metrics
- Quick troubleshooting links

---

## Log Analysis

### View All Logs

```bash
# All services, last 100 lines each
./scripts/hybrid-ai-stack.sh logs

# Follow logs in real-time
./scripts/hybrid-ai-stack.sh logs -f
```

### Search Logs for Errors

```bash
# Search for errors across all services
for container in $(podman ps --filter "label=nixos.quick-deploy.ai-stack=true" --format "{{.Names}}"); do
    echo "=== $container ==="
    podman logs $container 2>&1 | grep -i error | tail -10
done
```

### Export Logs for Debugging

```bash
# Export all logs to file
./scripts/hybrid-ai-stack.sh logs > ai-stack-logs-$(date +%Y%m%d-%H%M%S).txt

# Export with timestamps
./scripts/hybrid-ai-stack.sh logs -t > logs.txt
```

---

## Performance Metrics

### Qdrant Performance

```bash
# Collection stats
curl http://localhost:6333/collections/error-solutions | jq '.result'

# Shows:
# - vectors_count
# - indexed_vectors_count
# - points_count
# - segments_count
```

### Database Size

```bash
# PostgreSQL size
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c "SELECT pg_size_pretty(pg_database_size('mcp'));"

# Redis memory
podman exec local-ai-redis redis-cli INFO memory | grep used_memory_human
```

### Disk Usage

```bash
# All AI stack data
du -sh ~/.local/share/nixos-ai-stack/

# By service
du -sh ~/.local/share/nixos-ai-stack/*
```

---

## Next Steps

- **Fix issues**: [Debugging Guide](12-DEBUGGING.md)
- **Optimize performance**: [Hybrid Workflow](40-HYBRID-WORKFLOW.md)
- **Understand logs**: [Error Logging](32-ERROR-LOGGING.md)
- **Database operations**: [Qdrant Guide](30-QDRANT-OPERATIONS.md)
