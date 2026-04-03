---
Status: active
Owner: system
Updated: 2026-04-03
---

# Battery Charge Threshold Configuration

## Overview

Your NixOS configuration includes **battery charge threshold management** to prolong battery lifespan by limiting maximum charge to 80% (configurable). This is why your laptop stops charging before reaching 100% even when plugged in.

## COSMIC Desktop Integration

**If you're using the COSMIC desktop environment** (default in this config), battery charge thresholds are managed by **COSMIC Settings → Power** panel:

- **GUI Path:** Settings → Power → Battery Lifespan
- **Toggle:** "Maximize Battery Lifespan" (caps charging at 80%)
- **How it works:** COSMIC writes directly to sysfs and manages thresholds automatically
- **Config location:** `~/.config/cosmic/com.system76.CosmicSettings.Power/` (RON format)

**When COSMIC is active, the NixOS declarative battery service is automatically disabled** to avoid conflicts. You have two options:

### Option A: Use COSMIC GUI (Recommended for COSMIC users)
1. Open **Settings** from the COSMIC launcher
2. Navigate to **Power**
3. Toggle **Battery Lifespan** on/off
4. Changes apply immediately and persist across reboots

### Option B: Use NixOS Declarative Control
If you prefer declarative config over COSMIC GUI, you can:
1. Disable COSMIC's power management (not recommended)
2. Configure thresholds in your NixOS config (see below)
3. Rebuild: `sudo nixos-rebuild switch`

**For most COSMIC users, the GUI is the easiest path.**

## Problem: Battery Won't Charge to 100%

**This is intentional** — your system is configured to stop charging at 80% to reduce battery wear. However, you can now toggle this behavior when you need full capacity (e.g., before traveling).

## Configuration Options

All battery settings are under `mySystem.hardware.battery.*` in your NixOS config:

### Charge Thresholds (Default: Enabled)

```nix
mySystem.hardware.battery.chargeThresholds = {
  enable = true;          # Master toggle: false = charge to 100%
  startThreshold = 20;    # Start charging when battery drops to 20%
  stopThreshold = 80;     # Stop charging at 80%
};
```

**When to change:**
- Set `enable = false` to allow charging to 100% (before trips)
- Adjust `stopThreshold = 90` or `95` for a middle ground
- Adjust `startThreshold = 30` or `40` if you prefer shallower discharge cycles

### Conservation Mode (Default: Disabled)

```nix
mySystem.hardware.battery.conservationMode = {
  enable = false;         # Set true for always-plugged-in use
  startThreshold = 50;    # Start charging at 50%
  stopThreshold = 60;     # Stop charging at 60%
};
```

**When to enable:**
- Laptop stays plugged in at a desk most of the time
- You want maximum battery longevity over capacity
- Typical for desktop replacement scenarios

## Runtime Toggle (No Rebuild Required)

Use the `battery-toggle.sh` script to change thresholds immediately without rebuilding:

```bash
# Check current status
./scripts/utils/battery-toggle.sh status

# Allow full 100% charge (before trip)
sudo ./scripts/utils/battery-toggle.sh full

# Return to balanced 20%-80% mode
sudo ./scripts/utils/battery-toggle.sh balanced

# Conservation mode for always-plugged-in
sudo ./scripts/utils/battery-toggle.sh conservation

# Custom thresholds
sudo ./scripts/utils/battery-toggle.sh custom 30 90
```

**Important:**
- Runtime changes persist until reboot or next `nixos-rebuild`, which reapplies your NixOS config thresholds
- **If COSMIC is active**, the NixOS service is disabled, so `nixos-rebuild` won't override your COSMIC GUI settings
- The script sends a desktop notification on COSMIC/GNOME/KDE when thresholds change

## Usage Scenarios

### Scenario 1: Normal Daily Use (Default)
Keep the default 20%-80% thresholds. This maximizes battery lifespan while providing adequate capacity.

**Config:**
```nix
mySystem.hardware.battery.chargeThresholds = {
  enable = true;
  startThreshold = 20;
  stopThreshold = 80;
};
```

### Scenario 2: Traveling Tomorrow (Need 100%)
**Option A - Runtime toggle (immediate):**
```bash
sudo ./scripts/utils/battery-toggle.sh full
```

**Option B - Config change (persistent across reboots):**
```nix
mySystem.hardware.battery.chargeThresholds.enable = false;
```

Then rebuild: `sudo nixos-rebuild switch`

### Scenario 3: Desktop Replacement (Always Plugged In)
Enable conservation mode to minimize battery wear:

```nix
mySystem.hardware.battery.conservationMode.enable = true;
```

This keeps the battery at 50%-60%, ideal for maximum longevity.

### Scenario 4: Balanced Approach (90% Cap)
If 80% feels too restrictive but you still want some protection:

```nix
mySystem.hardware.battery.chargeThresholds = {
  enable = true;
  startThreshold = 20;
  stopThreshold = 90;  # Raise from 80 to 90
};
```

## How It Works

The implementation writes thresholds to the kernel's sysfs interface:

```
/sys/class/power_supply/BAT*/charge_control_start_threshold
/sys/class/power_supply/BAT*/charge_control_end_threshold
```

A systemd service (`battery-charge-thresholds`) applies these on:
- Boot (`multi-user.target`)
- Resume from suspend (`suspend.target`)

**Hardware Support:** This feature requires kernel 5.9+ and hardware support (common on ThinkPads, some other business laptops). Check support:

```bash
ls -l /sys/class/power_supply/BAT*/charge_control_*_threshold
```

If these files exist and are writable, your hardware supports charge control.

## Priority Order

The system applies thresholds in this order:

1. **Conservation mode** (if `conservationMode.enable = true`)
   - Overrides all other settings with conservation thresholds
2. **Charge thresholds** (if `chargeThresholds.enable = true`)
   - Uses configured start/stop thresholds
3. **Full charge** (if `chargeThresholds.enable = false`)
   - Sets start=0, stop=100 (no limits)

## Files Modified

- `nix/modules/core/options.nix` — Battery configuration options
- `nix/modules/hardware/mobile.nix` — Threshold enforcement logic
- `scripts/utils/battery-toggle.sh` — Runtime toggle script

## Troubleshooting

### COSMIC GUI: Battery Lifespan toggle doesn't stick
This is a known COSMIC bug (see pop-os/cosmic-epoch#2800). Workarounds:
1. Use the runtime script instead: `sudo ./scripts/utils/battery-toggle.sh full`
2. Check if COSMIC's config is corrupted: `ls -la ~/.config/cosmic/`
3. Reset COSMIC power settings: Remove `~/.config/cosmic/com.system76.CosmicSettings.Power/` and restart COSMIC settings

### COSMIC GUI: Can't find battery settings
- Ensure you're on COSMIC 1.0.5+ (battery percentage indicator was added then)
- Check that UPower is running: `systemctl status upower`
- Verify battery is detected: `upower -i /org/freedesktop/UPower/devices/battery_BAT0`

### "No battery found" error (runtime script)
Check if your battery is detected:
```bash
ls /sys/class/power_supply/
```
Should show `BAT0` or similar. If not, your kernel may not have battery drivers loaded.

### "Charge threshold interface not found" (runtime script)
Your hardware may not support sysfs charge control. This is common on:
- Consumer-grade laptops (non-business lines)
- Some Dell/HP models
- Older hardware (pre-2020)

**Workaround:** Some vendors provide their own tools:
- **Lenovo:** `tlp` or `ideapad-laptop` kernel module
- **ASUS:** `asus-nb-wmi` kernel module
- **Dell:** `dell-laptop` kernel module or `smbios` tools

### Thresholds reset after reboot
**Non-COSMIC setups:** This is expected. The systemd service reapplies your NixOS config thresholds on boot. Use the runtime script after boot if you need different values temporarily.

**COSMIC setups:** COSMIC should persist your GUI settings automatically. If not, this is a COSMIC bug - report it upstream.

### Battery still charges to 80% after setting `enable = false`
**Non-COSMIC setups:** Run `sudo nixos-rebuild switch` to apply the config change, then reboot or restart the service:
```bash
sudo systemctl restart battery-charge-thresholds
```

**COSMIC setups:** The NixOS service is disabled when COSMIC is active. Use the COSMIC GUI or runtime script instead.

## References

- Linux kernel battery documentation: `Documentation/power/battery.rst`
- COSMIC battery threshold bug: https://github.com/pop-os/cosmic-epoch/issues/2800
- COSMIC Settings Power panel: `~/.config/cosmic/com.system76.CosmicSettings.Power/`
- ThinkPad battery thresholds: `thinkpad-acpi` kernel module
- NixOS power management: `nix/modules/hardware/mobile.nix`
- COSMIC desktop module: `nix/modules/roles/desktop.nix`
