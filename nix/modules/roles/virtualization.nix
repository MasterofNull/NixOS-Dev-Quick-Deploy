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

  vmHelper = name: command: pkgs.writeShellScriptBin name ''
    set -euo pipefail
    exec ${pkgs.libvirt}/bin/virsh ${command} "$@"
  '';
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
      libvirt      # virsh CLI expected by health checks
      qemu_kvm     # qemu-system-* binaries for local VM execution
      virt-viewer  # Display guest VM consoles (VNC/SPICE)
      spice-gtk    # SPICE client libraries for virt-viewer
      (vmHelper "vm-list" "list --all")
      (vmHelper "vm-snapshot" "snapshot-list")
      (pkgs.writeShellScriptBin "vm-create-nixos" ''
        set -euo pipefail
        echo "vm-create-nixos helper is declaratively installed." >&2
        echo "Create a VM with virt-install/virsh using your preferred image." >&2
        exit 0
      '')
    ];
  };
}
