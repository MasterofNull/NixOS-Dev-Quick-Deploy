{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# AI Stack role — native NixOS service implementation.
#
# Activated when: mySystem.roles.aiStack.enable = true
#
# Runtime
# ───────
# llamacpp
#   • llama-server on :8080 (OpenAI-compatible API, ROCm-accelerated on AMD)
#   • Open WebUI on :3000 (wired to llama-server via OPENAI_API_BASE_URLS)
#   • Qdrant vector DB on :6333 (when vectorDb.enable)
#   • No daemon overhead — llama.cpp serves models directly from GGUF files.
# ---------------------------------------------------------------------------
let
  cfg  = config.mySystem;
  ports = cfg.ports;
  ai   = cfg.aiStack;

  roleEnabled = cfg.roles.aiStack.enable;
  listenAddr  = if ai.listenOnLan then "0.0.0.0" else "127.0.0.1";
  llama       = ai.llamaCpp;
  swb         = ai.switchboard;

  hasOpenWebui = lib.versionAtLeast lib.version "24.11";
  hasQdrant    = lib.versionAtLeast lib.version "24.11";

  # HuggingFace download: resolved repo/file from options (fall back to model basename).
  hfRepo = llama.huggingFaceRepo;
  hfFile = if llama.huggingFaceFile != null
           then llama.huggingFaceFile
           else baseNameOf llama.model;
  hasAutoDownload = hfRepo != null;
  hfSha256 = llama.sha256;
  hfSha256Valid = hfSha256 != null && builtins.match "^[a-fA-F0-9]{64}$" hfSha256 != null;

  resolvedAccel =
    if ai.acceleration != "auto" then ai.acceleration
    else if cfg.hardware.gpuVendor == "amd" || cfg.hardware.igpuVendor == "amd" then "rocm"
    else if cfg.hardware.gpuVendor == "nvidia" then "cuda"
    else "cpu";

  hasGpuLayersArg = lib.any (arg:
    lib.hasPrefix "--n-gpu-layers" arg || lib.hasPrefix "--gpu-layers" arg
  ) llama.extraArgs;

  # GPU layer offloading: pass 99 when ROCm/CUDA is active and the user
  # has not already supplied their own --n-gpu-layers flag.
  accelArgs = lib.optionals (resolvedAccel != "cpu" && !hasGpuLayersArg) [
    "--n-gpu-layers" "99"
  ];

  llamaArgs = accelArgs ++ llama.extraArgs;

  # ── ROCm runtime environment for AMD GPU acceleration ─────────────────────
  # HSA_OVERRIDE_GFX_VERSION lets llama.cpp use AMD APU/iGPU variants that
  # are not in the official ROCm support matrix. Common values:
  #   "9.0.0"  — Ryzen 5000 / Van Gogh APU (gfx90c)
  #   "10.3.0" — Ryzen 5000 / Cezanne APU (gfx90c uses 9.0.0 too)
  #   "11.0.0" — Ryzen 7000 / Phoenix APU (gfx1103)
  # Unset (null) = let ROCm auto-detect; correct for officially supported GPUs.
  rocmEnv = lib.optionalAttrs (resolvedAccel == "rocm") (
    {
      # Disable SDMA (DMA copy engine) on integrated APUs — prevents hangs
      # on some Ryzen iGPU variants under ROCm compute workloads.
      HSA_ENABLE_SDMA       = "0";
      # Improve memory allocation for APU unified memory access.
      GPU_MAX_ALLOC_PERCENT = "100";
      GPU_SINGLE_ALLOC_PERCENT = "100";
      GPU_MAX_HEAP_SIZE     = "100";
      # Use the system ROCm OpenCL ICD.
      OPENCL_VENDOR_PATH    = "/run/opengl-driver/etc/OpenCL/vendors";
    }
    // lib.optionalAttrs (ai.rocmGfxOverride != null) {
      HSA_OVERRIDE_GFX_VERSION = ai.rocmGfxOverride;
      # Set HCC target matching the override for HIP kernels.
      HCC_AMDGPU_TARGET = "gfx${builtins.replaceStrings ["."] [""] ai.rocmGfxOverride}";
    }
  );

  # Convert env attrset to "KEY=VALUE" strings for systemd Environment=.
  rocmEnvList = lib.mapAttrsToList (k: v: "${k}=${v}") rocmEnv;

  embed = ai.embeddingServer;

  # Embedding server HF download vars (same pattern as chat model).
  embedHfRepo = embed.huggingFaceRepo;
  embedHfFile = if embed.huggingFaceFile != null
                then embed.huggingFaceFile
                else baseNameOf embed.model;
  hasEmbedAutoDownload = embedHfRepo != null;
  embedHfSha256 = embed.sha256;
  embedHfSha256Valid = embedHfSha256 != null && builtins.match "^[a-fA-F0-9]{64}$" embedHfSha256 != null;

  # Open WebUI environment — wired to llama-server (OpenAI-compatible API).
  openWebuiEnv =
    {
      OPENAI_API_BASE_URLS = "http://127.0.0.1:${toString (if swb.enable then swb.port else llama.port)}";
      OPENAI_API_KEYS      = "dummy";  # llama-server ignores the value
      OLLAMA_BASE_URL      = "";       # disable built-in Ollama probe
      WEBUI_AUTH           = lib.mkDefault "false";
      ENABLE_SIGNUP        = lib.mkDefault "false";
    }
    // lib.optionalAttrs embed.enable {
      # NOTE: VECTOR_DB / QDRANT_URI intentionally omitted — the NixOS
      # open-webui package does not bundle qdrant_client and crashes on import.
      # Open WebUI uses its built-in chromadb for RAG vector storage.
      # Qdrant itself runs on :6333 for the AIDB MCP server.
      # Wire Open WebUI to the dedicated embedding server.
      RAG_EMBEDDING_ENGINE      = "openai";
      RAG_OPENAI_API_BASE_URL   = "http://127.0.0.1:${toString embed.port}/v1";
      RAG_OPENAI_API_KEY        = "dummy";
      EMBEDDING_MODEL_API_BASE_URL = "http://127.0.0.1:${toString embed.port}/v1";
    };
in
{
  config = lib.mkMerge [

    (lib.mkIf (roleEnabled && ai.models != [ ]) {
      warnings = [
        "mySystem.aiStack.models is deprecated and ignored for llama.cpp. Set mySystem.aiStack.llamaCpp.model to a GGUF path instead."
      ];
    })

    (lib.mkIf roleEnabled {
      assertions = [
        {
          assertion = !hasAutoDownload || hfSha256Valid;
          message = "mySystem.aiStack.llamaCpp.huggingFaceRepo requires mySystem.aiStack.llamaCpp.sha256 (64 hex chars).";
        }
        {
          assertion = !hasEmbedAutoDownload || embedHfSha256Valid;
          message = "mySystem.aiStack.embeddingServer.huggingFaceRepo requires mySystem.aiStack.embeddingServer.sha256 (64 hex chars).";
        }
        # Phase 11.3.3 — Model allowlist enforcement
        {
          assertion = cfg.aiStack.modelAllowlist == [ ] || builtins.elem hfRepo cfg.aiStack.modelAllowlist;
          message = "mySystem.aiStack.llamaCpp.huggingFaceRepo \"${hfRepo}\" is not in mySystem.aiStack.modelAllowlist. Add to allowlist or change model repo.";
        }
        {
          assertion = cfg.aiStack.modelAllowlist == [ ] || builtins.elem embedHfRepo cfg.aiStack.modelAllowlist;
          message = "mySystem.aiStack.embeddingServer.huggingFaceRepo \"${embedHfRepo}\" is not in mySystem.aiStack.modelAllowlist. Add to allowlist or change model repo.";
        }
        # Phase 5.2.4 — hard block: AI stack requires at least 12 GB to load any model.
        {
          assertion = cfg.hardware.systemRamGb >= 12;
          message = "AI stack: minimum 12 GB RAM required (mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb}). Disable mySystem.roles.aiStack.enable or increase RAM.";
        }
        # Phase 16.1.2 — reject invalid hardwareTier values with a descriptive message.
        # The enum type in options.nix enforces this at parse time; this assertion
        # provides a friendlier context-aware message in the AI stack module itself.
        {
          assertion = builtins.elem cfg.hardwareTier [ "nano" "micro" "small" "medium" "large" ];
          message = "AI stack: mySystem.hardwareTier = \"${cfg.hardwareTier}\" is not valid. Expected one of: nano micro small medium large. Check nix/lib/hardware-tier.nix or override mySystem.hardwareTier in your host config.";
        }
      ];
      # Phase 5.2.4 — advisory warning: 14B/13B models are marginal below 16 GB.
      # Phase 16.2.2 — warn when configured model likely exceeds 70% of system RAM.
      warnings =
        lib.optional (
          cfg.hardware.systemRamGb < 16 &&
          (lib.hasInfix "14b" (lib.toLower llama.model) || lib.hasInfix "13b" (lib.toLower llama.model))
        ) "AI stack: a 14B/13B model is configured but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 16). Consider Qwen2.5-Coder-7B Q4_K_M instead."
        ++ lib.optional (
          cfg.hardware.systemRamGb < 24 &&
          (lib.hasInfix "70b" (lib.toLower llama.model) || lib.hasInfix "65b" (lib.toLower llama.model))
        ) "AI stack: a 70B/65B model requires ~40 GB RAM but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 24). Inference will likely OOM."
        ++ lib.optional (
          cfg.hardware.systemRamGb < 12 &&
          (lib.hasInfix "32b" (lib.toLower llama.model))
        ) "AI stack: a 32B model requires ~20 GB RAM but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 12).";
    })

    # Phase 16.5.1 — aarch64 NEON build of llama.cpp.
    # Inject the overlay only on aarch64-linux; on x86_64 it is a no-op.
    # The overlay patches cmakeFlags to enable NEON and disable Metal/OpenCL.
    (lib.mkIf (roleEnabled && pkgs.stdenv.hostPlatform.isAarch64) {
      nixpkgs.overlays = [
        (import ../../lib/overlays/llama-cpp-aarch64.nix)
      ];
    })

    # ── llama.cpp — active when llamaCpp.enable regardless of backend ─────────
    # The llama-server provides an OpenAI-compatible HTTP API on :8080.
    # Model path is controlled by mySystem.aiStack.llamaCpp.model; the unit
    # starts automatically once a GGUF file exists at that path.
    (lib.mkIf (roleEnabled && llama.enable) {

      users.groups.llama = { };
      users.users.llama = {
        isSystemUser = true;
        group        = "llama";
        description  = "llama.cpp inference server";
        home         = "/var/lib/llama-cpp";
        createHome   = true;
      };
      users.users.${cfg.primaryUser}.extraGroups = lib.mkAfter [ "llama" ];

      systemd.tmpfiles.rules = [
        "d /var/lib/llama-cpp 0750 llama llama -"
        "d /var/lib/llama-cpp/models 0750 llama llama -"
        # Log directory writable by llama service
        "d /var/log/llama-cpp 0750 llama llama -"
      ];

      systemd.services.llama-cpp = {
        description = "llama.cpp OpenAI-compatible inference server";
        wantedBy    = [ "multi-user.target" ];
        after       = [ "network.target" "llama-cpp-model-fetch.service" ];
        requires    = [ "llama-cpp-model-fetch.service" ];
        serviceConfig = {
          PartOf           = [ "ai-stack.target" ];
          Type             = "simple";
          User             = "llama";
          Group            = "llama";
          Restart          = "on-failure";
          RestartSec       = "5s";
          StateDirectory   = "llama-cpp";
          RuntimeDirectory = "llama-cpp";
          # Phase 5.2.2: allow model weights to be locked in RAM (mlockall).
          # Prevents OS from paging out model pages during inference under pressure.
          LimitMEMLOCK     = "infinity";
          # ROCm environment variables for AMD GPU acceleration.
          # Empty list when resolvedAccel != "rocm" — no overhead.
          Environment      = rocmEnvList;
          # Phase 13.1.3 — inference server never needs internet access;
          # model weights are fetched by a separate dedicated download service.
          IPAddressAllow = [ "127.0.0.1/8" "::1/128" ];
          IPAddressDeny  = [ "any" ];
          ExecStart = lib.concatStringsSep " " ([
            "${pkgs.llama-cpp}/bin/llama-server"
            "--host" (lib.escapeShellArg llama.host)
            "--port" (toString llama.port)
            "--model" (lib.escapeShellArg llama.model)
          ] ++ (map lib.escapeShellArg llamaArgs));
        };
      };

      # Model fetch oneshot — downloads the GGUF from HuggingFace on first boot
      # if the file is absent.  Subsequent boots skip the download instantly.
      # Check progress / errors with: journalctl -u llama-cpp-model-fetch -f
      systemd.services.llama-cpp-model-fetch = {
        description = "llama.cpp model download (first-boot provisioning)";
        wantedBy    = [ "multi-user.target" ];
        after       = [ "network-online.target" "local-fs.target" ];
        wants       = [ "network-online.target" ];
        before      = [ "llama-cpp.service" ];
        serviceConfig = {
          Type            = "oneshot";
          RemainAfterExit = true;
          User            = "root";  # needs write to /var/lib/llama-cpp
          ExecStart = pkgs.writeShellScript "llama-model-fetch" (''
            set -euo pipefail
            model="${llama.model}"
            model_dir="$(dirname "$model")"

            # Ensure model directory exists with correct ownership.
            install -d -m 0750 -o llama -g llama "$model_dir"

            if [ -f "$model" ]; then
              echo "llama-cpp: model already present at $model"
              exit 0
            fi

          '' + (if hasAutoDownload then ''
            hf_url="https://huggingface.co/${hfRepo}/resolve/main/${hfFile}"
            echo "llama-cpp: downloading model from $hf_url"
            echo "llama-cpp: destination: $model"

            tmp="$(mktemp "$model_dir/.fetch-XXXXXX")"
            trap 'rm -f "$tmp"' EXIT

            ${pkgs.curl}/bin/curl \
              --location \
              --retry 5 \
              --retry-delay 10 \
              --retry-connrefused \
              --connect-timeout 30 \
              --max-time 7200 \
              --progress-bar \
              --output "$tmp" \
              "$hf_url"

            sz=$(stat -c%s "$tmp" 2>/dev/null || echo 0)
            if [ "$sz" -lt 1048576 ]; then
              echo "llama-cpp: download appears corrupt ($sz bytes) — check HF repo/file config" >&2
              exit 1
            fi

            expected_sha="${hfSha256}"
            actual_sha="$(${pkgs.coreutils}/bin/sha256sum "$tmp" | ${pkgs.gawk}/bin/awk '{print $1}')"
            if [ "$actual_sha" != "$expected_sha" ]; then
              echo "llama-cpp: SHA256 mismatch for downloaded model" >&2
              echo "expected: $expected_sha" >&2
              echo "actual:   $actual_sha" >&2
              exit 1
            fi

            # Phase 11.3 — Model Weight Integrity: Run safety verification
            # This checks for pickle magic bytes and records provenance metadata.
            echo "llama-cpp: running Phase 11.3 model safety verification..."
            ${pkgs.bash}/bin/bash ${mcp.repoPath}/scripts/verify-model-safety.sh \
              --hf-repo "${hfRepo}" \
              --provenance-dir "${dataDir}/models" \
              "$tmp"

            mv "$tmp" "$model"
            chown llama:llama "$model"
            chmod 0640 "$model"
            trap - EXIT
            echo "llama-cpp: model ready ($sz bytes) at $model"
          '' else ''
            echo "llama-cpp: model not found at $model" >&2
            echo "llama-cpp: set mySystem.aiStack.llamaCpp.huggingFaceRepo to enable auto-download" >&2
            echo "llama-cpp: or place the GGUF manually, then: systemctl start llama-cpp" >&2
            # Exit 0 so llama-cpp.service is not blocked on a missing option.
            exit 0
          ''));
        };
      };

      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan (
        [ llama.port ]
        ++ lib.optional swb.enable swb.port
        ++ lib.optional (ai.ui.enable && hasOpenWebui) 3000
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantHttp
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantGrpc
      );

      # Keep model files private, but grant explicit read access to the
      # primary desktop user for local desktop clients (e.g. GPT4All).
      systemd.services.ai-local-model-access = {
        description = "Grant primary user ACL access to local llama.cpp models";
        wantedBy = [ "multi-user.target" ];
        after = [ "llama-cpp-model-fetch.service" "llama-cpp-embed-model-fetch.service" ];
        wants = [ "llama-cpp-model-fetch.service" "llama-cpp-embed-model-fetch.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          User = "root";
          ExecStart = pkgs.writeShellScript "ai-local-model-access" ''
            set -euo pipefail
            model_root="/var/lib/llama-cpp"
            model_dir="/var/lib/llama-cpp/models"

            if ! id "${cfg.primaryUser}" >/dev/null 2>&1; then
              exit 0
            fi
            if [ ! -d "$model_dir" ]; then
              exit 0
            fi

            ${pkgs.acl}/bin/setfacl -m "u:${cfg.primaryUser}:r-x" "$model_root" "$model_dir"
            ${pkgs.acl}/bin/setfacl -d -m "u:${cfg.primaryUser}:r-x" "$model_dir"
            find "$model_dir" -type f -print0 | xargs -0 -r ${pkgs.acl}/bin/setfacl -m "u:${cfg.primaryUser}:r--"
          '';
        };
      };
    })

    # ── Open WebUI ────────────────────────────────────────────────────────────
    (lib.mkIf (roleEnabled && ai.ui.enable && hasOpenWebui) {
      services.open-webui = {
        enable      = true;
        host        = listenAddr;
        port        = 3000;
        environment = openWebuiEnv;
      };
    })

    # ── Dedicated embedding server — separate llama.cpp instance on :8081 ──────
    # Serves /v1/embeddings for RAG ingestion (Qdrant) and Open WebUI.
    # Uses a small, fast embedding model (e.g. nomic-embed-text-v1.5 ~274 MB)
    # rather than the larger chat model so inference and embedding don't contend.
    (lib.mkIf (roleEnabled && embed.enable) {

      # Model fetch oneshot — same idempotent pattern as the chat model.
      systemd.services.llama-cpp-embed-model-fetch = {
        description = "llama.cpp embedding model download (first-boot provisioning)";
        wantedBy    = [ "multi-user.target" ];
        after       = [ "network-online.target" "local-fs.target" ];
        wants       = [ "network-online.target" ];
        before      = [ "llama-cpp-embed.service" ];
        serviceConfig = {
          Type            = "oneshot";
          RemainAfterExit = true;
          User            = "root";
          ExecStart = pkgs.writeShellScript "llama-embed-model-fetch" (''
            set -euo pipefail
            model="${embed.model}"
            model_dir="$(dirname "$model")"
            install -d -m 0750 -o llama -g llama "$model_dir"

            if [ -f "$model" ]; then
              echo "llama-cpp-embed: model already present at $model"
              exit 0
            fi

          '' + (if hasEmbedAutoDownload then ''
            hf_url="https://huggingface.co/${embedHfRepo}/resolve/main/${embedHfFile}"
            echo "llama-cpp-embed: downloading from $hf_url"
            echo "llama-cpp-embed: destination: $model"

            tmp="$(mktemp "$model_dir/.fetch-embed-XXXXXX")"
            trap 'rm -f "$tmp"' EXIT

            ${pkgs.curl}/bin/curl \
              --location \
              --retry 5 \
              --retry-delay 10 \
              --retry-connrefused \
              --connect-timeout 30 \
              --max-time 3600 \
              --progress-bar \
              --output "$tmp" \
              "$hf_url"

            sz=$(stat -c%s "$tmp" 2>/dev/null || echo 0)
            if [ "$sz" -lt 1048576 ]; then
              echo "llama-cpp-embed: download appears corrupt ($sz bytes)" >&2
              exit 1
            fi

            expected_sha="${embedHfSha256}"
            actual_sha="$(${pkgs.coreutils}/bin/sha256sum "$tmp" | ${pkgs.gawk}/bin/awk '{print $1}')"
            if [ "$actual_sha" != "$expected_sha" ]; then
              echo "llama-cpp-embed: SHA256 mismatch for downloaded model" >&2
              echo "expected: $expected_sha" >&2
              echo "actual:   $actual_sha" >&2
              exit 1
            fi

            # Phase 11.3 — Model Weight Integrity: Run safety verification
            # This checks for pickle magic bytes and records provenance metadata.
            echo "llama-cpp-embed: running Phase 11.3 model safety verification..."
            ${pkgs.bash}/bin/bash ${mcp.repoPath}/scripts/verify-model-safety.sh \
              --hf-repo "${embedHfRepo}" \
              --provenance-dir "${dataDir}/models" \
              "$tmp"

            mv "$tmp" "$model"
            chown llama:llama "$model"
            chmod 0640 "$model"
            trap - EXIT
            echo "llama-cpp-embed: model ready ($sz bytes) at $model"
          '' else ''
            echo "llama-cpp-embed: model not found at $model" >&2
            echo "llama-cpp-embed: set mySystem.aiStack.embeddingServer.huggingFaceRepo to enable auto-download" >&2
            exit 0
          ''));
        };
      };

      # Embedding inference server — llama.cpp with --embedding flag only.
      # Chat completions are intentionally disabled on this instance.
      systemd.services.llama-cpp-embed = {
        description = "llama.cpp embedding server (:${toString embed.port})";
        wantedBy    = [ "multi-user.target" ];
        after       = [ "network.target" "llama-cpp-embed-model-fetch.service" ];
        requires    = [ "llama-cpp-embed-model-fetch.service" ];
        serviceConfig = {
          PartOf           = [ "ai-stack.target" ];
          Type             = "simple";
          User             = "llama";
          Group            = "llama";
          Restart          = "on-failure";
          RestartSec       = "5s";
          StateDirectory   = "llama-cpp";
          RuntimeDirectory = "llama-cpp-embed";
          LimitMEMLOCK     = "infinity";
          # Phase 13.1.3 — embedding server needs no internet access.
          IPAddressAllow   = [ "127.0.0.1/8" "::1/128" ];
          IPAddressDeny    = [ "any" ];
          Environment      = rocmEnvList;
          ExecStart = lib.concatStringsSep " " ([
            "${pkgs.llama-cpp}/bin/llama-server"
            "--host" (lib.escapeShellArg llama.host)
            "--port" (toString embed.port)
            "--model" (lib.escapeShellArg embed.model)
            "--embedding"        # embedding-only mode; disables chat completions
            "--pooling" "mean"   # mean pooling — correct for nomic/bge models
            "--ctx-size" "512"   # embedding models use short contexts
            "--threads" "4"
          ] ++ (map lib.escapeShellArg embed.extraArgs));
        };
      };

      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan [
        embed.port
      ];
    })

    # ── Phase 5.1.3 — AI workload kernel tuning ───────────────────────────────
    # NUMA balancing causes periodic memory-page migrations that introduce
    # latency spikes during LLM inference on single-socket AMD APUs/CPUs.
    # Setting to 0 trades potential long-term NUMA locality gains for
    # consistent low-latency inference on the common single-socket topology.
    # vm.nr_overcommit_hugepages: allows transparent hugepage allocation even
    # when the system is under memory pressure (llama.cpp benefits during load).
    (lib.mkIf roleEnabled {
      boot.kernel.sysctl = {
        "kernel.numa_balancing"         = lib.mkDefault 0;
        "vm.nr_overcommit_hugepages"    = lib.mkDefault 0;
        # Phase 5.2.1 — overcommit: prevents OOM kills during llama.cpp mmap+COW
        # model loading. Mode 1 = always allow; ratio 100 = commit up to RAM+swap.
        "vm.overcommit_memory"          = lib.mkDefault 1;
        "vm.overcommit_ratio"           = lib.mkDefault 100;
      };
      # Phase 5.1.4 / 16.3.2 — unlock full AMD GPU power management features.
      # Required for LACT manual frequency control and ROCm compute workloads.
      # ppfeaturemask=0xffffffff enables all amdgpu power management feature bits.
      # Guard: only inject when an AMD GPU is actually present (resolvedAccel == "rocm").
      # On Intel/NVIDIA/CPU-only hosts the parameter is silently ignored, but we
      # avoid polluting the kernel command line unnecessarily.
      boot.kernelParams = lib.mkIf (resolvedAccel == "rocm")
        (lib.mkAfter [ "amdgpu.ppfeaturemask=0xffffffff" ]);
    })

    # ── Qdrant vector database — shared across backends ───────────────────────
    # ── Phase 5.5.2 + 16.2.1 — Tier-based default model selection ─────────────
    # lib.mkDefault means the user can override with mySystem.aiStack.llamaCpp.model.
    # These defaults assume HF auto-download will place the file at the path below.
    (lib.mkIf (roleEnabled && llama.huggingFaceRepo == null) {
      mySystem.aiStack.llamaCpp.model = lib.mkDefault (
        let
          modelDir = "/var/lib/llama-cpp/models";
          tierModels = {
            nano   = "${modelDir}/qwen2.5-0.5b-instruct-q8_0.gguf";
            micro  = "${modelDir}/qwen2.5-1.5b-instruct-q8_0.gguf";
            small  = "${modelDir}/phi-4-mini-instruct-q4_k_m.gguf";
            medium = "${modelDir}/qwen2.5-coder-7b-instruct-q4_k_m.gguf";
            large  = "${modelDir}/qwen2.5-coder-14b-instruct-q4_k_m.gguf";
          };
        in
          tierModels.${cfg.hardwareTier}
      );
    })

    # Phase 16.5.2 — skip Open WebUI on nano/micro tiers (too heavy for ≤2 GB RAM).
    # The llama.cpp HTTP API remains available for direct OpenAI-compatible access.
    # Users can override with: mySystem.aiStack.ui.enable = true;
    (lib.mkIf roleEnabled {
      mySystem.aiStack.ui.enable = lib.mkDefault (
        cfg.hardwareTier != "nano" && cfg.hardwareTier != "micro"
      );
    })

    (lib.mkIf (roleEnabled && ai.vectorDb.enable && hasQdrant) {
      services.qdrant.enable = true;
      services.qdrant.settings.service = {
        http_port = ports.qdrantHttp;
        grpc_port = ports.qdrantGrpc;
      };
      systemd.services.qdrant = {
        partOf = [ "ai-stack.target" ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
      };
    })

  ];
}
