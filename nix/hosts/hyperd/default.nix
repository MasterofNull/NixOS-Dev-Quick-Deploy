{ lib, config, pkgs, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  mySystem.localhostIsolation.enable = lib.mkDefault true;
  mySystem.mcpServers.repoPath =
    lib.mkDefault "/home/${config.mySystem.primaryUser}/Documents/NixOS-Dev-Quick-Deploy";

  # ── ThinkPad P14s ClickPad — libinput tuning ─────────────────────────────
  # Problem 1: two-finger scroll triggers middle-click → X11 PRIMARY paste.
  #   Fix: middleEmulation=false + clickMethod=clickfinger (finger count
  #   determines button, not pad zones — eliminates accidental middle clicks).
  # Problem 2: touchpad glitchy / imprecise during fast gestures.
  #   Fix: disableWhileTyping prevents mis-clicks when typing.
  services.libinput.touchpad = {
    middleEmulation    = lib.mkDefault false;
    clickMethod        = lib.mkDefault "clickfinger";
    disableWhileTyping = lib.mkDefault true;
    tapping            = lib.mkDefault true;
    scrollMethod       = lib.mkDefault "twofinger";
    naturalScrolling   = lib.mkDefault false;
  };

  # ── AMD Cezanne APU stability fixes ──────────────────────────────────────
  # DMCUB firmware errors on boot can cause system freezes. These kernel
  # parameters improve stability on Ryzen 5000 mobile (Cezanne) APUs.
  boot.kernelParams = lib.mkAfter [
    # Disable PSR (Panel Self Refresh) — known to cause display freezes on
    # AMD APUs, especially under Wayland compositors like COSMIC.
    "amdgpu.dcdebugmask=0x10"
    # Alternative: completely disable DC PSR if above doesn't help:
    # "amdgpu.dcfeaturemask=0x0"
  ];

  # ── Polkit rules for COSMIC power settings ───────────────────────────────
  # Allow users in wheel group to change power profiles without password.
  security.polkit.extraConfig = ''
    polkit.addRule(function(action, subject) {
      if ((action.id == "org.freedesktop.UPower.PowerProfiles.switch-profile" ||
           action.id == "org.freedesktop.UPower.PowerProfiles.hold-profile" ||
           action.id == "org.freedesktop.UPower.PowerProfiles.configure-action" ||
           action.id == "org.freedesktop.login1.suspend" ||
           action.id == "org.freedesktop.login1.hibernate" ||
           action.id == "org.freedesktop.login1.power-off") &&
          subject.isInGroup("wheel")) {
        return polkit.Result.YES;
      }
    });
  '';

  # ── Firmware updates for GPU stability ───────────────────────────────────
  hardware.enableRedistributableFirmware = lib.mkDefault true;
  services.fwupd.enable = lib.mkDefault true;

  # ── Host-level font baseline ─────────────────────────────────────────────
  fonts = {
    fontconfig.enable = true;
    fontDir.enable = true;
    packages = with pkgs; [
      nerd-fonts.meslo-lg
      nerd-fonts.jetbrains-mono
      nerd-fonts.fira-code
      nerd-fonts.hack
      noto-fonts
      noto-fonts-color-emoji
    ];
  };
}
