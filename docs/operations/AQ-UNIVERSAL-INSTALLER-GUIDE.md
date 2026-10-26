---
Status: Active
Owner: hyperd
Last Updated: 2026-10-25
---

# AQ-OS SOTA Universal USB Installer & Bare-Metal/VM Deployment Manual

> **Scope**: Declarative, repeatable installer specification and live execution runbook for deploying the complete NixOS AI Agentic Software Factory onto bare metal, hypervisors (Proxmox, KVM/QEMU, ESXi, VMware), cloud VPS, and local workstations across x86_64 and aarch64 architectures.
> **Standard**: Zero hardcoded secrets, automated hardware fact discovery, optional full-disk LUKS/TPM2 encryption, and rootless VM-verified disk partitioning.

---

## 1. Architectural Architecture & Pre-Flight

The installer reproduces the full NixOS AI developer factory (`ai-dev` / `aqos-workstation`):
1. **Host Orchestration & Inference**: `llama.cpp` APU offload / CUDA / ROCm acceleration.
2. **Knowledge & Telemetry Mesh**: AIDB (`:8002`), Hybrid-Coordinator (`:8003`), Ralph Loop (`:8004`), Switchboard (`:8085`), and Command Center Cockpit (`:8889`).
3. **Defense-in-Depth Confinement**: Bubblewrap execution cells, Landlock egress sandboxing, AppArmor LSM profiles, and systemd cgroups v2.
4. **Secret Management**: SOPS/age encrypted at rest; decrypted into volatile `/run/secrets` (tmpfs).

```
                      +-----------------------------------+
                      |   AQ-OS Universal Live USB ISO    |
                      +-----------------+-----------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
        [Bare Metal Hardware]                         [Virtual Hypervisors]
  (Intel/AMD x86_64, ARM aarch64)               (Proxmox VE, KVM/libvirt, WSL2)
                 |                                             |
                 v                                             v
     nixos-generate-config                       disko (gpt-plain / gpt-luks)
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
                       +----------------------------------+
                       |    nixos-install --flake .#host  |
                       +----------------+-----------------+
                                        |
                                        v
                       +----------------------------------+
                       |   First-Boot Finalizer (s2)      |
                       |  - Age Key Auto-Provisioning     |
                       |  - Service Homeostasis Ignition  |
                       +----------------------------------+
```

---

## 2. Generating the SOTA Bootable USB Installer

To build the universal installation ISO directly from this repository:

```bash
# 1. Build the declarative installer image
nix build .#nixosConfigurations.aqos-install-vm-plain.config.system.build.isoImage -o result-iso

# 2. Identify the target USB flash drive (e.g., /dev/sdb)
lsblk -d -o NAME,SIZE,MODEL,TRAN

# 3. Write directly to USB using rootless dd/pipe or standard dd
sudo dd if=$(echo result-iso/iso/*.iso) of=/dev/sdX bs=4M status=progress conv=fsync oflag=direct
```

---

### 2.3 Verified Flake Derivations (Pre-Flight Evaluated)
- **Plain Ext4/ZFS Target**: `/nix/store/r4nq257k8nn4vy97cdccv7y4i62238p7-nixos-system-aqos-install-vm-26.05.20261015.26f4107.drv`
- **TPM2/LUKS Encrypted Target**: `/nix/store/v8g0635nsmq04fxklgz5bdycbjahankl-nixos-system-aqos-install-vm-26.05.20261015.26f4107.drv`

## 3. Universal Hardware Target Matrices

| Hardware Class | Recommended Profile | Storage Layout | Model Offload Envelope |
| :--- | :--- | :--- | :--- |
| **High-End AI Workstation** (24GB+ VRAM/RAM) | `aqos-workstation` | `gpt-luks-ext4` (TPM2) | Full 35B MoE / 32-layer APU offload |
| **Edge / Compact Node** (16GB RAM) | `aqos-server` | `gpt-ext4` | 8B Q4_K_M quantized / 12 layers |
| **Proxmox / KVM Virtual Machine** | `aqos-vm` | `disko` virtio | Swappable test model / remote inference |
| **Headless CI / Cluster Node** | `aqos-ci` | `zfs-root` | Remote API fallback (`switchboard`) |

---

## 4. Bare-Metal & VM Installation Walkthrough

### Step 1: Booting into the Live Installer
1. Insert the bootable USB drive into the target system and boot via UEFI (`F11`, `F12`, or `Del`).
2. Select **AQ-OS SOTA Installer (NixOS 26.05 Flake)** from the GRUB boot menu.
3. The live environment will auto-log in to a shell with rootless agent capabilities and the installer CLI ready.

### Step 2: Running Hardware Fact Discovery
Run the autonomous hardware discovery script:
```bash
# Probes PCI devices, CPU microarchitecture, GPU VRAM, NVMe drives, and RAM limits
bash scripts/governance/discover-system-facts.sh
```
This inspects the system and generates:
- Target drive selection (`/dev/nvme0n1` or `/dev/sda`).
- Hardware layout configuration (`hardware-configuration.nix`).
- Model memory envelope parameters.

### Step 3: Executing Declarative Partitioning & Deployment
Run the guided deployment harness:
```bash
# Option A: Full-Disk Encrypted (Recommended for portable/metal systems)
sudo nixos-quick-deploy.sh --target /dev/nvme0n1 --layout gpt-luks-ext4 --profile aqos-workstation

# Option B: Plain Partitioning (Cloud VPS / Disposable VMs)
sudo nixos-quick-deploy.sh --target /dev/vda --layout gpt-ext4 --profile aqos-vm
```

During execution, `disko` will format the drive, create UEFI ESP partitions, configure swap and ext4/zfs root mounts, populate the initial `/mnt` root, and execute `nixos-install --flake .#aqos-workstation`.

---

## 5. Post-Install & First-Boot Finalization (Slice s2)

Upon initial reboot into the freshly installed disk:
1. **Hardware-Bound Decryption**:
   - If TPM2 auto-unlock was selected, the system boots unattended without manual passphrase input.
2. **First-Boot Agentic Ignition**:
   - The declarative `aqos-first-boot.service` executes once.
   - Decrypts SOPS service credentials (`/run/secrets/*`) using the machine's assigned age key.
   - Spins up PostgreSQL, Qdrant, llama.cpp, AIDB, and Switchboard.
   - Seeds baseline RAG knowledge collections from local git repositories into AIDB (`:8002`).
3. **Verification**:
   ```bash
   # Run authoritative host verification
   python3 scripts/testing/harness_qa/main.py 0
   ```
   All 7 layers (L1 through L7) will report healthy status, and the Command Center Dashboard Cockpit will be accessible at `http://localhost:8889`.
