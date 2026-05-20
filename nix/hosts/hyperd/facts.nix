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
      rocmGpuTarget = null;
      accelerationClass = "amd-apu-renoir";
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
                                                              # NOTE: Using non-MTP model while MTP download completes.
                                                              # Switch back to "qwen3.6-35b-mtp" and add MTP extraArgs after
                                                              # Qwen3.6-35B-A3B-UD-Q5_K_S.gguf (or Q4_K_XL) finishes downloading.
                                                              llamaCpp.activeModel = "qwen3.6-35b";
                                                              # useSymlink: llama-server loads from a stable symlink path.
                                                              # After this rebuild, future model swaps need NO rebuild:
                                                              #   sudo aq-model-switch <key>
                                                              llamaCpp.useSymlink = true;
                                                              llamaCpp.extraArgs = [
                                                                # Qwen3.6-35B on this CPU needs up to 5 minutes for large prompts.
                                                                "--timeout" "600"
                                                                # 27GB RAM: 22.1GB model + KV cache leaves no room for >1 parallel slot.
                                                                "--parallel" "1"
                                                                "--batch-size" "512"
                                                                "--ubatch-size" "256"
                                                                "--threads" "8"
                                                                "--threads-batch" "8"
                                                                # Full 41-layer Vulkan offload overruns this Renoir iGPU and ends in
                                                                # ErrorDeviceLost during model load. Keep a smaller partial offload so
                                                                # Qwen remains the active harness model without crashing startup.
                                                                "--n-gpu-layers" "12"
                                                                "--flash-attn" "off"
                                                                "--mlock"
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
