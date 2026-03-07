{
  lib,
  config,
  pkgs,
  ...
}:
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
  cfg = config.mySystem;
  ports = cfg.ports;
  ai = cfg.aiStack;

  roleEnabled = cfg.roles.aiStack.enable;
  listenAddr =
    if ai.listenOnLan
    then "0.0.0.0"
    else "127.0.0.1";
  llama = ai.llamaCpp;
  swb = ai.switchboard;
  dataDir = "/var/lib/llama-cpp";
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  mutableLogDir = cfg.deployment.mutableSpaces.aiStackLogDir;

  hasOpenWebui = lib.versionAtLeast lib.version "24.11";
  hasQdrant = lib.versionAtLeast lib.version "24.11";

  # HuggingFace download: resolved repo/file from options (fall back to model basename).
  hfRepo = llama.huggingFaceRepo;
  hfFile =
    if llama.huggingFaceFile != null
    then llama.huggingFaceFile
    else baseNameOf llama.model;
  hasAutoDownload = hfRepo != null;
  hfSha256 = llama.sha256;
  hfSha256Valid = hfSha256 != null && builtins.match "^[a-fA-F0-9]{64}$" hfSha256 != null;

  resolvedAccel =
    if ai.acceleration != "auto"
    then ai.acceleration
    else if cfg.hardware.gpuVendor == "amd" || cfg.hardware.igpuVendor == "amd"
    then "rocm"
    else if cfg.hardware.gpuVendor == "nvidia"
    then "cuda"
    else "cpu";

  hasGpuLayersArg =
    lib.any (
      arg:
        lib.hasPrefix "--n-gpu-layers" arg || lib.hasPrefix "--gpu-layers" arg
    )
    llama.extraArgs;

  # GPU layer offloading: pass 99 when ROCm/CUDA is active and the user
  # has not already supplied their own --n-gpu-layers flag.
  accelArgs = lib.optionals (resolvedAccel != "cpu" && !hasGpuLayersArg) [
    "--n-gpu-layers"
    "99"
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
      HSA_ENABLE_SDMA = "0";
      # Improve memory allocation for APU unified memory access.
      GPU_MAX_ALLOC_PERCENT = "100";
      GPU_SINGLE_ALLOC_PERCENT = "100";
      GPU_MAX_HEAP_SIZE = "100";
      # Enable Unified Memory Architecture mode for APU shared memory.
      GGML_HIP_UMA = "1";
      # Use the system ROCm OpenCL ICD.
      OPENCL_VENDOR_PATH = "/run/opengl-driver/etc/OpenCL/vendors";
    }
    // lib.optionalAttrs (ai.rocmGfxOverride != null) {
      HSA_OVERRIDE_GFX_VERSION = ai.rocmGfxOverride;
      # Set HCC target matching the override for HIP kernels.
      HCC_AMDGPU_TARGET = "gfx${builtins.replaceStrings ["."] [""] ai.rocmGfxOverride}";
    }
  );

  # Vulkan environment for Mesa RADV on AMD GPUs.
  # Required for ggml-vulkan to find the ICD loader.
  vulkanEnv = {
    # Point Vulkan loader to NixOS ICD files
    VK_ICD_FILENAMES = "/run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json";
    # Ensure libvulkan can find the driver
    VK_DRIVER_FILES = "/run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json";
  };

  # Combined GPU environment: Vulkan for AMD (preferred), ROCm as fallback
  gpuEnv = if resolvedAccel == "rocm" then vulkanEnv else rocmEnv;

  # Convert env attrset to "KEY=VALUE" strings for systemd Environment=.
  rocmEnvList = lib.mapAttrsToList (k: v: "${k}=${v}") gpuEnv;

  embed = ai.embeddingServer;

  # Embedding server HF download vars (same pattern as chat model).
  embedHfRepo = embed.huggingFaceRepo;
  embedHfFile =
    if embed.huggingFaceFile != null
    then embed.huggingFaceFile
    else baseNameOf embed.model;
  hasEmbedAutoDownload = embedHfRepo != null;
  # Use empty string when sha256 is null to avoid coercion errors in shell scripts.
  embedHfSha256 = if embed.sha256 != null then embed.sha256 else "";
  embedHfSha256Valid = embed.sha256 != null && builtins.match "^[a-fA-F0-9]{64}$" embed.sha256 != null;

  aiHarnessCliWrappers = pkgs.symlinkJoin {
    name = "ai-harness-cli-wrappers";
    paths = [
      (pkgs.writeShellScriptBin "aqd" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-hints" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-hints" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-report" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-report" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-qa" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-qa" "$@"
      '')
      (pkgs.writeShellScriptBin "harness-rpc" ''
        exec "${pkgs.nodejs}/bin/node" "${cfg.mcpServers.repoPath}/scripts/ai/harness-rpc.js" "$@"
      '')
      (pkgs.writeShellScriptBin "project-init" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" workflows project-init "$@"
      '')
      (pkgs.writeShellScriptBin "workflow-primer" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" workflows primer "$@"
      '')
      (pkgs.writeShellScriptBin "workflow-brownfield" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" workflows brownfield "$@"
      '')
      (pkgs.writeShellScriptBin "workflow-retrofit" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" workflows retrofit "$@"
      '')
    ];
  };

  # Open WebUI environment — wired to llama-server (OpenAI-compatible API).
  openWebuiEnv =
    {
      OPENAI_API_BASE_URLS = "http://127.0.0.1:${toString (
        if swb.enable
        then swb.port
        else llama.port
      )}";
      OPENAI_API_KEYS = "dummy"; # llama-server ignores the value
      OLLAMA_BASE_URL = ""; # disable built-in Ollama probe
      WEBUI_AUTH = lib.mkDefault "false";
      ENABLE_SIGNUP = lib.mkDefault "false";
    }
    // lib.optionalAttrs embed.enable {
      # NOTE: VECTOR_DB / QDRANT_URI intentionally omitted — the NixOS
      # open-webui package does not bundle qdrant_client and crashes on import.
      # Open WebUI uses its built-in chromadb for RAG vector storage.
      # Qdrant itself runs on :6333 for the AIDB MCP server.
      # Wire Open WebUI to the dedicated embedding server.
      RAG_EMBEDDING_ENGINE = "openai";
      RAG_OPENAI_API_BASE_URL = "http://127.0.0.1:${toString embed.port}/v1";
      RAG_OPENAI_API_KEY = "dummy";
      EMBEDDING_MODEL_API_BASE_URL = "http://127.0.0.1:${toString embed.port}/v1";
    };
in {
  config = lib.mkMerge [
    (lib.mkIf (roleEnabled && ai.models != []) {
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
          # sha256 = null is allowed (skips verification; set after first deploy).
          # sha256 = "..." must be 64 hex chars if provided.
          assertion = !hasEmbedAutoDownload || embed.sha256 == null || embedHfSha256Valid;
          message = "mySystem.aiStack.embeddingServer.sha256 must be 64 hex characters when set.";
        }
        # Phase 11.3.3 — Model allowlist enforcement
        {
          assertion = cfg.aiStack.modelAllowlist == [] || builtins.elem hfRepo cfg.aiStack.modelAllowlist;
          message = "mySystem.aiStack.llamaCpp.huggingFaceRepo \"${hfRepo}\" is not in mySystem.aiStack.modelAllowlist. Add to allowlist or change model repo.";
        }
        {
          assertion = cfg.aiStack.modelAllowlist == [] || builtins.elem embedHfRepo cfg.aiStack.modelAllowlist;
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
          assertion = builtins.elem cfg.hardwareTier ["nano" "micro" "small" "medium" "large"];
          message = "AI stack: mySystem.hardwareTier = \"${cfg.hardwareTier}\" is not valid. Expected one of: nano micro small medium large. Check nix/lib/hardware-tier.nix or override mySystem.hardwareTier in your host config.";
        }
      ];
      # Phase 5.2.4 — advisory warning: 14B/13B models are marginal below 16 GB.
      # Phase 16.2.2 — warn when configured model likely exceeds 70% of system RAM.
      warnings =
        lib.optional (
          cfg.hardware.systemRamGb
          < 16
          && (lib.hasInfix "14b" (lib.toLower llama.model) || lib.hasInfix "13b" (lib.toLower llama.model))
        ) "AI stack: a 14B/13B model is configured but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 16). Consider Qwen2.5-Coder-7B Q4_K_M instead."
        ++ lib.optional (
          cfg.hardware.systemRamGb
          < 24
          && (lib.hasInfix "70b" (lib.toLower llama.model) || lib.hasInfix "65b" (lib.toLower llama.model))
        ) "AI stack: a 70B/65B model requires ~40 GB RAM but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 24). Inference will likely OOM."
        ++ lib.optional (
          cfg.hardware.systemRamGb
          < 12
          && (lib.hasInfix "32b" (lib.toLower llama.model))
        ) "AI stack: a 32B model requires ~20 GB RAM but mySystem.hardware.systemRamGb = ${toString cfg.hardware.systemRamGb} (< 12).";
    })

    # ── Phase 20.1 — llama.cpp version tracking overlay ────────────────────────
    # When trackLatest = true, build llama.cpp from source using the pinned
    # version in nix/pins/llama-cpp.json. This allows tracking upstream releases
    # independently of nixpkgs channel updates.
    # Update the pin with: scripts/ai/update-llama-cpp.sh
    (lib.mkIf (roleEnabled && llama.trackLatest) {
      nixpkgs.overlays = [
        (import ../../lib/overlays/llama-cpp-latest.nix {
          pinFile = ../../pins/llama-cpp.json;
          useFallback = llama.useFallback;
          # Use Vulkan for AMD GPUs (better APU compatibility than ROCm)
          enableVulkan = (resolvedAccel == "rocm");
          enableRocm = false; # Disabled: ROCm crashes on Cezanne APU
          enableCuda = (resolvedAccel == "cuda");
        })
      ];
    })

    # Phase 16.5.1 — aarch64 NEON build of llama.cpp.
    # Inject the overlay only on aarch64-linux; on x86_64 it is a no-op.
    # The overlay patches cmakeFlags to enable NEON and disable Metal/OpenCL.
    # Applied after the version overlay so NEON flags compose correctly.
    (lib.mkIf (roleEnabled && config.nixpkgs.hostPlatform.isAarch64) {
      nixpkgs.overlays = [
        (import ../../lib/overlays/llama-cpp-aarch64.nix)
      ];
    })

    # ── llama.cpp — active when llamaCpp.enable regardless of backend ─────────
    # The llama-server provides an OpenAI-compatible HTTP API on :8080.
    # Model path is controlled by mySystem.aiStack.llamaCpp.model; the unit
    # starts automatically once a GGUF file exists at that path.
    (lib.mkIf (roleEnabled && llama.enable) {
      users.groups.llama = {};
      users.users.llama = {
        isSystemUser = true;
        group = "llama";
        description = "llama.cpp inference server";
        home = "/var/lib/llama-cpp";
        createHome = true;
        # GPU access requires video/render groups for ROCm/CUDA
        extraGroups = lib.optionals (resolvedAccel == "rocm" || resolvedAccel == "cuda") [
          "video"
          "render"
        ];
      };
      users.users.${cfg.primaryUser}.extraGroups = lib.mkAfter ["llama"];

      systemd.tmpfiles.rules = [
        "d /var/lib/llama-cpp 0750 llama llama -"
        "d /var/lib/llama-cpp/models 0750 llama llama -"
        # Log directory writable by llama service
        "d /var/log/llama-cpp 0750 llama llama -"
      ];

      systemd.services.llama-cpp = {
        description = "llama.cpp OpenAI-compatible inference server";
        wantedBy = ["multi-user.target"];
        after = ["network.target" "llama-cpp-model-fetch.service"];
        requires = ["llama-cpp-model-fetch.service"];
        serviceConfig = {
          PartOf = ["ai-stack.target"];
          Type = "simple";
          User = "llama";
          Group = "llama";
          Restart = "on-failure";
          RestartSec = "5s";
          StateDirectory = "llama-cpp";
          RuntimeDirectory = "llama-cpp";
          # Phase 5.2.2: allow model weights to be locked in RAM (mlockall).
          # Prevents OS from paging out model pages during inference under pressure.
          LimitMEMLOCK = "infinity";
          # ROCm environment variables for AMD GPU acceleration.
          # Empty list when resolvedAccel != "rocm" — no overhead.
          Environment = rocmEnvList;
          # Phase 13.1.3 — inference server never needs internet access;
          # model weights are fetched by a separate dedicated download service.
          IPAddressAllow = ["127.0.0.1/8" "::1/128"];
          IPAddressDeny = ["any"];
          ExecStart = lib.concatStringsSep " " ([
              "${pkgs.llama-cpp}/bin/llama-server"
              "--host"
              (lib.escapeShellArg llama.host)
              "--port"
              (toString llama.port)
              "--model"
              (lib.escapeShellArg llama.model)
              "--ctx-size"
              (toString llama.ctxSize)
            ]
            ++ (map lib.escapeShellArg llamaArgs));
        };
      };

      # Model fetch oneshot — downloads the GGUF from HuggingFace on first boot
      # if the file is absent.  Subsequent boots skip the download instantly.
      # Check progress / errors with: journalctl -u llama-cpp-model-fetch -f
      systemd.services.llama-cpp-model-fetch = {
        description = "llama.cpp model download (first-boot provisioning)";
        wantedBy = ["multi-user.target"];
        after = ["network-online.target" "local-fs.target"];
        wants = ["network-online.target"];
        before = ["llama-cpp.service"];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          User = "root"; # needs write to /var/lib/llama-cpp
          ExecStart = pkgs.writeShellScript "llama-model-fetch" (''
              set -euo pipefail
              model="${llama.model}"
              model_dir="$(dirname "$model")"
              model_meta="${llama.model}.source-meta"
              desired_ref="${hfRepo}:${hfFile}:${hfSha256}"

              # Ensure model directory exists with correct ownership.
              install -d -m 0750 -o llama -g llama "$model_dir"

              if [ -f "$model" ]; then
                if [ -f "$model_meta" ]; then
                  current_ref="$(cat "$model_meta" 2>/dev/null || true)"
                else
                  current_ref=""
                fi

                if [ "$current_ref" = "$desired_ref" ]; then
                  echo "llama-cpp: model already present and matches requested source at $model"
                  exit 0
                fi

                # Backward compatibility: if metadata file is missing but hash matches,
                # keep the model and stamp metadata so future runs are idempotent.
                if [ -z "$current_ref" ]; then
                  existing_sha="$(${pkgs.coreutils}/bin/sha256sum "$model" | ${pkgs.gawk}/bin/awk '{print $1}')"
                  if [ "$existing_sha" = "${hfSha256}" ]; then
                    echo "$desired_ref" > "$model_meta"
                    chown llama:llama "$model_meta"
                    chmod 0640 "$model_meta"
                    echo "llama-cpp: model hash matches requested source; metadata recorded"
                    exit 0
                  fi
                fi

                echo "llama-cpp: existing model differs from requested source; downloading verified replacement before swap"
                rm -f "$model_meta"
              fi

            ''
            + (
              if hasAutoDownload
              then ''
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
                ${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/testing/verify-model-safety.sh \
                  --hf-repo "${hfRepo}" \
                  --provenance-dir "${dataDir}/models" \
                  "$tmp"

                mv "$tmp" "$model"
                chown llama:llama "$model"
                chmod 0640 "$model"
                echo "$desired_ref" > "$model_meta"
                chown llama:llama "$model_meta"
                chmod 0640 "$model_meta"
                trap - EXIT
                echo "llama-cpp: model ready ($sz bytes) at $model"
              ''
              else ''
                echo "llama-cpp: model not found at $model" >&2
                echo "llama-cpp: set mySystem.aiStack.llamaCpp.huggingFaceRepo to enable auto-download" >&2
                echo "llama-cpp: or place the GGUF manually, then: systemctl start llama-cpp" >&2
                # Exit 0 so llama-cpp.service is not blocked on a missing option.
                exit 0
              ''
            ));
        };
      };

      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan (
        [llama.port]
        ++ lib.optional swb.enable swb.port
        ++ lib.optional (ai.ui.enable && hasOpenWebui) ports.openWebui
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantHttp
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) ports.qdrantGrpc
      );

      # Phase 3.5 — Suspend/resume recovery for llama-cpp inference server.
      # ROCm GPU state can become invalid after suspend; restart llama-cpp to
      # reinitialize the GPU context cleanly. Uses systemd sleep hooks.
      systemd.services.llama-cpp-resume = {
        description = "Restart llama.cpp after system resume";
        wantedBy = ["sleep.target"];
        after = ["sleep.target"];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.systemd}/bin/systemctl restart llama-cpp.service";
        };
      };

      # Keep model files private, but grant explicit read access to the
      # primary desktop user for local desktop clients (e.g. GPT4All).
      systemd.services.ai-local-model-access = {
        description = "Grant primary user ACL access to local llama.cpp models";
        wantedBy = ["multi-user.target"];
        after = ["llama-cpp-model-fetch.service" "llama-cpp-embed-model-fetch.service"];
        wants = ["llama-cpp-model-fetch.service" "llama-cpp-embed-model-fetch.service"];
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
        enable = true;
        host = listenAddr;
        port = ports.openWebui;
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
        wantedBy = ["multi-user.target"];
        after = ["network-online.target" "local-fs.target"];
        wants = ["network-online.target"];
        before = ["llama-cpp-embed.service"];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          User = "root";
          ExecStart = pkgs.writeShellScript "llama-embed-model-fetch" (''
              set -euo pipefail
              model="${embed.model}"
              model_dir="$(dirname "$model")"
              model_meta="${embed.model}.source-meta"
              desired_ref="${embedHfRepo}:${embedHfFile}:${embedHfSha256}"
              install -d -m 0750 -o llama -g llama "$model_dir"

              if [ -f "$model" ]; then
                if [ -f "$model_meta" ]; then
                  current_ref="$(cat "$model_meta" 2>/dev/null || true)"
                else
                  current_ref=""
                fi

                if [ "$current_ref" = "$desired_ref" ]; then
                  echo "llama-cpp-embed: model already present and matches requested source at $model"
                  exit 0
                fi

                # If sha is pinned and matches, retain model and stamp metadata.
                if [ -z "$current_ref" ] && [ -n "${embedHfSha256}" ]; then
                  existing_sha="$(${pkgs.coreutils}/bin/sha256sum "$model" | ${pkgs.gawk}/bin/awk '{print $1}')"
                  if [ "$existing_sha" = "${embedHfSha256}" ]; then
                    echo "$desired_ref" > "$model_meta"
                    chown llama:llama "$model_meta"
                    chmod 0640 "$model_meta"
                    echo "llama-cpp-embed: model hash matches requested source; metadata recorded"
                    exit 0
                  fi
                fi

                # If sha is not pinned, fallback to filename/source check.
                if [ -z "$current_ref" ] && [ -z "${embedHfSha256}" ] && [ "$(basename "$model")" = "${embedHfFile}" ]; then
                  echo "$desired_ref" > "$model_meta"
                  chown llama:llama "$model_meta"
                  chmod 0640 "$model_meta"
                  echo "llama-cpp-embed: model filename matches requested source; metadata recorded"
                  exit 0
                fi

                echo "llama-cpp-embed: existing model differs from requested source; downloading verified replacement before swap"
                rm -f "$model_meta"
              fi

            ''
            + (
              if hasEmbedAutoDownload
              then ''
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

                actual_sha="$(${pkgs.coreutils}/bin/sha256sum "$tmp" | ${pkgs.gawk}/bin/awk '{print $1}')"
                echo "llama-cpp-embed: sha256 = $actual_sha"
                ${
                  # Only verify if sha256 was provided; if null, print hash for user to record.
                  if embedHfSha256Valid then ''
                expected_sha="${embedHfSha256}"
                if [ "$actual_sha" != "$expected_sha" ]; then
                  echo "llama-cpp-embed: SHA256 mismatch for downloaded model" >&2
                  echo "expected: $expected_sha" >&2
                  echo "actual:   $actual_sha" >&2
                  exit 1
                fi
                echo "llama-cpp-embed: SHA256 verified"
                  '' else ''
                echo "llama-cpp-embed: WARNING — no sha256 configured; add the hash above to facts.nix to enable integrity checking"
                  ''
                }

                # Phase 11.3 — Model Weight Integrity: Run safety verification
                # This checks for pickle magic bytes and records provenance metadata.
                echo "llama-cpp-embed: running Phase 11.3 model safety verification..."
                ${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/testing/verify-model-safety.sh \
                  --hf-repo "${embedHfRepo}" \
                  --provenance-dir "${dataDir}/models" \
                  "$tmp"

                mv "$tmp" "$model"
                chown llama:llama "$model"
                chmod 0640 "$model"
                echo "$desired_ref" > "$model_meta"
                chown llama:llama "$model_meta"
                chmod 0640 "$model_meta"
                trap - EXIT
                echo "llama-cpp-embed: model ready ($sz bytes) at $model"
              ''
              else ''
                echo "llama-cpp-embed: model not found at $model" >&2
                echo "llama-cpp-embed: set mySystem.aiStack.embeddingServer.huggingFaceRepo to enable auto-download" >&2
                exit 0
              ''
            ));
        };
      };

      # Embedding inference server — llama.cpp with --embedding flag only.
      # Chat completions are intentionally disabled on this instance.
      systemd.services.llama-cpp-embed = {
        description = "llama.cpp embedding server (:${toString embed.port})";
        wantedBy = ["multi-user.target"];
        after = ["network.target" "llama-cpp-embed-model-fetch.service"];
        requires = ["llama-cpp-embed-model-fetch.service"];
        serviceConfig = {
          PartOf = ["ai-stack.target"];
          Type = "simple";
          User = "llama";
          Group = "llama";
          Restart = "on-failure";
          RestartSec = "5s";
          StateDirectory = "llama-cpp";
          RuntimeDirectory = "llama-cpp-embed";
          LimitMEMLOCK = "infinity";
          # Phase 13.1.3 — embedding server needs no internet access.
          IPAddressAllow = ["127.0.0.1/8" "::1/128"];
          IPAddressDeny = ["any"];
          Environment = rocmEnvList;
          ExecStart = lib.concatStringsSep " " ([
              "${pkgs.llama-cpp}/bin/llama-server"
              "--host"
              (lib.escapeShellArg llama.host)
              "--port"
              (toString embed.port)
              "--model"
              (lib.escapeShellArg embed.model)
              "--embedding" # embedding-only mode; disables chat completions
              "--pooling"
              embed.pooling
              "--ctx-size"
              (toString embed.ctxSize)
              "--threads"
              "8"
              "--n-gpu-layers"
              "99"
            ]
            ++ (map lib.escapeShellArg embed.extraArgs));
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
        "kernel.numa_balancing" = lib.mkDefault 0;
        "vm.nr_overcommit_hugepages" = lib.mkDefault 0;
        # Phase 5.2.1 — overcommit: prevents OOM kills during llama.cpp mmap+COW
        # model loading. Mode 1 = always allow; ratio 100 = commit up to RAM+swap.
        "vm.overcommit_memory" = lib.mkDefault 1;
        "vm.overcommit_ratio" = lib.mkDefault 100;
      };
      # Phase 5.1.4 / 16.3.2 — unlock full AMD GPU power management features.
      # Required for LACT manual frequency control and ROCm compute workloads.
      # ppfeaturemask=0xffffffff enables all amdgpu power management feature bits.
      # Guard: only inject when an AMD GPU is actually present (resolvedAccel == "rocm").
      # On Intel/NVIDIA/CPU-only hosts the parameter is silently ignored, but we
      # avoid polluting the kernel command line unnecessarily.
      boot.kernelParams =
        lib.mkIf (resolvedAccel == "rocm")
        (lib.mkAfter ["amdgpu.ppfeaturemask=0xffffffff"]);
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
            nano = "${modelDir}/qwen2.5-0.5b-instruct-q8_0.gguf";
            micro = "${modelDir}/qwen2.5-1.5b-instruct-q8_0.gguf";
            small = "${modelDir}/phi-4-mini-instruct-q4_k_m.gguf";
            medium = "${modelDir}/qwen2.5-coder-7b-instruct-q4_k_m.gguf";
            large = "${modelDir}/qwen2.5-coder-14b-instruct-q4_k_m.gguf";
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

    # ── Phase 12.1.1 — AppArmor profile for llama-cpp inference server ────────
    # Confines the llama-server binary to only the paths it legitimately needs:
    #   - /nix/store/** read      — Nix executables, libraries, data files
    #   - model directory read    — GGUF model files
    #   - log/state directories   — write for logs and runtime state
    #   - loopback network        — serve the API; deny raw/packet sockets
    # Deny rules block writes to home/root and execution of shell interpreters.
    # Note: AppArmor must be enabled (security.apparmor.enable = true in base.nix).
    (lib.mkIf (roleEnabled && llama.enable) {
      security.apparmor.policies."ai-llama-cpp" = {
        state = "enforce";
        profile = ''
          #include <tunables/global>
          # Phase 12.1.1 — llama-cpp inference server confinement
          # Binary path uses glob to survive Nix store hash changes on rebuilds.
          profile ai-llama-cpp /nix/store/*/bin/llama-server {
            #include <abstractions/base>

            # --- Nix store access (executables, libraries, shared data) ------
            /nix/store/** r,
            /nix/store/**/*.so* mr,

            # --- Model files (read-only) ------------------------------------
            ${"/var/lib/llama-cpp/models/**"} r,

            # --- Log and state directories (write) --------------------------
            /var/log/llama-cpp/** rw,
            /var/lib/llama-cpp/** rw,
            /run/llama-cpp/ rw,
            /run/llama-cpp/** rw,

            # --- System paths needed by the runtime -------------------------
            /proc/sys/kernel/osrelease r,
            /proc/meminfo r,
            /proc/cpuinfo r,
            /sys/devices/system/cpu/** r,
            /sys/devices/system/node/** r,
            /sys/bus/pci/devices/** r,

            # --- ROCm/HSA sysfs paths for GPU enumeration --------------------
            /sys/class/kfd/** r,
            /sys/devices/virtual/kfd/** r,

            # --- Device access -----------------------------------------------
            /dev/null rw,
            /dev/urandom r,
            /dev/random r,
            # ROCm GPU access (AMD iGPU / dGPU)
            /dev/kfd rw,
            /dev/dri/card* rw,
            /dev/dri/renderD* rw,

            # --- Network: loopback TCP only ----------------------------------
            network inet stream,
            network inet6 stream,
            deny network raw,
            deny network packet,

            # --- Deny shell execution and home-directory writes -------------
            deny /bin/sh x,
            deny /bin/bash x,
            deny /usr/bin/sh x,
            deny /usr/bin/bash x,
            deny /home/** rwx,
            deny /root/** rwx,
          }
        '';
      };
    })

    # Ensure aq-* scripts are always discoverable in interactive shells.
    # This must not depend on shell-completions, otherwise aq-hints can be missing
    # from PATH when completions are disabled.
    (lib.mkIf roleEnabled {
      environment.systemPackages = [ aiHarnessCliWrappers ];
      environment.variables.AQ_HINTS_BIN = "${cfg.mcpServers.repoPath}/scripts/ai/aq-hints";
      environment.etc."profile.d/aq-path.sh" = {
        mode = "0644";
        text = ''
          export PATH="${cfg.mcpServers.repoPath}/scripts:$PATH"
        '';
      };
    })

    # Phase 19.1.4 — shell tab-completions for aq-* tools.
    # Phase 19.3.2 — Continue.dev @aq-hints HTTP context provider (config managed by HM base.nix).
    # Note: ~/.continue/config.json is written by the HM createContinueConfig activation hook
    # in nix/home/base.nix with a version sentinel; do NOT also manage it here with
    # systemd.tmpfiles — that creates a read-only symlink that conflicts with the HM hooks.
    (lib.mkIf (roleEnabled && cfg.aiStack.shellCompletions) {
      environment.etc."profile.d/aq-completions.sh" = {
        mode = "0644";
        source = "${cfg.mcpServers.repoPath}/scripts/ai/aq-completions.sh";
      };
    })

    # Phase 18.4.2 — AI stack MOTD: condensed digest on login when report is stale.
    # Enabled via mySystem.aiStack.motdReport = true (default: false).
    (lib.mkIf (roleEnabled && cfg.aiStack.motdReport) {
      environment.etc."profile.d/ai-report-motd.sh" = {
        mode = "0644";
        text = let
          repoPath = cfg.mcpServers.repoPath;
        in ''
          # AI Stack MOTD — Phase 18.4.2
          # Prints a condensed digest if the last aq-report is >24h old.
          _aq_motd() {
            local stamp_file="/tmp/aq-report-motd-stamp"
            local report_script="${repoPath}/scripts/ai/aq-report"
            [[ -x "$report_script" ]] || return 0
            if [[ -f "$stamp_file" ]]; then
              local age=$(( $(date +%s) - $(stat -c %Y "$stamp_file") ))
              [[ $age -lt 86400 ]] && return 0
            fi
            touch "$stamp_file"
            local out
            out=$("$report_script" --since=7d --format=text 2>/dev/null) || return 0
            # Print only the 5 most informative lines: routing, cache, trend, top gap, first rec
            printf '\n── AI Stack Digest ──\n'
            printf '%s\n' "$out" | grep -E '^\s+(Local:|Hits:|Runs:|  1\.|  1\. )' | head -5
            printf '  Full report: %s --since=7d\n' "${repoPath}/scripts/ai/aq-report"
            printf '────────────────────\n\n'
          }
          _aq_motd
        '';
      };
    })

    # Phase 18.5.2 — Weekly report auto-imports to AIDB every Sunday 08:00.
    (lib.mkIf roleEnabled {
      systemd.services.ai-weekly-report = {
        description = "AI Stack weekly performance report and AIDB import";
        after = ["network-online.target" "ai-stack.target"];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = "root";
          ExecStart = let
            script = "${cfg.mcpServers.repoPath}/scripts/ai/aq-report";
          in "${script} --since=7d --format=md --aidb-import";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          PrivateTmp = true;
          MemoryMax = "256M";
        };
      };

      systemd.timers.ai-weekly-report = {
        description = "Weekly AI stack performance report timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar = "Sun 08:00:00";
          Persistent = true;
          RandomizedDelaySec = "15min";
        };
      };
    })

    # Phase 18 — Bi-weekly prompt leaderboard update via aq-prompt-eval.
    (lib.mkIf roleEnabled {
      systemd.services.ai-prompt-eval = {
        description = "AI stack prompt registry evaluation and leaderboard update";
        after = ["network-online.target" "ai-stack.target"];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${cfg.mcpServers.repoPath}/scripts/ai/aq-prompt-eval";
          StandardOutput = "journal";
          StandardError  = "journal";
          NoNewPrivileges = true;
          ProtectSystem   = "strict";
          ProtectHome     = "read-only";
          PrivateTmp      = true;
          MemoryMax       = "256M";
        };
      };

      systemd.timers.ai-prompt-eval = {
        description = "Bi-weekly prompt eval leaderboard refresh timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar     = "Wed 02:00:00";
          Persistent     = true;
          RandomizedDelaySec = "30min";
        };
      };
    })

    # Phase 19 — Weekly CLAUDE.md / AGENTS.md / registry import into AIDB.
    (lib.mkIf roleEnabled {
      systemd.services.ai-import-agent-instructions = {
        description = "Import agent instruction files (CLAUDE.md, AGENTS.md, registry) into AIDB";
        after = ["network-online.target" "ai-aidb.service"];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/data/import-agent-instructions.sh";
          StandardOutput = "journal";
          StandardError  = "journal";
          NoNewPrivileges = true;
          ProtectSystem   = "strict";
          ProtectHome     = "read-only";
          PrivateTmp      = true;
          MemoryMax       = "128M";
        };
      };

      systemd.timers.ai-import-agent-instructions = {
        description = "Weekly agent instruction AIDB import timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar     = "Mon 00:03:00";
          Persistent     = true;
          RandomizedDelaySec = "10min";
        };
      };
    })

    # PRSI — Weekly auto-import of knowledge for top recurring query gaps.
    # Runs aq-gap-import which: reads query-gaps.jsonl → gemini generates docs
    # → AIDB import → rebuild-qdrant-collections (closes gap→knowledge→Qdrant loop).
    (lib.mkIf roleEnabled {
      systemd.services.ai-gap-import = {
        description = "AI gap knowledge auto-import (PRSI gap closure)";
        after = ["network-online.target" "ai-aidb.service"];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${cfg.mcpServers.repoPath}/scripts/ai/aq-gap-import";
          StandardOutput = "journal";
          StandardError  = "journal";
          NoNewPrivileges = true;
          ProtectSystem   = "strict";
          ProtectHome     = "read-only";
          PrivateTmp      = true;
          # Needs network for Gemini API and Qdrant rebuild
          PrivateNetwork  = false;
          MemoryMax       = "512M";
          Environment = [
            "GAPS_JSONL=${mutableLogDir}/query-gaps.jsonl"
            "MIN_OCCURRENCES=3"
            "MAX_GAPS=5"
          ];
        };
      };

      systemd.timers.ai-gap-import = {
        description = "Weekly PRSI gap knowledge import timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar     = "Sat 03:00:00";
          Persistent     = true;
          RandomizedDelaySec = "30min";
        };
      };

      systemd.services.ai-optimizer = {
        description = "AI stack agentic optimizer (PRSI action loop)";
        after = [ "network-online.target" "ai-aidb.service" "ai-hybrid-coordinator.service" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/ai/aq-optimizer --since=1d";
          StandardOutput = "journal";
          StandardError  = "journal";
          NoNewPrivileges = true;
          ProtectSystem   = "strict";
          ProtectHome     = "read-only";
          PrivateTmp      = true;
          PrivateNetwork  = false;
          MemoryMax       = "256M";
          ReadWritePaths  = [
            mutableOptimizerDir
            mutableLogDir
          ];
          Environment = [
            "AIDB_URL=http://127.0.0.1:${toString cfg.mcpServers.aidbPort}"
            "PYTHONPATH=${cfg.mcpServers.repoPath}/scripts"
          ] ++ lib.optional cfg.secrets.enable
              "AIDB_API_KEY_FILE=/run/secrets/${cfg.secrets.names.aidbApiKey}";
        };
      };

      systemd.timers.ai-optimizer = {
        description = "Daily AI stack agentic optimizer timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar          = "daily";
          Persistent          = true;
          RandomizedDelaySec  = "15min";
        };
      };

      systemd.services.ai-prsi-orchestrator = {
        description = "PRSI orchestrator cycle (identify → approve-low-risk → execute)";
        after = [ "network-online.target" "ai-aidb.service" "ai-hybrid-coordinator.service" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/automation/prsi-orchestrator.py cycle --since=1d --execute-limit=5";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          PrivateNetwork = false;
          MemoryMax = "256M";
          ReadWritePaths = [
            mutableOptimizerDir
            mutableLogDir
          ];
          Environment = [
            "PRSI_ACTION_QUEUE_PATH=${mutableOptimizerDir}/prsi/action-queue.json"
            "PRSI_ACTIONS_LOG_PATH=${mutableLogDir}/prsi-actions.jsonl"
            "PRSI_POLICY_FILE=${cfg.mcpServers.repoPath}/config/runtime-prsi-policy.json"
            "PRSI_STATE_PATH=${mutableOptimizerDir}/prsi/runtime-state.json"
          ];
        };
      };

      systemd.timers.ai-prsi-orchestrator = {
        description = "Hourly PRSI orchestrator timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar = "hourly";
          Persistent = true;
          RandomizedDelaySec = "10min";
        };
      };

      systemd.services.ai-cache-prewarm = lib.mkIf ai.aiHarness.runtime.cachePrewarm.enable {
        description = "AI stack semantic cache prewarm";
        after = [ "network-online.target" "ai-hybrid-coordinator.service" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/data/seed-routing-traffic.sh --count ${toString ai.aiHarness.runtime.cachePrewarm.queryCount}";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          PrivateNetwork = false;
          MemoryMax = "192M";
          ReadWritePaths = [
            mutableLogDir
          ];
          Environment = [
            "HYB_URL=http://127.0.0.1:${toString cfg.mcpServers.hybridPort}"
            "AIDB_URL=http://127.0.0.1:${toString cfg.mcpServers.aidbPort}"
          ] ++ lib.optional cfg.secrets.enable
              "HYBRID_API_KEY_FILE=/run/secrets/${cfg.secrets.names.hybridApiKey}";
        };
      };

      systemd.timers.ai-cache-prewarm = lib.mkIf ai.aiHarness.runtime.cachePrewarm.enable {
        description = "Periodic AI stack cache prewarm timer";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar = "*-*-* *:0/${toString ai.aiHarness.runtime.cachePrewarm.intervalMinutes}:00";
          Persistent = true;
          RandomizedDelaySec = "5min";
        };
      };
    })

    (lib.mkIf (roleEnabled && ai.vectorDb.enable && hasQdrant) {
      services.qdrant.enable = true;
      services.qdrant.settings.service = {
        http_port = ports.qdrantHttp;
        grpc_port = ports.qdrantGrpc;
      };
      systemd.services.qdrant = {
        partOf = ["ai-stack.target"];
        after = ["network-online.target"];
        wants = ["network-online.target"];
      };
    })
  ];
}
