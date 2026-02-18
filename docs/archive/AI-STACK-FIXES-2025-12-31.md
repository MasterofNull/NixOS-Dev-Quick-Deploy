# AI Stack Fixes - December 31, 2025

## Issues Identified and Resolved

### 1. Container Dependency Errors

**Problem:**
```
Error: "local-ai-llama-cpp" is not a valid container, cannot be used as a dependency
Error: "local-ai-hybrid-coordinator" is not a valid container, cannot be used as a dependency
Error: no container with name or ID "local-ai-aider" found
Error: no container with name or ID "local-ai-autogpt" found
```

**Root Cause:**
- Services were configured with strict `depends_on` that referenced container names instead of service names
- Optional agent services (aider, autogpt, ralph-wiggum) were set as required dependencies
- Missing health check conditions caused race conditions during startup

**Fix Applied:**
Updated [ai-stack/compose/docker-compose.yml](/ai-stack/compose/docker-compose.yml):

1. **Changed dependency format** from simple list to condition-based:
   ```yaml
   # OLD (incorrect)
   depends_on:
     - postgres
     - redis
     - llama-cpp

   # NEW (correct)
   depends_on:
     postgres:
       condition: service_healthy
     redis:
       condition: service_healthy
     qdrant:
       condition: service_healthy
   ```

2. **Made agent services optional** using Docker Compose profiles:
   ```yaml
   aider:
     profiles: ["agents", "full"]  # Only start with --profile agents

   autogpt:
     profiles: ["agents", "full"]  # Only start with --profile agents

   ralph-wiggum:
     profiles: ["agents", "full"]  # Only start with --profile agents
   ```

3. **Removed llama-cpp dependency** from services using host networking (they connect via localhost:8080)

### 2. AutoGPT Container Symlink Conflict

**Problem:**
```
Error: unable to copy from docker://significantgravitas/auto-gpt:latest
symlink usr/bin /home/hyperd/.local/share/containers/storage/vfs/dir/.../bin: file exists
```

**Root Cause:**
- AutoGPT image has conflicting symlink structure that clashes with Podman's VFS storage
- Podman tries to create `/usr/bin` → `/bin` symlink but file already exists in layer

**Fix Applied:**
1. **Made AutoGPT optional** - moved to `agents` profile so it's not pulled by default
2. **Updated cleanup script** to remove problematic images before rebuild
3. **Added image cleanup** in [scripts/compose-clean-restart.sh](/scripts/compose-clean-restart.sh):
   ```bash
   if [[ " ${SERVICES[*]} " =~ " autogpt " ]]; then
       podman rmi -f $(podman images | grep -i auto-gpt | awk '{print $3}') 2>/dev/null || true
   fi
   ```

### 3. Service Startup Order Issues

**Problem:**
- Services starting before dependencies were ready
- No health checks to verify service availability
- Race conditions causing connection failures

**Fix Applied:**
Enhanced dependency management:
```yaml
aidb:
  depends_on:
    postgres:
      condition: service_healthy  # Wait for Postgres to be healthy
    redis:
      condition: service_healthy  # Wait for Redis to be healthy
    qdrant:
      condition: service_healthy  # Wait for Qdrant to be healthy
```

All core services now have proper health checks:
- **Qdrant**: HTTP endpoint on port 6333
- **PostgreSQL**: `pg_isready` check
- **Redis**: `redis-cli ping` check
- **llama.cpp**: HTTP health endpoint
- **AIDB**: HTTP health endpoint
- **Hybrid Coordinator**: HTTP health endpoint

## Service Architecture Changes

### Core Services (Always Started)
These run by default with `podman-compose up -d`:
- **Qdrant** - Vector database
- **PostgreSQL** - Primary database with pgvector
- **Redis** - Cache and session storage
- **MindsDB** - Analytics platform
- **AIDB** - MCP server for context and telemetry
- **Hybrid Coordinator** - Context augmentation and learning
- **Health Monitor** - Self-healing infrastructure
- **Open WebUI** - Web interface

### Optional Services (Use Profiles)
These require explicit profile activation:

#### Agent Profile (`--profile agents`)
- **Aider** - AI pair programming
- **AutoGPT** - Autonomous agent
- **Ralph Wiggum** - Continuous orchestration loop

#### llama.cpp (Optional Inference)
- Start separately: `podman-compose up -d llama-cpp`
- Not required for core stack to function
- Used only when local inference is needed

## Usage Commands

### Start Core Stack Only
```bash
cd ai-stack/compose
podman-compose up -d
```

### Start with Agent Services
```bash
cd ai-stack/compose
podman-compose --profile agents up -d
```

### Start Everything Including llama.cpp
```bash
cd ai-stack/compose
podman-compose up -d llama-cpp
podman-compose --profile agents up -d
```

### Clean Restart (Fixes Conflicts)
```bash
./scripts/compose-clean-restart.sh
```

### Restart Specific Service
```bash
./scripts/compose-clean-restart.sh aidb
./scripts/compose-clean-restart.sh hybrid-coordinator
```

## Testing and Validation

### Verify Core Services
```bash
# Check running containers
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# Check service health
curl http://localhost:6333/healthz  # Qdrant
curl http://localhost:8091/health   # AIDB
curl http://localhost:8092/health   # Hybrid Coordinator
```

### Verify Database Connectivity
```bash
# PostgreSQL
podman exec local-ai-postgres pg_isready -U mcp

# Redis
podman exec local-ai-redis redis-cli ping
```

### View Logs
```bash
# All services
podman-compose logs -f

# Specific service
podman-compose logs -f aidb
podman-compose logs -f hybrid-coordinator
```

## Files Modified

1. [ai-stack/compose/docker-compose.yml](/ai-stack/compose/docker-compose.yml)
   - Fixed all `depends_on` configurations
   - Added service profiles for optional components
   - Enhanced health check conditions

2. [scripts/compose-clean-restart.sh](/scripts/compose-clean-restart.sh)
   - Updated dependency detection logic
   - Added AutoGPT image cleanup
   - Enhanced service-specific handling

3. [scripts/hybrid-ai-stack.sh](/scripts/hybrid-ai-stack.sh)
   - Already correctly implemented
   - No changes needed

## Recommended Actions

### For Development
1. Use core stack only: `podman-compose up -d`
2. Add llama.cpp when needed: `podman-compose up -d llama-cpp`
3. Enable agents for testing: `podman-compose --profile agents up -d`

### For Production
1. Always use health check conditions
2. Monitor startup order with `podman-compose logs -f`
3. Use `./scripts/compose-clean-restart.sh` for clean restarts
4. Regularly prune unused images: `podman image prune -f`

### Troubleshooting

#### If containers fail to start:
```bash
# Clean restart everything
./scripts/compose-clean-restart.sh

# Or manually:
podman stop $(podman ps -q --filter "label=nixos.quick-deploy.ai-stack=true")
podman rm -f $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")
podman-compose up -d
```

#### If AutoGPT has symlink errors:
```bash
# Remove the image and rebuild
podman rmi -f $(podman images | grep auto-gpt | awk '{print $3}')
podman-compose --profile agents up -d autogpt
```

#### If services can't connect:
```bash
# Verify health of dependencies first
podman ps
podman inspect local-ai-postgres | grep -A 5 Health
podman inspect local-ai-redis | grep -A 5 Health
podman inspect local-ai-qdrant | grep -A 5 Health
```

## Summary

All identified errors have been resolved:
- ✅ Container dependency errors fixed with proper health check conditions
- ✅ AutoGPT symlink conflict avoided by making it optional
- ✅ Missing container errors eliminated by using service profiles
- ✅ Service startup order properly configured with `depends_on` conditions
- ✅ Enhanced cleanup scripts for manual intervention when needed

The AI stack now starts reliably with core services, and optional agent services can be enabled on-demand without breaking the base stack.
