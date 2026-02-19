{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.roles.aiStack.enable        = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;
    mySystem.aiStack = {
      # llama.cpp backend: native OpenAI-compatible inference server.
      # No Ollama daemon — models are loaded directly from GGUF files in
      # /var/lib/llama-cpp/models/.
      backend = lib.mkDefault "llamacpp";

      # llamaCpp service settings.
      # Place a GGUF file at the path below, then:
      #   systemctl start llama-cpp
      # The service starts automatically on subsequent boots once the file exists.
      llamaCpp = {
        enable    = lib.mkDefault true;
        host      = lib.mkDefault "127.0.0.1";  # loopback-only
        port      = lib.mkDefault 8080;
        model     = lib.mkDefault "/var/lib/llama-cpp/models/model.gguf";
        # GPU offload defaults are now derived from mySystem.aiStack.acceleration
        # (auto -> rocm/cuda/cpu based on hardware.gpuVendor) in roles/ai-stack.nix.
        # Set extraArgs only when you want to override/tune defaults, e.g.:
        #   extraArgs = [ "--n-gpu-layers" "64" "--threads" "8" ];
        extraArgs = lib.mkDefault [ ];
      };

      # Open WebUI browser interface — connects to llama-server on :8080.
      ui.enable = lib.mkDefault true;

      # Qdrant vector DB — enable when RAG or embedding workflows are needed.
      vectorDb.enable = lib.mkDefault false;

      # Expose inference server and Open WebUI on LAN (default: loopback only).
      listenOnLan = lib.mkDefault false;
    };
  };
}
