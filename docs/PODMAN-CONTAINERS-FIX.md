# Podman Containers Not Created - Fix Guide

## Problem

After running `nixos-quick-deploy.sh`, Podman containers (Ollama, Open WebUI, Qdrant, MindsDB) were not created.

## Root Cause

The Podman containers are only included in the Home Manager configuration when `LOCAL_AI_STACK_ENABLED=true`. This flag defaults to `false` if:
- No Hugging Face token was provided during deployment
- The user skipped the local AI stack setup

When `LOCAL_AI_STACK_ENABLED=false`, the entire `services.podman` block (including container definitions) is excluded from the generated configuration.

## Solution

### Option 1: Enable via Environment Variable (Quick Fix)

1. **Set the environment variable:**
   ```bash
   export LOCAL_AI_STACK_ENABLED=true
   ```

2. **Optionally set a Hugging Face token** (if you have one):
   ```bash
   export HUGGINGFACEHUB_API_TOKEN="your-token-here"
   ```

3. **Persist the preference:**
   ```bash
   mkdir -p ~/.config/nixos-quick-deploy
   echo "LOCAL_AI_STACK_ENABLED=true" > ~/.config/nixos-quick-deploy/local-ai-stack.env
   ```

4. **Regenerate and rebuild the configuration:**
   ```bash
   # Navigate to your deployment directory
   cd /path/to/NixOS-Dev-Quick-Deploy
   
   # Re-run the configuration generation (Phase 3)
   # This will regenerate templates/home.nix with containers enabled
   ./nixos-quick-deploy.sh --skip-phases 1,2,4,5,6,7,8,9
   
   # Or manually rebuild Home Manager
   home-manager switch --flake ~/.config/home-manager#$(hostname)
   ```

### Option 2: Re-run Full Deployment (Recommended)

1. **Set environment variables:**
   ```bash
   export LOCAL_AI_STACK_ENABLED=true
   # Optional: export HUGGINGFACEHUB_API_TOKEN="your-token"
   ```

2. **Re-run the deployment script:**
   ```bash
   ./nixos-quick-deploy.sh
   ```

   When prompted for the Hugging Face token:
   - Enter your token to enable the full AI stack
   - Or press Enter to skip (containers will still be created, but some AI features may be limited)

### Option 3: Manual Configuration Edit

If you prefer to manually enable it:

1. **Edit the preference file:**
   ```bash
   mkdir -p ~/.config/nixos-quick-deploy
   echo "LOCAL_AI_STACK_ENABLED=true" > ~/.config/nixos-quick-deploy/local-ai-stack.env
   ```

2. **Regenerate configuration:**
   ```bash
   # Source the deployment script's config
   source config/variables.sh
   
   # Regenerate home.nix
   # (This requires running the config generation phase)
   ```

3. **Rebuild Home Manager:**
   ```bash
   home-manager switch --flake ~/.config/home-manager#$(hostname)
   ```

## Verification

After rebuilding, verify that containers are defined:

1. **Check if podman-ai-stack helper exists:**
   ```bash
   test -f ~/.local/bin/podman-ai-stack && echo "✓ Helper installed" || echo "✗ Helper missing"
   ```

2. **Check systemd user services:**
   ```bash
   systemctl --user list-units --type=service | grep podman
   ```

3. **Start the containers:**
   ```bash
   podman-ai-stack up
   ```

4. **Check container status:**
   ```bash
   podman-ai-stack status
   podman ps -a
   ```

## Expected Containers

After enabling and rebuilding, you should see these containers defined (but not started by default):

- `local-ai-ollama` - Ollama inference runtime
- `local-ai-open-webui` - Open WebUI interface
- `local-ai-qdrant` - Qdrant vector database
- `local-ai-mindsdb` - MindsDB orchestration layer

## Notes

- Containers have `autoStart = false`, so they won't automatically start after rebuild
- You must manually run `podman-ai-stack up` to start them
- Container images will be pulled the first time you start them
- Data is stored in `~/.local/share/podman-ai-stack/`

## Troubleshooting

### Containers still not appearing after rebuild

1. **Check the generated configuration:**
   ```bash
   grep -A 5 "services.podman" ~/.config/home-manager/home.nix
   ```

2. **Verify the placeholder was replaced:**
   ```bash
   grep "LOCAL_AI_STACK_ENABLED_PLACEHOLDER" ~/.config/home-manager/home.nix
   # Should return nothing (placeholder should be replaced with "true")
   ```

3. **Check Home Manager build logs:**
   ```bash
   home-manager switch --flake ~/.config/home-manager#$(hostname) 2>&1 | tee /tmp/hm-build.log
   ```

### Podman service not starting

1. **Check Podman installation:**
   ```bash
   which podman
   podman --version
   ```

2. **Check systemd user services:**
   ```bash
   systemctl --user status podman.service
   ```

3. **Enable linger (for rootless containers to persist across logouts):**
   ```bash
   loginctl enable-linger $USER
   ```

## Related Documentation

- `docs/ROOTLESS_PODMAN.md` - Podman rootless setup guide
- `README.md` - Main deployment documentation
- `docs/AI-STACK-FULL-INTEGRATION.md` - AI stack integration details

