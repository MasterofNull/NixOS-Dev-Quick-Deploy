# Virtualization Setup for NixOS Development

## Overview

The NixOS-Dev-Quick-Deploy system includes a complete virtualization stack for safe development and testing. This allows you to test NixOS configurations in isolated VMs before applying them to your base system, preventing system failures and the need for fresh installs.

## What's Included

### System-Level Services (via `virtualization.nix`)

- **KVM/QEMU** - Hardware-accelerated virtualization
- **Libvirt** - Virtualization management daemon
- **Virt-manager** - GUI for managing VMs
- **OVMF** - UEFI firmware with Secure Boot and TPM 2.0 support
- **Nested Virtualization** - For testing VM-in-VM scenarios
- **SPICE USB Redirection** - Enhanced guest integration
- **Rootless Operation** - Security-focused rootless QEMU

### User-Level Tools (via `home.nix`)

- **virt-manager** - GUI VM manager
- **virt-viewer** - VM display viewer
- **libvirt** - CLI tools (virsh, virt-install)
- **virtinst** - virt-install command-line tool
- **virt-top** - VM resource monitoring
- **libguestfs** - VM disk image tools
- **vagrant** - VM provisioning and automation
- **quickemu** - Quick VM testing for various OSes
- **bridge-utils** - Network bridge management

## Verification

After deployment, verify virtualization is working:

```bash
# Check if libvirtd service is running
systemctl status libvirtd

# Check if you're in the libvirtd group
groups | grep libvirtd

# List available VMs
virsh list --all

# Test KVM availability
lsmod | grep kvm

# Check virtualization capabilities
virt-host-validate
```

## Usage

### Create a NixOS Test VM

```bash
# Use the helper script (from virtualization.nix)
vm-create-nixos mytest 4096 2 20
# Creates: name=mytest, RAM=4GB, CPUs=2, Disk=20GB

# Or manually with virt-install
virt-install \
  --name nixos-test \
  --memory 4096 \
  --vcpus 2 \
  --disk size=20 \
  --cdrom /path/to/nixos-minimal.iso \
  --os-variant nixos-unstable \
  --network network=default \
  --graphics spice
```

### Manage VMs

```bash
# List all VMs
vm-list
# or
virsh list --all

# Start a VM
virsh start mytest

# Stop a VM
virsh shutdown mytest

# Open virt-manager GUI
virt-manager

# View VM console
virt-viewer mytest
```

### Create Snapshots

```bash
# Create snapshot
vm-snapshot mytest before-config-change

# List snapshots
virsh snapshot-list mytest

# Restore snapshot
virsh snapshot-revert mytest before-config-change
```

### Network Configuration

The default NAT network (virbr0) is automatically created. VMs get IPs in the 192.168.122.0/24 range.

```bash
# Check network status
virsh net-list --all

# Start default network
virsh net-start default

# View network info
virsh net-info default
```

## Development Workflow

### Testing NixOS Configurations

1. **Create a test VM:**
   ```bash
   vm-create-nixos nixos-test 4096 2 20
   ```

2. **Install NixOS in the VM** using the ISO

3. **Test your configuration:**
   - Copy your `configuration.nix` to the VM
   - Test `nixos-rebuild switch` in the VM
   - Verify everything works

4. **Snapshot before changes:**
   ```bash
   vm-snapshot nixos-test stable-state
   ```

5. **Apply to base system** only after VM testing succeeds

### Quick Testing with Quickemu

```bash
# Test Windows, macOS, or other Linux distros
quickemu --vm ubuntu-22.04.conf
quickemu --vm windows-11.conf
```

## Troubleshooting

### "Permission denied" errors

```bash
# Ensure you're in the libvirtd group
sudo usermod -aG libvirtd $USER
# Log out and back in, or:
newgrp libvirtd
```

### KVM not available

```bash
# Check if virtualization is enabled in BIOS
# Check if KVM modules are loaded
lsmod | grep kvm

# Load modules if needed
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd
```

### VM won't start

```bash
# Check libvirtd logs
journalctl -u libvirtd -n 50

# Check VM logs
virsh dominfo mytest
virsh dumpxml mytest | less
```

### Network issues

```bash
# Restart default network
virsh net-destroy default
virsh net-start default

# Check firewall rules
sudo iptables -L -n | grep virbr0
```

## Helper Scripts

The virtualization module provides these helper scripts:

- `vm-create-nixos` - Quick NixOS VM creation
- `vm-list` - List all VMs with status
- `vm-snapshot` - Create/restore VM snapshots

## Benefits for NixOS Development

1. ✅ **Safe Testing** - Test configurations without risking base system
2. ✅ **Quick Rollback** - Use snapshots to revert failed changes
3. ✅ **Multi-OS Testing** - Test against different OS versions
4. ✅ **Isolated Environments** - Test networking, services, etc. safely
5. ✅ **Development Speed** - Faster iteration without full reinstalls

## Related Documentation

- `templates/nixos-improvements/virtualization.nix` - Full module source
- `docs/SYSTEM-AUDIT-AND-IMPROVEMENTS-DEC-2025.md` - Virtualization recommendations
- NixOS Manual: [Virtualisation](https://nixos.org/manual/nixos/stable/#ch-virtualisation)



