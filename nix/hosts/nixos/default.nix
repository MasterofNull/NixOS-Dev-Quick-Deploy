{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ── Host-Specific Configuration ───────────────────────────────────────────────
  # Profile-level features (kernel, hardening, security, fonts, libinput, etc.)
  # are now in nix/modules/profiles/ai-dev.nix. This file only contains
  # host-specific overrides.

  # Keep Steam available on this workstation (override profile default)
  mySystem.roles.gaming.enable = lib.mkForce true;

  # Pin prometheus GID for localhost-isolation nftables rules
  users.groups.prometheus.gid = lib.mkDefault 255;

  # Force vector DB on for this host (override facts.nix default)
  mySystem.aiStack.vectorDb.enable = lib.mkForce true;

  # MCP servers repo path - host-specific due to username
  mySystem.mcpServers.repoPath =
    lib.mkDefault "/home/${config.mySystem.primaryUser}/Documents/NixOS-Dev-Quick-Deploy";

  # ── AMD Cezanne APU stability fixes ──────────────────────────────────────────
  # DMCUB firmware errors on boot can cause system freezes. These kernel
  # parameters improve stability on Ryzen 5000 mobile (Cezanne) APUs.
  boot.kernelParams = lib.mkAfter [
    "amdgpu.dcdebugmask=0x10"
  ];
}
