# Troubleshooting Guide

This guide covers common issues and their solutions for the NixOS Dev Quick Deploy setup.

---

## VSCodium Continue Extension Issues

### Error: "LLM VS Code client: couldn't create connection to server"

The Continue extension requires proper configuration to connect to your LLM backend. Here's how to fix it:

#### 1. Configure Continue Extension

After installation, you need to configure Continue to use your LLM backend:

1. Open VSCodium
2. Press `Ctrl+Shift+P` and search for "Continue: Open Config"
3. Or click the Continue icon in the sidebar and click "Configure"

#### 2. Set Up Your LLM Provider

Choose one of these options:

**Option A: Use Local Ollama**
```json
{
  "models": [
    {
      "title": "Ollama",
      "provider": "ollama",
      "model": "codellama:7b",
      "apiBase": "http://localhost:11434"
    }
  ]
}
```

**Option B: Use OpenAI**
```json
{
  "models": [
    {
      "title": "GPT-4",
      "provider": "openai",
      "model": "gpt-4",
      "apiKey": "your-api-key-here"
    }
  ]
}
```

**Option C: Use Local Hugging Face TGI**
```json
{
  "models": [
    {
      "title": "Local LLM",
      "provider": "openai",
      "model": "HuggingFaceH4/zephyr-7b-beta",
      "apiBase": "http://localhost:8080/v1"
    }
  ]
}
```

#### 3. Start Your LLM Service

Make sure your chosen LLM service is running:

```bash
# For Ollama
systemctl --user start ollama

# For Hugging Face TGI
systemctl --user start huggingface-tgi

# Verify it's running
curl http://localhost:11434/api/tags  # Ollama
# or
curl http://localhost:8080/health     # TGI
```

#### 4. Reload VSCodium

After configuration:
1. Save the Continue config
2. Reload VSCodium: `Ctrl+Shift+P` → "Developer: Reload Window"
3. The Continue extension should now connect successfully

---

## Duplicate Applications in Menu

### Why This Happens

After running the quick deploy script, you might see duplicate entries for the same application in your applications menu (Firefox, VLC, Cursor, etc.). This happens because:

1. Applications can be installed from multiple sources (system packages, Flatpak, home-manager)
2. The desktop environment indexes all `.desktop` files from all sources
3. Initially, these may appear as separate entries

### Solution

**This is normal and will resolve automatically after a system reboot.**

The desktop environment (COSMIC) deduplicates application entries on startup. After rebooting:
- Duplicate entries will be merged
- Only one entry per application will appear
- The most recent/appropriate version will be used

If duplicates persist after reboot:

```bash
# Clear desktop cache
rm -rf ~/.cache/gnome-shell/
rm -rf ~/.cache/cosmic/

# Update desktop database
update-desktop-database ~/.local/share/applications/

# Reboot
sudo reboot
```

### Prevention

The latest version of the quick deploy script includes a `force_clean_environment_setup()` function that:
- Removes all existing flatpak applications before reinstallation
- Cleans home-manager generations
- Ensures fresh installation every run

This minimizes duplicates by ensuring clean state before each installation.

---

## Home Manager and Flatpak Not Replacing Configs

### Issue

Running the quick deploy script multiple times doesn't replace existing configurations or flatpak environment.

### Solution (Already Fixed)

The latest version of the script includes `force_clean_environment_setup()` which performs **complete environment replacement**:

#### Home Manager Replacement
1. **Backs up** all existing configurations to `~/.config-backups/`
2. **Removes** ALL old home-manager generations
3. **Cleans** nix profile garbage
4. **Replaces** all configs with fresh versions

#### Complete Flatpak Environment Replacement
1. **Backs up** list of installed apps to `~/.cache/nixos-quick-deploy/flatpak-backup-*.txt`
2. **Backs up** entire flatpak directory to `~/.cache/nixos-quick-deploy/flatpak-environment-backup-*/`
3. **Uninstalls** ALL flatpak apps and runtimes (`flatpak uninstall --user --all`)
4. **Removes** entire `~/.local/share/flatpak/` directory:
   - Apps, runtimes, repo, overrides, remotes.d - everything
5. **Removes** `~/.config/flatpak/` configuration directory
6. **Rebuilds** complete flatpak environment from scratch via home-manager

Every run of the script now performs a **complete clean installation** of both home-manager and flatpak while preserving backups.

### Restore Previous Configs

If you need to restore previous configurations:

```bash
# Find your home-manager config backups
ls -lt ~/.config-backups/

# Restore from specific backup
cp -a ~/.config-backups/pre-switch-20251031_123456/. ~/

# Or restore just specific files
cp ~/.config-backups/pre-switch-20251031_123456/.zshrc ~/

# Find flatpak environment backups
ls -lt ~/.cache/nixos-quick-deploy/

# Restore complete flatpak environment (if needed)
rm -rf ~/.local/share/flatpak
cp -a ~/.cache/nixos-quick-deploy/flatpak-environment-backup-20251031_123456 ~/.local/share/flatpak

# Or just check what apps were installed
cat ~/.cache/nixos-quick-deploy/flatpak-backup-20251031_123456.txt
```

---

## System Health Check Shows Only Podman

### Issue

Running `./scripts/system-health-check.sh` only shows "Checking Podman..." and exits.

### Solution (Fixed in Latest Version)

This was caused by `set -e` in the script causing early exit when check functions returned non-zero values (for warnings or failures).

**The fix has been applied** - the script now uses `set -uo pipefail` instead of `set -euo pipefail`.

To verify the fix:
```bash
cd ~/NixOS-Dev-Quick-Deploy
./scripts/system-health-check.sh
```

You should now see all checks running:
- Core System Tools
- Programming Languages & Runtimes
- Nix Ecosystem
- AI Development Tools
- Python AI/ML Packages
- Editors & IDEs
- Shell Configuration
- Flatpak Applications
- Environment Variables & PATH
- AI Systemd Services
- Network Services

---

## Podman Overlay Mount Failures or `/merged` Artifacts

### Symptoms

- `nixos-rebuild switch` aborts with `overlay: mount: invalid argument`.
- `/var/lib/containers/storage/overlay/*/merged` (or the user equivalent under
  `~/.local/share/containers/`) remains after a failed deployment.
- Rootless Podman containers refuse to start after a reboot.

### Resolution

1. Re-run Phase 1 (System Initialization) so the new
   `run_rootless_podman_diagnostics` helper reports kernel, filesystem, and
   namespace issues before the switch.
2. Follow the step-by-step fixes in
   [`docs/ROOTLESS_PODMAN.md`](ROOTLESS_PODMAN.md) to correct filesystem
   formatting, reinstall helper binaries, and clean stale overlay directories.
3. After applying the fixes, re-run `nixos-rebuild switch`.

### Automated recovery (v4.0.0+)

The validator now attempts to clean corrupted Podman storage automatically when
it finds mounted `overlay/*/merged` directories:

- **System scope:** `run_rootless_podman_diagnostics` unmounts any overlay mounts
  left under `/var/lib/containers/storage/overlay/`, removes the hashed layer
  directories, and executes `sudo podman system reset --force` so the rootful
  storage database and overlay metadata are regenerated. See the Podman manual
  for details on `podman system reset`. [link](https://docs.podman.io/en/v5.0.3/markdown/podman-system-reset.1.html)
- **Rootless scope:** The helper repeats the same process for
  `~/.local/share/containers/storage/overlay/` using `fusermount3`/`fusermount`
  for unprivileged mounts and runs `podman system reset --force` without sudo to
  rebuild the per-user store.
- If either cleanup step still reports mounted entries after the automated run,
  the deployment halts so you can manually inspect the affected directories.

### Additional gating checks

- Re-run the deployment generator so container storage probing can refresh the
  driver that NixOS writes into `storage.conf`. The helper examines the
  filesystem behind `/var/lib/containers`, falls back to the safer `vfs`
  default when no specialised driver applies, and emits a warning when the
  existing file still pins an incompatible value such as `overlay`. This keeps
  the deprecated configuration's behaviour while surfacing stale entries before
  they trigger emergency mode: `./nixos-quick-deploy.sh --resume`.
  【F:lib/common.sh†L1213-L1304】
- Run the automated rootless diagnostics (included in Phase 1 and exposed via
  `./scripts/system-health-check.sh --detailed`) to confirm user namespaces,
  subordinate ID ranges, `fuse-overlayfs`, and stale `overlay/*/merged`
  directories are handled before the switch is attempted. 【F:lib/common.sh†L867-L1014】
- If stale overlay directories remain, clean them with Podman (`podman rm --force --all`
  followed by `podman system prune --volumes`) or unmount them manually with
  `findmnt`/`umount` as described below. 【F:docs/ROOTLESS_PODMAN.md†L37-L67】

---

## Zswap zpool Module Unavailable During Boot

### Symptoms

- Boot logs print `zswap: zpool z3fold not available` and the kernel falls back
  to an uncompressed swap backend.
- Hibernation swap provisioning created by the quick deploy script does not
  engage compression even though zswap was enabled previously.

### Resolution

1. Regenerate the configuration so the zswap helper can re-probe the available
   zpools and select the first kernel-supported option (z3fold → zbud →
   zsmalloc). `./nixos-quick-deploy.sh --resume` runs
   `select_zswap_memory_pool` automatically before templating the NixOS config. 【F:lib/config.sh†L1406-L1434】【F:lib/common.sh†L1213-L1231】
2. Rebuild the system profile (`sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager`)
   and reboot. Inspect `/proc/cmdline` to confirm that the regenerated kernel
   parameters now point at the detected zswap zpool.
3. If you need to override zswap entirely (for troubleshooting hardware with
   unstable compression support), re-run the deploy script with `--disable-zswap`
   or restore automatic detection with `--zswap-auto`. 【F:nixos-quick-deploy.sh†L301-L456】

## Flatpak Apps Not Installing

### Issue

Flatpak applications fail to install or the flatpak-managed-install service fails.

### Check Service Status

```bash
# Check if service ran
systemctl --user status flatpak-managed-install.service

# View logs
journalctl --user -u flatpak-managed-install.service

# Check flatpak remotes
flatpak remotes --user
```

### Degraded Systemd Session Warning

If you see "The user systemd session is degraded" during home-manager activation, this is typically caused by a previous failed service run. The script automatically handles this by:

1. **Automatic cleanup**: Before each home-manager activation, the script resets any failed service states
2. **Improved resilience**: The service now uses `RemainAfterExit=false` to prevent lingering failed states
3. **No auto-start**: The service only runs when explicitly triggered by the deployment script

If the warning persists, manually reset the service:

```bash
# Reset failed state
systemctl --user reset-failed flatpak-managed-install.service

# Verify session health
systemctl --user status

# If needed, manually start the service
systemctl --user start flatpak-managed-install.service
```

This issue has been resolved in recent updates. If you continue to see degraded session warnings, ensure you're running the latest version of the deployment script.

### Manual Installation

If the service fails, install apps manually:

```bash
# Ensure flathub is configured
flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo

# Install apps
flatpak install --user flathub org.mozilla.firefox
flatpak install --user flathub md.obsidian.Obsidian
flatpak install --user flathub ai.cursor.Cursor
flatpak install --user flathub com.lmstudio.LMStudio
flatpak install --user flathub org.videolan.VLC

# Verify
flatpak list --user --app
```

### Or Re-run Home Manager

```bash
cd ~/.dotfiles/home-manager
home-manager switch --flake .
```

---

## Path Issues - Commands Not Found

### Issue

Commands like `home-manager`, `claude-wrapper`, or `aider` are not found after installation.

### Solution

```bash
# Reload shell environment
source ~/.zshrc

# Or start a new shell
exec zsh

# Update PATH immediately
export PATH="$HOME/.nix-profile/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

# Verify
which home-manager
which claude-wrapper
which aider
```

### Permanent Fix

Ensure these lines are in your `~/.zshrc` (should be added by home-manager):

```bash
# Nix
if [ -e ~/.nix-profile/etc/profile.d/nix.sh ]; then
  . ~/.nix-profile/etc/profile.d/nix.sh
fi

# Home Manager session variables
if [ -f ~/.nix-profile/etc/profile.d/hm-session-vars.sh ]; then
  . ~/.nix-profile/etc/profile.d/hm-session-vars.sh
fi
```

---

## Ollama Service Not Starting

### Check Status

```bash
systemctl --user status ollama
journalctl --user -u ollama -f
```

### Common Issues

**1. Port Already in Use**
```bash
# Check what's using port 11434
sudo ss -tulpn | grep 11434

# Kill the process if needed
sudo kill <PID>

# Restart
systemctl --user restart ollama
```

**2. Model Not Downloaded**
```bash
# Download a model
ollama pull codellama:7b

# List models
ollama list

# Test
ollama run codellama:7b "Hello"
```

**3. Service Not Enabled**
```bash
systemctl --user enable ollama
systemctl --user start ollama
```

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs**: Most services log to `journalctl --user -u <service-name>`
2. **Run health check**: `./scripts/system-health-check.sh --detailed`
3. **Review documentation**: See the [docs/](.) directory
4. **File an issue**: [GitHub Issues](https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues)

Include in your bug report:
- Output of `./scripts/system-health-check.sh --detailed`
- Relevant log files from `/tmp/` or `journalctl`
- Your NixOS version: `nixos-version`
- Home Manager version: `home-manager --version`
