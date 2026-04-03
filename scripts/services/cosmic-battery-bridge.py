#!/usr/bin/env python3
"""
COSMIC Battery Threshold D-Bus Bridge

Provides a system76-power-compatible D-Bus interface for battery charge
thresholds so COSMIC Settings can manage battery charging without requiring
the actual system76-power daemon.

D-Bus Interface:
  Service:  com.system76.PowerDaemon
  Path:     /com/system76/PowerDaemon
  Methods:
    - GetChargeProfiles() → Array of ChargeProfile structs
    - GetChargeThresholds() → (start: byte, end: byte)
    - SetChargeThresholds(start: byte, end: byte)

This bridges COSMIC's GUI to the kernel's sysfs interface:
  /sys/class/power_supply/BAT*/charge_control_start_threshold
  /sys/class/power_supply/BAT*/charge_control_end_threshold
"""

import sys
import os
import glob
import logging
import json
from pathlib import Path

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# ── Configuration ─────────────────────────────────────────────────────────────

BATTERY_SYSFS_PATH = "/sys/class/power_supply"
START_THRESHOLD_FILE = "charge_control_start_threshold"
END_THRESHOLD_FILE = "charge_control_end_threshold"

# Charge profiles matching system76-power's defaults
CHARGE_PROFILES = [
    {
        "id": "full_charge",
        "title": "Full Charge",
        "description": "Battery is charged to its full capacity for the longest possible use on battery power. Charging resumes when the battery falls below 96% charge.",
        "start": 90,
        "end": 100,
    },
    {
        "id": "balanced",
        "title": "Balanced",
        "description": "A balanced approach to battery lifespan and capacity. Good for most usage patterns.",
        "start": 86,
        "end": 90,
    },
    {
        "id": "max_lifespan",
        "title": "Maximize Battery Lifespan",
        "description": "Minimizes battery wear by keeping charge between 50-60%. Best for laptops that stay plugged in most of the time.",
        "start": 50,
        "end": 60,
    },
]

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] cosmic-battery-bridge: %(message)s",
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


def find_batteries():
    """Find all battery sysfs paths."""
    return sorted(glob.glob(os.path.join(BATTERY_SYSFS_PATH, "BAT*")))


def get_threshold_paths(battery_path):
    """Return (start_path, end_path) for a battery, or (None, None)."""
    start_path = os.path.join(battery_path, START_THRESHOLD_FILE)
    end_path = os.path.join(battery_path, END_THRESHOLD_FILE)
    if os.path.isfile(start_path) and os.path.isfile(end_path):
        return start_path, end_path
    return None, None


def read_threshold(path):
    """Read a charge threshold value from sysfs."""
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError) as e:
        log.error(f"Failed to read {path}: {e}")
        return None


def write_threshold(path, value):
    """Write a charge threshold value to sysfs."""
    try:
        with open(path, "w") as f:
            f.write(str(value))
        return True
    except OSError as e:
        log.error(f"Failed to write {value} to {path}: {e}")
        return False


def set_charge_thresholds_on_battery(start, end):
    """
    Write charge thresholds to all detected batteries.

    Follows the same pattern as system76-power:
    1. Temporarily set end to 100 (firmware workaround)
    2. Write start threshold
    3. Write end threshold
    """
    if end <= start:
        raise ValueError(
            f"Charge end threshold ({end}) must be strictly greater than start ({start})"
        )

    if not (0 <= start <= 100 and 0 <= end <= 100):
        raise ValueError(f"Thresholds must be between 0 and 100, got ({start}, {end})")

    batteries = find_batteries()
    if not batteries:
        raise RuntimeError("No batteries found in sysfs")

    success = False
    for bat_path in batteries:
        start_path, end_path = get_threshold_paths(bat_path)
        if start_path is None or end_path is None:
            log.warning(f"Charge thresholds not supported for {bat_path}")
            continue

        bat_name = os.path.basename(bat_path)
        log.info(f"Setting {bat_name} thresholds: start={start}, end={end}")

        # Firmware workaround: set end to 100 first to allow lowering start
        if not write_threshold(end_path, 100):
            raise RuntimeError(f"Failed to set {bat_name} end threshold to 100")

        if not write_threshold(start_path, start):
            raise RuntimeError(f"Failed to set {bat_name} start threshold to {start}")

        if not write_threshold(end_path, end):
            raise RuntimeError(f"Failed to set {bat_name} end threshold to {end}")

        log.info(f"✓ {bat_name}: start={start}%, end={end}%")
        success = True

    if not success:
        raise RuntimeError(
            "Charge thresholds are not supported by the kernel for this hardware"
        )


def get_charge_thresholds_from_battery():
    """Read current charge thresholds from the first available battery."""
    batteries = find_batteries()
    for bat_path in batteries:
        start_path, end_path = get_threshold_paths(bat_path)
        if start_path is None:
            continue
        start = read_threshold(start_path)
        end = read_threshold(end_path)
        if start is not None and end is not None:
            return start, end
    return None, None


# ── D-Bus Service ─────────────────────────────────────────────────────────────

DBUS_BUS_NAME = "com.system76.PowerDaemon"
DBUS_OBJECT_PATH = "/com/system76/PowerDaemon"
DBUS_INTERFACE = "com.system76.PowerDaemon"


class PowerDaemon(dbus.service.Object):
    """
    D-Bus service implementing the system76-power interface for battery
    charge thresholds. This allows COSMIC Settings to discover and manage
    battery charging without the actual system76-power daemon.
    """

    def __init__(self):
        bus = dbus.SystemBus()
        dbus.service.Object.__init__(self, bus, DBUS_OBJECT_PATH)
        log.info(f"Registered D-Bus service: {DBUS_BUS_NAME} at {DBUS_OBJECT_PATH}")

    @dbus.service.method(
        DBUS_INTERFACE,
        in_signature="",
        out_signature="a(ssssu)",
    )
    def GetChargeProfiles(self):
        """
        Return available charge profiles for the UI dropdown.

        Returns an array of structs: (id, title, description, start, end)
        Matching system76-power's ChargeProfile structure.
        """
        log.info("GetChargeProfiles() called")
        profiles = []
        for p in CHARGE_PROFILES:
            profiles.append(
                (p["id"], p["title"], p["description"], dbus.Byte(p["start"]), dbus.Byte(p["end"]))
            )
        return profiles

    @dbus.service.method(
        DBUS_INTERFACE,
        in_signature="",
        out_signature="yy",
    )
    def GetChargeThresholds(self):
        """
        Return current charge thresholds from the battery.

        Returns (start, end) as bytes.
        """
        log.info("GetChargeThresholds() called")
        start, end = get_charge_thresholds_from_battery()
        if start is None or end is None:
            # Return defaults if sysfs not available
            log.warning("Could not read thresholds from sysfs, returning defaults")
            return dbus.Byte(90), dbus.Byte(100)
        return dbus.Byte(start), dbus.Byte(end)

    @dbus.service.method(
        DBUS_INTERFACE,
        in_signature="yy",
        out_signature="",
    )
    def SetChargeThresholds(self, start, end):
        """
        Set battery charge thresholds.

        Called by COSMIC Settings when user selects a profile or custom values.
        """
        log.info(f"SetChargeThresholds({start}, {end}) called")
        try:
            set_charge_thresholds_on_battery(start, end)
            log.info(f"✓ Thresholds set successfully: start={start}%, end={end}%")
        except (RuntimeError, ValueError) as e:
            log.error(f"Failed to set thresholds: {e}")
            raise dbus.exceptions.DBusException(
                str(e),
                name="com.system76.PowerDaemon.Error.ThresholdError",
            )

    @dbus.service.method(
        DBUS_INTERFACE,
        in_signature="",
        out_signature="b",
    )
    def GetChargeThresholdsSupported(self):
        """
        Return whether charge thresholds are supported on this hardware.

        COSMIC uses this to determine whether to show the battery threshold UI.
        """
        log.info("GetChargeThresholdsSupported() called")
        supported = len(find_batteries()) > 0
        if supported:
            # Check if at least one battery supports thresholds
            for bat_path in find_batteries():
                start_path, _ = get_threshold_paths(bat_path)
                if start_path is not None and os.access(start_path, os.W_OK):
                    return True
        return False


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    """Start the D-Bus service and run the GLib main loop."""
    log.info("Starting COSMIC Battery Threshold D-Bus Bridge")

    # Check sysfs support before starting
    batteries = find_batteries()
    if not batteries:
        log.warning("No batteries found — service will start but thresholds won't apply")
    else:
        supported_count = 0
        for bat_path in batteries:
            start_path, _ = get_threshold_paths(bat_path)
            if start_path is not None:
                supported_count += 1
        log.info(f"Found {len(batteries)} batteries, {supported_count} support thresholds")

    # Initialize D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # Register the service
    bus = dbus.SystemBus()
    try:
        bus.request_name(DBUS_BUS_NAME)
    except dbus.exceptions.DBusException as e:
        log.error(f"Failed to acquire D-Bus name {DBUS_BUS_NAME}: {e}")
        sys.exit(1)

    daemon = PowerDaemon()

    # Run main loop
    log.info("Entering main loop...")
    try:
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        bus.release_name(DBUS_BUS_NAME)
        log.info("D-Bus service stopped")


if __name__ == "__main__":
    main()
