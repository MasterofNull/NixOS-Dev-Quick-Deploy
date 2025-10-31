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

## Home Manager Not Replacing Configs

### Issue

Running the quick deploy script multiple times doesn't replace existing configurations.

### Solution (Already Fixed)

The latest version of the script includes `force_clean_environment_setup()` which:

1. **Backs up** all existing configurations to `~/.config-backups/`
2. **Removes** old home-manager generations
3. **Uninstalls** existing flatpak applications
4. **Cleans** nix profile garbage
5. **Replaces** all configs with fresh versions

Every run of the script now performs a clean installation while preserving backups.

### Restore Previous Configs

If you need to restore previous configurations:

```bash
# Find your backup
ls -lt ~/.config-backups/

# Restore from specific backup
cp -a ~/.config-backups/pre-switch-20251031_123456/. ~/

# Or restore just specific files
cp ~/.config-backups/pre-switch-20251031_123456/.zshrc ~/
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
