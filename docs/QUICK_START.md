# Quick Start Guide
## NixOS Quick Deploy - Get Started in 5 Minutes

**Version**: 4.0.0  
**Last Updated**: March 2025

---

## Prerequisites

Before you start, ensure you have:
- ✅ A running NixOS system
- ✅ Internet connection
- ✅ At least 50GB free disk space in `/nix`
- ✅ Sudo privileges

---

## Installation

### 1. Download or Clone

```bash
# Option A – one-liner (ideal for fresh installs)
curl -fsSL https://raw.githubusercontent.com/MasterofNull/NixOS-Dev-Quick-Deploy/main/nixos-quick-deploy.sh | bash

# Option B – clone locally for repeat use / offline tweaks
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git ~/NixOS-Dev-Quick-Deploy
cd ~/NixOS-Dev-Quick-Deploy
chmod +x nixos-quick-deploy.sh
```

### 2. Run Your First Deployment

```bash
./nixos-quick-deploy.sh
```

From there the orchestrator:
- ✓ Detects hardware, captures git identity/shell/editor preferences
- ✓ Records build acceleration choices (binary caches, remote builders/private Cachix, or local compilation)
- ✓ Creates backups and renders flake-based configs
- ✓ Applies declarative NixOS + Home Manager switches
- ✓ Installs Flatpaks, Claude Code, and dev shells in parallel
- ✓ Runs validation + final health checks with a summarized report

---

## Common Usage Scenarios

### Scenario 1: First-Time Deployment

```bash
# Run normal deployment (will resume if interrupted)
./nixos-quick-deploy.sh
```

**What happens (binary cache path):**
- Hardware + prerequisite validation (≈3 minutes)
- Backup + template rendering (≈5 minutes)
- Build acceleration prompts (binary caches vs. remote builders/private Cachix vs. local compilation)
- Declarative Home Manager + system switch (10‑20 minutes depending on kernel/toolchain churn)
- Additional tooling (Flatpaks, Claude Code, dev shells) in parallel (≈10 minutes)
- Final validation/health check (≈5 minutes)
- **Total time:** ~20‑40 minutes (binary caches) or 60‑120 minutes (full source builds)

### Scenario 2: Resuming After Failure

If deployment fails or is interrupted:

```bash
# Automatically resumes from last completed phase
./nixos-quick-deploy.sh
```

The script automatically detects where it left off and continues!

### Scenario 3: Preview Changes (Dry Run)

Want to see what will happen without making changes?

```bash
# Preview mode - no actual changes
./nixos-quick-deploy.sh --dry-run
```

### Scenario 4: Start Fresh

Starting over from scratch (clears cached preferences such as Flatpak profile, MangoHud mode, remote builders, etc.):

```bash
./nixos-quick-deploy.sh --reset-state
```

### Scenario 5: Something Went Wrong - Rollback

If deployment breaks your system:

```bash
# Rollback to previous working state
./nixos-quick-deploy.sh --rollback
```

This instantly reverts to your last working NixOS generation!

---

## Quick Reference: Common Commands

### Basic Operations

```bash
# Show help
./nixos-quick-deploy.sh --help

# Show version
./nixos-quick-deploy.sh --version

# Normal deployment
./nixos-quick-deploy.sh

# Quiet mode (only errors/warnings)
./nixos-quick-deploy.sh --quiet

# Verbose mode (detailed output)
./nixos-quick-deploy.sh --verbose
```

### Phase Control

```bash
# List all phases with status
./nixos-quick-deploy.sh --list-phases

# Start from specific phase (skip phases 1-3)
./nixos-quick-deploy.sh --start-from-phase 4

# Skip specific phases
./nixos-quick-deploy.sh --skip-phase 5 --skip-phase 7

# Test a single phase
./nixos-quick-deploy.sh --test-phase 4
```

### Troubleshooting

```bash
# Debug mode (bash -x, verbose logging)
./nixos-quick-deploy.sh --debug

# Skip final health check (useful for rapid iteration)
./nixos-quick-deploy.sh --skip-health-check

# Show detailed info about a phase
./nixos-quick-deploy.sh --show-phase-info 6
```

---

## Understanding the 8 Phases

The deployment runs in 8 sequential phases:

| Phase | Name | Duration | Description |
|-------|------|----------|-------------|
| **1** | System Initialization | 3 min | Hardware probe, MangoHud/Flatpak profile prep, prerequisite installs |
| **2** | System Backup | 2 min | Snapshot configs + record rollback metadata |
| **3** | Configuration Generation | 5 min | Render `/etc/nixos`, hardware config, Home Manager, and flake files |
| **4** | Pre-deployment Validation | 5 min | Dry-run builds, disk/resume checks, imperative package scan |
| **5** | Declarative Deployment | 15 min | Remove nix-env packages, run `home-manager` + `nixos-rebuild switch` |
| **6** | Additional Tooling | 10 min | Install Flatpaks, Claude CLI, dev shells, and OpenSkills stack in parallel |
| **7** | Post-Deployment Validation | 5 min | GPU driver validation, remote builder sanity, health check setup |
| **8** | Finalization & Reporting | 5 min | Permission cleanup, optional swapfile removal, final report & health summary |

**Total Time**: 20‑40 minutes with binary caches, 60‑120 minutes when building everything locally.

---

## What Gets Installed?

### System Configuration
- COSMIC desktop + Hyprland session
- Kernel preference ladder (`linuxPackages_6_17` ➜ `linuxPackages_xanmod` ➜ `linuxPackages_lqx` ➜ `linuxPackages_zen` ➜ `linuxPackages_latest`)
- GPU drivers, MangoHud overlays, and Gamescope tuned automatically
- Rootless Podman defaults, PipeWire, ZRAM, nix-ld, and declarative Home Manager workspace
- Flatpak remotes, profile caching, and MangoHud preference files stored under `$STATE_DIR/preferences`

### Development Tools (Highlights)
- **Languages:** Python 3.13/3.14 (mask-aware), Node.js 22, Go, Rust, Ruby, Java toolchains
- **Version Control:** Git, Lazygit, git-credential-manager, GitHub CLI, Gitea server
- **Editors:** VSCodium (with Claude/Continue/Codeium), Neovim, Cursor, Helix, JetBrains via Flatpak (optional)
- **Container/Cloud:** Podman, Buildah, Skopeo, Podman Desktop, Docker-compatible CLI wrappers
- **Observability:** Netdata, Grafana + Loki + Promtail + Vector, Glances, Cockpit
- **Modern CLI:** `ripgrep`, `fd`, `fzf`, `bat`, `eza`, `htop/btop`, `jq/yq`, `nix-tree`, `statix`, `nix-index`

### AI/ML Environment
- Claude Code CLI + wrappers (`claude-wrapper`, `gpt-codex-wrapper`, `codex-wrapper`, `openai-wrapper`, `gooseai-wrapper`)
- Aider, Continue, Codeium, Cursor, Postman, DBeaver, Obsidian, and other AI workstation apps (profile-dependent)
- Ollama, Hugging Face TGI (opt-in), Qdrant, Open WebUI, Jupyter Lab
- Python stack with PyTorch, TensorFlow, LangChain, LlamaIndex, LiteLLM, Sentence Transformers, FAISS, Polars, Dask, Black/Ruff/Mypy/Pylint — all pinned in flake overlays for reproducibility

### Desktop Applications (via Flatpak)
- Browsers, media players, productivity apps
- Auto-updated and sandboxed

---

## Troubleshooting

### Problem: "Insufficient disk space"

**Solution:**
```bash
# Free up space
sudo nix-collect-garbage -d
sudo nix-store --optimize
sudo nix-store --gc

# Then retry
./nixos-quick-deploy.sh
```

### Problem: "Package not found"

**Solution:**
```bash
# Update Nix channels
sudo nix-channel --update
nixos-rebuild switch

# Then retry
./nixos-quick-deploy.sh
```

### Problem: "Phase X failed"

**Solution:**
```bash
# Check logs
cat ~/.config/nixos-quick-deploy/logs/deploy-*.log

# Restart failed phase
./nixos-quick-deploy.sh --restart-failed

# Or restart from safe point
./nixos-quick-deploy.sh --restart-from-safe-point
```

### Problem: "System is broken after deployment"

**Solution:**
```bash
# Immediate rollback
./nixos-quick-deploy.sh --rollback

# Or manually rollback
sudo nixos-rebuild switch --rollback
```

---

## Where Are Things Located?

### Configuration Files
```
/etc/nixos/configuration.nix       # System configuration
~/.config/home-manager/home.nix    # User configuration
~/.dotfiles/                       # User dotfiles
```

### Script Files
```
NixOS-Dev-Quick-Deploy/
├── nixos-quick-deploy.sh  # Main script
├── lib/                           # 10 library files
├── config/                        # 2 config files
├── phases/                        # 10 phase modules
└── docs/                          # Documentation
```

### Logs and State
```
~/.config/nixos-quick-deploy/
├── logs/                          # Deployment logs
│   └── deploy-YYYYMMDD_HHMMSS.log
├── state.json                     # Resume state
├── rollback-info.json             # Rollback point
└── backup/                        # Configuration backups
```

---

## Next Steps

After successful deployment:

1. **Reboot** (optional but recommended)
   ```bash
   sudo reboot
   ```

2. **Verify Installation**
   ```bash
   # Check NixOS version
   nixos-version

   # Check installed packages
   nix-env -q

   # Check Home Manager
   home-manager --version
   ```

3. **Customize Your System**
   - Edit `/etc/nixos/configuration.nix` for system changes
   - Edit `~/.config/home-manager/home.nix` for user changes
   - Run `sudo nixos-rebuild switch` to apply changes

4. **Explore Installed Tools**
   ```bash
   # Try the AI tools
   ollama --help

   # Try the container tools
   podman --version

   # List Flatpak apps
   flatpak list
   ```

---

## Tips and Best Practices

### ✅ Do's
- ✅ Always run with normal privileges (not root)
- ✅ Let it resume if interrupted
- ✅ Check logs if something fails
- ✅ Use `--dry-run` for preview
- ✅ Create backups before major changes

### ❌ Don'ts
- ❌ Don't run as root (uses sudo when needed)
- ❌ Don't interrupt during Phase 6 (deployment)
- ❌ Don't modify config files during deployment
- ❌ Don't skip phases without understanding them
- ❌ Don't ignore warnings

---

## Getting Help

### Documentation
- **Full Docs**: See `docs/` directory
- **Architecture**: See `docs/MODULAR_ARCHITECTURE_PROPOSAL.md`
- **Workflow**: See `docs/WORKFLOW_CHART.md`
- **Dependencies**: See `docs/DEPENDENCY_CHART.md`

### Support
- **Issues**: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues
- **Discussions**: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/discussions

### Logs
```bash
# View latest log
cat ~/.config/nixos-quick-deploy/logs/deploy-*.log | tail -100

# View all logs
ls -lh ~/.config/nixos-quick-deploy/logs/

# Watch log in real-time (during deployment)
tail -f ~/.config/nixos-quick-deploy/logs/deploy-*.log
```

---

## FAQ

**Q: How long does deployment take?**
A: First-time deployment: 30-60 minutes. Subsequent runs with resume: 5-30 minutes.

**Q: Can I interrupt the deployment?**
A: Yes! The script has resume capability. Just run it again.

**Q: Will this break my current system?**
A: No! The script creates backups and rollback points. You can always revert.

**Q: Can I customize what gets installed?**
A: Yes! Edit the phase files in `phases/` directory before running.

**Q: Does this work on non-NixOS systems?**
A: No, this is specifically for NixOS. The script validates you're on NixOS before starting.

**Q: How do I uninstall?**
A: Use the rollback feature, then delete the cloned directory.

---

## Quick Command Cheat Sheet

```bash
# ====== BASIC OPERATIONS ======
./nixos-quick-deploy.sh                    # Normal run
./nixos-quick-deploy.sh --help             # Show help
./nixos-quick-deploy.sh --version          # Show version
./nixos-quick-deploy.sh --dry-run          # Preview only

# ====== CONTROL ======
./nixos-quick-deploy.sh --reset-state      # Start fresh
./nixos-quick-deploy.sh --rollback         # Undo deployment
./nixos-quick-deploy.sh --restart-failed   # Restart failed phase

# ====== PHASE MANAGEMENT ======
./nixos-quick-deploy.sh --list-phases      # List all phases
./nixos-quick-deploy.sh --test-phase 4     # Test phase 4 only
./nixos-quick-deploy.sh --skip-phase 5     # Skip phase 5
./nixos-quick-deploy.sh --start-from-phase 6   # Start from phase 6

# ====== OUTPUT CONTROL ======
./nixos-quick-deploy.sh --quiet            # Quiet mode
./nixos-quick-deploy.sh --verbose          # Verbose mode
./nixos-quick-deploy.sh --debug            # Debug trace
```

---

## Success Indicators

You'll know deployment succeeded when you see:

```
✓ Phase 1:  System Initialization - Complete
✓ Phase 2:  System Backup - Complete
✓ Phase 3:  Configuration Generation - Complete
✓ Phase 4:  Pre-Deployment Validation - Complete
✓ Phase 5:  Declarative Deployment - Complete
✓ Phase 6:  Additional Tooling - Complete
✓ Phase 7:  Post-Deployment Validation - Complete
✓ Phase 8:  Finalization & Report - Complete

🎉 Deployment completed successfully!
```

---

## Ready to Start?

```bash
cd NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

Good luck! 🚀

---

**Need more help?** Check the full documentation in the `docs/` directory or open an issue on GitHub.
