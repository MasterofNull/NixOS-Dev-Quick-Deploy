# NixOS Rebuild Recovery Instructions

## Problem Summary

Your system has two issues preventing successful rebuilds:

1. **Stuck Service**: A `nixos-rebuild-switch-to-configuration` service from 3+ hours ago is still running, blocking new rebuild attempts
2. **Broken sudo symlink**: `/run/current-system/sw/bin/sudo` points to a binary without setuid bit
   - **Working sudo available**: `/run/wrappers/bin/sudo` has correct permissions

## Quick Recovery Steps

### Step 1: Run the Recovery Script

Open a terminal and run:

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
bash ./fix-stuck-rebuild.sh
```

This script will:
- Stop the stuck `nixos-rebuild-switch-to-configuration` service
- Reset failed systemd units
- Reload systemd daemon
- Use the working sudo wrapper at `/run/wrappers/bin/sudo`

**Note**: You'll be prompted for your password when the script runs `sudo` commands.

### Step 2: Retry NixOS Rebuild

After the recovery script completes successfully, retry the rebuild:

```bash
/run/wrappers/bin/sudo nixos-rebuild switch --flake ~/.config/home-manager#$(hostname)
```

**Or** run the deployment script again:

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

---

## Manual Recovery (If Script Fails)

If the automated script doesn't work, run these commands manually:

```bash
# Stop stuck service
/run/wrappers/bin/sudo systemctl stop nixos-rebuild-switch-to-configuration.service

# If it won't stop, force kill it
/run/wrappers/bin/sudo systemctl kill -s SIGKILL nixos-rebuild-switch-to-configuration.service

# Reset failed units
/run/wrappers/bin/sudo systemctl reset-failed

# Reload systemd
/run/wrappers/bin/sudo systemctl daemon-reload

# Retry rebuild
/run/wrappers/bin/sudo nixos-rebuild switch --flake ~/.config/home-manager#$(hostname)
```

---

## What Will Be Fixed

Once the rebuild completes successfully:

1. ✅ **Sudo will be restored** - The correct sudo binary with setuid will be activated
2. ✅ **TGI directories created** - `/var/lib/huggingface/cache` and `/run/huggingface-scout` will be created
3. ✅ **TGI services will start** - Both `huggingface-tgi` and `huggingface-tgi-scout` services will be able to start
4. ✅ **Better error detection** - The validation scripts will properly detect and report service failures

---

## Verification After Rebuild

Once the rebuild completes, verify TGI services:

```bash
# Check service status
systemctl status huggingface-tgi.service
systemctl status huggingface-tgi-scout.service

# Check if directories were created
ls -la /var/lib/huggingface/cache
ls -la /var/lib/huggingface-scout/cache
ls -la /run/huggingface-scout

# Test endpoints
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8085/health
```

---

## Why This Happened

The previous `nixos-rebuild` was interrupted or failed during the activation phase:
1. The new system was built but not fully switched to
2. The `switch-to-configuration` script got stuck
3. sudo and other system wrappers weren't properly activated
4. The stuck service blocked subsequent rebuild attempts

This is a known edge case in NixOS when rebuilds fail partway through activation.
