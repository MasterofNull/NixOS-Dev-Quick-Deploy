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
                                                              # MTP (Multi-Token Prediction) variant: bakes draft heads into the GGUF
                                                              # for speculative decoding. Requires llama.cpp b9180+ (MTP merged 2026-05-16).
                                                              # Expected ~1.4-2x decode throughput vs non-MTP on this CPU-dominant setup.
                                                              llamaCpp.activeModel = "qwen3.6-35b-mtp";
                                                              # useSymlink: llama-server loads from a stable symlink path.
                                                              # After this rebuild, future model swaps need NO rebuild:
                                                              #   sudo aq-model-switch <key>
                                                              llamaCpp.useSymlink = true;
                                                              llamaCpp.extraArgs = [
                                                                # Qwen3.6-35B on this CPU needs up to 5 minutes for large prompts.
                                                                # 120s caused every meaningful editor request to be killed mid-flight.
                                                                "--timeout" "600"
                                                                # MTP requires --parallel 1 (-np > 1 is unsupported with draft-mtp).
                                                                "--parallel" "1"
                                                                "--batch-size" "512"
                                                                # 64-token micro-batches drove prompt latency to 64ms/tok (8x slower
                                                                # than 256-token batches). 256 fits comfortably in 27GB RAM with mlock.
                                                                "--ubatch-size" "256"
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
                                                                # MTP speculative decoding: draft-mtp uses the model's built-in MTP
                                                                # heads to predict N tokens ahead and verify in bulk. Start at 2 for
                                                                # CPU-dominant inference (Renoir APU); tune up to 4 if acceptance
                                                                # rate stays high (monitor via llama-server /metrics endpoint).
                                                                "--spec-type" "draft-mtp"
                                                                "--spec-draft-n-max" "2"
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
