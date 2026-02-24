{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  isAmd = cfg.hardware.cpuVendor == "amd";
in
{
  # AMD CPU: microcode, P-state, thermal.
  # Owns services.thermald.enable for ALL profiles — Intel cpu/intel.nix sets it true.
  hardware.cpu.amd.updateMicrocode = lib.mkIf isAmd (lib.mkDefault true);

  # schedutil is built into the kernel; no module load needed.
  powerManagement.cpuFreqGovernor = lib.mkIf isAmd (lib.mkDefault "schedutil");

  # Enable AMD P-state driver when the kvm-amd module is loaded (virtualisation or bare-metal).
  # lib.mkAfter ensures it appends after any hardware-configuration.nix params.
  boot.kernelParams = lib.mkIf isAmd (lib.mkAfter [
    "amd_pstate=active"
  ]);

  # thermald is Intel-only; explicitly disable on AMD to prevent crash loops.
  # This is the single owner of services.thermald.enable — do not set it elsewhere.
  services.thermald.enable = lib.mkIf isAmd (lib.mkForce false);

  # ── NIX-ISSUE-006: Blacklist HiSilicon/Huawei kernel modules ───────────────
  # The Linux kernel includes HiSilicon modules compiled as loadable modules.
  # On AMD x86_64 systems these drivers are for absent hardware, add boot
  # noise, and carry known CVEs (CVE-2024-42147, CVE-2024-47730,
  # CVE-2024-38568, CVE-2024-38569). Blacklisting prevents auto-load.
  boot.blacklistedKernelModules = lib.mkIf isAmd (lib.mkAfter [
    "hisi_sec2"     # HiSilicon crypto accelerator
    "hisi_hpre"     # HiSilicon RSA/DH accelerator
    "hisi_zip"      # HiSilicon ZIP/decompress accelerator
    "hisi_trng"     # HiSilicon true RNG
    "hisi_qm"       # HiSilicon Queue Manager (shared infrastructure)
    "hisi_pcie_pmu" # HiSilicon PCIe performance monitor
    "hns3"          # Huawei HNS3 NIC driver
    "hclge"         # HNS3 PF driver
    "hnae3"         # HNS3 base framework
  ]);
}
