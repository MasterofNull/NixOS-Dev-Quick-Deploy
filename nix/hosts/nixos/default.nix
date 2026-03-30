{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ── Host-Specific Configuration ───────────────────────────────────────────────
  # Shared ai-dev and workstation-class behavior now lives in
  # nix/modules/profiles/ai-dev.nix and
  # nix/modules/host-classes/p14s-amd-ai-workstation.nix.
  # Keep only host-specific overrides here.

  # Keep Steam available on this workstation (override profile default)
  mySystem.roles.gaming.enable = lib.mkForce true;

  # Pin prometheus GID for localhost-isolation nftables rules
  users.groups.prometheus.gid = lib.mkDefault 255;
}
