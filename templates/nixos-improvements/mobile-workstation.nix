# NixOS Mobile Workstation Optimizations
# Target: Laptops, mobile workstations, AMD iGPU systems
# Purpose: Battery life, thermal management, power efficiency
#
# Features:
# - TLP for advanced power management
# - Power-profiles-daemon integration
# - WiFi power saving
# - Thermal throttling
# - Lid close/suspend handling
# - AMD iGPU optimizations
# - Hibernate support
#
# Usage: Import in configuration.nix:
#   imports = [ ./nixos-improvements/mobile-workstation.nix ];
#
# Note: This module uses lib.mkDefault extensively so values can be
# overridden in your main configuration.nix

{ config, pkgs, lib, ... }:

let
  # Detect if this is likely a laptop/mobile system
  isLaptop = builtins.pathExists "/sys/class/power_supply/BAT0"
          || builtins.pathExists "/sys/class/power_supply/BAT1";
  
  # Detect AMD CPU/GPU
  hasAmdCpu = config.hardware.cpu.amd.updateMicrocode or false;
in
{
  # =========================================================================
  # TLP - Advanced Power Management (Linux Laptop)
  # =========================================================================
  # TLP provides excellent battery optimization without manual configuration
  # It automatically switches between AC and battery power profiles

  services.tlp = {
    enable = lib.mkDefault true;
    settings = {
      # CPU Governor
      CPU_SCALING_GOVERNOR_ON_AC = "performance";
      CPU_SCALING_GOVERNOR_ON_BAT = "powersave";
      
      # CPU Turbo Boost
      CPU_BOOST_ON_AC = 1;
      CPU_BOOST_ON_BAT = 0;
      
      # CPU Energy Performance Preference (AMD/Intel)
      CPU_ENERGY_PERF_POLICY_ON_AC = "performance";
      CPU_ENERGY_PERF_POLICY_ON_BAT = "power";
      
      # Platform Profile (AMD specific - performance/balanced/low-power)
      PLATFORM_PROFILE_ON_AC = "performance";
      PLATFORM_PROFILE_ON_BAT = "low-power";
      
      # WiFi Power Saving
      WIFI_PWR_ON_AC = "off";
      WIFI_PWR_ON_BAT = "on";
      
      # USB Autosuspend
      USB_AUTOSUSPEND = 1;
      USB_EXCLUDE_BTUSB = 1;  # Don't suspend Bluetooth
      USB_EXCLUDE_PHONE = 1;  # Don't suspend phones (charging)
      
      # PCIe ASPM (Active State Power Management)
      PCIE_ASPM_ON_AC = "default";
      PCIE_ASPM_ON_BAT = "powersupersave";
      
      # Runtime Power Management for PCIe devices
      RUNTIME_PM_ON_AC = "on";
      RUNTIME_PM_ON_BAT = "auto";
      
      # SATA Link Power Management
      SATA_LINKPWR_ON_AC = "med_power_with_dipm";
      SATA_LINKPWR_ON_BAT = "min_power";
      
      # NVMe Runtime Power Management
      AHCI_RUNTIME_PM_ON_AC = "on";
      AHCI_RUNTIME_PM_ON_BAT = "auto";
      
      # Screen Brightness (0-100)
      # Uncomment and adjust if you want TLP to manage brightness
      # BRIGHTNESS_ON_AC = 100;
      # BRIGHTNESS_ON_BAT = 50;
      
      # Sound Power Management
      SOUND_POWER_SAVE_ON_AC = 0;
      SOUND_POWER_SAVE_ON_BAT = 1;
      
      # Battery Charge Thresholds (if supported by hardware)
      # Helps prolong battery lifespan by not charging to 100%
      # Uncomment if your laptop supports it (ThinkPad, some ASUS, etc.)
      # START_CHARGE_THRESH_BAT0 = 40;
      # STOP_CHARGE_THRESH_BAT0 = 80;
    };
  };

  # =========================================================================
  # Power-Profiles-Daemon (Alternative/Companion to TLP)
  # =========================================================================
  # Provides GNOME/KDE integration for power profile switching
  # Note: Can conflict with TLP - choose one or the other

  # Disabled by default since TLP is more comprehensive
  # Enable this instead of TLP if you prefer GUI power profile switching
  # Using mkForce to override COSMIC's default setting (which enables it)
  services.power-profiles-daemon.enable = lib.mkForce false;

  # =========================================================================
  # Thermald - Intel Thermal Management
  # =========================================================================
  # Automatically manages CPU temperature to prevent thermal throttling
  # Primarily for Intel but also works on some AMD systems
  
  services.thermald.enable = lib.mkDefault true;

  # =========================================================================
  # UPower - Battery Monitoring
  # =========================================================================
  # Required for battery status in desktop environments
  
  services.upower = {
    enable = lib.mkDefault true;
    # Action when battery is critically low
    criticalPowerAction = lib.mkDefault "Hibernate";
    # Battery percentage thresholds
    percentageLow = lib.mkDefault 15;
    percentageCritical = lib.mkDefault 5;
    percentageAction = lib.mkDefault 2;
  };

  # =========================================================================
  # Lid Close & Suspend Handling
  # =========================================================================
  
  services.logind = {
    # What to do when lid is closed
    lidSwitch = lib.mkDefault "suspend";
    lidSwitchDocked = lib.mkDefault "ignore";  # External monitor connected
    lidSwitchExternalPower = lib.mkDefault "ignore";  # On AC power
    
    # Power button behavior
    powerKey = lib.mkDefault "suspend";
    powerKeyLongPress = lib.mkDefault "poweroff";
    
    # Suspend key (if present on keyboard)
    suspendKey = lib.mkDefault "suspend";
    
    # Hibernate key
    hibernateKey = lib.mkDefault "hibernate";
    
    # Kill user processes on logout for clean session
    killUserProcesses = lib.mkDefault false;
    
    # Idle action (auto-suspend after inactivity)
    # Set to "ignore" to disable auto-suspend
    extraConfig = ''
      IdleAction=ignore
      IdleActionSec=30min
      HandleLidSwitchExternalPower=ignore
    '';
  };

  # =========================================================================
  # Hibernate Support
  # =========================================================================
  # Enable hibernation (suspend-to-disk)
  # Requires a swap partition/file at least as large as RAM
  
  # Hybrid sleep (suspend + hibernate safety net)
  systemd.sleep.extraConfig = ''
    AllowSuspend=yes
    AllowHibernation=yes
    AllowSuspendThenHibernate=yes
    AllowHybridSleep=yes
    HibernateDelaySec=3600
  '';

  # =========================================================================
  # AMD iGPU Optimizations
  # =========================================================================
  
  # AMD GPU power management
  boot.kernelParams = lib.mkIf hasAmdCpu [
    # AMD GPU power management
    "amdgpu.ppfeaturemask=0xffffffff"  # Enable all power features
    "amdgpu.dcdebugmask=0x10"          # Disable S0i3 reporting (power states)
    
    # AMD CPU power management
    "amd_pstate=active"                 # Use AMD P-State driver (Zen 2+)
  ];
  
  # Enable AMD GPU overclocking/undervolting support
  hardware.amdgpu.overdrive.enable = lib.mkDefault hasAmdCpu;
  
  # Hardware video acceleration for AMD
  hardware.graphics = {
    enable = lib.mkDefault true;
    enable32Bit = lib.mkDefault true;  # For 32-bit games/apps
  };
  
  # ROCm OpenCL for AMD GPUs (AI/ML compute)
  hardware.amdgpu.opencl.enable = lib.mkDefault hasAmdCpu;

  # =========================================================================
  # Network Optimizations for Mobile
  # =========================================================================
  
  networking.networkmanager = {
    # WiFi power saving
    wifi.powersave = lib.mkDefault true;
    
    # WiFi backend (iwd is faster and more efficient than wpa_supplicant)
    wifi.backend = lib.mkDefault "iwd";
  };
  
  # Enable iwd (Intel Wireless Daemon) for better WiFi performance
  networking.wireless.iwd = {
    enable = lib.mkDefault true;
    settings = {
      General = {
        EnableNetworkConfiguration = true;
        # Roaming between access points
        RoamThreshold = -70;
        RoamThreshold5G = -76;
      };
      Network = {
        EnableIPv6 = true;
        RoutePriorityOffset = 300;
      };
      Settings = {
        AutoConnect = true;
      };
    };
  };

  # =========================================================================
  # Bluetooth Power Management
  # =========================================================================
  
  hardware.bluetooth = {
    enable = lib.mkDefault true;
    powerOnBoot = lib.mkDefault false;  # Save power, enable manually
    settings = {
      General = {
        # Fast connect for known devices
        FastConnectable = true;
        # Power saving
        Experimental = true;
      };
    };
  };

  # =========================================================================
  # CPU Frequency Scaling
  # =========================================================================
  
  # AMD P-State driver (for Zen 2+ CPUs)
  # This is more efficient than the older acpi-cpufreq driver
  boot.kernelModules = lib.mkIf hasAmdCpu [ "amd_pstate" ];
  
  # CPU frequency governor
  # schedutil is good for both performance and battery
  powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil";
  
  # Enable power management
  powerManagement.enable = lib.mkDefault true;
  powerManagement.powertop.enable = lib.mkDefault true;

  # =========================================================================
  # Backlight Control
  # =========================================================================
  
  # Allow users to control screen brightness
  programs.light.enable = lib.mkDefault true;
  
  # Alternative: brightnessctl
  environment.systemPackages = with pkgs; [
    brightnessctl       # CLI brightness control
    powertop            # Power consumption analyzer
    acpi                # Battery status CLI
    lm_sensors          # Hardware sensors
  ];

  # =========================================================================
  # Fan Control (if supported)
  # =========================================================================
  
  # Enable lm_sensors for temperature monitoring
  hardware.sensor.hddtemp.enable = lib.mkDefault true;
  
  # Fancontrol daemon (if supported by hardware)
  # Uncomment if your laptop supports PWM fan control
  # hardware.fancontrol.enable = true;

  # =========================================================================
  # Documentation
  # =========================================================================
  
  environment.etc."nixos/MOBILE-WORKSTATION.txt".text = ''
    ==========================================
    NixOS Mobile Workstation Optimizations
    ==========================================
    
    POWER PROFILES:
    ---------------
    On AC Power:
      - CPU Governor: performance
      - CPU Boost: enabled
      - WiFi Power Save: off
      - Max performance
    
    On Battery:
      - CPU Governor: powersave
      - CPU Boost: disabled
      - WiFi Power Save: on
      - PCIe ASPM: powersupersave
      - Optimized for battery life
    
    COMMANDS:
    ---------
    Check TLP status:
      $ sudo tlp-stat -s
    
    Check battery status:
      $ acpi -V
      $ upower -d
    
    Check power consumption:
      $ sudo powertop
    
    Control brightness:
      $ brightnessctl set 50%
      $ light -S 50
    
    Check temperatures:
      $ sensors
    
    Check CPU frequency:
      $ watch -n1 "cat /proc/cpuinfo | grep MHz"
    
    LID BEHAVIOR:
    -------------
    Lid closed (on battery): suspend
    Lid closed (on AC): ignore
    Lid closed (docked): ignore
    
    BATTERY TIPS:
    -------------
    1. Use TLP default settings for good balance
    2. Enable WiFi power saving on battery
    3. Reduce screen brightness on battery
    4. Close unused applications
    5. Consider undervolting AMD CPUs
    
    AMD iGPU:
    ---------
    - Using RADV (Vulkan) driver
    - VA-API via radeonsi
    - ROCm for compute (if enabled)
    - P-State driver for efficient frequency scaling
    
    TROUBLESHOOTING:
    ----------------
    If battery drain is high:
      $ sudo powertop --auto-tune
      $ tlp-stat -b  # Check battery health
    
    If WiFi is slow:
      $ iwd  # Check iwd status
      $ nmcli connection show
    
    ==========================================
    Configuration: mobile-workstation.nix
    ==========================================
  '';
}

