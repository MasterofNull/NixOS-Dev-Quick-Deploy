# Declarative Microarchitectural CPU Cache Timing Side-Channel Isolation
# Prevents covert cross-core/SMT cache timing attacks between untrusted agents and host workloads.
{
  config,
  pkgs,
  lib,
  ...
}: let
  cfg = config.mySystem.security.microarchitecturalIsolation;
in {
  options.mySystem.security.microarchitecturalIsolation = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Enforce strict physical core pinning, isolcpus/nohz_full/rcu_nocbs,
        SMT disabling (nosmt), and dedicated isolated container/microVM slices.
      '';
    };

    isolatedCores = lib.mkOption {
      type = lib.types.str;
      default = "4-7";
      description = "Core range to strip from CFS scheduler for untrusted agent workloads.";
    };

    housekeepingCores = lib.mkOption {
      type = lib.types.str;
      default = "0-3";
      description = "Housekeeping cores handling host system, timers, and interrupts.";
    };
  };

  config = lib.mkIf cfg.enable {
    # 1. Kernel Hardening & CPU Line Isolation
    boot.kernelParams = [
      "nosmt"
      "isolcpus=managed_irq,domain,${cfg.isolatedCores}"
      "nohz_full=${cfg.isolatedCores}"
      "rcu_nocbs=${cfg.isolatedCores}"
      "irqaffinity=${cfg.housekeepingCores}"
      "workqueue.cpumask=${cfg.housekeepingCores}"
    ];

    # 2. Virtualization & Libvirt Host Bindings
    virtualisation.libvirtd = {
      enable = true;
      qemu = {
        package = pkgs.qemu_kvm;
        runAsRoot = false;
        swtpm.enable = true;
        ovmf.enable = true;
        verbatimConfig = ''
          cgroup_controllers = [ "cpu", "devices", "memory", "cpuset" ]
        '';
      };
    };

    # 3. System Packages for Inspection and NUMA Pinning
    environment.systemPackages = with pkgs; [
      libvirt
      qemu_kvm
      virt-manager
      util-linux
      numactl
    ];

    # 4. Dedicated cgroup slice for isolated agent runtimes
    systemd.slices."agent-isolated" = {
      description = "Microarchitecturally Isolated AI Agent Workload Slice";
      sliceConfig = {
        AllowedCPUs = cfg.isolatedCores;
        MemoryAccounting = true;
        CPUAccounting = true;
        IOAccounting = true;
      };
    };
  };
}
