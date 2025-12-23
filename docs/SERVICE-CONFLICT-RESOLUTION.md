# Service Conflict Resolution

## Overview

The NixOS Quick Deploy script now automatically detects and resolves conflicts between system-level and user-level services during deployment. This prevents port conflicts and service failures when the same service (e.g., llama.cpp, Qdrant) is configured at both levels.

## Problem Statement

When deploying with home-manager, you may encounter service conflicts like:

```
Error: rootlessport listen tcp 0.0.0.0:6333: bind: address already in use
```

This happens when:
1. **System-level service** (e.g., `llama-cpp.service`) is running as root
2. **User-level service** (e.g., `podman-local-ai-llama-cpp.service`) tries to use the same port
3. Both services attempt to bind to the same network port simultaneously

## Solution: Automatic Conflict Resolution

The deployment script (Phase 5) now includes automatic conflict detection and resolution **before** applying home-manager configuration.

### How It Works

1. **Detection Phase** (Step 6.5)
   - Scans for active system-level services (llama.cpp, qdrant, etc.)
   - Checks if corresponding user-level services are enabled in `home.nix`
   - Identifies port conflicts

2. **Resolution Phase**
   - Automatically disables conflicting system services
   - Allows user-level services to start cleanly
   - Logs all actions taken

3. **Deployment Continues**
   - Home-manager configuration applied without conflicts
   - User-level services start successfully
   - No manual intervention required

## Configuration

### Automatic Resolution (Default)

By default, the script automatically resolves conflicts by disabling system services:

```bash
AUTO_RESOLVE_SERVICE_CONFLICTS=true  # Default in config/variables.sh
```

### Manual Resolution

To handle conflicts manually:

```bash
AUTO_RESOLVE_SERVICE_CONFLICTS=false ./nixos-quick-deploy.sh
```

When manual mode is enabled, the script will:
1. Detect conflicts
2. Ask for confirmation before resolving
3. Provide manual resolution instructions if declined

## Conflict Resolution Strategies

### Strategy 1: Disable System Services (Recommended)

**Best for:** Development, single-user systems, declarative management

```bash
# Automatic (happens during deployment)
sudo systemctl disable --now ollama.service
sudo systemctl disable --now qdrant.service
```

**Advantages:**
- ✅ User-level services (rootless containers)
- ✅ Managed declaratively via home-manager
- ✅ No root privileges needed for management
- ✅ Version controlled configuration

### Strategy 2: Disable User Services

**Best for:** Shared systems, production deployments

Edit `~/.dotfiles/home-manager/home.nix`:

```nix
localAiStackEnabled = false;  # Disable user-level AI stack
```

**Advantages:**
- ✅ System-wide service availability
- ✅ Centralized management
- ✅ Better for multi-user systems

### Strategy 3: Change Ports

**Best for:** Testing, running both simultaneously

Edit `~/.dotfiles/home-manager/home.nix`:

```nix
  ollamaPort = 11435;      # Changed from 11434
  qdrantHttpPort = 6335;   # Changed from 6333
  qdrantGrpcPort = 6336;   # Changed from 6334
```

**Advantages:**
- ✅ Run both system and user services
- ✅ Test migrations
- ⚠️ Requires updating client configurations

## Service Conflict Map

The following services are monitored for conflicts:

| System Service | User Service | Ports |
|----------------|--------------|-------|
| `ollama.service` | `podman-local-ai-ollama.service` | 11434 |
| `qdrant.service` | `podman-local-ai-qdrant.service` | 6333, 6334 |

Additional services can be added in `lib/service-conflict-resolution.sh`.

## Manual Conflict Resolution

If you need to manually resolve conflicts:

### Check for Conflicts

```bash
# Check system services
sudo systemctl status ollama.service
sudo systemctl status qdrant.service

# Check user services
systemctl --user status podman-local-ai-ollama.service
systemctl --user status podman-local-ai-qdrant.service

# Check port usage
ss -tlnp | grep -E ':(6333|6334|11434)'
```

### Disable System Services

```bash
# Stop and disable system-level AI services
sudo systemctl stop ollama.service qdrant.service
sudo systemctl disable ollama.service qdrant.service
```

### Disable User Services

```bash
# Edit home.nix
nano ~/.dotfiles/home-manager/home.nix

# Set:
localAiStackEnabled = false;

# Apply
home-manager switch --flake ~/.dotfiles/home-manager#hyperd
```

### Restart After Resolution

```bash
# If using user-level services
systemctl --user start podman-local-ai-network.service
systemctl --user start podman-local-ai-ollama.service
systemctl --user start podman-local-ai-qdrant.service
systemctl --user start podman-local-ai-open-webui.service
systemctl --user start podman-local-ai-mindsdb.service
```

## Integration with nixos-quick-deploy.sh

The conflict resolution is integrated into Phase 5 (Declarative Deployment):

```
Phase 5: Declarative Deployment
├── Step 6.1: Check for nix-env packages
├── Step 6.2: Final deployment confirmation
├── Step 6.3: Remove ALL nix-env packages
├── Step 6.4: Update flake inputs
├── Step 6.5: Service Conflict Detection & Resolution ← NEW
├── Step 6.6: Prepare home manager targets
├── Step 6.7: Apply home manager configuration
├── Step 6.8: Configure Flatpak remotes
└── Step 6.9: Apply NixOS system configuration
```

The conflict check runs **before** home-manager configuration is applied, ensuring:
- No service start failures during deployment
- Clean transition from system to user services
- Proper error handling and rollback capability

## Logging and Debugging

### View Conflict Detection Logs

```bash
# During deployment
tail -f ~/.cache/nixos-quick-deploy/logs/deploy-*.log

# Check service status after deployment
systemctl --user status podman-local-ai-ollama.service
journalctl --user -u podman-local-ai-ollama.service -n 50
```

### Generate Conflict Report

```bash
# Source the library manually
source /path/to/lib/service-conflict-resolution.sh

# Generate report
generate_conflict_report /tmp/conflict-report.txt
cat /tmp/conflict-report.txt
```

## Troubleshooting

### Issue: Services Still Conflicting After Deployment

**Solution:**
```bash
# Verify system services are actually disabled
sudo systemctl is-enabled ollama.service  # Should show "disabled"
sudo systemctl is-active ollama.service   # Should show "inactive"

# If still enabled, manually disable
sudo systemctl disable --now ollama.service qdrant.service

# Restart user services
systemctl --user restart podman-local-ai-ollama.service
```

### Issue: Auto-Resolution Not Working

**Check:**
1. Verify library is loaded: `declare -F pre_home_manager_conflict_check`
2. Check configuration: `echo $AUTO_RESOLVE_SERVICE_CONFLICTS`
3. Review deployment logs for errors

### Issue: Need to Switch Back to System Services

```bash
# Re-enable system services
sudo systemctl enable --now ollama.service qdrant.service

# Disable user services
# Edit home.nix: localAiStackEnabled = false
home-manager switch --flake ~/.dotfiles/home-manager#hyperd
```

## Best Practices

1. **Choose One Deployment Model**
   - Either system-level OR user-level, not both
   - User-level recommended for development

2. **Keep Configuration Declarative**
   - Set `localAiStackEnabled` appropriately in home.nix
   - Don't mix imperative and declarative service management

3. **Test After Deployment**
   - Verify services are running: `systemctl --user status podman-local-ai-*`
   - Test endpoints: `curl http://localhost:11434/api/tags`

4. **Monitor First Deployment**
   - Watch logs during initial deployment
   - Verify conflict resolution messages
   - Test all services after completion

## Related Documentation

- [Rootless Podman Guide](ROOTLESS_PODMAN.md)
- [Home Manager Integration](HOME_MANAGER.md)
- [Service Management](SERVICE_MANAGEMENT.md)

## References

- [service-conflict-resolution.sh](../lib/service-conflict-resolution.sh) - Implementation
- [phase-05-declarative-deployment.sh](../phases/phase-05-declarative-deployment.sh) - Integration point
- [home.nix](../templates/home.nix) - User service configuration
