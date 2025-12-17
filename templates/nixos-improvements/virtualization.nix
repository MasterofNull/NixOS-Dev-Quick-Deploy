# KVM/QEMU/Libvirt Virtualization Stack Configuration
# NixOS 25.11 Xantusia
# Purpose: Full virtualization support for development and testing
#
# Features:
# - KVM/QEMU with hardware acceleration
# - Virt-manager GUI
# - OVMF UEFI + Secure Boot + TPM 2.0
# - Nested virtualization
# - Rootless operation
# - SPICE USB redirection
#
# Usage: Import this file in your configuration.nix:
#   imports = [ ./nixos-improvements/virtualization.nix ];

{ config, pkgs, lib, ... }:

let
  virtInstallAvailable = pkgs ? virtinst;
  virtInstallCmd =
    if virtInstallAvailable then "${pkgs.virtinst}/bin/virt-install" else "virt-install";
  libvirtDefaultNetworkScript = pkgs.writeShellScript "libvirt-default-network" ''
    set -eu
    virsh_bin="${pkgs.libvirt}/bin/virsh"
    net_name="default"

    # Define network if missing (virsh net-define is idempotent per net_name).
    if ! "$virsh_bin" net-info "$net_name" >/dev/null 2>&1; then
      tmp_xml="$(mktemp)"
      cat >"$tmp_xml" <<'EOF'
<network>
  <name>default</name>
  <forward mode='nat'/>
  <bridge name='virbr0' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>
EOF
      "$virsh_bin" net-define "$tmp_xml" >/dev/null 2>&1 || true
      "$virsh_bin" net-autostart "$net_name" >/dev/null 2>&1 || true
      rm -f "$tmp_xml"
    fi

    # Start network; ignore failure if already active.
    "$virsh_bin" net-start "$net_name" >/dev/null 2>&1 || true
  '';
in

{
  # =========================================================================
  # Core Virtualization Services
  # =========================================================================
  virtualisation = {
    libvirtd = {
      enable = true;
      qemu = {
        package = pkgs.qemu_kvm;
        runAsRoot = false;
        swtpm.enable = true;
      };
    };
  };

  # =========================================================================
  # Virtual Machine Management Tools
  # =========================================================================

  # Virt-manager: GUI for managing VMs
  programs.virt-manager.enable = true;

  # SPICE: Enhanced desktop virtualization protocol
  virtualisation.spiceUSBRedirection.enable = true;

  # =========================================================================
  # User Configuration
  # =========================================================================

  # Add all users in the 'wheel' group to libvirtd group for VM management
  # This allows admin users to manage VMs without manual group assignment
  users.groups.libvirtd.members = lib.attrNames (
    lib.filterAttrs (name: user: builtins.elem "wheel" user.extraGroups) config.users.users
  );

  # =========================================================================
  # Nested Virtualization
  # =========================================================================

  # Enable nested virtualization for testing VM-in-VM scenarios
  boot.extraModprobeConfig = ''
    # Intel CPUs
    options kvm_intel nested=1
    options kvm_intel enable_shadow_vmcs=1
    options kvm_intel enable_apicv=1
    options kvm_intel ept=1

    # AMD CPUs
    options kvm_amd nested=1
    options kvm_amd npt=1
  '';

  # =========================================================================
  # Network Configuration
  # =========================================================================

  # Allow reverse path filtering for VM networking
  networking.firewall.checkReversePath = false;

  # Default NAT network for VMs (virbr0)
  # Automatically created by libvirtd

  # Optional: Open ports for VNC/SPICE access from other machines
  # networking.firewall.allowedTCPPorts = [ 5900 5901 5902 ];  # VNC
  # networking.firewall.allowedTCPPorts = [ 5900 5901 5902 ];  # SPICE

  # =========================================================================
  # System Packages & Helper Scripts
  # =========================================================================

  environment.systemPackages =
    (with pkgs; [
      # Core virtualization tools
      virt-manager              # GUI VM manager
      virt-viewer               # VM display viewer
      libvirt                   # Provides virsh CLI and core tooling

      # VM automation
      vagrant                   # VM provisioning tool
      quickemu                  # Quick VM testing (Windows, macOS, etc.)

      # Network tools
      bridge-utils              # Network bridge management
      dnsmasq                   # DHCP/DNS for VM networks

      # Debugging
      qemu                      # QEMU utilities
      libguestfs                # VM disk image tools
      libguestfs-with-appliance # Appliance for guestfs

      # Performance analysis
      virt-top                  # VM resource monitoring
    ])
    ++ lib.optional virtInstallAvailable pkgs.virtinst
    ++ [
      # Helper scripts
      (pkgs.writeShellScriptBin "vm-create-nixos" ''
      #!/usr/bin/env bash
      # Quick NixOS VM creation script
      set -euo pipefail

      NAME=''${1:-nixos-test}
      MEMORY=''${2:-4096}
      CPUS=''${3:-2}
      DISK_SIZE=''${4:-20}

      echo "🚀 Creating NixOS VM: $NAME"
      echo "  Memory: $MEMORY MB"
      echo "  CPUs: $CPUS"
      echo "  Disk: $DISK_SIZE GB"

      # Download latest NixOS ISO (or specify path)
      ISO_URL="https://channels.nixos.org/nixos-25.11/latest-nixos-minimal-x86_64-linux.iso"
      ISO_PATH="/var/lib/libvirt/images/nixos-minimal.iso"

      if [ ! -f "$ISO_PATH" ]; then
        echo "📥 Downloading NixOS ISO..."
        ${pkgs.curl}/bin/curl -L "$ISO_URL" -o "$ISO_PATH"
      fi

      # Ensure virt-install is available
      if ! command -v virt-install >/dev/null 2>&1; then
        echo "virt-install is not available. Install the virtinst package or add it to environment.systemPackages."
        exit 1
      fi

      # Create VM
      ${virtInstallCmd} \
        --name "$NAME" \
        --memory "$MEMORY" \
        --vcpus "$CPUS" \
        --disk size="$DISK_SIZE" \
        --cdrom "$ISO_PATH" \
        --os-variant nixos-unstable \
        --network network=default \
        --graphics spice \
        --console pty,target_type=serial \
        --boot uefi

      echo "✅ VM created: $NAME"
      echo "   Access with: virt-manager"
    '')

    (pkgs.writeShellScriptBin "vm-list" ''
      #!/usr/bin/env bash
      # List all VMs with status
      echo "📋 Virtual Machines:"
      ${pkgs.libvirt}/bin/virsh list --all
    '')

    (pkgs.writeShellScriptBin "vm-snapshot" ''
      #!/usr/bin/env bash
      # Create VM snapshot
      set -euo pipefail

      VM_NAME="$1"
      SNAPSHOT_NAME="''${2:-snapshot-$(date +%Y%m%d-%H%M%S)}"

      echo "📸 Creating snapshot: $SNAPSHOT_NAME for $VM_NAME"
      ${pkgs.libvirt}/bin/virsh snapshot-create-as "$VM_NAME" "$SNAPSHOT_NAME"
      echo "✅ Snapshot created"
    '')
  ];

  # =========================================================================
  # Documentation (declarative via environment.etc)
  # =========================================================================

  environment.etc."nixos/VM-QUICKSTART.txt".text = ''
    ========================================
    NixOS Virtualization Quick Start Guide
    ========================================

    Create a NixOS VM:
      $ vm-create-nixos myvm 4096 2 20

    List all VMs:
      $ vm-list

    Start a VM:
      $ virsh start myvm

    Connect to VM console:
      $ virt-manager
      # OR
      $ virt-viewer myvm

    Create snapshot:
      $ vm-snapshot myvm my-snapshot

    Stop a VM:
      $ virsh shutdown myvm

    Delete a VM:
      $ virsh undefine myvm --remove-all-storage

    Check VM status:
      $ virsh dominfo myvm

    ========================================
    For full documentation, see:
      - https://nixos.wiki/wiki/Libvirt
      - https://nixos.wiki/wiki/Virt-manager
    Configuration: virtualization.nix
    ========================================
  '';



  # Default NAT network
  systemd.services."libvirt-network-default" = {
    description = "Libvirt default NAT network";
    after = [ "libvirtd.service" ];
    requires = [ "libvirtd.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${pkgs.runtimeShell} -c ${lib.escapeShellArg "${libvirtDefaultNetworkScript}"}";
      ExecStop = "${pkgs.runtimeShell} -c ${lib.escapeShellArg "${pkgs.libvirt}/bin/virsh net-destroy default >/dev/null 2>&1 || true"}";
    };
  };
}
