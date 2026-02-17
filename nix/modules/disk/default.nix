{ lib, config, ... }:
let
  cfg = config.mySystem.disk;
in
{
  # Avoid config-conditional imports (can recurse during module evaluation).
  # Each layout module is imported unconditionally and self-gates via mkIf.
  imports = [
    ./gpt-efi-ext4.nix
    ./gpt-efi-btrfs.nix
    ./gpt-luks-ext4.nix
  ];

  warnings = lib.optional (cfg.luks.enable && cfg.layout != "gpt-luks-ext4")
    "mySystem.disk.luks.enable=true is set, but layout is not gpt-luks-ext4.";
}
