# Skill Name: nixos-deployment

## Description
Comprehensive NixOS deployment automation with 8-phase workflow for declarative system configuration, package management, and AI stack integration.

## When to Use
- Setting up new NixOS systems from scratch
- Updating existing NixOS configurations declaratively
- Migrating from imperative to declarative configuration
- Deploying AI development environments with Ollama, Qdrant, MindsDB
- Troubleshooting NixOS deployment issues
- Managing flakes-based NixOS configurations
- Setting up GPU-accelerated AI workloads

## Prerequisites
- NixOS system (tested on NixOS 23.11+)
- Root or sudo access for system-level changes
- Git configured with valid identity
- Internet connection for package downloads
- At least 20GB free disk space

## Usage

### Basic Full Deployment
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

This runs all 8 phases interactively:
1. System Initialization
2. System Backup
3. Configuration Generation
4. Pre-deployment Validation
5. Declarative Deployment
6. Additional Tooling
7. Post-deployment Validation
8. Finalization and Report

### Resume from Specific Phase
```bash
./nixos-quick-deploy.sh --start-from-phase 5
```

Skip earlier phases and resume from Phase 5 (useful for iterative testing).

### Skip Health Check
```bash
./nixos-quick-deploy.sh --skip-health-check
```

Bypass post-deployment health validation (use for faster testing cycles).

### Reset State (Start Fresh)
```bash
./nixos-quick-deploy.sh --reset-state
```

Clear all state and preferences, start from Phase 1 with fresh prompts.

### List All Phases
```bash
./nixos-quick-deploy.sh --list-phases
```

Display all 8 phases with descriptions.

### Check Version
```bash
./nixos-quick-deploy.sh --version
```

## Command-Line Options

- `--start-from-phase N`: Resume deployment from phase N (1-8)
- `--skip-health-check`: Skip post-deployment health validation
- `--reset-state`: Clear state and start fresh
- `--list-phases`: Show all deployment phases
- `--version`: Display script version
- `--help`: Show help message
- `--resume N`: Resume from specific phase with preserved state

## Output Interpretation

### Success Indicators
- ✅ **Green checkmarks**: Phase completed successfully
- **State file updated**: `~/.cache/nixos-quick-deploy/state.json`
- **Health check passes**: All services verified
- **Final report generated**: Complete deployment summary

### Common Errors

**"Phase X failed"**
- Solution: Check logs in `~/.cache/nixos-quick-deploy/logs/deploy-*.log`
- Look for specific error messages
- Resume from failed phase after fixing

**"Permission denied"**
- Solution: Run with sudo or ensure user has necessary permissions
- Check file ownership in `$HOME/.dotfiles/home-manager/`

**"Flake evaluation failed"**
- Solution: Check `flake.nix` syntax
- Verify all inputs are accessible
- Run `nix flake check` for detailed errors

**"Git identity not configured"**
- Solution: Configure git or respond to Phase 1 prompts
- Edit `~/.cache/nixos-quick-deploy/preferences/git-identity.env`

**"GPU not detected"**
- Solution: Check if GPU drivers are loaded
- Verify with `lspci | grep -i vga`
- May need to enable proprietary drivers

## State Management

The script maintains state in `~/.cache/nixos-quick-deploy/state.json`:

```json
{
  "current_phase": 8,
  "completed_phases": [1, 2, 3, 4, 5, 6, 7, 8],
  "deployment_id": "20251122_094500",
  "version": "5.0.0"
}
```

### State Operations
- **View state**: `cat ~/.cache/nixos-quick-deploy/state.json`
- **Clear state**: `rm ~/.cache/nixos-quick-deploy/state.json`
- **Manual phase override**: Edit `current_phase` in JSON

## Configuration Files

After deployment, configurations are stored in:

```
~/.dotfiles/home-manager/
├── configuration.nix     # System configuration
├── home.nix              # Home Manager configuration
├── flake.nix             # Flake inputs and outputs
└── hardware-configuration.nix  # Hardware-specific config
```

### Editing Configurations

1. Edit configuration file:
```bash
vim ~/.dotfiles/home-manager/configuration.nix
```

2. Deploy changes:
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --start-from-phase 5
```

3. Verify:
```bash
./scripts/system-health-check.sh
```

## AI Stack Integration

This deployment includes comprehensive AI development tools:

### Local AI Services
- **Ollama** (port 11434): Local LLM inference
- **Qdrant** (ports 6333, 6334): Vector database
- **MindsDB** (ports 47334, 7735): ML orchestration
- **Open WebUI** (port 3001): Chat interface
- **PostgreSQL** (port 5432): MCP server database
- **Redis** (port 6379): MCP server cache

### Managing AI Services
```bash
# Start all AI services
ai-servicectl start all

# Check status
ai-servicectl status all

# Stop specific service
ai-servicectl stop ollama

# View logs
ai-servicectl logs qdrant
```

## Related Skills
- `ai-service-management`: Control AI stack services (Ollama, Qdrant, etc.)
- `health-monitoring`: Validate system health and configuration
- `ai-model-management`: Manage AI models and downloads
- `mcp-database-setup`: Setup PostgreSQL and Redis for MCP server

## MCP Integration

This skill integrates with the AIDB MCP Server for:
- **Tool execution logging**: Track deployments in PostgreSQL
- **State persistence**: Maintain deployment history
- **Error tracking**: Analyze failure patterns
- **Progressive tool discovery**: Expose deployment capabilities to AI agents

### MCP Tool Mapping
```python
{
    "tool_name": "nixos-quick-deploy",
    "skill_name": "nixos-deployment",
    "skill_file": ".claude/skills/nixos-deployment/SKILL.md",
    "category": "system-management"
}
```

## Examples

### Example 1: First-Time NixOS Setup

**Scenario**: Fresh NixOS installation, need to set up development environment.

```bash
# 1. Clone repository
git clone https://github.com/your-org/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# 2. Run full deployment
./nixos-quick-deploy.sh

# 3. Follow prompts for:
#    - Git identity (name, email)
#    - GPU detection (select GPU vendor)
#    - Package selection (gaming, development, etc.)
#    - AI stack (enable/disable)

# Expected output:
# ✓ Phase 1: System Initialization - COMPLETE
# ✓ Phase 2: System Backup - COMPLETE
# ✓ Phase 3: Configuration Generation - COMPLETE
# ✓ Phase 4: Pre-deployment Validation - COMPLETE
# ✓ Phase 5: Declarative Deployment - COMPLETE
# ✓ Phase 6: Additional Tooling - COMPLETE
# ✓ Phase 7: Post-deployment Validation - COMPLETE
# ✓ Phase 8: Finalization and Report - COMPLETE

# Result: Fully configured NixOS system with AI stack
```

### Example 2: Update System After Configuration Changes

**Scenario**: Made changes to `configuration.nix`, need to deploy.

```bash
# 1. Edit configuration
vim ~/.dotfiles/home-manager/configuration.nix

# Add new package:
# environment.systemPackages = with pkgs; [
#   # ... existing packages ...
#   neovim  # NEW
# ];

# 2. Deploy changes (skip earlier phases)
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --start-from-phase 5

# Expected output:
# ✓ Phase 5: Declarative Deployment - COMPLETE
# ✓ Phase 6: Additional Tooling - COMPLETE
# ✓ Phase 7: Post-deployment Validation - COMPLETE
# ✓ Phase 8: Finalization and Report - COMPLETE

# 3. Verify new package
which neovim
# Output: /run/current-system/sw/bin/neovim

# Result: Configuration updated, new package installed
```

### Example 3: Troubleshooting Failed Deployment

**Scenario**: Deployment failed at Phase 5, need to debug and retry.

```bash
# 1. Check error logs
tail -100 ~/.cache/nixos-quick-deploy/logs/deploy-*.log

# Found error:
# ERROR: Syntax error in configuration.nix line 1234

# 2. Fix configuration
vim ~/.dotfiles/home-manager/configuration.nix

# Fix syntax error (missing semicolon)

# 3. Validate fix
nix flake check ~/.dotfiles/home-manager/

# 4. Resume deployment from failed phase
./nixos-quick-deploy.sh --start-from-phase 5

# Expected output:
# ✓ Phase 5: Declarative Deployment - COMPLETE (now succeeds)
# ... remaining phases complete ...

# Result: Deployment completes successfully after fix
```

### Example 4: Fresh Start After Testing

**Scenario**: Tested deployment multiple times, want to reset for final clean run.

```bash
# 1. Reset all state and preferences
./nixos-quick-deploy.sh --reset-state

# This clears:
# - ~/.cache/nixos-quick-deploy/state.json
# - ~/.cache/nixos-quick-deploy/preferences/
# - Backup history (optional)

# 2. Run full deployment from scratch
./nixos-quick-deploy.sh

# 3. Respond to all prompts again with final values

# Result: Clean deployment with final configuration
```

### Example 5: Check Deployment Status Without Running

**Scenario**: Want to see current phase and deployment history.

```bash
# 1. View current state
cat ~/.cache/nixos-quick-deploy/state.json

# Output:
# {
#   "current_phase": 8,
#   "completed_phases": [1, 2, 3, 4, 5, 6, 7, 8],
#   "deployment_id": "20251122_094500"
# }

# 2. List all phases
./nixos-quick-deploy.sh --list-phases

# Output:
# Phase 1: System Initialization
# Phase 2: System Backup
# Phase 3: Configuration Generation
# Phase 4: Pre-deployment Validation
# Phase 5: Declarative Deployment
# Phase 6: Additional Tooling
# Phase 7: Post-deployment Validation
# Phase 8: Finalization and Report

# 3. View latest deployment log
less ~/.cache/nixos-quick-deploy/logs/deploy-$(ls -t ~/.cache/nixos-quick-deploy/logs/ | head -1)

# Result: Complete status overview without running deployment
```

## Advanced Usage

### Custom GPU Configuration

If GPU auto-detection fails:

```bash
# 1. Manually specify GPU
export GPU_VENDOR="nvidia"  # or "amd" or "intel"

# 2. Run deployment
./nixos-quick-deploy.sh

# Or edit configuration directly:
vim ~/.dotfiles/home-manager/configuration.nix

# Add:
# services.xserver.videoDrivers = [ "nvidia" ];
```

### Selective Package Installation

Skip package prompts by pre-setting preferences:

```bash
mkdir -p ~/.cache/nixos-quick-deploy/preferences

cat > ~/.cache/nixos-quick-deploy/preferences/packages.env << 'EOF'
GAMING_PACKAGES=true
DEVELOPMENT_PACKAGES=true
AI_STACK=true
FLATPAK_PACKAGES=false
EOF

./nixos-quick-deploy.sh
```

### Automated/Headless Deployment

For CI/CD or scripted deployments:

```bash
# Pre-configure all preferences
mkdir -p ~/.cache/nixos-quick-deploy/preferences

# Git identity
echo 'GIT_USER_NAME="CI Bot"' > ~/.cache/nixos-quick-deploy/preferences/git-identity.env
echo 'GIT_USER_EMAIL="ci@example.com"' >> ~/.cache/nixos-quick-deploy/preferences/git-identity.env

# GPU (skip detection)
echo 'GPU_VENDOR="none"' > ~/.cache/nixos-quick-deploy/preferences/gpu.env

# Packages
echo 'GAMING_PACKAGES=false' > ~/.cache/nixos-quick-deploy/preferences/packages.env
echo 'AI_STACK=true' >> ~/.cache/nixos-quick-deploy/preferences/packages.env

# Run deployment (all prompts skipped)
./nixos-quick-deploy.sh --skip-health-check
```

## Rollback Procedure

If deployment causes issues:

```bash
# 1. List NixOS generations
sudo nix-env --list-generations --profile /nix/var/nix/profiles/system

# Output:
#   1   2025-11-20 10:00:00
#   2   2025-11-21 15:30:00
#   3   2025-11-22 09:45:00 (current)

# 2. Rollback to previous generation
sudo nixos-rebuild switch --rollback

# Or rollback to specific generation
sudo nix-env --switch-generation 2 --profile /nix/var/nix/profiles/system
sudo /nix/var/nix/profiles/system/bin/switch-to-configuration switch

# 3. Verify rollback
nixos-version
```

## Performance Tips

### Speed Up Deployments

1. **Use binary cache**:
```nix
# In configuration.nix
nix.settings.substituters = [
  "https://cache.nixos.org"
  "https://nix-community.cachix.org"
];
```

2. **Parallel downloads**:
```nix
nix.settings.max-jobs = "auto";
nix.settings.cores = 0;  # Use all CPU cores
```

3. **Skip unnecessary phases**:
```bash
./nixos-quick-deploy.sh --start-from-phase 5 --skip-health-check
```

## Security Considerations

### Secrets Management

The deployment supports sops-nix for encrypted secrets:

```bash
# 1. Generate age key (done automatically in Phase 1)
age-keygen -o ~/.config/sops/age/keys.txt

# 2. Edit secrets
cd ~/.dotfiles/home-manager
sops secrets.yaml

# 3. Deploy with encrypted secrets
./nixos-quick-deploy.sh --start-from-phase 5
```

### Permissions

Default permissions after deployment:
- `/nix/store`: Read-only for all users
- `~/.dotfiles/`: User-owned
- `/run/secrets/`: Root-owned, 0400 permissions

## Logs and Debugging

### Log Locations
- **Deployment logs**: `~/.cache/nixos-quick-deploy/logs/deploy-*.log`
- **State file**: `~/.cache/nixos-quick-deploy/state.json`
- **Backup location**: `~/.cache/nixos-quick-deploy/backups/`
- **System logs**: `journalctl -xe`

### Debug Mode

Enable verbose logging:

```bash
export NIXOS_DEPLOY_DEBUG=1
./nixos-quick-deploy.sh
```

### Common Log Messages

```
INFO: Starting Phase 5: Declarative Deployment
DEBUG: Running nixos-rebuild switch...
SUCCESS: Phase 5 completed in 45 seconds
ERROR: Phase 5 failed with exit code 1
WARNING: GPU driver not loaded, continuing anyway
```

## Version Compatibility

- **Script Version**: 5.0.0
- **NixOS**: 23.11 or later
- **Home Manager**: Latest stable
- **Flakes**: Enabled by default

## Support and Documentation

- **README**: `~/Documents/NixOS-Dev-Quick-Deploy/README.md`
- **Deployment Success Report**: `DEPLOYMENT-SUCCESS-V5.md`
- **System Improvements**: `SYSTEM-IMPROVEMENTS-V5.md`
- **Health Check**: `./scripts/system-health-check.sh --detailed`

## Skill Metadata

- **Skill Version**: 1.0.0
- **Last Updated**: 2025-11-22
- **Compatibility**: OpenSkills 1.2.1+
- **MCP Integration**: Yes
- **Category**: system-management
- **Tags**: nixos, deployment, automation, ai-stack, flakes, declarative
