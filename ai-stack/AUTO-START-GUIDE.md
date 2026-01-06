# AI Stack Auto-Start Configuration Guide

**Date:** December 31, 2025
**Version:** 1.0.0

---

## Overview

This guide explains how to configure the NixOS AI Stack to automatically start:
1. After NixOS Quick Deploy completes
2. After system reboots
3. After system shutdowns and restarts

---

## ✅ What's Already Configured

### 1. Container Restart Policies

All AI stack containers have `restart: unless-stopped` configured in [docker-compose.yml](compose/docker-compose.yml):

```yaml
services:
  llama-cpp:
    restart: unless-stopped
  qdrant:
    restart: unless-stopped
  redis:
    restart: unless-stopped
  postgres:
    restart: unless-stopped
  aidb:
    restart: unless-stopped
  hybrid-coordinator:
    restart: unless-stopped
  nixos-docs:
    restart: unless-stopped
  ralph-wiggum:
    restart: unless-stopped
  health-monitor:
    restart: unless-stopped
  # ... all 13+ services
```

**What this means:**
- ✅ Containers auto-restart if they crash
- ✅ Containers persist across `podman-compose restart`
- ✅ Containers **will NOT** auto-start after system reboot (by default)
- ⚠️ Manual intervention needed: `podman-compose up -d` after reboot

---

## 🔧 Auto-Start Configuration Options

### Option 1: NixOS Systemd Service (Recommended)

**Best for:** Production systems, hands-off operation

**Steps:**

1. **Copy the NixOS module to your configuration:**

```bash
# Add to /etc/nixos/configuration.nix
imports = [
  /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/templates/nixos-improvements/ai-stack-autostart.nix
];
```

2. **Rebuild NixOS:**

```bash
sudo nixos-rebuild switch
```

3. **Verify service is enabled:**

```bash
systemctl status ai-stack.service
```

**What you get:**
- ✅ Auto-start on boot
- ✅ Auto-restart on failure
- ✅ Proper dependency management (waits for network)
- ✅ Automatic health checks every 15 minutes
- ✅ Runs as unprivileged user (hyperd)

**Service files created:**
- `systemd.services.ai-stack` - Main startup service
- `systemd.services.ai-stack-health` - Health check service
- `systemd.timers.ai-stack-health` - Health check timer
- `systemd.user.services.ai-stack-monitor` - Dashboard (optional)

---

### Option 2: Podman Systemd Generator

**Best for:** Quick setup, minimal configuration

**Steps:**

1. **Generate systemd units from docker-compose.yml:**

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose up -d
cd ~/.config/systemd/user/
podman generate systemd --new --files --name local-ai-llama-cpp
```

2. **Enable services:**

```bash
systemctl --user enable container-local-ai-llama-cpp.service
systemctl --user enable container-local-ai-qdrant.service
# ... repeat for each container
```

3. **Enable linger (keeps services running after logout):**

```bash
loginctl enable-linger $USER
```

**What you get:**
- ✅ Auto-start on boot
- ⚠️ More manual setup (per-container)
- ⚠️ No automatic health checks

---

### Option 3: Startup Script in User Session

**Best for:** Development, testing, non-critical systems

**Steps:**

1. **Create autostart script:**

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/ai-stack.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=AI Stack Auto-Start
Exec=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/start-ai-stack-and-dashboard.sh
X-GNOME-Autostart-enabled=true
EOF
```

2. **Make script executable:**

```bash
chmod +x ~/.config/autostart/ai-stack.desktop
```

**What you get:**
- ✅ Simple setup
- ⚠️ Requires graphical login
- ⚠️ Starts after user login (not on boot)
- ⚠️ No automatic health checks

---

## 📊 AI Stack Monitor Dashboard Auto-Start

The [ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh) dashboard can be configured to auto-start:

### Option A: Systemd User Service (Recommended)

Already configured in [ai-stack-autostart.nix](../templates/nixos-improvements/ai-stack-autostart.nix):

```bash
# Enable the monitor dashboard
systemctl --user enable ai-stack-monitor.service
systemctl --user start ai-stack-monitor.service
```

### Option B: Terminal Multiplexer (tmux/screen)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Auto-start AI stack monitor in tmux session
if command -v tmux &>/dev/null && [[ -z "$TMUX" ]]; then
  if ! tmux has-session -t ai-monitor 2>/dev/null; then
    tmux new-session -d -s ai-monitor '/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-monitor.sh'
  fi
fi
```

**Access the dashboard:**
```bash
tmux attach -t ai-monitor
```

---

## 🚀 Auto-Start After NixOS Quick Deploy

The deployment script already handles this automatically:

**What happens:**

1. **Phase 8 (AI Stack Deployment):**
   - Runs [start-ai-stack-and-dashboard.sh](../scripts/start-ai-stack-and-dashboard.sh)
   - Starts all containers with `podman-compose up -d`
   - Runs health checks
   - Starts dashboard services

2. **Deployment Completion:**
   - Shows monitor dashboard location
   - Logs all actions
   - Provides troubleshooting hints

**Manual restart if needed:**
```bash
./scripts/start-ai-stack-and-dashboard.sh
```

---

## 🔍 Verification

### Check Container Status

```bash
podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected output:**
```
NAMES                          STATUS          PORTS
local-ai-llama-cpp             Up X hours      8080/tcp
local-ai-qdrant                Up X hours      6333/tcp
local-ai-redis                 Up X hours      6379/tcp
local-ai-postgres              Up X hours      5432/tcp
local-ai-aidb                  Up X hours      8091/tcp
local-ai-hybrid-coordinator    Up X hours      8092/tcp
local-ai-nixos-docs            Up X hours      8094/tcp
local-ai-ralph-wiggum          Up X hours      8093/tcp
local-ai-health-monitor        Up X hours      8095/tcp
```

### Check Systemd Service (If Using Option 1)

```bash
# Check service status
systemctl status ai-stack.service

# View logs
journalctl -u ai-stack.service -f

# Check health timer
systemctl list-timers --all | grep ai-stack
```

### Run Verification Script

```bash
./scripts/verify-upgrades.sh
```

---

## 🛠️ Troubleshooting

### Containers Not Starting After Reboot

**Symptom:** Containers are stopped after system reboot

**Solution:**
1. Enable systemd service (Option 1)
2. Or manually start: `cd ai-stack/compose && podman-compose up -d`

### Health Checks Failing

**Symptom:** Health check service reports errors

**Solution:**
```bash
# Check which service is unhealthy
podman ps -a --filter health=unhealthy

# View container logs
podman logs local-ai-<service-name>

# Restart specific service
podman-compose restart <service-name>
```

### Monitor Dashboard Not Updating

**Symptom:** Dashboard shows stale data or freezes

**Solution:**
```bash
# Kill and restart monitor
pkill -f ai-stack-monitor.sh
./scripts/ai-stack-monitor.sh
```

### Service Fails to Start on Boot

**Symptom:** `systemctl status ai-stack.service` shows failed

**Common causes:**
1. Network not ready: Check `After=network-online.target`
2. Permissions: Ensure User/Group match in service file
3. Working directory: Verify path in `WorkingDirectory=`

**Debug:**
```bash
# View detailed logs
journalctl -u ai-stack.service -b

# Check dependencies
systemctl list-dependencies ai-stack.service

# Manually test startup
sudo -u hyperd bash -c 'cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose && podman-compose up -d'
```

---

## 📝 Configuration Files Summary

| File | Purpose | Auto-Start Method |
|------|---------|-------------------|
| [docker-compose.yml](compose/docker-compose.yml) | Container definitions | `restart: unless-stopped` |
| [ai-stack-autostart.nix](../templates/nixos-improvements/ai-stack-autostart.nix) | Systemd integration | Option 1 (Recommended) |
| [ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh) | Live dashboard | Systemd user service |
| [start-ai-stack-and-dashboard.sh](../scripts/start-ai-stack-and-dashboard.sh) | Manual startup | Quick deploy integration |
| [nixos-quick-deploy.sh](../nixos-quick-deploy.sh) | Main deployment | Shows monitor at completion |

---

## 🎯 Recommended Setup

**For most users (production-ready):**

```bash
# 1. Add to NixOS configuration
sudo nano /etc/nixos/configuration.nix
# Add: imports = [ /home/hyperd/.../ai-stack-autostart.nix ];

# 2. Rebuild NixOS
sudo nixos-rebuild switch

# 3. Verify services
systemctl status ai-stack.service

# 4. (Optional) Enable monitor dashboard
systemctl --user enable ai-stack-monitor.service

# 5. Test reboot
sudo reboot
# Wait for system to come back up
podman ps  # Should show all containers running
```

---

## 🔮 Future Enhancements

Planned improvements:

- [ ] Kubernetes deployment manifests
- [ ] Graceful degradation (start core services first)
- [ ] Automatic backup on shutdown
- [ ] Resource quota enforcement
- [ ] Multi-node cluster support

---

## 📞 Support

**Documentation:**
- Main README: [README.md](../README.md)
- Upgrades Guide: [UPGRADES-2025.md](UPGRADES-2025.md)
- Quick Reference: [QUICK-REFERENCE.md](QUICK-REFERENCE.md)

**Troubleshooting:**
```bash
# Health check
./scripts/system-health-check.sh --detailed

# AI stack health
./scripts/ai-stack-health.sh

# Verification
./scripts/verify-upgrades.sh

# Live monitoring
./scripts/ai-stack-monitor.sh
```

---

**Status:** ✅ Production Ready
**Last Updated:** December 31, 2025
**Maintainer:** NixOS Quick Deploy Team
