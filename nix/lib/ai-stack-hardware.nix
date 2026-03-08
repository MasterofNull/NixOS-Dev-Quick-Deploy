/**
  AI Stack Hardware Abstraction Layer

  Provides hardware-agnostic GPU detection, acceleration selection, and
  environment configuration for the AI stack. Designed for portability
  to containers (Docker, Podman) on Linux, Windows (WSL2), and macOS.

  Supported accelerators:
    - cuda   — NVIDIA GPUs (discrete)
    - vulkan — AMD/Intel/NVIDIA via Vulkan compute (best for APUs)
    - rocm   — AMD ROCm/HIP (deprecated; falls back to vulkan)
    - metal  — Apple Silicon (macOS native only)
    - cpu    — Universal fallback

  Usage:
    let
      hwLib = import ../lib/ai-stack-hardware.nix { inherit lib pkgs; };
      accel = hwLib.resolveAcceleration {
        gpuVendor = "amd";
        igpuVendor = "amd";
        system = "x86_64-linux";
        explicit = "auto";
      };
      env = hwLib.getEnvironment accel;
    in ...

  Container export:
    hwLib.exportForContainer { acceleration = "vulkan"; ... }
*/
{ lib, pkgs ? null }:

let
  # Load hardware profiles from JSON (portable config)
  profilesPath = ../../config/ai-stack-hardware-profiles.json;
  profiles = builtins.fromJSON (builtins.readFile profilesPath);

  # Platform detection helpers
  systemToPlatform = system:
    if system == "x86_64-linux" then "x86_64-linux"
    else if system == "aarch64-linux" then "aarch64-linux"
    else if system == "x86_64-darwin" then "x86_64-darwin"
    else if system == "aarch64-darwin" then "aarch64-darwin"
    else "x86_64-linux";  # default

  # Vendor to accelerator mapping
  vendorToAccelerator = { vendor, platform }:
    let
      platformDefaults = profiles.platform_defaults.${platform} or profiles.platform_defaults."x86_64-linux";
    in
    platformDefaults.${vendor} or platformDefaults.none or "cpu";

  # Check if accelerator is available on platform
  acceleratorAvailable = { accel, platform }:
    let
      accelConfig = profiles.accelerators.${accel} or null;
    in
    accelConfig != null && builtins.elem platform (accelConfig.platforms or []);

in {
  /**
    Resolve the best acceleration mode for given hardware.

    Arguments:
      gpuVendor   — "nvidia", "amd", "intel", "apple", "none"
      igpuVendor  — "amd", "intel", "none" (integrated GPU)
      system      — Nix system string (e.g., "x86_64-linux")
      explicit    — User-specified mode or "auto"

    Returns: "cuda" | "vulkan" | "rocm" | "metal" | "cpu"
  */
  resolveAcceleration = {
    gpuVendor ? "none",
    igpuVendor ? "none",
    system ? "x86_64-linux",
    explicit ? "auto",
  }:
    let
      platform = systemToPlatform system;

      # Effective GPU vendor (discrete > integrated)
      effectiveVendor =
        if gpuVendor != "none" then gpuVendor
        else if igpuVendor != "none" then igpuVendor
        else "none";

      # Auto-detected accelerator
      autoDetected = vendorToAccelerator {
        vendor = effectiveVendor;
        inherit platform;
      };

      # Handle explicit selection
      resolved =
        if explicit == "auto" then autoDetected
        else if explicit == "rocm" then
          # ROCm is deprecated; remap to vulkan
          if acceleratorAvailable { accel = "vulkan"; inherit platform; }
          then "vulkan"
          else "cpu"
        else if acceleratorAvailable { accel = explicit; inherit platform; }
        then explicit
        else "cpu";
    in
    resolved;

  /**
    Get environment variables for an accelerator.

    Arguments:
      accel         — Accelerator name
      deviceIndex   — GPU device index (default: "0")
      gpuVendor     — For Vulkan ICD selection
      system        — Platform string
      gfxVersion    — ROCm GFX version override
      cpuThreads    — CPU thread count for CPU mode

    Returns: Attribute set of environment variables
  */
  getEnvironment = {
    accel,
    deviceIndex ? "0",
    gpuVendor ? "amd",
    system ? "x86_64-linux",
    gfxVersion ? null,
    cpuThreads ? "8",
  }:
    let
      platform = systemToPlatform system;
      accelConfig = profiles.accelerators.${accel} or {};

      # Vulkan ICD path selection
      vulkanIcdPath =
        let
          vendorConfig = accelConfig.vendors.${gpuVendor} or {};
          icdKey = if lib.hasSuffix "aarch64" platform then "icd_linux_aarch64" else "icd_linux";
        in
        vendorConfig.${icdKey} or vendorConfig.icd_linux or "";

      # Base environment from profile
      baseEnv = accelConfig.environment or {};

      # Substitute template variables
      substituteEnv = env:
        builtins.mapAttrs (name: value:
          builtins.replaceStrings
            ["\${device_index:-0}" "\${device_index}" "\${icd_path}" "\${gfx_version}" "\${cpu_threads}" "\${state_dir}"]
            [deviceIndex deviceIndex vulkanIcdPath (if gfxVersion != null then gfxVersion else "") cpuThreads "/var/lib/llama-cpp"]
            value
        ) env;
    in
    substituteEnv baseEnv;

  /**
    Get llama.cpp runtime arguments for an accelerator.

    Arguments:
      accel      — Accelerator name
      cpuThreads — Thread count for CPU operations

    Returns: List of command-line arguments
  */
  getRuntimeArgs = { accel, cpuThreads ? "8" }:
    let
      accelConfig = profiles.accelerators.${accel} or {};
      flags = accelConfig.llama_cpp_flags.runtime or [];
    in
    map (arg:
      builtins.replaceStrings ["\${cpu_threads}"] [cpuThreads] arg
    ) flags;

  /**
    Get CMake flags for building llama.cpp with accelerator support.

    Arguments:
      accel — Accelerator name

    Returns: List of CMake flag strings
  */
  getCmakeFlags = { accel }:
    let
      accelConfig = profiles.accelerators.${accel} or {};
    in
    accelConfig.llama_cpp_flags.cmake or [];

  /**
    Get hardware tier based on system RAM.

    Arguments:
      systemRamGb — System RAM in gigabytes

    Returns: "nano" | "micro" | "small" | "medium" | "large"
  */
  getHardwareTier = { systemRamGb }:
    let
      tiers = profiles.hardware_tiers;
      findTier = name: tier:
        systemRamGb >= (builtins.elemAt tier.ram_range 0) &&
        systemRamGb < (builtins.elemAt tier.ram_range 1);
      matchingTiers = lib.filterAttrs findTier tiers;
    in
    if matchingTiers == {} then "small"
    else builtins.head (builtins.attrNames matchingTiers);

  /**
    Get recommended model parameters for a hardware tier.

    Arguments:
      tier — Hardware tier name

    Returns: Attribute set with quant, max_params, ctx_size
  */
  getTierRecommendations = { tier }:
    let
      tierConfig = profiles.hardware_tiers.${tier} or profiles.hardware_tiers.small;
    in {
      quant = tierConfig.recommended_quant;
      maxParams = tierConfig.max_model_params;
      ctxSize = tierConfig.ctx_size;
    };

  /**
    Export configuration for container deployment.

    Arguments:
      accel         — Accelerator name
      gpuVendor     — GPU vendor for Vulkan
      deviceIndex   — GPU device index
      cpuThreads    — CPU thread count
      modelsDir     — Host path to models
      stateDir      — Host path to state

    Returns: Attribute set with env, volumes, ports, deps
  */
  exportForContainer = {
    accel,
    gpuVendor ? "amd",
    deviceIndex ? "0",
    cpuThreads ? "8",
    modelsDir ? "/var/lib/llama-cpp/models",
    stateDir ? "/var/lib/llama-cpp",
  }:
    let
      env = lib.self.getEnvironment {
        inherit accel deviceIndex gpuVendor cpuThreads;
      };
      accelConfig = profiles.accelerators.${accel} or {};
      containerExport = profiles.container_export;
    in {
      environment = env;
      runtimeArgs = lib.self.getRuntimeArgs { inherit accel cpuThreads; };
      volumes = [
        "${modelsDir}:/models:ro"
        "${stateDir}:/var/lib/llama-cpp:rw"
      ];
      ports = containerExport.ports;
      dependencies = accelConfig.container_deps or [];
      accelerator = accel;
      platform = accelConfig.platforms or [];
    };

  /**
    Generate environment file content for container deployment.

    Arguments: Same as exportForContainer

    Returns: String content for .env file
  */
  generateEnvFile = args:
    let
      export = lib.self.exportForContainer args;
      envLines = lib.mapAttrsToList (k: v: "${k}=${v}") export.environment;
      metaLines = [
        "# AI Stack Container Configuration"
        "# Generated by ai-stack-hardware.nix"
        "# Accelerator: ${export.accelerator}"
        ""
        "AI_STACK_ACCELERATOR=${export.accelerator}"
        "AI_STACK_INFERENCE_PORT=${toString export.ports.inference}"
        "AI_STACK_EMBEDDING_PORT=${toString export.ports.embedding}"
        "AI_STACK_WEBUI_PORT=${toString export.ports.webui}"
        ""
      ];
    in
    lib.concatStringsSep "\n" (metaLines ++ envLines ++ [""]);

  /**
    Check if hardware supports a specific accelerator.

    Arguments:
      accel  — Accelerator to check
      system — Nix system string

    Returns: Boolean
  */
  isAcceleratorSupported = { accel, system }:
    acceleratorAvailable { inherit accel; platform = systemToPlatform system; };

  /**
    List all supported accelerators for a platform.

    Arguments:
      system — Nix system string

    Returns: List of accelerator names
  */
  listSupportedAccelerators = { system }:
    let
      platform = systemToPlatform system;
      platformDefaults = profiles.platform_defaults.${platform} or {};
    in
    platformDefaults.priority or ["cpu"];

  # Re-export profiles for inspection
  inherit profiles;
}
