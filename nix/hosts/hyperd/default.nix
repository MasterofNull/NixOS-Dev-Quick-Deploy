{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ── Host-Specific Configuration ───────────────────────────────────────────────
  # Profile-level features (kernel, hardening, security, fonts, etc.) are now in
  # nix/modules/profiles/ai-dev.nix. This file only contains hardware-specific
  # overrides that cannot be generalized across hosts.

  # MCP servers repo path - host-specific due to username
  mySystem.mcpServers.repoPath =
    lib.mkDefault "/home/${config.mySystem.primaryUser}/Documents/NixOS-Dev-Quick-Deploy";

  # ── AMD Cezanne APU stability fixes ──────────────────────────────────────────
  # DMCUB firmware errors on boot can cause system freezes. These kernel
  # parameters improve stability on Ryzen 5000 mobile (Cezanne) APUs.
  # Only needed for AMD APUs with PSR issues - not a general profile setting.
  boot.kernelParams = lib.mkAfter [
    # Disable PSR (Panel Self Refresh) — known to cause display freezes on
    # AMD APUs, especially under Wayland compositors like COSMIC.
    "amdgpu.dcdebugmask=0x10"
  ];
}
