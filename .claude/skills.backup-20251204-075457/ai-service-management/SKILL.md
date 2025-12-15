# Skill Name: ai-service-management

## Description
Control and manage local AI stack services including Ollama, Qdrant, MindsDB, Open WebUI, PostgreSQL, and Redis through a unified CLI interface.

## When to Use
- Starting/stopping AI services (Ollama, Qdrant, etc.)
- Checking status of AI stack components
- Viewing logs for troubleshooting
- Restarting services after configuration changes
- Managing the local AI development environment
- Monitoring AI service health

## Prerequisites
- NixOS system with AI stack deployed
- Systemd user services configured
- Podman containers for AI services
- Network access (local-ai network)

## Usage

### Start All AI Services
```bash
ai-servicectl start all
```

Starts all AI stack services in order:
1. Network (local-ai)
2. Ollama (LLM inference)
3. Qdrant (vector database)
4. MindsDB (ML orchestration)
5. Open WebUI (chat interface)

### Check Status of All Services
```bash
ai-servicectl status all
```

Shows running status for each service with color-coded indicators.

### Stop All Services
```bash
ai-servicectl stop all
```

Stops all AI services in reverse order.

### Restart All Services
```bash
ai-servicectl restart all
```

Restarts all services (useful after configuration changes).

### Manage Individual Services
```bash
# Start specific service
ai-servicectl start ollama

# Stop specific service
ai-servicectl stop qdrant

# Restart specific service
ai-servicectl restart mindsdb

# Check status of specific service
ai-servicectl status webui
```

### View Service Logs
```bash
# View logs (live tail)
ai-servicectl logs ollama

# Press Ctrl+C to exit

# View logs for specific service
ai-servicectl logs qdrant
ai-servicectl logs mindsdb
ai-servicectl logs webui
```

## Command-Line Options

```
ai-servicectl <command> [service|all]

COMMANDS:
    start       Start service(s)
    stop        Stop service(s)
    restart     Restart service(s)
    status      Show service status
    logs        Show service logs (live tail)

SERVICES:
    network     Podman network for AI stack
    ollama      Ollama LLM inference
    qdrant      Qdrant vector database
    mindsdb     MindsDB orchestration
    webui       Open WebUI interface
    all         All services
```

## Output Interpretation

### Success Indicators
- ✓ **Green checkmarks**: Service started/stopped successfully
- **"running"** (green): Service is active
- **Access points displayed**: URLs for each service

### Error Messages
- ✗ **Red crosses**: Operation failed
- **"stopped"** (red): Service is not running
- **"Failed to start"**: Check logs with `ai-servicectl logs <service>`

### Status Output Example
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI Service Control - status all services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Network: running
✓ Ollama: running
✓ Qdrant: running
✓ MindsDB: running
✓ Open WebUI: running

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Access points:
  • Ollama API:    http://localhost:11434
  • Open WebUI:    http://localhost:8081
  • Qdrant:        http://localhost:6333
  • MindsDB:       http://localhost:7735
```

## Service Ports

- **Ollama API**: http://localhost:11434
- **Open WebUI**: http://localhost:8081
- **Qdrant HTTP**: http://localhost:6333
- **Qdrant gRPC**: localhost:6334
- **MindsDB API**: localhost:47334
- **MindsDB GUI**: http://localhost:7735

## Related Skills
- `nixos-deployment`: Deploy NixOS system with AI stack
- `health-monitoring`: Validate system and service health
- `ai-model-management`: Manage AI models and downloads
- `mcp-database-setup`: Setup MCP server databases

## MCP Integration

This skill integrates with the AIDB MCP Server for:
- Service status monitoring
- Uptime tracking
- Error alerting
- Performance metrics

## Examples

### Example 1: Start AI Stack for Development

**Scenario**: Beginning work session, need to start all AI services.

```bash
# Start all services
ai-servicectl start all

# Output:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI Service Control - start all services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ▶ Starting podman-local-ai-network...
# ✓ podman-local-ai-network started
# ▶ Starting podman-local-ai-ollama...
# ✓ podman-local-ai-ollama started
# ▶ Starting podman-local-ai-qdrant...
# ✓ podman-local-ai-qdrant started
# ▶ Starting podman-local-ai-mindsdb...
# ✓ podman-local-ai-mindsdb started
# ▶ Starting podman-local-ai-open-webui...
# ✓ podman-local-ai-open-webui started

# Verify with status check
ai-servicectl status all

# Result: All services running, ready for development
```

### Example 2: Troubleshoot Ollama Service

**Scenario**: Ollama not responding, need to investigate.

```bash
# Check current status
ai-servicectl status ollama

# Output:
# ✗ Ollama: stopped

# View logs to diagnose
ai-servicectl logs ollama

# Output shows:
# Error: CUDA not available
# Falling back to CPU mode

# Restart service
ai-servicectl restart ollama

# Verify fix
curl http://localhost:11434/api/tags

# Result: Service restarted, issue resolved
```

### Example 3: Stop Services to Save Resources

**Scenario**: Done with AI development, want to free up system resources.

```bash
# Stop all AI services
ai-servicectl stop all

# Output:
# ▶ Stopping podman-local-ai-open-webui...
# ✓ podman-local-ai-open-webui stopped
# ▶ Stopping podman-local-ai-mindsdb...
# ✓ podman-local-ai-mindsdb stopped
# ▶ Stopping podman-local-ai-qdrant...
# ✓ podman-local-ai-qdrant stopped
# ▶ Stopping podman-local-ai-ollama...
# ✓ podman-local-ai-ollama stopped
# ▶ Stopping podman-local-ai-network...
# ✓ podman-local-ai-network stopped

# Verify all stopped
ai-servicectl status all

# Output shows all services "stopped" (red)

# Result: All services stopped, resources freed
```

### Example 4: Monitor Qdrant During Heavy Workload

**Scenario**: Running large vector search operations, want to monitor Qdrant logs.

```bash
# Start log monitoring (live tail)
ai-servicectl logs qdrant

# Output (live stream):
# 2025-11-22 10:05:23 INFO  [qdrant] Collection created: embeddings
# 2025-11-22 10:05:24 INFO  [qdrant] Indexing 10000 vectors...
# 2025-11-22 10:05:30 INFO  [qdrant] Indexing complete
# 2025-11-22 10:05:31 INFO  [qdrant] Search query: dimension=384, limit=10
# 2025-11-22 10:05:31 INFO  [qdrant] Search completed in 45ms
# ...
# (Press Ctrl+C to exit)

# Result: Real-time monitoring of vector operations
```

### Example 5: Restart Services After Configuration Change

**Scenario**: Updated Ollama model configuration, need to apply changes.

```bash
# Check current running services
ai-servicectl status all

# Edit Ollama configuration (example)
vim ~/.config/ollama/config.json

# Restart Ollama to apply changes
ai-servicectl restart ollama

# Output:
# ▶ Restarting podman-local-ai-ollama...
# ✓ podman-local-ai-ollama restarted

# Verify configuration applied
curl http://localhost:11434/api/tags | jq .

# Result: New configuration active
```

## Advanced Usage

### Check Systemd Service Status Directly
```bash
# Detailed status for specific service
systemctl --user status podman-local-ai-ollama

# View full service logs
journalctl --user -u podman-local-ai-ollama -f
```

### Manage Container Directly with Podman
```bash
# List all AI containers
podman ps --filter label=nixos.quick-deploy.ai-stack=true

# Inspect container
podman inspect local-ai-ollama

# View container logs
podman logs local-ai-ollama

# Execute command in container
podman exec -it local-ai-ollama bash
```

### Network Troubleshooting
```bash
# Check if local-ai network exists
podman network ls | grep local-ai

# Inspect network
podman network inspect local-ai

# Test connectivity between containers
podman exec local-ai-ollama ping -c 3 local-ai-qdrant
```

## Common Issues and Solutions

### Issue: "Service failed to start"
```bash
# Check system logs
journalctl --user -xe

# Check if port is already in use
sudo netstat -tlnp | grep 11434  # Ollama port

# Stop conflicting service
sudo systemctl stop conflicting-service

# Retry
ai-servicectl start ollama
```

### Issue: "Container already exists"
```bash
# Remove stale container
podman rm -f local-ai-ollama

# Restart service
ai-servicectl start ollama
```

### Issue: "Network not found"
```bash
# Recreate network
podman network create local-ai

# Restart all services
ai-servicectl restart all
```

### Issue: "Out of memory"
```bash
# Check container memory usage
podman stats

# Stop unused services to free memory
ai-servicectl stop mindsdb

# Allocate more memory to container (edit service file)
vim ~/.config/systemd/user/podman-local-ai-ollama.service
# Add: --memory=4g

# Reload and restart
systemctl --user daemon-reload
ai-servicectl restart ollama
```

## Performance Optimization

### Reduce Startup Time
```bash
# Enable systemd user lingering (start services at boot)
loginctl enable-linger $USER

# Enable specific services
systemctl --user enable podman-local-ai-ollama.service
systemctl --user enable podman-local-ai-qdrant.service
```

### Resource Limits
```bash
# Edit service file to add limits
vim ~/.config/systemd/user/podman-local-ai-ollama.service

# Add under [Service]:
CPUQuota=200%
MemoryLimit=4G

# Reload and restart
systemctl --user daemon-reload
ai-servicectl restart ollama
```

## Security Considerations

### Network Isolation
- All services run on isolated `local-ai` network
- Only exposed ports are accessible from host
- No external network access by default

### User-Level Services
- Services run as user (not root)
- No privileged containers
- Rootless Podman for additional security

### Access Control
- Services bind to localhost only
- No authentication by default (local development)
- Add authentication for production use

## Skill Metadata

- **Skill Version**: 1.0.0
- **Last Updated**: 2025-11-22
- **Compatibility**: OpenSkills 1.2.1+, NixOS 23.11+
- **MCP Integration**: Yes
- **Category**: ai-infrastructure
- **Tags**: ai-stack, ollama, qdrant, mindsdb, service-management, podman
