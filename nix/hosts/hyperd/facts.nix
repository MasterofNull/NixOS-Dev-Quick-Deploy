{ ... }:
{
  mySystem = {
    hostName = "hyperd";
    primaryUser = "hyperd";
    profile = "ai-dev";
    system = "x86_64-linux";
    hardware = {
      gpuVendor = "amd";
      igpuVendor = "none";
      cpuVendor = "amd";
      storageType = "nvme";
      systemRamGb = 27;
      isMobile = true;
      firmwareType = "efi";
      earlyKmsPolicy = "off";
      nixosHardwareModule = "lenovo-thinkpad-p14s-amd-gen2";
    };
    kernel = {
      track = "latest-stable";
    };
    deployment = {
      enableHibernation = false;
      swapSizeGb = 0;
      rootFsckMode = "check";
      initrdEmergencyAccess = true;
    };
    disk = {
      layout = "none";
      device = "/dev/disk/by-id/CHANGE-ME";
      luks.enable = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };
    secureboot.enable = false;
    aiStack = {
              # Keep the host pinned to Qwen 3.6 for local harness validation. The
              # editor/switchboard layer must tolerate its longer startup lifecycle
              # rather than silently downgrading the test model.
              llamaCpp.activeModel = "qwen3.6-35b";
              # useSymlink: llama-server loads from a stable symlink path.
              # After this rebuild, future model swaps need NO rebuild:
              #   sudo aq-model-switch <key>
              llamaCpp.useSymlink = true;
              llamaCpp.extraArgs = [
                "--timeout" "120"
                "--parallel" "1"
                "--batch-size" "512"
                "--ubatch-size" "64"
                "--threads" "8"
                "--threads-batch" "8"
                # Full 41-layer Vulkan offload overruns this Renoir iGPU and ends in
                # ErrorDeviceLost during model load. Keep a smaller partial offload so
                # Qwen remains the active harness model without crashing startup.
                "--n-gpu-layers" "12"
                "--flash-attn" "off"
                "--mlock"
                # Enable jinja2 chat template so Qwen's built-in tool-calling template
                # is active. Required for the switchboard local-tool-calling profile.
                "--jinja"
              ];
              embeddingServer = {
                activeModel = "bge-m3";
                # useSymlink: embedding model also uses stable symlink path.
                # Swap with: sudo aq-model-switch --embed <key>
                useSymlink = true;
                # Renoir iGPU shares VRAM with system RAM. --n-gpu-layers 99 in
                # ai-stack.nix causes GPU OOM for inputs > ~400 tokens. Override
                # to 12 layers (same as chat model) for reliable KV-cache headroom.
                extraArgs = [ "--n-gpu-layers" "12" ];
              };
            };
  };
}
