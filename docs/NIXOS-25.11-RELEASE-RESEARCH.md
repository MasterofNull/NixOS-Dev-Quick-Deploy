# NixOS 25.11 "Xantusia" - Comprehensive Release Research

**Release Date:** November 30, 2025
**Research Date:** December 3, 2025
**Project:** NixOS-Dev-Quick-Deploy
**Status:** Production Release (Stable)

---

## Executive Summary

NixOS 25.11 "Xantusia" represents a major milestone release with contributions from **2,742 contributors** authoring **59,430 commits** since the previous release.

### Release Statistics

- ✅ **7,002 new packages** added
- ✅ **25,252 existing packages** updated
- ✅ **107 new modules** added
- ✅ **1,778 new configuration options** added
- ⚠️ **6,338 outdated packages** removed
- ⚠️ **41 outdated modules** removed
- ⚠️ **807 configuration options** removed

### Support Timeline

- **Active Support:** Until June 30, 2026 (7 months)
- **Previous Release (25.05 "Warbler"):** EOL December 31, 2025

### Release Managers

- @jopejoe1
- @leona-ya

---

## Major System Updates

### Desktop Environments

#### GNOME 49 "Brescia"

**Breaking Change:** X11 session support completely removed

**New Features:**
- New video player application
- New document viewer (replacing Evince)
- Redesigned calendar application with improved UI
- Enhanced Wayland-native performance
- XWayland support maintained for legacy X11 apps

**Migration Path:**
```nix
# Ensure XWayland is enabled for legacy apps
programs.xwayland.enable = true;
```

**Sources:**
- [NixOS Blog - Official Release](https://nixos.org/blog/announcements/2025/nixos-2511/)
- [Release Notes](https://nixos.org/manual/nixos/stable/release-notes)

#### COSMIC Desktop Environment (Beta)

**Status:** Beta version, production-ready

**Key Features:**
- Rust-based desktop environment from System76
- Lightweight and highly customizable architecture
- Tiled window manager with Lua scripting support
- Native Wayland compositor
- Performance-optimized for modern hardware

**Configuration:**
```nix
# Enable COSMIC desktop
services.desktopManager.cosmic.enable = true;

# Enable COSMIC greeter (login manager)
services.displayManager.cosmic-greeter.enable = true;

# Performance boost with System76 scheduler
services.system76-scheduler.enable = true;

# Exclude specific default apps (25.11+ only)
environment.cosmic.excludePackages = [
  # pkgs.cosmic-edit
  # pkgs.cosmic-files
];
```

**Sources:**
- [9to5Linux - COSMIC Beta Release](https://9to5linux.com/nixos-25-11-released-with-gnome-49-cosmic-beta-and-firewalld-support)
- [NixOS Wiki - COSMIC](https://wiki.nixos.org/wiki/COSMIC)
- [GitHub - nixos-cosmic](https://github.com/lilyinstarlight/nixos-cosmic)

#### Pantheon Desktop

**Change:** Now defaults to Wayland sessions instead of X11

---

### Linux Kernel & Core System

#### Kernel Updates

| Component | Previous | NixOS 25.11 | Notes |
|-----------|----------|-------------|-------|
| Default Kernel | 6.6 | **6.12 LTS** | All supported kernels remain available |
| Linux 5.4 | ✅ | ❌ Removed | End of upstream support |

**Custom Kernel Support:**
- TKG, XanMod, Liquorix, Zen kernels still supported
- User-configured kernel preferences preserved

**Sources:**
- [Phoronix - NixOS 25.11 Released](https://www.phoronix.com/news/NixOS-25.11-Released)

#### Toolchain Updates

| Component | Previous | NixOS 25.11 | Impact |
|-----------|----------|-------------|--------|
| GCC | 13 | **14** | Improved C++23 support, better optimizations |
| LLVM/Clang | - | **21** | Alternative to GCC 14 |
| CMake | 3.x | **4.x** | Major version bump |

**Sources:**
- [NixOS Blog](https://nixos.org/blog/announcements/2025/nixos-2511/)
- [9to5Linux](https://9to5linux.com/nixos-25-11-released-with-gnome-49-cosmic-beta-and-firewalld-support)

---

## Programming Language & Runtime Updates

### Python Ecosystem

#### Python 3.13 Now Default

**Major Change:** The `python3` attribute now points to **CPython 3.13**

**Package Availability:**
```nix
# Default Python (3.13)
python3
python3Packages.<package>

# Specific Python versions
python313
python313Packages.<package>

python312
python312Packages.<package>
```

**Shell Example:**
```bash
nix-shell -p 'python313.withPackages(ps: with ps; [ numpy pandas torch ])'
```

**Sources:**
- [NixOS Wiki - Python](https://nixos.wiki/wiki/Python)
- [nixpkgs Python Documentation](https://github.com/NixOS/nixpkgs/blob/master/doc/languages-frameworks/python.section.md)

#### AI/ML Package Ecosystem

**PyTorch:**
- Package: `python3Packages.pytorch` or `python3Packages.torch`
- CUDA Support: Available via `python3Packages.torchWithCuda`
- Recommend: Use `cuda-maintainers` cache for faster builds

```bash
cachix use cuda-maintainers
```

**TensorFlow:**
- Package: `python3Packages.tensorflow`
- GPU Support: `python3Packages.tensorflowWithCuda`
- ROCm Support: Community packaging in progress

**LangChain Ecosystem:**

Full integration available with modular packages:
- `python3Packages.langchain-core` - Core framework
- `python3Packages.langchain-openai` - OpenAI integration
- `python3Packages.langchain-huggingface` - HuggingFace models
- `python3Packages.langchain-mongodb` - MongoDB vector store
- `python3Packages.langchain-aws` - AWS Bedrock integration
- `python3Packages.langchain-perplexity` - Perplexity API

**Sources:**
- [NixOS Discourse - PyTorch CUDA](https://discourse.nixos.org/t/pytorch-with-cuda-support/51189)
- [NixOS Wiki - TensorFlow](https://nixos.wiki/wiki/Tensorflow)
- [MyNixOS - LangChain Packages](https://mynixos.com/nixpkgs/package/python312Packages.langchain-core)
- [NixOS Discourse - AI Packages](https://discourse.nixos.org/t/on-nixpkgs-and-the-ai-follow-up-to-2023-nix-developer-dialogues/37087)

### Node.js Updates

- `nodejs_latest` updated from 23.x to **24.x**
- `nodejs_23` removed in favor of `nodejs_24`

### Database Versions

**PostgreSQL:**
- Default for new installations (`system.stateVersion >= 25.11`): **PostgreSQL 17**
- All previous versions remain available for existing systems

**OpenSSH:**
- Updated from 9.9p2 to **10.0p2**
- **Breaking:** DSA key support dropped

---

## New System Features

### 1. NixOS-Init (Rust-based Systemd Initrd)

**Revolutionary Feature:** Bashless initialization system

**Benefits:**
- Build NixOS systems without any interpreter dependencies
- Faster boot times
- Reduced attack surface
- Better error handling with Rust safety guarantees

**Configuration:**
```nix
system.nixos-init.enable = true;
```

**Status:** Stable, production-ready

**Sources:**
- [NixOS Manual - Release Notes](https://nixos.org/manual/nixos/stable/release-notes)

### 2. FirewallD Support

**New Capability:** Dynamic firewall management

**Two Integration Modes:**

**Standalone Service:**
```nix
services.firewalld.enable = true;
```

**Backend to Existing Firewall:**
```nix
networking.firewall = {
  enable = true;
  backend = "firewalld";
};
```

**Advantages:**
- Runtime rule changes without restart
- Zone-based management
- D-Bus API for automation
- Better integration with containerized workloads

**Sources:**
- [9to5Linux - FirewallD Support](https://9to5linux.com/nixos-25-11-released-with-gnome-49-cosmic-beta-and-firewalld-support)
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

### 3. rEFInd Boot Manager

**New Option:** Graphical UEFI boot manager

**Use Case:** Multi-boot systems, dual-boot configurations

**Configuration:**
```nix
boot.loader.refind.enable = true;
```

**Features:**
- Graphical boot menu
- Automatic OS detection
- Custom themes support
- Touchscreen-friendly interface

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

### 4. NixOS-Rebuild-NG

**Major Change:** Default rebuild tool rewritten in Rust

**Previous:** Perl implementation
**Current:** Rust implementation (faster, more reliable)

**Automatically Enabled:** No configuration needed

**Benefits:**
- Improved error messages
- Better progress reporting
- Reduced rebuild times
- Enhanced rollback safety

---

## Container & Virtualization Improvements

### Podman Rootless Containers - Native Support

**Major Breakthrough:** `virtualisation.oci-containers` now supports rootless mode natively

**Previous Limitation:** Rootless Podman containers required manual systemd user services

**New Capability:**
```nix
virtualisation.oci-containers.containers.myapp = {
  image = "docker.io/library/nginx:latest";

  # NEW: Rootless mode
  podman.user = "username";

  # NEW: Health checks
  healthcheck = {
    interval = "30s";
    timeout = "10s";
    retries = 3;
  };
};
```

**Technical Improvements:**

1. **Container ID Files:** Moved to `/run/${containerName}` for rootless write access
2. **SD-Notify Support:** `sdnotify = "healthy"` keeps units activating until healthy
3. **Cgroup Delegation:** `Delegate=yes` enables proper cgroup support for rootless
4. **Subuid/Subgid Fixes:** Colliding ranges resolved automatically

**Breaking Change Warning:**

Users with existing rootless containers may see warnings on first activation:
```
Warning: New subuid range assigned. Please adjust file ownership if using rootless containers.
```

**Migration Guide:**
```bash
# Check current subuid/subgid
cat /etc/subuid
cat /etc/subgid

# After upgrade, verify container storage
podman info --format '{{.Store.GraphDriverName}}'
```

**Sources:**
- [GitHub PR #368565 - Rootless OCI Containers](https://github.com/NixOS/nixpkgs/pull/368565)
- [NixOS Discourse - Rootless Podman](https://discourse.nixos.org/t/rootless-podman-setup-with-home-manager/57905)
- [NixOS Wiki - Podman](https://wiki.nixos.org/wiki/Podman)

### Docker Updates

**Version Change:** Docker 27.x → **Docker 28.x**

**Reason:** Docker 27.x reached EOL on May 2, 2025

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

---

## New Services & Modules (107 Total)

### Monitoring & Performance

#### LACT - GPU Monitoring & Configuration

```nix
services.lact.enable = true;
```

**Features:**
- AMD, NVIDIA, and Intel GPU support
- Clock tuning and voltage offset
- Fan curve customization
- Power limit adjustment
- GTK GUI application

**Auto-Detection:**
```nix
# Auto-enable when GPU detected (default)
services.lact.enable = "auto";

# For AMD GPU overclocking
hardware.amdgpu.overdrive.enable = true;
```

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

#### Other Monitoring Tools

- `services.beszel` - Lightweight server monitoring
- `nvme-rs` - NVMe drive monitoring and alerts

### Networking & Security

#### CrowdSec - Collaborative IPS

```nix
services.crowdsec.enable = true;
```

**Features:**
- Free, open-source intrusion prevention
- Community-powered threat intelligence
- Automatic IP blocklist updates
- Integration with existing firewalls

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

#### Other Networking Services

- `services.chhoto-url` - Rust-based URL shortener
- `Warpgate` - SSH/HTTPS bastion host
- `EasyTier` - Decentralized VPN mesh network
- Enhanced Nebula overlay network support

### AI & Translation

#### LibreTranslate - Machine Translation API

```nix
services.libretranslate.enable = true;
```

**Features:**
- Free, open-source translation API
- Local/offline translation
- REST API compatible with Google Translate
- Multiple language support

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

### Media & Entertainment

- `Ersatz TV` - Personal IPTV server
- `Spoolman` - 3D printer filament tracking

### Self-Hosted Applications

- `Pi-hole` - Network-wide ad blocking
- `Linkwarden` - Bookmark manager
- `Paisa` - Personal finance tracker

### Development Tools

- `Radicle CI broker` - Decentralized code collaboration

---

## Breaking Changes & Deprecations

### Desktop Environment Removals

#### Qt 5 KDE Variants - Completely Removed

**Removed Packages:**
- Qt 5 versions of KDE Plasma
- Qt 5 KDE Gear applications
- Qt 5 Maui applications
- Qt 5 Deepin desktop

**Migration Path:**
- Use Qt 6 versions (available and recommended)
- All KDE applications migrated to Qt 6

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

#### GNOME X11 Sessions

**Breaking Change:** X11 sessions completely removed from GNOME 49

**Workaround:**
```nix
# Enable XWayland for legacy X11 apps
programs.xwayland.enable = true;
```

### Kernel Removals

- **Linux 5.4** and all variants removed (upstream EOL)

### Database & Service Changes

#### PostgreSQL Default Version

**For New Installations Only:**
```nix
# system.stateVersion = "25.11";
# Automatic default: PostgreSQL 17

# Existing systems preserve their version
# system.stateVersion = "24.11";
# Stays on PostgreSQL 16 (or configured version)
```

#### Prosody XMPP Server

**Major Version:** Upgraded to Prosody 0.13

**Breaking Changes:**
- Some modules removed or renamed
- Configuration syntax updates required
- Check Prosody migration guide

#### Meilisearch

**Change:** Now defaults to latest version instead of pinned version

**Impact:** Automatic version updates on rebuild

#### Immich Photo Management

**Breaking Change:** pgvecto-rs deprecated

**Migration Required:**
```nix
# New default: VectorChord
# Requires database migration for existing installations
```

**Sources:**
- [NixOS Manual](https://nixos.org/manual/nixos/stable/release-notes)

### Network & Service Configuration

#### NetworkManager VPN Plugins

**Breaking Change:** VPN plugins no longer installed by default

**Fix:**
```nix
networking.networkmanager.vpnPlugins = [
  pkgs.networkmanager-openvpn
  pkgs.networkmanager-wireguard
  # Add other VPN plugins as needed
];
```

#### Display Manager TTY Allocation

**Change:** Display managers now strictly use `tty1`

**Impact:** Custom TTY configurations may need adjustment

#### Postfix TLS Configuration

**Breaking Change:** TLS configuration restructured

**Migration:** Check `services.postfix.tlsConfig` documentation

### Removed Services (Unmaintained)

The following services have been removed:
- Gateone
- Polipo
- PostfixAdmin
- Multiple other unmaintained packages

**Check your configuration for these services before upgrading**

---

## Home Manager 25.11 Changes

### Profile Management Deprecation

**Breaking Change:** Activation script no longer updates home-manager profile

**Impact:**
- Profile updates are now the responsibility of the calling tool
- `home-manager` CLI tool handles profile updates
- NixOS/nix-darwin modules handle their own profiles

**Restore Old Behavior (Not Recommended):**
```nix
home-manager.enableLegacyProfileManagement = true;
```

**Sources:**
- [Home Manager Release Notes](https://nix-community.github.io/home-manager/release-notes.xhtml)

### Shadow Profile Removal

**Change:** NixOS/nix-darwin modules no longer create per-user "shadow profiles"

**Benefits:**
- Cleaner profile management
- Reduced disk usage
- Simplified profile hierarchy

### Password Store Default Change

**Breaking Change:**
```nix
# OLD behavior (< 25.11):
# programs.password-store.settings automatically set:
# PASSWORD_STORE_DIR = $XDG_DATA_HOME/password-store

# NEW behavior (>= 25.11):
# Uses upstream default: $HOME/.password-store
```

**Migration:**
```nix
# Explicitly set if you need XDG compliance:
programs.password-store.settings = {
  PASSWORD_STORE_DIR = "${config.xdg.dataHome}/password-store";
};
```

---

## Additional Notable Changes

### Boot & Containers

**NixOS Container Detection:**
```nix
boot.isNspawnContainer = true;
```
- New option for container-specific configurations
- Optimizes settings for systemd-nspawn containers

### Hardware Configuration

**AMD GPU Overdrive:**
```nix
hardware.amdgpu.overdrive = {
  enable = true;
  # Enables overclocking/undervolting for AMD GPUs
};
```

**ACME Certificate Management:**
- Revamped certificate renewal process
- Better scalability for large deployments
- Improved error handling

### Firmware & Bootloader

**libvirt OVMF Paths:**
- New naming scheme for UEFI firmware
- Automatic migration for existing VMs

**Limine Bootloader:**
- Now supports Secure Boot functionality

### RFC42 Conversions

**Systemd & Logind Settings:**

Many configuration options migrated to RFC42 style:
```nix
# OLD:
services.logind.extraConfig = "IdleAction=lock";

# NEW (RFC42):
services.logind.settings = {
  Login = {
    IdleAction = "lock";
  };
};
```

---

## macOS-Specific Changes

### Minimum Requirements

**New Minimum:** macOS Sonoma 14.0

**Default SDK:** 14.4

**Impact:** Older macOS versions no longer supported for Nix builds

**Sources:**
- [nixpkgs Release Notes](https://nixos.org/manual/nixpkgs/stable/release-notes)

---

## Comparison with NixOS-Dev-Quick-Deploy Current System

### System Analysis

Based on the current deployment configuration:

#### ✅ Already Well-Positioned

| Feature | Current System | NixOS 25.11 | Status |
|---------|----------------|-------------|--------|
| COSMIC Desktop | ✅ Enabled | ✅ Beta (Stable) | Ready for upgrade |
| Hyprland Wayland | ✅ Configured | ✅ Continued support | Compatible |
| Podman Rootless | ✅ Manual setup | ✅ Native OCI support | **Major upgrade available** |
| Python 3.13 | ✅ Available (with PYTHON_PREFER_PY314 flag) | ✅ Default | Compatible |
| AI/ML Packages | ✅ 60+ packages pre-installed | ✅ Full ecosystem | Compatible |

#### ⚡ Upgrade Opportunities

**1. Kernel Configuration**

Current:
```nix
# Preference track: linuxPackages_6_17 → TKG → XanMod → Liquorix → Zen → latest
```

NixOS 25.11 Default:
```nix
# linuxPackages_6_12 (LTS)
```

**Recommendation:** Keep current preference track (all kernels still supported)

**2. Compiler Upgrade**

- Current: Likely GCC 13
- 25.11: **GCC 14** (automatic upgrade)
- Impact: Better C++23 support, improved optimizations

**3. Podman OCI Containers Migration**

**Current Implementation:**
```bash
# Manual systemd user services in:
# ~/.config/systemd/user/podman-*.service
```

**Recommended Migration to 25.11:**
```nix
virtualisation.oci-containers.containers = {
  lemonade = {
    image = "ghcr.io/lemonade/server:latest";
    podman.user = "hyperd";  # NEW: Native rootless
    ports = [ "8000:8000" ];
    volumes = [
      "${config.home.homeDirectory}/.cache/huggingface:/models:ro"
    ];
  };

  mcp-postgres = {
    image = "timescale/timescaledb-ha:pg17";
    podman.user = "hyperd";
    ports = [ "5432:5432" ];
    environment = {
      POSTGRES_DB = "mcp";
      POSTGRES_USER = "mcp";
    };
  };

  mcp-redis = {
    image = "redis:7-alpine";
    podman.user = "hyperd";
    ports = [ "6379:6379" ];
  };
};
```

**4. PostgreSQL Upgrade Path**

Current AI-Optimizer Stack:
```yaml
# docker-compose.yml
postgres:
  image: timescale/timescaledb-ha:pg16  # or pg15
```

25.11 Recommendation:
```yaml
postgres:
  image: timescale/timescaledb-ha:pg17  # New default
```

**Migration Steps:**
1. Backup existing database
2. Update image tag
3. Run `pg_upgrade` or dump/restore
4. Test AIDB MCP server compatibility

**5. New Features to Adopt**

**LACT GPU Monitoring:**
```nix
# Auto-enables when AMD/NVIDIA/Intel GPU detected
services.lact.enable = true;

# For AMD overclocking (if needed)
hardware.amdgpu.overdrive.enable = true;
```

**FirewallD (Optional):**
```nix
# Better for dynamic container port management
networking.firewall.backend = "firewalld";
```

**NixOS-Init (Performance):**
```nix
# Faster boot with Rust-based initrd
system.nixos-init.enable = true;
```

#### ⚠️ Potential Compatibility Issues

**1. Home Manager Profile Management**

Current:
```bash
# ~/.dotfiles/home-manager/
# Managed by home-manager switch
```

Action Required:
- Review Home Manager 25.11 release notes
- Test profile management changes
- May need to set `enableLegacyProfileManagement = true` temporarily

**2. Flatpak VSCodium Conflict**

Current Configuration:
```nix
# programs.vscode (declarative) in home.nix
```

Ensure no Flatpak VSCodium:
```bash
# Check for conflicts
flatpak list --user | grep -i codium

# Remove if found (conflicts with declarative config)
flatpak uninstall com.vscodium.codium
```

**3. Subuid/Subgid Ranges**

**First activation warning expected:**
```
Warning: Subuid ranges have been adjusted. Check file ownership.
```

**Fix (if needed):**
```bash
# Check container storage ownership
ls -la ~/.local/share/containers/storage/

# Reset if needed
podman system reset --force
```

**4. AI-Optimizer Docker Compose Compatibility**

**Test Required:**
- Verify Docker 28.x compatibility with current compose files
- Check Lemonade server compatibility with updated Python 3.13
- Test AIDB MCP server with PostgreSQL 17 (if upgrading)

#### 🆕 New Capabilities to Explore

**1. LibreTranslate for Local AI Translation**

Use case: AI-Optimizer document translation without external APIs

```nix
services.libretranslate = {
  enable = true;
  port = 5000;
};
```

**2. CrowdSec IPS for Network Monitoring**

Aligns with project goal: "Network Activity Monitoring - Threat detection and automated response"

```nix
services.crowdsec = {
  enable = true;
  settings = {
    api.server.listen_uri = "127.0.0.1:8080";
  };
};
```

**3. Improved Hyprland UWSM Integration**

Already available in 24.11, continued in 25.11:
```nix
programs.hyprland = {
  enable = true;
  uwsm.enable = true;  # Universal Wayland Session Manager
};
```

---

## Upgrade Strategy Recommendations

### Phase 1: Preparation (Before Upgrade)

**1. Backup Critical Data**

```bash
# AI-Optimizer data
tar -czf ~/backup-ai-optimizer-$(date +%Y%m%d).tar.gz \
  ~/.local/share/ai-optimizer \
  ~/.config/ai-optimizer

# NixOS configurations
tar -czf ~/backup-nixos-config-$(date +%Y%m%d).tar.gz \
  ~/.dotfiles/home-manager \
  /etc/nixos/configuration.nix

# State and preferences
tar -czf ~/backup-state-$(date +%Y%m%d).tar.gz \
  ~/.cache/nixos-quick-deploy
```

**2. Document Current State**

```bash
# Run health check
./scripts/system-health-check.sh --detailed > pre-upgrade-health.txt

# List installed packages
nix-env -qa > pre-upgrade-packages.txt

# Check current generations
sudo nix-env --list-generations --profile /nix/var/nix/profiles/system
home-manager generations
```

**3. Test in VM (Recommended)**

```nix
# Create test VM configuration
# Test upgrade path before production
```

### Phase 2: Upgrade Execution

**1. Update Channel References**

```nix
# In flake.nix or configuration.nix
nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
home-manager.url = "github:nix-community/home-manager/release-25.11";
```

**2. Update System State Version**

```nix
system.stateVersion = "25.11";
home.stateVersion = "25.11";
```

**3. Apply Upgrade**

```bash
# Update flake inputs
nix flake update ~/.dotfiles/home-manager

# Rebuild system
sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager

# Rebuild home environment
home-manager switch --flake ~/.dotfiles/home-manager
```

### Phase 3: Post-Upgrade Validation

**1. Run Health Checks**

```bash
./scripts/system-health-check.sh --detailed
./scripts/test_services.sh
./scripts/test_real_world_workflows.sh
```

**2. Verify AI-Optimizer Stack**

```bash
cd ~/Documents/AI-Optimizer
docker compose ps
curl http://localhost:8091/health
curl http://localhost:8000/health  # Lemonade
```

**3. Test Podman Rootless Migration**

```bash
# Check rootless containers
podman ps --all
podman info --format '{{.Store.GraphDriverName}}'

# Verify file ownership
ls -la ~/.local/share/containers/storage/
```

**4. Validate Python Environment**

```bash
python3 --version  # Should show 3.13.x
python3 -c "import torch; print(torch.__version__)"
python3 -c "import tensorflow; print(tensorflow.__version__)"
python3 -c "import langchain; print(langchain.__version__)"
```

### Rollback Plan

**If Issues Occur:**

```bash
# System rollback
sudo nixos-rebuild switch --rollback

# Home Manager rollback
home-manager generations  # Find previous generation
home-manager switch --switch-generation <NUMBER>

# Container reset (if needed)
podman system reset --force
```

---

## Migration Checklist

### Pre-Upgrade

- [ ] Backup AI-Optimizer data (`~/.local/share/ai-optimizer/`)
- [ ] Backup NixOS configurations (`~/.dotfiles/home-manager/`)
- [ ] Backup deployment state (`~/.cache/nixos-quick-deploy/`)
- [ ] Document current package list
- [ ] Run system health check (baseline)
- [ ] Stop AI-Optimizer services
- [ ] Create VM test environment (optional but recommended)

### Configuration Updates

- [ ] Update `nixpkgs` channel/flake to `nixos-25.11`
- [ ] Update `home-manager` to `release-25.11`
- [ ] Set `system.stateVersion = "25.11"`
- [ ] Set `home.stateVersion = "25.11"`
- [ ] Review and update deprecated options
- [ ] Add new module options (FirewallD, LACT, etc.)

### Post-Upgrade Validation

- [ ] Verify kernel version (`uname -r` → 6.12.x)
- [ ] Verify GCC version (`gcc --version` → 14.x)
- [ ] Verify Python version (`python3 --version` → 3.13.x)
- [ ] Test COSMIC desktop functionality
- [ ] Test Hyprland Wayland session
- [ ] Verify Podman rootless containers
- [ ] Test AI/ML Python packages (PyTorch, TensorFlow, LangChain)
- [ ] Start AI-Optimizer stack
- [ ] Verify AIDB MCP server health
- [ ] Verify Lemonade inference server
- [ ] Run full system health check
- [ ] Test real-world workflows

### AI-Optimizer Specific

- [ ] Verify PostgreSQL compatibility (consider v17 upgrade)
- [ ] Test Redis AOF persistence
- [ ] Verify Lemonade model loading
- [ ] Test MCP server endpoints
- [ ] Verify document imports (512+ NixOS configs)
- [ ] Test skill discovery
- [ ] Validate time-series data tables
- [ ] Test vector search functionality

### Documentation

- [ ] Update `AGENTS.md` with 25.11 information
- [ ] Document any breaking changes encountered
- [ ] Update `README.md` with new features
- [ ] Create upgrade notes for future reference

---

## Key Resources & References

### Official Documentation

- [NixOS 25.11 Release Announcement](https://nixos.org/blog/announcements/2025/nixos-2511/)
- [NixOS Manual - Release Notes](https://nixos.org/manual/nixos/stable/release-notes)
- [nixpkgs Release Notes](https://nixos.org/manual/nixpkgs/stable/release-notes)
- [Home Manager 25.11 Release Notes](https://nix-community.github.io/home-manager/release-notes.xhtml)

### GitHub Resources

- [NixOS/nixpkgs - Release 25.11 Branch](https://github.com/NixOS/nixpkgs/tree/release-25.11)
- [Release Schedule Issue #443568](https://github.com/NixOS/nixpkgs/issues/443568)
- [Feature Freeze & Blockers Issue #444721](https://github.com/NixOS/nixpkgs/issues/444721)
- [Podman Rootless PR #368565](https://github.com/NixOS/nixpkgs/pull/368565)

### Community Articles

- [Phoronix - NixOS 25.11 Released](https://www.phoronix.com/news/NixOS-25.11-Released)
- [9to5Linux - GNOME 49, COSMIC Beta, FirewallD](https://9to5linux.com/nixos-25-11-released-with-gnome-49-cosmic-beta-and-firewalld-support)
- [LinuxAdictos - Features & Changes](https://en.linuxadictos.com/nixos-25-11-xantusia-all-the-new-features-and-key-changes.html)

### Wiki & Community

- [NixOS Wiki - COSMIC](https://wiki.nixos.org/wiki/COSMIC)
- [NixOS Wiki - Hyprland](https://wiki.nixos.org/wiki/Hyprland)
- [NixOS Wiki - Podman](https://wiki.nixos.org/wiki/Podman)
- [NixOS Wiki - Python](https://wiki.nixos.org/wiki/Python)
- [NixOS Discourse - 25.11 Release Discussion](https://discourse.nixos.org/t/let-s-have-a-great-25-11-release-cycle/69475)

---

## Tags

`nixos-25.11`, `xantusia`, `release-notes`, `gnome-49`, `cosmic-beta`, `python-3.13`, `gcc-14`, `kernel-6.12`, `podman-rootless`, `firewalld`, `ai-ml-packages`, `pytorch`, `tensorflow`, `langchain`, `nixos-init`, `home-manager`, `upgrade-guide`, `breaking-changes`, `migration-guide`

---

**Document Version:** 1.0
**Last Updated:** December 3, 2025
**Maintained By:** AI Research Team
**Project:** NixOS-Dev-Quick-Deploy / AI-Optimizer Integration
