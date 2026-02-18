{ lib, ... }:
{
  mySystem.roles.aiStack.enable = lib.mkDefault true;
  mySystem.aiStack = {
    enable = lib.mkDefault true;
    modelProfile = lib.mkDefault "auto";
    embeddingModel = lib.mkDefault "BAAI/bge-small-en-v1.5";
    llamaDefaultModel = lib.mkDefault "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF";
    llamaModelFile = lib.mkDefault "qwen2.5-coder-7b-instruct-q4_k_m.gguf";
  };
}
