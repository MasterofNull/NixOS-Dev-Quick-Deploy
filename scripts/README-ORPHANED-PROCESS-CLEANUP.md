# Orphaned Process Cleanup

## Problem Statement

When AI stack containers using `network_mode: host` crash or are forcibly stopped, their processes can sometimes survive outside the container context. These **orphaned processes** continue to hold ports, preventing new containers from binding to the same ports.

### Symptoms

- Containers stuck in crash loops with "address already in use" errors
- High restart counts (50-100+) for containers like aidb and open-webui
- `lsof -i:PORT` shows processes with old timestamps (e.g., from previous day)
- No logs from containers because they crash before logging starts

### Root Cause

The `network_mode: host` setting allows containers to share the host's network namespace. When containers crash:
1. The container process tree may not be fully cleaned up
2. Child processes (Python servers, daemons) can persist
3. These processes hold onto TCP ports
4. New container instances cannot bind to the same ports
5. Container restart policy causes infinite crash loop

## Solution

We've implemented **three layers of protection** against orphaned processes:

### Layer 1: Enhanced Stop Script

**File:** [`scripts/stop-ai-stack.sh`](./stop-ai-stack.sh)

Enhanced to kill orphaned processes by:
- **Port-based cleanup**: Checks all AI stack ports (8091, 8791, 8092, 8094, 3001, 8098) and kills processes
- **Pattern-based cleanup**: Kills processes matching AI stack patterns (server.py, uvicorn, daemons)
- **Verification**: Confirms all ports are free before exiting

**Usage:**
```bash
./scripts/stop-ai-stack.sh
```

### Layer 2: Smart Start Script

**File:** [`scripts/start-ai-stack-and-dashboard.sh`](./start-ai-stack-and-dashboard.sh)

Enhanced pre-flight checks that:
- **Detect orphaned processes**: Scans AI stack ports for suspicious processes
- **Automatic cleanup**: Calls stop-ai-stack.sh if orphans detected
- **Graceful handling**: Warns user but continues if cleanup succeeds

**No user action required** - cleanup happens automatically!

### Layer 3: Standalone Cleanup Utility

**File:** [`scripts/cleanup-orphaned-ai-processes.sh`](./cleanup-orphaned-ai-processes.sh)

Comprehensive cleanup utility that:
- Checks all AI stack ports for orphaned processes
- Identifies processes by pattern matching (server.py, daemons, etc.)
- Verifies processes are NOT in containers (checks cgroup)
- Provides detailed reporting of what was killed
- Returns exit code 0 if all ports clear, 1 if issues remain

**Usage:**
```bash
# Manual cleanup
./scripts/cleanup-orphaned-ai-processes.sh

# Check status only (dry run)
./scripts/cleanup-orphaned-ai-processes.sh --dry-run  # TODO: implement
```

**Example Output:**
```
ℹ Scanning for orphaned AI stack processes...
⚠ Found orphaned aidb-http process on port 8091
    PID: 1328823
    Command: python3 -u /app/server.py --config /app/config/config.yaml
✓ Killed orphaned process 1328823
⚠ Found orphaned open-webui process on port 3001
    PID: 95306
    Command: /usr/local/bin/python3 -m uvicorn open_webui.main:app --host 0.0.0.0 --port 3001
✓ Killed orphaned process 95306

=== Cleanup Summary ===
Processes killed: 2
✓ All AI stack ports are free
```

## Systemd Integration

### Option A: Traditional Systemd Service

**File:** [`templates/systemd/ai-stack-cleanup.service`](../templates/systemd/ai-stack-cleanup.service)

**Install:**
```bash
# Copy service file
sudo cp templates/systemd/ai-stack-cleanup.service /etc/systemd/system/

# Update ExecStart path if needed
sudo nano /etc/systemd/system/ai-stack-cleanup.service

# Enable and start
sudo systemctl enable ai-stack-cleanup.service
sudo systemctl start ai-stack-cleanup.service

# Check status
sudo systemctl status ai-stack-cleanup.service
```

The service runs **once on boot** before podman.service starts, ensuring clean slate.

### Option B: NixOS Declarative Module

**File:** [`templates/nixos-improvements/ai-stack-cleanup.nix`](../templates/nixos-improvements/ai-stack-cleanup.nix)

**Install:**
```nix
# In your configuration.nix
{
  imports = [
    ./templates/nixos-improvements/ai-stack-cleanup.nix
  ];

  services.ai-stack-cleanup = {
    enable = true;           # Enable the cleanup service
    onBoot = true;           # Run on system boot (default)
    onShutdown = false;      # Optionally run on shutdown to prevent orphans
  };
}
```

**Rebuild:**
```bash
sudo nixos-rebuild switch
```

**Benefits:**
- Fully declarative configuration
- Automatic dependency management
- Security hardening built-in
- Integration with NixOS service management

## AI Stack Ports Reference

The cleanup scripts monitor these ports:

| Port  | Service              | Protocol | Notes                    |
|-------|---------------------|----------|--------------------------|
| 8091  | aidb HTTP           | HTTP     | Main MCP API             |
| 8791  | aidb WebSocket      | WS       | Real-time connections    |
| 8092  | hybrid-coordinator  | HTTP     | Hybrid learning API      |
| 8094  | nixos-docs          | HTTP     | Documentation server     |
| 3001  | open-webui          | HTTP     | Web interface            |
| 8098  | ralph-wiggum        | HTTP     | Loop orchestrator        |
| 6333  | qdrant              | HTTP     | Vector database          |
| 8080  | llama.cpp           | HTTP     | LLM inference            |
| 5432  | postgres            | TCP      | Database                 |
| 6379  | redis               | TCP      | Cache                    |
| 47334 | mindsdb             | HTTP     | Analytics                |

## Process Patterns Monitored

The cleanup scripts identify AI stack processes by these patterns:

- `server.py --config` - AIDB and coordinator servers
- `start_with_discovery.sh` - AIDB startup script
- `start_with_learning.sh` - Hybrid coordinator startup
- `tool_discovery_daemon.py` - AIDB tool discovery
- `continuous_learning_daemon.py` - Hybrid learning daemon
- `self_healing_daemon.py` - Health monitor daemon
- `uvicorn.*open_webui.main:app.*3001` - Open WebUI server
- `ralph.*server.py` - Ralph Wiggum orchestrator

## Troubleshooting

### Cleanup Script Reports Ports Still In Use

**Check what's using the port:**
```bash
lsof -i:8091
sudo ss -tulpn | grep :8091
```

**If it's a legitimate container:**
- The container is running normally - no action needed
- Cleanup script only kills orphaned host processes, not container processes

**If it's a stubborn orphaned process:**
```bash
# Force kill
sudo kill -9 $(lsof -ti:8091)

# Verify it's gone
lsof -i:8091
```

### Container Still Crash Loops After Cleanup

**Check container logs for different error:**
```bash
podman logs local-ai-aidb 2>&1 | tail -50
```

**Common issues:**
- Database connection failed (check postgres is healthy)
- Missing environment variables
- Volume permission issues

### Cleanup Script Fails with Permission Denied

**Run as root or with sudo:**
```bash
sudo ./scripts/cleanup-orphaned-ai-processes.sh
```

The script needs root privileges to:
- Kill processes owned by other users
- Access /proc filesystem
- Read all network sockets

## Integration with CI/CD

Add cleanup as a pre-deployment step:

```yaml
# .github/workflows/deploy.yml
- name: Cleanup orphaned processes
  run: |
    sudo ./scripts/cleanup-orphaned-ai-processes.sh || true

- name: Deploy AI stack
  run: |
    ./scripts/start-ai-stack-and-dashboard.sh
```

## Prevention Best Practices

1. **Use stop script before deploys:**
   ```bash
   ./scripts/stop-ai-stack.sh
   ./scripts/start-ai-stack-and-dashboard.sh
   ```

2. **Enable systemd service for boot cleanup:**
   - Prevents issues after unexpected power loss
   - Ensures clean state before containers start

3. **Monitor for orphaned processes:**
   ```bash
   # Add to cron or systemd timer
   0 */6 * * * /path/to/cleanup-orphaned-ai-processes.sh
   ```

4. **Consider switching from host to bridge networking:**
   - Prevents orphaned processes entirely
   - Better isolation
   - Requires port mapping updates

## Related Issues

This cleanup system resolves:
- [#1] Container crash loops with "address already in use"
- [#2] High restart counts (50-100+)
- [#3] Dashboard showing low health percentage
- [#4] nixos-quick-deploy script hanging during deployment

## Credits

Implemented as part of session 2026-01-02 healthcheck fixes.
Root cause analysis and solution documented in database report ID 1.
