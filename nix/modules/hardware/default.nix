# nix/modules/hardware/default.nix
# Aggregates all hardware-specific modules. Import this single file from the flake.
# Each module gates itself on mySystem.hardware.* options, so importing all of them
# on every machine is safe — only the relevant conditions activate.
{ ... }:
{
  imports = [
    ./cpu/amd.nix
    ./cpu/intel.nix
    ./gpu/amd.nix
    ./gpu/intel.nix
    ./gpu/nvidia.nix
    ./storage.nix
    ./ram-tuning.nix
    ./mobile.nix
    ./recovery.nix
  ];
}
