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
                                                              # Q5_K_S MTP model (manually placed from ~/Downloads after browser download).
                                                              # MTP draft heads enable speculative decoding (~1.5–2× throughput gain).
                                                              llamaCpp.activeModel = "qwen3.6-35b-mtp-q5";
                                                              # This 27GB mobile workstation cannot keep the Q5_K_S chat
                                                              # model mlocked while VSCodium, browser, dashboard, AIDB,
                                                              # Qdrant, and the embedding server are active. Keep the local
                                                              # model available, but reserve desktop headroom.
                                                              llamaCpp.ctxSize = 8192;
                                                              # useSymlink: llama-server loads from a stable symlink path.
                                                              # Future model swaps need NO rebuild: sudo aq-model-switch <key>
                                                              llamaCpp.useSymlink = true;
                                                              llamaCpp.extraArgs = [
                                                                # Qwen3.6-35B on this CPU needs up to 5 minutes for large prompts.
                                                                "--timeout" "600"
                                                                # 27GB RAM: 24.5GB model (Q5_K_S) + KV cache = tight; 1 parallel slot only.
                                                                "--parallel" "1"
                                                                "--batch-size" "512"
                                                                "--ubatch-size" "256"
                                                                "--threads" "8"
                                                                "--threads-batch" "8"
                                                                # Renoir iGPU: 12 layers avoids ErrorDeviceLost at startup.
                                                                "--n-gpu-layers" "12"
                                                                "--flash-attn" "off"
                                                                "--jinja"
                                                                # MTP speculative decoding — draft heads bundled in this GGUF.
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
                                                                extraArgs = [ "--threads" "4" "--n-gpu-layers" "12" ];
                                                              };
                                                            };
  };
}
