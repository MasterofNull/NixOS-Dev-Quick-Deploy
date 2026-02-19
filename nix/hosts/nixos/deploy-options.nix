{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.roles.aiStack.enable = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;
    mySystem.aiStack = {
      # ollama backend: native NixOS systemd services (no K3s, no containers).
      # Switch to "k3s" only once the Kubernetes stack is operational.
      backend      = lib.mkDefault "ollama";
      acceleration = lib.mkDefault "auto";  # auto → rocm for AMD GPU

      # Models pulled by the ollama-model-pull oneshot on first boot.
      # Add or swap tags here; see https://ollama.com/library for available models.
      models = lib.mkDefault [ "qwen2.5-coder:7b" ];

      ui.enable      = lib.mkDefault true;   # Open WebUI on :3000
      llamaCpp.enable = lib.mkDefault true;   # Native llama.cpp server on :8080
      vectorDb.enable = lib.mkDefault false; # Qdrant — enable when RAG is needed
      listenOnLan    = lib.mkDefault false;  # loopback only (127.0.0.1)
    };
  };
}
