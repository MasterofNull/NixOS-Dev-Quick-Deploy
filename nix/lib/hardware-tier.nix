/**
  Phase 16.1.1 — Hardware capability tier classifier.

  Computes a tier string from host hardware facts so that NixOS modules can
  apply tier-appropriate defaults without hardcoding per-host values.

  Tiers (ascending capability):
    nano   — SBC / low-power embedded  (< 2 GB RAM)
    micro  — Raspberry Pi / light SBC  (2–7 GB RAM)
    small  — Laptop / thin client      (8–15 GB RAM)
    medium — Workstation / desktop     (16–31 GB RAM)
    large  — High-end workstation / server (≥ 32 GB RAM)

  The `hasDiscreteGpu` flag nudges the tier one level up (caps at "large")
  to prefer GPU-accelerated model defaults.  The `cpuArchitecture` field is
  exposed for modules that need to gate x86_64-specific features.

  Usage in base.nix:
      let
        computeTier = import ../lib/hardware-tier.nix { inherit lib; };
        tier = computeTier {
          systemRamGb     = cfg.hardware.systemRamGb;
          hasDiscreteGpu  = cfg.hardware.gpuVendor != "none"
                         && cfg.hardware.gpuVendor != "integrated";
          cpuArchitecture = if pkgs.stdenv.hostPlatform.isx86_64 then "x86_64"
                            else if pkgs.stdenv.hostPlatform.isAarch64 then "aarch64"
                            else "other";
        };
      in
        mySystem.hardwareTier = lib.mkDefault tier;
*/
{ lib }:
{
  systemRamGb     ? 4,
  hasDiscreteGpu  ? false,
  cpuArchitecture ? "x86_64",
}:
let
  # Base tier determined solely by RAM.
  ramTier =
    if systemRamGb < 2 then "nano"
    else if systemRamGb < 8 then "micro"
    else if systemRamGb < 16 then "small"
    else if systemRamGb < 32 then "medium"
    else "large";

  tierOrder = [ "nano" "micro" "small" "medium" "large" ];

  tierIndex = tier:
    let idx = lib.lists.findFirstIndex (x: x == tier) null tierOrder;
    in if idx == null then 2 else idx;  # default to "small" index if unknown

  # Discrete GPU nudges tier one level up (better model defaults).
  gpuBump = if hasDiscreteGpu then 1 else 0;

  rawIndex = lib.min
    (tierIndex ramTier + gpuBump)
    (builtins.length tierOrder - 1);
in
  builtins.elemAt tierOrder rawIndex
