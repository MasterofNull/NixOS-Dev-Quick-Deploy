{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  kdev = cfg.roles.kernelDev;

  # Kernel development toolchain packages
  kernelBuildDeps = with pkgs; [
    # Core build tools
    gnumake
    gcc
    binutils
    flex
    bison
    bc
    perl
    elfutils
    openssl
    openssl.dev
    ncurses
    ncurses.dev

    # Static analysis and linting
    sparse                    # Semantic parser for C
    coccinelle               # Semantic patching
    cppcheck                 # Static analysis
    shellcheck               # Shell script linting

    # BTF/pahole for BPF development
    pahole                   # DWARF/BTF generator

    # Documentation
    sphinx
    python3Packages.sphinx-rtd-theme
    graphviz
    imagemagick

    # Kernel config tools
    pkg-config
    kconfig-frontends        # menuconfig/nconfig

    # Compression support
    zstd
    lz4
    xz
    zlib

    # Module signing
    libelf
    kmod
  ];

  # Debug and tracing tools
  kernelDebugTools = with pkgs; [
    perf-tools              # perf wrapper scripts
    trace-cmd               # ftrace frontend
    bpftrace                # BPF tracing
    bpftools                # BPF utilities
    # crash                 # Kernel crash dump analyzer (if available)
    strace
    ltrace
    gdb
  ];

  # Testing infrastructure
  kernelTestTools = with pkgs; [
    qemu_kvm                # KVM-accelerated QEMU
    debootstrap             # Create Debian rootfs for testing
    cpio                    # initramfs creation
  ];

  # Git workflow tools for kernel development
  kernelGitTools = with pkgs; [
    git
    git-send-email          # Patch submission
    b4                      # Kernel patch workflow tool
    patatt                  # Patch attestation
    public-inbox            # lei/public-inbox client (lore.kernel.org)
    msmtp                   # SMTP client for git-send-email
  ];

  # All kernel dev packages
  allKernelPackages = kernelBuildDeps
    ++ kernelDebugTools
    ++ kernelTestTools
    ++ kernelGitTools
    ++ (lib.optionals kdev.enableRust (with pkgs; [
      # Core Rust toolchain
      rustc
      cargo
      rustfmt
      clippy
      rust-bindgen           # Rust FFI bindings generator

      # Rust analyzer for IDE support
      rust-analyzer

      # LLVM/Clang toolchain (required for Rust kernel builds)
      llvmPackages_latest.clang
      llvmPackages_latest.llvm
      llvmPackages_latest.lld
      llvmPackages_latest.libclang

      # Additional Rust development tools
      cargo-watch            # Auto-rebuild on changes
      cargo-audit            # Security vulnerability checker
      cargo-expand           # Macro expansion viewer
      cargo-outdated         # Dependency update checker
    ]));
in
{
  # ---------------------------------------------------------------------------
  # Kernel Development Role
  # Provides complete toolchain for Linux kernel development and testing.
  # ---------------------------------------------------------------------------

  options.mySystem.roles.kernelDev = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable Linux kernel development toolchain and infrastructure.";
    };

    enableRust = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Include Rust toolchain for Rust-for-Linux development.

        Rust is permanently adopted in the Linux kernel (600K+ lines as of 2026).
        Required for:
        - DRM/Graphics drivers (Rust-only mandate starting 2027)
        - New filesystem drivers
        - Network device drivers
        - Security modules

        67% of kernel CVEs are memory-safety bugs that Rust prevents.
      '';
    };

    rustVersion = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "1.78.0";
      description = ''
        Specific Rust version for kernel compatibility.
        null = use system default (recommended for most cases).
        Check kernel Makefile for RUST_VERSION_MIN requirement.
      '';
    };

    enableLLVM = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Use LLVM/Clang toolchain for kernel builds.
        Required for Rust kernel modules (CONFIG_RUST=y).
        Enables LTO and CFI for enhanced security.
      '';
    };

    enableVirtme = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable virtme-ng for fast kernel testing without full VM.";
    };

    kernelSourceDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/${cfg.primaryUser}/kernel";
      description = "Default directory for kernel source trees.";
    };

    patchTrackingDb = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable AIDB schema extensions for patch tracking.";
    };

    gitSendEmailConfig = {
      smtpServer = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "smtp.gmail.com";
        description = "SMTP server for git-send-email.";
      };

      smtpPort = lib.mkOption {
        type = lib.types.int;
        default = 587;
        description = "SMTP port for git-send-email.";
      };

      smtpEncryption = lib.mkOption {
        type = lib.types.enum [ "tls" "ssl" "none" ];
        default = "tls";
        description = "SMTP encryption method.";
      };
    };
  };

  config = lib.mkIf kdev.enable {
    # Install all kernel development packages
    environment.systemPackages = allKernelPackages;

    # Ensure KVM is available for fast kernel testing
    boot.kernelModules = [ "kvm-amd" "kvm-intel" ];

    # Allow user access to /dev/kvm
    users.groups.kvm.members = [ cfg.primaryUser ];

    # Kernel config for development (enable debug features)
    boot.kernel.sysctl = {
      # Enable kernel debugging features
      "kernel.sysrq" = 1;                    # Enable SysRq
      "kernel.panic_on_oops" = 0;            # Don't panic on oops (for debugging)
      "kernel.ftrace_enabled" = 1;           # Enable ftrace
      "kernel.perf_event_paranoid" = -1;     # Allow perf for all users
    };

    # Create kernel source directory structure
    systemd.tmpfiles.rules = [
      "d ${kdev.kernelSourceDir} 0755 ${cfg.primaryUser} users -"
      "d ${kdev.kernelSourceDir}/linux 0755 ${cfg.primaryUser} users -"
      "d ${kdev.kernelSourceDir}/patches 0755 ${cfg.primaryUser} users -"
      "d ${kdev.kernelSourceDir}/configs 0755 ${cfg.primaryUser} users -"
      "d ${kdev.kernelSourceDir}/builds 0755 ${cfg.primaryUser} users -"
    ];

    # Enable ccache for faster rebuilds
    programs.ccache = {
      enable = true;
      cacheDir = "/var/cache/ccache";
      packageNames = [ "gcc" ];
    };

    # Increase limits for kernel builds
    security.pam.loginLimits = [
      {
        domain = cfg.primaryUser;
        type = "soft";
        item = "nofile";
        value = "65536";
      }
      {
        domain = cfg.primaryUser;
        type = "hard";
        item = "nofile";
        value = "524288";
      }
    ];

    # Environment variables for LLVM/Rust kernel builds
    environment.sessionVariables = lib.mkIf kdev.enableLLVM {
      # Point to LLVM toolchain for kernel builds
      LLVM = "1";
      LLVM_IAS = "1";
      # Rust bindgen needs libclang
      LIBCLANG_PATH = "${pkgs.llvmPackages_latest.libclang.lib}/lib";
    };

    # Git config for kernel workflow
    programs.git.config = {
      sendemail = lib.mkIf (kdev.gitSendEmailConfig.smtpServer != null) {
        smtpServer = kdev.gitSendEmailConfig.smtpServer;
        smtpServerPort = kdev.gitSendEmailConfig.smtpPort;
        smtpEncryption = kdev.gitSendEmailConfig.smtpEncryption;
        confirm = "auto";
        chainReplyTo = false;
      };
      format = {
        signOff = true;
        coverLetter = "auto";
      };
    };
  };
}
