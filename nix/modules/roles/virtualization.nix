{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Virtualization role — KVM/QEMU host support via libvirtd.
#
# Activated when: mySystem.roles.virtualization.enable = true
#
# Provisions:
#   - virtualisation.libvirtd   — daemon + QEMU driver
#   - OVMF UEFI firmware        — for EFI guest VMs
#   - SPICE USB redirection     — USB pass-through to guests
#   - programs.virt-manager     — GTK management UI
#   - Primary user added to libvirtd + kvm groups
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  virtEnabled = cfg.roles.virtualization.enable;
in
{
  config = lib.mkIf virtEnabled {

    # ---- libvirtd / QEMU --------------------------------------------------
    virtualisation.libvirtd = {
      enable = lib.mkDefault true;
      qemu = {
        ovmf.enable = lib.mkDefault true;  # UEFI firmware for EFI guests
        runAsRoot   = lib.mkDefault false; # run QEMU as qemu-kvm user
      };
    };

    # SPICE USB redirection daemon (required for guest USB pass-through).
    virtualisation.spiceUSBRedirection.enable = lib.mkDefault true;

    # ---- Management UI ----------------------------------------------------
    programs.virt-manager.enable = lib.mkDefault true;

    # ---- Primary user groups ----------------------------------------------
    # lib.mkAfter appends without replacing defaults set in core/users.nix.
    users.users.${cfg.primaryUser}.extraGroups =
      lib.mkAfter [ "libvirtd" "kvm" ];

    # ---- Extra packages ---------------------------------------------------
    environment.systemPackages = with pkgs; [
      virt-viewer  # Display guest VM consoles (VNC/SPICE)
      spice-gtk    # SPICE client libraries for virt-viewer
    ];
  };
}
