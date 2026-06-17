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
                          # llama.cpp divides --ctx-size by --parallel slots; keep
                          # one slot so local tool-calling gets the full 16k window.
                          llamaCpp.ctxSize = 8192;
                          # useSymlink: llama-server loads from a stable symlink path.
                          # Future model swaps need NO rebuild: sudo aq-model-switch <key>
                          llamaCpp.useSymlink = true;
                          llamaCpp.extraArgs = [
                            # Qwen3.6-35B on this CPU needs up to 5 minutes for large prompts.
                            "--timeout"
                            "3600"
                            # 27GB RAM: one slot gets full 8192 ctx; SWB_LOCAL_CONCURRENCY=1.
                            # Phase 176: was "2" — halved context to 4096 per slot, causing
                            # agent context overflow on multi-tool tasks (4250 > 4096).
                            "--parallel"
                            "1"
                            "--batch-size"
                            "512"
                            "--ubatch-size"
                            "256"
                            "--threads"
                            "8"
                            "--threads-batch"
                            "8"
                            # Renoir iGPU: 12 layers avoids ErrorDeviceLost at startup.
                            "--n-gpu-layers"
                            "12"
                            # flash-attn is now enabled via ai-stack.nix kvCacheType block
                            # (Phase 66.1: q8_0 KV cache requires --flash-attn)
                            "--jinja"
                          ];
                          # MTP speculative decoding — declared as first-class options so
                          # the coordinator can read AI_SPECULATIVE_DECODING_ENABLED correctly.
                          llamaCpp.specType = "draft-mtp";
                          llamaCpp.specDraftNMax = 2;
                          embeddingServer = {
                            activeModel = "bge-m3";
                            # useSymlink: embedding model also uses stable symlink path.
                            # Swap with: sudo aq-model-switch --embed <key>
                            useSymlink = true;
                            # Renoir iGPU shares VRAM with system RAM. --n-gpu-layers 99 in
                            # ai-stack.nix causes GPU OOM for inputs > ~400 tokens. Override
                            # to 12 layers (same as chat model) for reliable KV-cache headroom.
                            extraArgs = ["--threads" "4" "--n-gpu-layers" "12" "--parallel" "4" "--ubatch-size" "2048"];
                          };

                          switchboard.remoteModelAliases = {
                            opencode = "qwen/qwen3-coder-32b";
                          };
                          aiHarness.eval.faithfulnessEnabled = true;
                          # Phase 171: calibrated for actual 3.45 tok/s throughput.
                          # Sync-safe budget: 2 tool calls × 74s + 232s synthesis
                          # + 60s queue overhead + 30s slack = 500s → outer = 530s.
                          # Tasks estimated >200s auto-route to async_mode via RoutingClass SSOT.
                          aiHarness.runtime.delegateTimeoutSeconds = 530;
                          autonomousImprovement.enable = true;
                        };
  };
}
