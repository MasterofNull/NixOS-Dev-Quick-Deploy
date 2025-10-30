# NixOS Quick Deploy - Modern Declarative System Setup

Complete automated setup for NixOS with home-manager, COSMIC desktop, Flatpak, and 800+ pre-configured packages.

## Quick Start - One Command

```bash
cd ~/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

**That's it!** Answer 4 questions, wait 20-35 minutes, reboot, then customize apps. Done.

---

## AI Workspace Overview

| Integration | Where it lives | What you get |
|-------------|----------------|--------------|
| **Cursor** | Flatpak (`ai.cursor.Cursor`) + `code-cursor` launcher | Launch Cursor from the terminal, Gitea task runners, or the desktop menu with local model defaults wired in. |
| **GPT Codex / OpenAI** | VSCodium Continue + aider/gpt-cli helpers | Ship a single OpenAI key to power Continue, aider, and `gpt-cli` for Codex/GPT-4 style completions against local or remote endpoints. |
| **Claude** | VSCodium Claude Code extension + managed Node wrapper | Use Claude instantly inside VSCodium; the script installs the CLI, wrapper, and settings so prompts work out of the box. |

Gitea inherits the same trio through its AI agent manifest: repository tasks can launch Cursor sessions, call aider with OpenAI/GPT Codex models, or hand work over to the Podman AI stack for local model workflows.

---

## What the Script Does Automatically

The **`nixos-quick-deploy.sh`** script automatically:

1. ✅ **Updates NixOS system configuration** (Cosmic desktop, Podman, Flakes)
2. ✅ **Runs `sudo nixos-rebuild switch`** automatically
3. ✅ **Creates home-manager configuration** (~100 packages)
4. ✅ **Runs `home-manager switch`** automatically
5. ✅ **Seeds Flatpak (Flathub remote + core desktop apps)**
6. ✅ **Builds flake development environment** for AIDB
7. ✅ **Publishes Cursor/GPT Codex/Claude workflows** across VSCodium & Gitea
8. ✅ **Configures Powerlevel10k** with high-contrast colors
9. ✅ **Verifies all packages** are in PATH
10. ✅ **Offers optional reboot**

**Total time:** 20-35 minutes (mostly downloading packages)

**User interaction:** Answer 4 simple questions
**Everything else:** Fully automated (no manual steps)

---

## What Gets Installed

### System Configuration (via nixos-rebuild)
- **Nix flakes** enabled
- **Podman** virtualization (rootless containers)
- **Cosmic desktop** environment
- **Unfree packages** allowed

### User Packages (via home-manager) - ~100 packages
**AIDB Requirements:**
- podman, podman-compose, sqlite, python3, openssl, bc, inotify-tools

**Development Tools:**
- git, neovim, vscodium, go, rust, ruby, nodejs
- Nix tools (nix-tree, nixpkgs-fmt, alejandra, statix, etc.)

**Modern CLI Tools:**
- ripgrep, bat, eza, fd, fzf, jq, yq, lazygit, htop, btop
- gpt-cli (talk to local Ollama, GPT Codex, or any OpenAI-compatible endpoint)
- podman-ai-stack (spin up Ollama, Open WebUI, Qdrant, MindsDB via Podman)
- obsidian-ai-bootstrap (install AI plugins into an Obsidian vault)
- hf-model-sync & hf-tgi (download models + run Hugging Face TGI locally)

**Terminal & Fonts:**
- ZSH with Powerlevel10k (high-contrast colors)
- Alacritty terminal
- Nerd Fonts (MesloLGS, FiraCode, JetBrainsMono, Hack)

**Desktop Apps:**
- cosmic-edit, cosmic-files, cosmic-term

### AI IDE & Forge Integrations (Declarative)
- **Cursor launcher & workspace glue** – `code-cursor` prefers the Flatpak, falls back to native binaries, and is exposed to the Gitea agent runner.
- **GPT Codex helpers** – aider, `gpt-cli`, Continue, Codeium, and ChatGPT extensions are pre-wired to OpenAI-style endpoints (local Hugging Face by default, OpenAI/Anthropic once tokens are set).
- **Claude Code** – CLI installed globally, wrapper fixes Node pathing, and VSCodium settings/extensions are merged so Claude prompts just work.
- **Gitea AI agent manifest** – ships with tasks for Cursor launches, aider OpenAI runs, GPT CLI completions, and Podman AI stack status checks inside the forge UI.

### Development Environment (via flake)
- AIDB-specific packages cached
- Python 3.11 environment ready
- Convenient commands: `aidb-dev`, `aidb-shell`, `aidb-info`

### Flatpak Applications (12 Pre-Enabled, 50+ Optional)
**Pre-Installed & Ready:**
- Flatseal (permissions manager)
- FileRoller (archive manager)
- Resources (system monitor - CPU/GPU/RAM)
- VLC & MPV (media players)
- Firefox (web browser - sandboxed)
- Obsidian (note-taking)
- Cursor (AI-assisted IDE / Code-Cursor)
- LM Studio (local LLM orchestration UI)
- Gitea (desktop UI for local forge & AI workflows)
- Podman Desktop (container dashboard for Podman/buildah)
- DB Browser for SQLite (GUI management for the bundled SQLite DB)

**Optional (One-Line Setup):**
- LibreOffice, GIMP, Inkscape, Blender, OBS Studio, Audacity
- GitUI, DBeaver (database IDE)
- Steam, Dolphin emulator, RPCS3
- Telegram, Slack, Thunderbird
- And 30+ more...

**To Enable:**
```bash
# Edit your config
nano ~/.dotfiles/home-manager/home.nix

# Uncomment apps you want (remove the # symbol)
# "org.libreoffice.LibreOffice"
# "org.gimp.GIMP"

# Apply changes
home-manager switch --flake ~/.dotfiles/home-manager
```

---

## What You Do (4 Simple Questions)

The script asks you:

1. **GitHub username** → For git config
2. **Editor** → vim/neovim/vscodium (choose 1-3)
3. **Replace config?** → Press Enter (yes)
4. **Reboot now?** → Type `y` or `n`

**Then wait 20-35 minutes while it works.**

**Everything else is automatic** - no manual steps, no running other commands, no configuration editing.

---

## After Installation (What Happens Next)

### 1. Reboot
```bash
sudo reboot
```
At login, select **"Cosmic"** desktop

### 2. Open Terminal
**P10k wizard runs automatically** (first ZSH launch only):
- Choose prompt style
- Choose color scheme (High Contrast Dark recommended)
- Choose what to show (time, icons, path)
- Restart shell - beautiful prompt ready!

### 3. Verify Everything Works
```bash
podman --version    # ✓ Works
python3 --version   # ✓ Works
ripgrep --version   # ✓ Works
home-manager --version  # ✓ CLI available from PATH
flatpak list --user --columns=application # ✓ Default desktop apps installed
aidb-dev           # ✓ Enters AIDB environment
codium             # ✓ Opens VSCodium with Claude Code
code-cursor        # ✓ Launches Cursor (Flatpak wrapper)
tea ai summarize   # ✓ Calls GPT Codex/OpenAI via aider + Tea CLI
```

**All done!** Everything is installed and configured.

---

## Useful Commands

### AIDB Development
```bash
aidb-dev         # Enter flake dev environment with all tools
aidb-shell       # Alternative way to enter dev environment
aidb-info        # Show AIDB environment information
aidb-update      # Update flake dependencies
```

### AI Stack Management
```bash
podman-ai-stack up        # Launch local LLM + vector DB + AI database services
podman-ai-stack status    # Check pod, container, and port health
podman-ai-stack logs      # Follow aggregated container logs
gpt-cli "plan this sprint" # Query local Hugging Face TGI, GPT Codex, or Ollama providers
obsidian-ai-bootstrap     # Install AI plugins into the default Obsidian vault
```

### NixOS Management
```bash
nrs              # sudo nixos-rebuild switch
hms              # home-manager switch
nfu              # nix flake update
```

### Container Management
```bash
podman pod ps    # List running pods
podman ps        # List running containers
```

### Development
```bash
lg               # lazygit
nixpkgs-fmt      # Format Nix code
alejandra        # Alternative Nix formatter
statix check     # Lint Nix code
```

---

## Files & Structure

### Main Script
- **`nixos-quick-deploy.sh`** - Main automated setup script (run this)

### Configuration Files
- **`flake.nix`** - AIDB development environment definition
- **`nixos-cosmic-config-template.nix`** - System config reference (auto-applied)
- **`p10k-setup-wizard.sh`** - Powerlevel10k configuration wizard (runs automatically)

### Helper Scripts (Optional)
- **`apply-home-manager-config.sh`** - Standalone home-manager setup (if needed)
- **`apply-cosmic-desktop.sh`** - Manual Cosmic setup (if needed)

---

## What Happens Step-by-Step

### 1. System Configuration (Automatic)
```
Checking Prerequisites...
Gathering User Information...
Updating NixOS System Configuration...
  ✓ Backing up /etc/nixos/configuration.nix
  ✓ Adding Cosmic desktop configuration
  ✓ Adding Podman virtualization
  ✓ Enabling Nix flakes
Running: sudo nixos-rebuild switch (automatic)
  ✓ NixOS system configuration applied successfully!
```

### 2. Home Manager Setup (Automatic)
```
Creating Home Manager Configuration...
  ✓ Configuration created with ~100 packages
Applying Home Manager Configuration...
Running: home-manager switch (automatic, no confirmation needed)
  ✓ Home manager configuration applied successfully!
Updating current shell environment...
  ✓ PATH updated with new packages
Verifying package installation...
  ✓ podman found at /home/user/.nix-profile/bin/podman
  ✓ python3 found at /home/user/.nix-profile/bin/python3
  ✓ ripgrep found at /home/user/.nix-profile/bin/ripgrep
  ✓ All critical packages are in PATH!
```

### 3. Flake Development Environment (Automatic)
```
Setting Up Flake-based Development Environment...
  ✓ Nix flakes enabled
Building flake development environment (may take a few minutes)...
  ✓ Flake development environment built and cached
  ✓ Created aidb-dev-env activation script
  ✓ Added AIDB flake aliases to .zshrc
```

### 4. AI IDE Integration (Automatic)
```
Installing Claude Code...
  ✓ Claude Code npm package installed
  ✓ Created claude-wrapper
Adding Claude Code Configuration to VSCodium...
  ✓ Claude Code settings merged successfully
Installing Additional VSCodium Extensions...
  ✓ Claude Code installed
  ✓ Additional extensions installation complete
```

> Home-manager provisions the rest of the AI toolchain during this stage—Cursor's launcher, aider/gpt-cli bindings, Continue/Codeium settings, and the declarative Gitea AI agent manifest all land alongside the Claude update.

### 5. Completion
```
Installation Complete!

✓ NixOS Quick Deploy Complete - FULLY CONFIGURED!

Important Notes:
  1. REBOOT REQUIRED: System configuration changed
     Run: sudo reboot
  2. After reboot: Select "Cosmic" from session menu
  3. Restart your terminal: exec zsh
  4. All configurations applied automatically!

Reboot now? [y/N]:
```

---

## Troubleshooting

### Packages not in PATH after installation

**Issue:** `podman: command not found`

**Solution:**
```bash
# Restart your shell
exec zsh

# Or manually source session vars
source ~/.nix-profile/etc/profile.d/hm-session-vars.sh
```

### Colors showing as `${GREEN}` instead of colored

**Issue:** Post-install output not showing colors

**Solution:** This was fixed. If you still see it:
```bash
# Re-download the latest script
cd ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy
git pull
```

### P10k prompt hard to read

**Issue:** Text blends with background

**Solution:**
```bash
# Run wizard again
rm ~/.config/p10k/.configured
exec zsh

# Choose option 1 (High Contrast Dark) or 7 (Custom High Contrast)
```

### Cosmic desktop not appearing

**Issue:** Only GNOME shows at login

**Solution:**
```bash
# Verify Cosmic is enabled
grep -i cosmic /etc/nixos/configuration.nix

# Rebuild if needed
sudo nixos-rebuild switch
sudo reboot
```

### home-manager switch failed

**Issue:** Conflicting files error

**Solution:**
```bash
# Script backs up conflicting files automatically
# If manual intervention needed, check the backup directory
ls -la ~/.config-backups/

# Or run the helper script
./apply-home-manager-config.sh
```

---

## Advanced Usage

### Skip Certain Steps

Edit `nixos-quick-deploy.sh` main() function to comment out steps:

```bash
main() {
    check_prerequisites
    gather_user_info

    # update_nixos_system_config  # Skip NixOS rebuild
    create_home_manager_config
    apply_home_manager_config
    # setup_flake_environment  # Skip flake setup
    install_claude_code
    configure_vscodium_for_claude
    install_vscodium_extensions

    print_post_install
}
```

### Manual System Configuration

If you prefer to configure NixOS system manually:

1. Comment out `update_nixos_system_config` in main()
2. Use the helper script:
   ```bash
   ./apply-cosmic-desktop.sh
   ```
3. Or manually edit `/etc/nixos/configuration.nix` using `nixos-cosmic-config-template.nix` as reference

### Customize P10k Later

```bash
# Remove configuration and run wizard again
rm ~/.config/p10k/.configured
exec zsh
```

---

## Technical Details

### What's Automated

| Task | Command | Automatic? |
|------|---------|-----------|
| System config update | Edit `/etc/nixos/configuration.nix` | ✅ Yes |
| NixOS rebuild | `sudo nixos-rebuild switch` | ✅ Yes |
| Home-manager config | Create `~/.dotfiles/home-manager/home.nix` | ✅ Yes |
| Home-manager switch | `home-manager switch --flake ~/.dotfiles/home-manager` | ✅ Yes |
| Flake build | `nix develop` | ✅ Yes |
| PATH update | Source session vars | ✅ Yes |
| Package verification | Check `which` for each package | ✅ Yes |
| Claude Code install | `npm install -g` | ✅ Yes |
| VSCodium config | Edit `settings.json` | ✅ Yes |
| Extension install | `codium --install-extension` | ✅ Yes |

**Only asks for:**
- GitHub username
- Editor preference
- Config replacement confirmation
- Optional reboot

### File Locations

| What | Where |
|------|-------|
| System config | `/etc/nixos/configuration.nix` |
| System backup | `/etc/nixos/configuration.nix.backup.TIMESTAMP` |
| Home-manager config | `~/.dotfiles/home-manager/home.nix` |
| Home-manager backup | `~/.dotfiles/home-manager/home.nix.backup.TIMESTAMP` |
| Config backups | `~/.config-backups/TIMESTAMP/` |
| P10k configuration | `~/.config/p10k/theme.sh` |
| ZSH config | `~/.zshrc` (managed by home-manager) |
| Installed packages | `~/.nix-profile/bin/` |
| Claude Code | `~/.npm-global/lib/node_modules/@anthropic-ai/claude-code/` |

---

## About the Other Files

**You only run `nixos-quick-deploy.sh`**

The other files are either:
- **Used automatically** by the main script (`flake.nix`, `p10k-setup-wizard.sh`, `nixos-cosmic-config-template.nix`)
- **Recovery tools** if something fails (`apply-home-manager-config.sh`, `apply-cosmic-desktop.sh`)

**Don't run anything else manually** - the main script handles everything.

---

## Summary

| What You Do | What Happens Automatically |
|-------------|----------------------------|
| Run `./nixos-quick-deploy.sh` | Updates `/etc/nixos/configuration.nix` |
| Answer 4 questions | Runs `sudo nixos-rebuild switch` |
| Wait 20-35 minutes | Creates `~/.dotfiles/home-manager/home.nix` |
| Reboot when done | Runs `home-manager switch` |
| Launch ZSH (P10k wizard auto-runs) | Builds `nix develop` environment |
| | Installs Claude Code + VSCodium |
| | Verifies packages in PATH |
| | **Everything ready to use!** |

**One script. Fully automated. Zero manual steps.** 🚀

---

## Next Steps - Deploy AIDB

After the script completes and you reboot:

```bash
# 1. Clone AIDB repository (if not already)
git clone <your-repo> ~/Documents/AI-Opitmizer
cd ~/Documents/AI-Opitmizer

# 2. Setup AIDB template
bash aidb-quick-setup.sh --template

# 3. Create your first project
bash aidb-quick-setup.sh --project MyProject

# 4. Start AIDB
cd ~/Documents/Projects/MyProject/.aidb/deployment/
./scripts/start.sh

# 5. Verify AIDB is running
curl http://localhost:8000/health
```

---

**Ready to start?**

```bash
cd ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy
./nixos-quick-deploy.sh
```

Sit back and let it work! ☕
