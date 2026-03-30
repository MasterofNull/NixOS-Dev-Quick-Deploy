{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ── Host-Specific Configuration ───────────────────────────────────────────────
  # Shared ai-dev and workstation-class behavior now lives in
  # nix/modules/profiles/ai-dev.nix and
  # nix/modules/host-classes/p14s-amd-ai-workstation.nix.
  # Keep only machine-specific overrides here.
}
