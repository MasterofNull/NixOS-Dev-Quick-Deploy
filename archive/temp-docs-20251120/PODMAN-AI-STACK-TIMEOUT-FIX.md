# Podman AI Stack Timeout Fix - Complete Solution

## Problem Summary

User-level Podman AI stack services (Ollama, Open WebUI, Qdrant) were failing to start with timeout errors during deployment:

```
⚠ Failed to start podman-local-ai-ollama.service
⚠ Failed to start podman-local-ai-qdrant.service
⚠ Failed to start podman-local-ai-open-webui.service
```

## Root Causes

### 1. Registry Auto-Update During Startup
**Issue**: `autoUpdate = "registry"` caused Podman to pull images from registries on every service start, which exceeded the 90-second default timeout.

**Fix**: Changed to `autoUpdate = "local"` to use pre-pulled images.

### 2. Startup Timeout Too Short
**Issue**: Large containers (Ollama: 3.75GB, Open WebUI: 4.38GB) take longer than 90 seconds to start, even with local images.

**Fix**: Increased `TimeoutStartSec` to 300 seconds via systemd drop-ins.

### 3. Images Not Pre-Pulled
**Issue**: Images were pulled during `home-manager switch`, causing deployment timeouts.

**Fix**: Added image pre-pull step before home-manager switch.

### 4. File Conflicts During Home Manager Switch
**Issue**: `.npmrc.backup` and `settings.json.backup` prevented successful home-manager switch.

**Fix**: Added cleanup before switch with `-b backup` flag.

## Solutions Implemented

### Fix 1: Update Template home.nix (Permanent Fix)

**File**: `templates/home.nix`

Changed all four Podman containers from `autoUpdate = "registry"` to `autoUpdate = "local"`:

```nix
# Lines 3370, 3389, 3409, 3428
autoUpdate = "local";  # Use local images to avoid timeout during home-manager switch
```

**Containers Fixed**:
- `podman-local-ai-ollama` (line 3370)
- `podman-local-ai-open-webui` (line 3389)
- `podman-local-ai-qdrant` (line 3409)
- `podman-local-ai-mindsdb` (line 3428)

### Fix 2: Pre-Pull Images Before Home Manager Switch

**File**: `phases/phase-05-declarative-deployment.sh`

**Location**: Lines 588-610 (after HuggingFace model pre-load)

```bash
# Pre-pull user-level Podman images to avoid timeout during home-manager switch
if command -v podman >/dev/null 2>&1; then
    print_info "Pre-pulling user-level AI stack images..."
    local -a user_images=(
        "docker.io/ollama/ollama:latest"
        "ghcr.io/open-webui/open-webui:latest"
        "docker.io/qdrant/qdrant:latest"
        "docker.io/mindsdb/mindsdb:latest"
    )
    local img
    for img in "${user_images[@]}"; do
        if ! podman image exists "$img" >/dev/null 2>&1; then
            print_info "Pulling $img..."
            if podman pull "$img" 2>&1 | grep -E '(Downloaded|already|Digest)'; then
                print_success "Pulled $img"
            else
                print_warning "Failed to pull $img (will retry during service start)"
            fi
        else
            print_success "$img already present"
        fi
    done
fi
```

### Fix 3: Cleanup Backup Files Before Home Manager Switch

**File**: `phases/phase-05-declarative-deployment.sh`

**Location**: Lines 361-363

```bash
# Clean up backup files that may block home-manager switch
rm -f "$HOME/.npmrc.backup" "$HOME/.config/VSCodium/User/settings.json.backup" 2>/dev/null || true

if $hm_cmd switch --flake "$hm_flake_target" -b backup 2>&1 | tee /tmp/home-manager-switch.log; then
```

**Changes**:
- Added cleanup of old `.backup` files
- Added `-b backup` flag to home-manager switch command

### Fix 4: Create Systemd Timeout Drop-ins

**File**: `phases/phase-08-finalization-and-report.sh`

**Location**: Lines 226-244 (before service enable)

```bash
# Create systemd drop-ins to increase timeout for large container startups
print_info "Creating service timeout overrides for Ollama and Open WebUI..."
mkdir -p "$HOME/.config/systemd/user/podman-local-ai-ollama.service.d"
mkdir -p "$HOME/.config/systemd/user/podman-local-ai-open-webui.service.d"

cat > "$HOME/.config/systemd/user/podman-local-ai-ollama.service.d/timeout.conf" <<'EOF'
[Service]
# Increase timeout for large container (Ollama is 3.75GB)
TimeoutStartSec=300
EOF

cat > "$HOME/.config/systemd/user/podman-local-ai-open-webui.service.d/timeout.conf" <<'EOF'
[Service]
# Increase timeout for large container (Open WebUI is 4.38GB)
TimeoutStartSec=300
EOF

systemctl --user daemon-reload
print_success "Timeout overrides created"
```

## Verification

After fixes, all services should start successfully:

```bash
# Check service status
systemctl --user status podman-local-ai-ollama.service
systemctl --user status podman-local-ai-open-webui.service
systemctl --user status podman-local-ai-qdrant.service

# Verify APIs
curl http://127.0.0.1:11434/api/tags  # Ollama
curl http://127.0.0.1:8081             # Open WebUI
curl http://127.0.0.1:6333/collections # Qdrant
```

Expected output:
```
✓ Ollama API responding
✓ Open WebUI responding
✓ Qdrant API responding
```

## Files Modified

1. **templates/home.nix**
   - Changed `autoUpdate = "registry"` → `autoUpdate = "local"` (4 containers)

2. **phases/phase-05-declarative-deployment.sh**
   - Added user Podman image pre-pull (lines 588-610)
   - Added backup file cleanup before home-manager switch (lines 361-363)
   - Added `-b backup` flag to home-manager switch (line 364)

3. **phases/phase-08-finalization-and-report.sh**
   - Added systemd timeout drop-in creation (lines 226-244)

## Testing

Run the integration test to verify all services:

```bash
./test-aidb-integration.sh
```

This will check:
- Gitea (AIDB)
- Ollama API and models
- TGI DeepSeek and Scout
- Open WebUI
- Qdrant
- Podman container status

## Benefits

1. **Faster Deployments**: No registry pulls during service starts
2. **Reliable Startups**: 300-second timeout handles large containers
3. **Better UX**: Images pre-pulled before home-manager switch
4. **No Conflicts**: Automatic backup file cleanup
5. **Persistent**: All fixes integrated into deployment scripts

## Architecture Note

The Podman AI stack uses:
- **autoUpdate = "local"**: Use locally cached images (updated manually via `podman pull`)
- **TimeoutStartSec = 300**: Allow 5 minutes for large container startup
- **Type = notify**: Systemd waits for container to signal ready
- **Restart = always**: Auto-restart on failure

Images are updated manually:
```bash
podman pull docker.io/ollama/ollama:latest
podman pull ghcr.io/open-webui/open-webui:latest
podman pull docker.io/qdrant/qdrant:latest
systemctl --user restart podman-local-ai-*.service
```

Or use the auto-update timer (if enabled):
```bash
systemctl --user enable --now podman-auto-update.timer
```
