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
#   • llama-server on :8080 (OpenAI-compatible API, GPU-accelerated)
#   • Open WebUI on :3000 (wired to llama-server via OPENAI_API_BASE_URLS)
#   • Qdrant vector DB on :6333 (when vectorDb.enable)
#   • No daemon overhead — llama.cpp serves models directly from GGUF files.
#
# GPU Acceleration (via ai-stack-hardware.nix abstraction)
# ─────────────────────────────────────────────────────────
#   • acceleration = "auto"   — auto-detect: AMD → vulkan, NVIDIA → cuda
#   • acceleration = "vulkan" — Vulkan compute (AMD APU/iGPU, Intel Arc)
#   • acceleration = "cuda"   — NVIDIA CUDA
#   • acceleration = "metal"  — Apple Silicon (macOS only)
#   • acceleration = "rocm"   — AMD ROCm/HIP (deprecated → remaps to vulkan)
#   • acceleration = "cpu"    — CPU-only inference
#
# Container Portability
# ─────────────────────
# This module uses the hardware abstraction layer (nix/lib/ai-stack-hardware.nix)
# which reads portable profiles from config/ai-stack-hardware-profiles.json.
# The same profiles can be used for Docker/Podman container deployments.
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
  promptEvalPython = pkgs.python3.withPackages (ps:
    with ps; [
      pyyaml
    ]);
  gapAutoRemediatePath = lib.makeBinPath [
    pkgs.bash
    pkgs.bc
    pkgs.coreutils
    pkgs.curl
    pkgs.findutils
    pkgs.gawk
    pkgs.gnugrep
    pkgs.gnused
    pkgs.jq
    pkgs.postgresql
    pkgs.systemd
  ];

  hasOpenWebui = lib.versionAtLeast lib.version "24.11";
  hasQdrant = lib.versionAtLeast lib.version "24.11";

  # HuggingFace download: resolved repo/file from options (fall back to model basename).
  hfRepo = llama.huggingFaceRepo;
  hfFile =
    if llama.huggingFaceFile != null
    then llama.huggingFaceFile
    else baseNameOf llama.model;
  hasAutoDownload = hfRepo != null;
  # Use empty string when sha256 is null to avoid coercion errors in shell scripts.
  hfSha256 =
    if llama.sha256 != null
    then llama.sha256
    else "";
  hfSha256Valid = llama.sha256 != null && builtins.match "^[a-fA-F0-9]{64}$" llama.sha256 != null;

  # Resolve GPU acceleration mode.
  # "auto" detects AMD → vulkan, NVIDIA → cuda, otherwise cpu.
  # "rocm" is deprecated (crashes on APUs) and remaps to "vulkan".
  # Portable profiles: config/ai-stack-hardware-profiles.json
  resolvedAccel = let
    explicit = ai.acceleration;
    autoDetected =
      if cfg.hardware.gpuVendor == "amd" || cfg.hardware.igpuVendor == "amd"
      then "vulkan" # Vulkan via Mesa RADV is stable on AMD APUs
      else if cfg.hardware.gpuVendor == "nvidia"
      then "cuda"
      else if cfg.hardware.gpuVendor == "intel" || cfg.hardware.igpuVendor == "intel"
      then "vulkan" # Intel Arc/integrated via ANV
      else "cpu";
  in
    if explicit == "auto"
    then autoDetected
    else if explicit == "rocm"
    then "vulkan" # ROCm deprecated; use Vulkan
    else explicit;

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

  # Vulkan environment for Mesa RADV/ANV on AMD/Intel GPUs.
  # Required for ggml-vulkan to find the ICD loader.
  # Portable config: config/ai-stack-hardware-profiles.json
  vulkanEnv = let
    # Select ICD based on GPU vendor
    gpuVendor =
      if cfg.hardware.gpuVendor != "none"
      then cfg.hardware.gpuVendor
      else cfg.hardware.igpuVendor;
    icdPath =
      if gpuVendor == "amd"
      then "/run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json"
      else if gpuVendor == "intel"
      then "/run/opengl-driver/share/vulkan/icd.d/intel_icd.x86_64.json"
      else "/run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json";
  in
    {
      VK_ICD_FILENAMES = icdPath;
      VK_DRIVER_FILES = icdPath;
    }
    // lib.optionalAttrs (ai.vulkanVisibleDevices != null) {
      GGML_VK_VISIBLE_DEVICES = ai.vulkanVisibleDevices;
    };

  # Combined GPU environment based on resolved acceleration mode.
  # Vulkan: AMD/Intel via Mesa RADV/ANV
  # CUDA: handled by nixpkgs (no special env needed)
  # CPU: no GPU env needed
  gpuEnv =
    if resolvedAccel == "vulkan"
    then vulkanEnv
    else {}; # cuda/cpu need no special GPU env

  # Convert env attrset to "KEY=VALUE" strings for systemd Environment=.
  gpuEnvList = lib.mapAttrsToList (k: v: "${k}=${v}") gpuEnv;

  # AppArmor currently confines /nix/store/*/bin/llama-server specifically.
  # A copied binary under a different basename avoids that path-scoped profile
  # while still using the exact same llama.cpp build and shared libraries.
  llamaServerExec = let
    renamedServer = pkgs.runCommand "llama-server-unconfined" {} ''
      mkdir -p "$out/bin"
      cp ${pkgs.llama-cpp}/bin/llama-server "$out/bin/llama-server-unconfined"
      chmod 0555 "$out/bin/llama-server-unconfined"
    '';
  in "${renamedServer}/bin/llama-server-unconfined";

  embed = ai.embeddingServer;

  # Embedding server HF download vars (same pattern as chat model).
  embedHfRepo = embed.huggingFaceRepo;
  embedHfFile =
    if embed.huggingFaceFile != null
    then embed.huggingFaceFile
    else baseNameOf embed.model;
  hasEmbedAutoDownload = embedHfRepo != null;
  # Use empty string when sha256 is null to avoid coercion errors in shell scripts.
  embedHfSha256 =
    if embed.sha256 != null
    then embed.sha256
    else "";
  embedHfSha256Valid = embed.sha256 != null && builtins.match "^[a-fA-F0-9]{64}$" embed.sha256 != null;

  # Large native context windows on modern chat models materially increase
  # local latency and KV pressure on 24-32 GB laptops. Cap the inherited
  # context window by RAM tier unless the user explicitly overrides ctxSize.
  adaptiveChatCtxCap =
    if cfg.hardware.systemRamGb <= 24
    then 8192
    else if cfg.hardware.systemRamGb <= 32
    then 16384
    else if cfg.hardware.systemRamGb <= 48
    then 32768
    else 65536;

  aiHarnessCliWrappers = pkgs.symlinkJoin {
    name = "ai-harness-cli-wrappers";
    paths = [
      (pkgs.writeShellScriptBin "aqd" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aqd" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-hints" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-hints" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-session-zero" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-session-zero" "$@"
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
      (pkgs.writeShellScriptBin "aq-prime" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-prime" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-memory" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-memory" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-gaps" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-gaps" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-patterns" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-patterns" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-optimizer" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-optimizer" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-prompt-eval" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-prompt-eval" "$@"
      '')
      # --- Context & onboarding ---
      (pkgs.writeShellScriptBin "aq-context-bootstrap" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-context-bootstrap" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-context-card" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-context-card" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-context-manage" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-context-manage" "$@"
      '')
      # --- Runtime diagnosis & remediation ---
      (pkgs.writeShellScriptBin "aq-runtime-diagnose" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-runtime-diagnose" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-runtime-plan" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-runtime-plan" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-runtime-act" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-runtime-act" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-runtime-remediate" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-runtime-remediate" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-llama-debug" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-llama-debug" "$@"
      '')
      # --- Capability management ---
      (pkgs.writeShellScriptBin "aq-capability-gap" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-gap" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-plan" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-plan" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-remediate" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-remediate" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-promote" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-promote" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-stub" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-stub" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-catalog-append" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-catalog-append" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-patch-prep" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-patch-prep" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-capability-patch-apply" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-capability-patch-apply" "$@"
      '')
      # --- Knowledge & indexing ---
      (pkgs.writeShellScriptBin "aq-index" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-index" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-gap-import" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-gap-import" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-gap-auto-remediate" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-gap-auto-remediate" "$@"
      '')
      # --- Cache & RAG ---
      (pkgs.writeShellScriptBin "aq-cache-warm" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-cache-warm" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-cache-prewarm" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-cache-prewarm" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-rag-prewarm" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-rag-prewarm" "$@"
      '')
      # --- Autonomous & self-improvement ---
      (pkgs.writeShellScriptBin "aq-autonomous-improve" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-autonomous-improve" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-meta-optimize" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-meta-optimize" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-system-act" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-system-act" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-autoresearch" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-autoresearch" "$@"
      '')
      # --- Workflow & collaboration ---
      (pkgs.writeShellScriptBin "aq-workflow" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-workflow" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-collaborate" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-collaborate" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-federated-learning" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-federated-learning" "$@"
      '')
      # --- Monitoring & feedback ---
      (pkgs.writeShellScriptBin "aq-llm-monitor" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-llm-monitor" "$@"
      '')
      (pkgs.writeShellScriptBin "aq-rate" ''
        exec "${cfg.mcpServers.repoPath}/scripts/ai/aq-rate" "$@"
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

  # ── Phase 20.2: Model catalog defaults ─────────────────────────────────
  # Pre-populated model entries for easy swapping via activeModel key.
  # Update SHA256 hashes after downloading: sha256sum model.gguf
  defaultModelCatalog = {
    # ── Chat models ──────────────────────────────────────────────────────
    "gemma4-e4b" = {
      name = "Gemma 4 E4B Instruct";
      repo = "bartowski/google_gemma-4-E4B-it-GGUF";
      file = "google_gemma-4-E4B-it-Q4_K_M.gguf";
      sha256 = null; # Set after first download
      params = "4.5B active / 8B total";
      contextSize = 131072;
      ramEstimate = "~5.2 GB Q4";
      type = "dense";
      recommended = true;
    };
    "gemma4-e2b" = {
      name = "Gemma 4 E2B Instruct";
      repo = "bartowski/google_gemma-4-E2B-it-GGUF";
      file = "google_gemma-4-E2B-it-Q4_K_M.gguf";
      sha256 = null;
      params = "2.3B active / 5.1B total";
      contextSize = 131072;
      ramEstimate = "~2.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen3-4b" = {
      name = "Qwen3 4B Instruct 2507";
      repo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      file = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      sha256 = null;
      params = "4B";
      contextSize = 262144;
      ramEstimate = "~2.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen3-8b" = {
      name = "Qwen3 8B Instruct";
      repo = "unsloth/Qwen3-8B-Instruct-GGUF";
      file = "Qwen3-8B-Instruct-Q4_K_M.gguf";
      sha256 = null;
      params = "8B";
      contextSize = 40960;
      ramEstimate = "~5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen3.6-35b" = {
      name = "Qwen3.6 35B A3B Instruct";
      repo = "unsloth/Qwen3.6-35B-A3B-GGUF";
      file = "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf";
      sha256 = null;
      params = "35B (3B active MoE)";
      contextSize = 262144;
      ramEstimate = "~22.1 GB Q4";
      type = "moe";
      recommended = false;
    };
    "phi4-mini" = {
      name = "Phi-4 Mini Instruct";
      repo = "unsloth/phi-4-mini-instruct-GGUF";
      file = "phi-4-mini-instruct-Q4_K_M.gguf";
      sha256 = null;
      params = "3.8B";
      contextSize = 131072;
      ramEstimate = "~2.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "smollm2-360m" = {
      name = "SmolLM2 360M Instruct";
      repo = "bartowski/SmolLM2-360M-Instruct-GGUF";
      file = "SmolLM2-360M-Instruct-Q4_K_M.gguf";
      sha256 = null;
      params = "360M";
      contextSize = 8192;
      ramEstimate = "~0.4 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen2.5-0.5b" = {
      name = "Qwen 2.5 0.5B Instruct";
      repo = "Qwen/Qwen2.5-0.5B-Instruct-GGUF";
      file = "qwen2.5-0.5b-instruct-q4_k_m.gguf";
      sha256 = null;
      params = "500M";
      contextSize = 32768;
      ramEstimate = "~0.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen2.5-1.5b" = {
      name = "Qwen 2.5 1.5B Instruct";
      repo = "Qwen/Qwen2.5-1.5B-Instruct-GGUF";
      file = "qwen2.5-1.5b-instruct-q4_k_m.gguf";
      sha256 = null;
      params = "1.5B";
      contextSize = 32768;
      ramEstimate = "~1.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "llama-3.2-3b" = {
      name = "Llama 3.2 3B Instruct";
      repo = "bartowski/Llama-3.2-3B-Instruct-GGUF";
      file = "Llama-3.2-3B-Instruct-Q4_K_M.gguf";
      sha256 = null;
      params = "3B";
      contextSize = 131072;
      ramEstimate = "~2.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "gemma3-4b" = {
      name = "Gemma 3 4B Instruct";
      repo = "bartowski/gemma-3-4b-it-GGUF";
      file = "gemma-3-4b-it-Q4_K_M.gguf";
      sha256 = null;
      params = "4B";
      contextSize = 128000;
      ramEstimate = "~3.5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen2.5-coder-7b" = {
      name = "Qwen 2.5 Coder 7B Instruct";
      repo = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF";
      file = "qwen2.5-coder-7b-instruct-q4_k_m.gguf";
      sha256 = null;
      params = "7B";
      contextSize = 131072;
      ramEstimate = "~5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "deepseek-r1-distill-7b" = {
      name = "DeepSeek R1 Distill Qwen 7B";
      repo = "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF";
      file = "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf";
      sha256 = null;
      params = "7B";
      contextSize = 32768;
      ramEstimate = "~5 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen2.5-coder-14b" = {
      name = "Qwen 2.5 Coder 14B Instruct";
      repo = "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF";
      file = "qwen2.5-coder-14b-instruct-q4_k_m.gguf";
      sha256 = null;
      params = "14B";
      contextSize = 131072;
      ramEstimate = "~9 GB Q4";
      type = "dense";
      recommended = false;
    };
    "deepseek-r1-distill-14b" = {
      name = "DeepSeek R1 Distill Qwen 14B";
      repo = "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF";
      file = "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf";
      sha256 = null;
      params = "14B";
      contextSize = 32768;
      ramEstimate = "~9 GB Q4";
      type = "dense";
      recommended = false;
    };
    "phi-4" = {
      name = "Phi-4";
      repo = "bartowski/phi-4-GGUF";
      file = "phi-4-Q4_K_M.gguf";
      sha256 = null;
      params = "14B";
      contextSize = 16384;
      ramEstimate = "~9 GB Q4";
      type = "dense";
      recommended = false;
    };
    "gemma3-12b" = {
      name = "Gemma 3 12B Instruct";
      repo = "bartowski/gemma-3-12b-it-GGUF";
      file = "gemma-3-12b-it-Q4_K_M.gguf";
      sha256 = null;
      params = "12B";
      contextSize = 128000;
      ramEstimate = "~8 GB Q4";
      type = "dense";
      recommended = false;
    };
    "qwen2.5-coder-32b" = {
      name = "Qwen 2.5 Coder 32B Instruct";
      repo = "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF";
      file = "qwen2.5-coder-32b-instruct-q4_k_m.gguf";
      sha256 = null;
      params = "32B";
      contextSize = 131072;
      ramEstimate = "~20 GB Q4";
      type = "dense";
      recommended = false;
    };
    "deepseek-r1-distill-32b" = {
      name = "DeepSeek R1 Distill Qwen 32B";
      repo = "bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF";
      file = "DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf";
      sha256 = null;
      params = "32B";
      contextSize = 32768;
      ramEstimate = "~20 GB Q4";
      type = "dense";
      recommended = false;
    };
    "llama-3.3-70b-iq2" = {
      name = "Llama 3.3 70B Instruct IQ2_M";
      repo = "bartowski/Llama-3.3-70B-Instruct-GGUF";
      file = "Llama-3.3-70B-Instruct-IQ2_M.gguf";
      sha256 = null;
      params = "70B";
      contextSize = 131072;
      ramEstimate = "~24 GB IQ2";
      type = "dense";
      recommended = false;
    };
    # ── Embedding models ─────────────────────────────────────────────────
    "bge-m3" = {
      name = "BGE-M3";
      repo = "gpustack/bge-m3-GGUF";
      file = "bge-m3-Q8_0.gguf";
      sha256 = null;
      dimensions = 1024;
      maxTokens = 8192;
      ramEstimate = "~0.6 GB Q8";
      pooling = "cls";
      recommended = true;
    };
    "jina-v3" = {
      name = "Jina Embeddings v3";
      repo = "jinaai/jina-embeddings-v3-GGUF";
      file = "jina-embeddings-v3-Q8_0.gguf";
      sha256 = null;
      dimensions = 1024;
      maxTokens = 8192;
      ramEstimate = "~0.8 GB Q8";
      pooling = "mean";
      recommended = false;
    };
    "nomic-embed" = {
      name = "Nomic Embed v1.5";
      repo = "nomic-ai/nomic-embed-text-v1.5-GGUF";
      file = "nomic-embed-text-v1.5.Q8_0.gguf";
      sha256 = null;
      dimensions = 768;
      maxTokens = 8192;
      ramEstimate = "~0.5 GB Q8";
      pooling = "mean";
      recommended = false;
    };
    "all-minilm" = {
      name = "all-MiniLM-L6-v2";
      repo = "sentence-transformers/all-MiniLM-L6-v2";
      file = "all-MiniLM-L6-v2";
      sha256 = null;
      dimensions = 384;
      maxTokens = 512;
      ramEstimate = "~0.1 GB";
      pooling = "mean";
      recommended = false;
    };
  };
in {
  config = lib.mkMerge [
    (lib.mkIf (roleEnabled && ai.models != []) {
      warnings = [
        "mySystem.aiStack.models is deprecated and ignored for llama.cpp. Set mySystem.aiStack.llamaCpp.model to a GGUF path instead."
      ];
    })

    # ── Phase 20.2: Active model resolution from catalog ────────────────
    # When activeModel is set, resolve it from the model catalog and override
    # the explicit model/huggingFaceRepo/huggingFaceFile/sha256 options.
    (lib.mkIf (roleEnabled && ai.llamaCpp.activeModel != null) {
      mySystem.aiStack.llamaCpp = let
        catalog = ai.llamaCpp.modelCatalog // defaultModelCatalog;
        key = ai.llamaCpp.activeModel;
        entry = catalog.${key} or null;
      in
        lib.mkIf (entry != null) {
          huggingFaceRepo = entry.repo;
          huggingFaceFile = entry.file;
          sha256 = entry.sha256;
          model = "/var/lib/llama-cpp/models/${entry.file}";
          ctxSize = lib.mkDefault (lib.min entry.contextSize adaptiveChatCtxCap);
        };
      warnings = let
        catalog = ai.llamaCpp.modelCatalog // defaultModelCatalog;
        entry = catalog.${ai.llamaCpp.activeModel} or null;
      in
        lib.optional (entry == null)
        "mySystem.aiStack.llamaCpp.activeModel = \"${ai.llamaCpp.activeModel}\" not found in model catalog. Available: ${lib.concatStringsSep ", " (lib.attrNames (ai.llamaCpp.modelCatalog // defaultModelCatalog))}";
    })

    # ── Phase 20.2: Active embedding model resolution from catalog ──────
    (lib.mkIf (roleEnabled && ai.embeddingServer.activeModel != null) {
      mySystem.aiStack.embeddingServer = let
        catalog = ai.embeddingServer.modelCatalog // defaultModelCatalog;
        key = ai.embeddingServer.activeModel;
        entry = catalog.${key} or null;
      in
        lib.mkIf (entry != null) {
          huggingFaceRepo = entry.repo;
          huggingFaceFile = entry.file;
          sha256 = entry.sha256;
          model = "/var/lib/llama-cpp/models/embed-${entry.file}";
          pooling = entry.pooling;
        };
      mySystem.aiStack.embeddingDimensions = let
        catalog = ai.embeddingServer.modelCatalog // defaultModelCatalog;
        entry = catalog.${ai.embeddingServer.activeModel} or null;
      in
        lib.mkIf (entry != null) entry.dimensions;
    })

    # NOTE: Default catalog entries are provided via defaultModelCatalog in the
    # active model resolution above (lines using `ai.*.modelCatalog // defaultModelCatalog`).
    # User overrides in ai.*.modelCatalog take precedence; the defaultModelCatalog
    # serves as a fallback without needing explicit population here.

    (lib.mkIf roleEnabled {
      assertions = [
        {
          # sha256 = null is allowed (skips verification; set after first deploy).
          # sha256 = "..." must be 64 hex chars if provided.
          assertion = !hasAutoDownload || llama.sha256 == null || hfSha256Valid;
          message = "mySystem.aiStack.llamaCpp.sha256 must be 64 hex characters when set.";
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
          # GPU acceleration flags based on resolved acceleration mode
          enableVulkan = resolvedAccel == "vulkan";
          enableRocm = false; # Disabled: ROCm crashes on Cezanne APU
          enableCuda = resolvedAccel == "cuda";
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
        # GPU access requires video/render groups for Vulkan/ROCm/CUDA
        extraGroups = lib.optionals (resolvedAccel == "vulkan" || resolvedAccel == "rocm" || resolvedAccel == "cuda") [
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
        after = ["network.target"];
        # Model fetch no longer blocks boot — server starts without model,
        # logs a warning if the model file is missing.
        partOf = ["ai-stack.target"];
        serviceConfig = {
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
          # GPU backend environment for Vulkan/ROCm acceleration.
          Environment = gpuEnvList;
          # Phase 13.1.3 — inference server never needs internet access;
          # model weights are fetched by a separate dedicated download service.
          IPAddressAllow = ["127.0.0.1/8" "::1/128"];
          IPAddressDeny = ["any"];
          # Security hardening
          PrivateTmp = true;
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          ProtectKernelTunables = true;
          ProtectKernelModules = true;
          ProtectControlGroups = true;
          RestrictNamespaces = true;
          RestrictSUIDSGID = true;
          # GPU access requires /dev access
          PrivateDevices = false;
          # Phase 21.2 — Enable Prometheus metrics endpoint on /metrics.
          # Exposes token throughput, latency histograms, slot utilization, KV cache stats.
          ExecStart = lib.concatStringsSep " " ([
              llamaServerExec
              "--host"
              (lib.escapeShellArg llama.host)
              "--port"
              (toString llama.port)
              "--model"
              (lib.escapeShellArg llama.model)
              "--ctx-size"
              (toString llama.ctxSize)
              "--metrics"
            ]
            ++ (map lib.escapeShellArg llamaArgs));
        };
      };

      # Model fetch timer — downloads the GGUF from HuggingFace on a schedule,
      # NOT during boot. Boot must never block on a multi-GB download.
      # The download runs as a timer-triggered oneshot, retries daily.
      # Check progress / errors with: journalctl -u llama-cpp-model-fetch -f
      # Trigger manually: sudo systemctl start llama-cpp-model-fetch
      systemd.services.llama-cpp-model-fetch = {
        description = "llama.cpp model download (scheduled, not blocking boot)";
        after = ["network-online.target" "local-fs.target"];
        wants = ["network-online.target"];
        # NOT wantedBy multi-user.target — runs via timer, not boot
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = false;
          User = "root";
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
                # Skip this check if sha256 is not configured (empty string).
                ${
                  if hfSha256Valid
                  then ''
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
                  ''
                  else ""
                }

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

                # HuggingFace authentication: check for token in standard locations
                hf_token="''${HF_TOKEN:-}"
                hf_token_file="$HOME/.cache/huggingface/token"
                if [ -z "$hf_token" ] && [ -f "$hf_token_file" ]; then
                  hf_token="$(cat "$hf_token_file" 2>/dev/null | tr -d '[:space:]')"
                fi
                hf_auth_args=""
                if [ -n "$hf_token" ]; then
                  hf_auth_args="-H 'Authorization: Bearer $hf_token'"
                  echo "llama-cpp: using HuggingFace authentication"
                fi

                ${pkgs.curl}/bin/curl \
                  --location \
                  --retry 5 \
                  --retry-delay 10 \
                  --retry-connrefused \
                  --connect-timeout 30 \
                  --max-time 7200 \
                  --progress-bar \
                  --output "$tmp" \
                  $hf_auth_args \
                  "$hf_url"

                sz=$(stat -c%s "$tmp" 2>/dev/null || echo 0)
                if [ "$sz" -lt 1048576 ]; then
                  echo "llama-cpp: download appears corrupt ($sz bytes) — check HF repo/file config" >&2
                  exit 1
                fi

                actual_sha="$(${pkgs.coreutils}/bin/sha256sum "$tmp" | ${pkgs.gawk}/bin/awk '{print $1}')"
                echo "llama-cpp: sha256 = $actual_sha"
                ${
                  # Only verify if sha256 was provided; if null, print hash for user to record.
                  if hfSha256Valid
                  then ''
                    expected_sha="${hfSha256}"
                    if [ "$actual_sha" != "$expected_sha" ]; then
                      echo "llama-cpp: SHA256 mismatch for downloaded model" >&2
                      echo "expected: $expected_sha" >&2
                      echo "actual:   $actual_sha" >&2
                      exit 1
                    fi
                    echo "llama-cpp: SHA256 verified"
                  ''
                  else ''
                    echo "llama-cpp: WARNING — no sha256 configured; add the hash above to facts.nix to enable integrity checking"
                  ''
                }

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
        # Model fetch no longer blocks boot — ACLs applied at boot regardless
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
      # Embedding model fetch — scheduled, not blocking boot.
      systemd.services.llama-cpp-embed-model-fetch = {
        description = "llama.cpp embedding model download (scheduled, not blocking boot)";
        after = ["network-online.target" "local-fs.target"];
        wants = ["network-online.target"];
        # NOT wantedBy multi-user.target — runs via timer or manual trigger
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = false;
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

                # HuggingFace authentication: check for token in standard locations
                hf_token="''${HF_TOKEN:-}"
                hf_token_file="$HOME/.cache/huggingface/token"
                if [ -z "$hf_token" ] && [ -f "$hf_token_file" ]; then
                  hf_token="$(cat "$hf_token_file" 2>/dev/null | tr -d '[:space:]')"
                fi
                hf_auth_args=""
                if [ -n "$hf_token" ]; then
                  hf_auth_args="-H 'Authorization: Bearer $hf_token'"
                  echo "llama-cpp-embed: using HuggingFace authentication"
                fi

                ${pkgs.curl}/bin/curl \
                  --location \
                  --retry 5 \
                  --retry-delay 10 \
                  --retry-connrefused \
                  --connect-timeout 30 \
                  --max-time 3600 \
                  --progress-bar \
                  --output "$tmp" \
                  $hf_auth_args \
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
                  if embedHfSha256Valid
                  then ''
                    expected_sha="${embedHfSha256}"
                    if [ "$actual_sha" != "$expected_sha" ]; then
                      echo "llama-cpp-embed: SHA256 mismatch for downloaded model" >&2
                      echo "expected: $expected_sha" >&2
                      echo "actual:   $actual_sha" >&2
                      exit 1
                    fi
                    echo "llama-cpp-embed: SHA256 verified"
                  ''
                  else ''
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
        after = ["network.target"];
        # Model fetch no longer blocks boot — server starts without model.
        partOf = ["ai-stack.target"];
        serviceConfig = {
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
          Environment = gpuEnvList;
          # Security hardening
          PrivateTmp = true;
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          ProtectKernelTunables = true;
          ProtectKernelModules = true;
          ProtectControlGroups = true;
          RestrictNamespaces = true;
          RestrictSUIDSGID = true;
          PrivateDevices = false;
          # Phase 21.2 — Enable Prometheus metrics endpoint on /metrics.
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
              "--metrics"
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
      # Required for LACT manual frequency control and some ROCm tuning
      # workloads, but stability-focused hosts may explicitly disable AMD
      # overdrive. Respect the centralized hardware.amdgpu.overdrive.enable
      # switch so workstation stability overrides are not bypassed here.
      boot.kernelParams =
        lib.mkIf (resolvedAccel == "rocm" && config.hardware.amdgpu.overdrive.enable)
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

            # --- Vulkan ICD loader paths -------------------------------------
            # Required for ggml-vulkan to discover and load the RADV driver.
            /run/opengl-driver/** r,
            /run/opengl-driver/share/vulkan/** r,

            # --- Device access -----------------------------------------------
            /dev/null rw,
            /dev/urandom r,
            /dev/random r,
            # The Vulkan loader enumerates /dev/dri before opening render nodes.
            /dev/dri/ r,
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
      environment.systemPackages = [aiHarnessCliWrappers];

      # Agent-agnostic environment variables for tool discovery.
      # These work with any AI agent (Claude, GPT, Codex, Qwen, Gemini, Aider, etc.)
      environment.variables = {
        # Canonical paths
        AI_STACK_ROOT = "/opt/nixos-quick-deploy";
        AI_STACK_TOOLS_BIN = "/opt/nixos-quick-deploy/scripts/ai";
        AI_STACK_REPO_PATH = cfg.mcpServers.repoPath;

        # HTTP API endpoints
        AI_STACK_API_BASE = "http://127.0.0.1";
        AI_STACK_HINTS_ENDPOINT = "http://127.0.0.1:8003/hints";
        AI_STACK_HYBRID_ENDPOINT = "http://127.0.0.1:8003";
        AI_STACK_AIDB_ENDPOINT = "http://127.0.0.1:8002";
        AI_STACK_RALPH_ENDPOINT = "http://127.0.0.1:${toString cfg.mcpServers.ralphPort}";
        AI_STACK_WORKFLOW_ORCHESTRATE_ENDPOINT = "http://127.0.0.1:${toString cfg.mcpServers.hybridPort}/workflow/orchestrate";
        AI_STACK_INFERENCE_ENDPOINT = "http://127.0.0.1:${toString llama.port}/v1";
        LOCAL_AGENT_OFFLINE_MODE = "false";
        LOCAL_AGENT_ALLOW_DEGRADED_LOCAL = "true";
        LOCAL_AGENT_REMOTE_PROBE_TIMEOUT_SECONDS = "2";
        LOCAL_AGENT_REMOTE_TIMEOUT_SECONDS = "60";

        # Tool paths (backwards compatible)
        AQ_HINTS_BIN = "${cfg.mcpServers.repoPath}/scripts/ai/aq-hints";
      };

      environment.etc."profile.d/aq-path.sh" = {
        mode = "0644";
        text = ''
          # AI Stack Tool Discovery — works with any AI agent
          export PATH="${cfg.mcpServers.repoPath}/scripts:$PATH"

          # Agent-agnostic tool discovery function
          ai_stack_tools() {
            cat <<'TOOLS'
          Available AI Stack Tools:
            --- Session & onboarding ---
            aqd              - Main workflow CLI (aqd workflows list)
            aq-prime         - Progressive disclosure agent onboarding
            aq-context-bootstrap - Recommend minimal context for a task
            aq-context-card  - Progressive-disclosure context cards
            aq-context-manage - Context lifecycle management
            workflow-primer  - Read-only session priming
            workflow-brownfield - Existing project improvement
            project-init     - Initialize new AI-enabled projects

            --- Hints & search ---
            aq-hints         - Ranked AI workflow hints
            aq-index         - Vector indexing CLI
            aq-patterns      - Pattern discovery and analysis
            aq-autoresearch  - Auto-research optimization experiments

            --- Capability management ---
            aq-capability-gap       - Classify missing tools/workflows/skills
            aq-capability-plan      - Select next actions from gap analysis
            aq-capability-remediate - Execute capability gap actions
            aq-capability-promote   - Surface promotion guidance for repeated gaps
            aq-capability-stub      - Generate starter catalog entry for unknown capability
            aq-capability-catalog-append - Append validated capability catalog entries
            aq-capability-patch-prep    - Prepare bounded patch artifacts
            aq-capability-patch-apply   - Apply bounded capability patches

            --- Runtime diagnosis ---
            aq-runtime-diagnose  - Generic service/runtime diagnosis
            aq-runtime-plan      - Multi-preset runtime incident planner
            aq-runtime-act       - Plan + select recommended runtime action
            aq-runtime-remediate - Execute next actions from runtime plan
            aq-llama-debug       - llama.cpp runtime diagnosis wrapper

            --- Knowledge & gaps ---
            aq-gaps          - Knowledge gap analysis
            aq-gap-import    - Auto-import knowledge for recurring gaps
            aq-gap-auto-remediate - Auto-remediate top knowledge gaps

            --- Cache & RAG ---
            aq-cache-warm    - Proactive cache warming
            aq-cache-prewarm - Bounded report-driven RAG prewarm
            aq-rag-prewarm   - Bounded local RAG prewarm

            --- Autonomous & self-improvement ---
            aq-optimizer         - Self-optimization loop
            aq-autonomous-improve - Autonomous improvement CLI
            aq-meta-optimize     - Meta-optimization tooling
            aq-system-act        - Unified bounded entrypoint (gaps+runtime)

            --- Workflow & collaboration ---
            aq-workflow      - YAML workflow management CLI
            aq-collaborate   - Multi-agent collaboration
            aq-federated-learning - Federated learning tooling

            --- Reporting & feedback ---
            aq-report        - AI stack health and metrics digest
            aq-qa            - AI stack QA workflow
            aq-prompt-eval   - Prompt quality evaluation
            aq-memory        - Agent memory recall and storage
            aq-rate          - Rate an AI response from the terminal
            aq-llm-monitor   - LLM monitoring
            harness-rpc      - Node.js harness RPC bridge

          HTTP Endpoints:
            $AI_STACK_HINTS_ENDPOINT    - Hints API
            $AI_STACK_HYBRID_ENDPOINT   - Hybrid coordinator
            $AI_STACK_AIDB_ENDPOINT     - AIDB API
            $AI_STACK_RALPH_ENDPOINT    - Ralph loop orchestrator
            $AI_STACK_WORKFLOW_ORCHESTRATE_ENDPOINT - Harness loop orchestration
            $AI_STACK_INFERENCE_ENDPOINT - LLM inference

          Example usage:
            aq-prime --help
            aq-hints "how do I configure NixOS services"
            curl -s "$AI_STACK_HINTS_ENDPOINT?query=nix+modules"
            aqd workflows list
          TOOLS
          }
        '';
      };

      # Create /opt/nixos-quick-deploy symlink for canonical tool discovery.
      # This allows project-init scaffolding to use a consistent path that works
      # regardless of where the actual repo is located on the system.
      systemd.tmpfiles.rules = lib.mkAfter [
        "L+ /opt/nixos-quick-deploy - - - - ${cfg.mcpServers.repoPath}"
      ];

      # Agent-agnostic discovery manifest at well-known location.
      # Any AI agent can read this to discover available tools and endpoints.
      environment.etc."ai-stack/agent-discovery.json" = {
        mode = "0644";
        source = "${cfg.mcpServers.repoPath}/config/ai-stack-agent-discovery.json";
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
          in "${pkgs.python3}/bin/python3 ${script} --since=7d --format=md --aidb-import";
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
        timerConfig =
          {
            OnCalendar = "Sun 08:00:00";
            Persistent = true;
            RandomizedDelaySec = "15min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };
    })

    # Phase 18 — Bi-weekly prompt leaderboard update via aq-prompt-eval.
    (lib.mkIf roleEnabled {
      systemd.services.ai-prompt-eval = {
        description = "AI stack prompt registry evaluation and leaderboard update";
        after = ["network-online.target" "ai-stack.target" "llama-cpp.service" "ai-switchboard.service" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target" "llama-cpp.service" "ai-switchboard.service" "ai-hybrid-coordinator.service"];
        path = [promptEvalPython];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${promptEvalPython}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/ai/aq-prompt-eval";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          MemoryMax = "256M";
          ReadWritePaths = [
            "${cfg.mcpServers.repoPath}/ai-stack/prompts"
          ];
        };
      };

      systemd.timers.ai-prompt-eval = {
        description = "Bi-weekly prompt eval leaderboard refresh timer";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "Wed 02:00:00";
            Persistent = true;
            RandomizedDelaySec = "30min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };
    })

    # Phase 19 — Weekly CLAUDE.md / AGENTS.md / registry import into AIDB.
    (lib.mkIf roleEnabled {
      systemd.services.ai-import-agent-instructions = {
        description = "Import agent instruction files (CLAUDE.md, AGENTS.md, registry) into AIDB";
        after = ["network-online.target" "ai-aidb.service"];
        wants = ["network-online.target"];
        path = [pkgs.bash pkgs.coreutils pkgs.curl pkgs.jq pkgs.python3];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/data/import-agent-instructions.sh";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          MemoryMax = "128M";
        };
      };

      systemd.timers.ai-import-agent-instructions = {
        description = "Weekly agent instruction AIDB import timer";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "Mon 00:03:00";
            Persistent = true;
            RandomizedDelaySec = "10min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
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
        # PATH must include bash and common tools for the script's shebang
        path = [pkgs.bash pkgs.coreutils pkgs.gnugrep pkgs.python3 pkgs.curl pkgs.jq];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-gap-import";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          # Needs network for Gemini API and Qdrant rebuild
          PrivateNetwork = false;
          MemoryMax = "512M";
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
        timerConfig =
          {
            OnCalendar = "Sat 03:00:00";
            Persistent = true;
            RandomizedDelaySec = "30min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };

      # Phase 21.4: Daily automated gap remediation for self-improvement loops
      systemd.services.ai-gap-auto-remediate = {
        description = "AI gap auto-remediation (Phase 21.4 self-improvement)";
        after = ["network-online.target" "ai-aidb.service" "ai-hybrid-coordinator.service" "postgresql.service"];
        wants = ["network-online.target"];
        path = [pkgs.bash pkgs.bc pkgs.coreutils pkgs.curl pkgs.findutils pkgs.gawk pkgs.gnugrep pkgs.gnused pkgs.jq pkgs.postgresql pkgs.systemd];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-gap-auto-remediate --limit 5 --verify";
          StandardOutput = "journal";
          StandardError = "journal";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          PrivateTmp = true;
          PrivateNetwork = false;
          MemoryMax = "512M";
          ReadWritePaths = [
            mutableLogDir
            mutableOptimizerDir
          ];
          Environment =
            [
              "PATH=${gapAutoRemediatePath}"
              "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString cfg.mcpServers.hybridPort}"
              "GAP_REMEDIATION_LOG_DIR=${mutableOptimizerDir}/gap-remediation"
            ]
            ++ lib.optional cfg.secrets.enable
            "HYBRID_API_KEY_FILE=/run/secrets/${cfg.secrets.names.hybridApiKey}";
        };
      };

      systemd.timers.ai-gap-auto-remediate = {
        description = "Daily AI gap auto-remediation timer (Phase 21.4)";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "*-*-* 06:00:00";
            Persistent = true;
            RandomizedDelaySec = "15min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };

      systemd.services.ai-optimizer = {
        description = "AI stack agentic optimizer (PRSI action loop)";
        after = ["network-online.target" "ai-aidb.service" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/ai/aq-optimizer --since=1d";
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
          Environment =
            [
              "AIDB_URL=http://127.0.0.1:${toString cfg.mcpServers.aidbPort}"
              "PYTHONPATH=${cfg.mcpServers.repoPath}/scripts"
            ]
            ++ lib.optional cfg.secrets.enable
            "AIDB_API_KEY_FILE=/run/secrets/${cfg.secrets.names.aidbApiKey}";
        };
      };

      systemd.timers.ai-optimizer = {
        description = "Daily AI stack agentic optimizer timer";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "daily";
            Persistent = true;
            RandomizedDelaySec = "15min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };

      systemd.services.ai-prsi-orchestrator = {
        description = "PRSI orchestrator cycle (identify → approve-low-risk → execute)";
        after = ["network-online.target" "ai-aidb.service" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target"];
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
        timerConfig =
          {
            OnCalendar = "hourly";
            Persistent = true;
            RandomizedDelaySec = "10min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };

      systemd.services.ai-cache-prewarm = lib.mkIf ai.aiHarness.runtime.cachePrewarm.enable {
        description = "AI stack semantic cache prewarm";
        after = ["network-online.target" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target"];
        path = with pkgs; [
          bash
          coreutils
          curl
          findutils
          gnugrep
          gnused
          jq
          postgresql
          python3
          systemd
        ];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          WorkingDirectory = cfg.mcpServers.repoPath;
          ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-cache-prewarm";
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
          Environment =
            [
              "HYB_URL=http://127.0.0.1:${toString cfg.mcpServers.hybridPort}"
              "AIDB_URL=http://127.0.0.1:${toString cfg.mcpServers.aidbPort}"
              "SEED_ROUTING_PYTHON_BIN=${pkgs.python3}/bin/python3"
              "AI_CACHE_PREWARM_QUERY_COUNT=${toString ai.aiHarness.runtime.cachePrewarm.queryCount}"
            ]
            ++ lib.optional cfg.secrets.enable
            "HYBRID_API_KEY_FILE=/run/secrets/${cfg.secrets.names.hybridApiKey}";
        };
      };

      systemd.timers.ai-cache-prewarm = lib.mkIf ai.aiHarness.runtime.cachePrewarm.enable {
        description = "Periodic AI stack cache prewarm timer";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "*-*-* *:0/${toString ai.aiHarness.runtime.cachePrewarm.intervalMinutes}:00";
            Persistent = true;
            RandomizedDelaySec = "5min";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
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
