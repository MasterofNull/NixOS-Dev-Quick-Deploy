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
      OPENAI_API_BASE_URLS = "http://127.0.0.1:${toString llama.port}";
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
      ];
    })

    # ── llama.cpp — active when llamaCpp.enable regardless of backend ─────────
    # The llama-server provides an OpenAI-compatible HTTP API on :8080.
    # Model path is controlled by mySystem.aiStack.llamaCpp.model; the unit
    # starts automatically once a GGUF file exists at that path.
    (lib.mkIf (roleEnabled && llama.enable) {

      users.groups.llama = { gid = 35011; };
      users.users.llama = {
        isSystemUser = true;
        group        = "llama";
        description  = "llama.cpp inference server";
        home         = "/var/lib/llama-cpp";
        createHome   = true;
      };

      systemd.tmpfiles.rules = [
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
          # ROCm environment variables for AMD GPU acceleration.
          # Empty list when resolvedAccel != "rocm" — no overhead.
          Environment      = rocmEnvList;
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
        ++ lib.optional (ai.ui.enable && hasOpenWebui) 3000
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantHttp
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantGrpc
      );
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

    # ── Qdrant vector database — shared across backends ───────────────────────
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
