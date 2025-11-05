# Quick Start Guide
## NixOS Quick Deploy - Get Started in 5 Minutes

**Version**: 3.2.0
**Last Updated**: January 2025

---

## Prerequisites

Before you start, ensure you have:
- ✅ A running NixOS system
- ✅ Internet connection
- ✅ At least 50GB free disk space in `/nix`
- ✅ Sudo privileges

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy
```

### 2. Make the Script Executable

```bash
chmod +x nixos-quick-deploy-modular.sh
```

### 3. Run Your First Deployment

```bash
./nixos-quick-deploy-modular.sh
```

That's it! The script will automatically:
- ✓ Validate your system
- ✓ Install prerequisites
- ✓ Backup your current configuration
- ✓ Generate optimized NixOS configs
- ✓ Deploy the new system
- ✓ Install additional tools
- ✓ Validate everything works

---

## Common Usage Scenarios

### Scenario 1: First-Time Deployment

```bash
# Run normal deployment (will resume if interrupted)
./nixos-quick-deploy-modular.sh
```

**What happens:**
- System validation (2-3 minutes)
- Prerequisites installation (5-10 minutes)
- Backup creation (1-2 minutes)
- Configuration generation (2-3 minutes)
- System deployment (10-20 minutes)
- Tools installation (5-15 minutes)
- Total time: ~30-60 minutes

### Scenario 2: Resuming After Failure

If deployment fails or is interrupted:

```bash
# Automatically resumes from last completed phase
./nixos-quick-deploy-modular.sh
```

The script automatically detects where it left off and continues!

### Scenario 3: Preview Changes (Dry Run)

Want to see what will happen without making changes?

```bash
# Preview mode - no actual changes
./nixos-quick-deploy-modular.sh --dry-run
```

### Scenario 4: Start Fresh

Starting over from scratch:

```bash
# Clear state and start from beginning
./nixos-quick-deploy-modular.sh --reset-state
```

### Scenario 5: Something Went Wrong - Rollback

If deployment breaks your system:

```bash
# Rollback to previous working state
./nixos-quick-deploy-modular.sh --rollback
```

This instantly reverts to your last working NixOS generation!

---

## Quick Reference: Common Commands

### Basic Operations

```bash
# Show help
./nixos-quick-deploy-modular.sh --help

# Show version
./nixos-quick-deploy-modular.sh --version

# Normal deployment
./nixos-quick-deploy-modular.sh

# Quiet mode (only errors/warnings)
./nixos-quick-deploy-modular.sh --quiet

# Verbose mode (detailed output)
./nixos-quick-deploy-modular.sh --verbose
```

### Phase Control

```bash
# List all phases with status
./nixos-quick-deploy-modular.sh --list-phases

# Start from specific phase (skip phases 1-3)
./nixos-quick-deploy-modular.sh --start-from-phase 4

# Skip specific phases
./nixos-quick-deploy-modular.sh --skip-phase 5 --skip-phase 7

# Test a single phase
./nixos-quick-deploy-modular.sh --test-phase 4
```

### Troubleshooting

```bash
# Debug mode (trace execution)
./nixos-quick-deploy-modular.sh --debug

# Skip health check (faster, less safe)
./nixos-quick-deploy-modular.sh --skip-health-check

# Show detailed phase info
./nixos-quick-deploy-modular.sh --show-phase-info 6
```

---

## Understanding the 10 Phases

The deployment runs in 10 sequential phases:

| Phase | Name | Duration | Description |
|-------|------|----------|-------------|
| **1** | Preparation | 2-3 min | Validate system requirements |
| **2** | Prerequisites | 5-10 min | Install needed packages first |
| **3** | Backup | 1-2 min | Backup current config (safe!) |
| **4** | Config Generation | 2-3 min | Generate NixOS configs |
| **5** | Cleanup | 1-2 min | Smart cleanup (not aggressive) |
| **6** | Deployment | 10-20 min | Deploy configs (point of no return) |
| **7** | Tools Installation | 5-15 min | Install extra tools in parallel |
| **8** | Validation | 2-3 min | Verify everything works |
| **9** | Finalization | 1-2 min | Apply final configurations |
| **10** | Reporting | 1 min | Generate success report |

**Total Time**: ~30-60 minutes

---

## What Gets Installed?

### System Configuration
- Hardware-optimized kernel modules
- GPU drivers (auto-detected: Intel/AMD/NVIDIA)
- Network and security settings
- Systemd services and timers

### Development Tools (100+)
- **Languages**: Python, Node.js, Rust, Go, Java
- **Version Control**: Git, GitHub CLI
- **Editors**: Vim, Neovim, VS Code (via Flatpak)
- **Container Tools**: Podman, Buildah, Skopeo
- **Build Tools**: GCC, Clang, CMake, Make

### AI/ML Environment
- **Libraries**: PyTorch, TensorFlow, Transformers
- **Tools**: Ollama, GPT4All, Aider
- **Platforms**: LangChain, LlamaIndex

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
./nixos-quick-deploy-modular.sh
```

### Problem: "Package not found"

**Solution:**
```bash
# Update Nix channels
sudo nix-channel --update
nixos-rebuild switch

# Then retry
./nixos-quick-deploy-modular.sh
```

### Problem: "Phase X failed"

**Solution:**
```bash
# Check logs
cat ~/.config/nixos-quick-deploy/logs/deploy-*.log

# Restart failed phase
./nixos-quick-deploy-modular.sh --restart-failed

# Or restart from safe point
./nixos-quick-deploy-modular.sh --restart-from-safe-point
```

### Problem: "System is broken after deployment"

**Solution:**
```bash
# Immediate rollback
./nixos-quick-deploy-modular.sh --rollback

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
├── nixos-quick-deploy-modular.sh  # Main script
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
./nixos-quick-deploy-modular.sh                    # Normal run
./nixos-quick-deploy-modular.sh --help             # Show help
./nixos-quick-deploy-modular.sh --version          # Show version
./nixos-quick-deploy-modular.sh --dry-run          # Preview only

# ====== CONTROL ======
./nixos-quick-deploy-modular.sh --reset-state      # Start fresh
./nixos-quick-deploy-modular.sh --rollback         # Undo deployment
./nixos-quick-deploy-modular.sh --restart-failed   # Restart failed phase

# ====== PHASE MANAGEMENT ======
./nixos-quick-deploy-modular.sh --list-phases      # List all phases
./nixos-quick-deploy-modular.sh --test-phase 4     # Test phase 4 only
./nixos-quick-deploy-modular.sh --skip-phase 5     # Skip phase 5
./nixos-quick-deploy-modular.sh --start-from-phase 6   # Start from phase 6

# ====== OUTPUT CONTROL ======
./nixos-quick-deploy-modular.sh --quiet            # Quiet mode
./nixos-quick-deploy-modular.sh --verbose          # Verbose mode
./nixos-quick-deploy-modular.sh --debug            # Debug trace
```

---

## Success Indicators

You'll know deployment succeeded when you see:

```
✓ Phase 1:  Preparation - Complete
✓ Phase 2:  Prerequisites - Complete
✓ Phase 3:  Backup - Complete
✓ Phase 4:  Config Generation - Complete
✓ Phase 5:  Cleanup - Complete
✓ Phase 6:  Deployment - Complete
✓ Phase 7:  Tools Installation - Complete
✓ Phase 8:  Validation - Complete
✓ Phase 9:  Finalization - Complete
✓ Phase 10: Reporting - Complete

🎉 Deployment completed successfully!
```

---

## Ready to Start?

```bash
cd NixOS-Dev-Quick-Deploy
./nixos-quick-deploy-modular.sh
```

Good luck! 🚀

---

**Need more help?** Check the full documentation in the `docs/` directory or open an issue on GitHub.
