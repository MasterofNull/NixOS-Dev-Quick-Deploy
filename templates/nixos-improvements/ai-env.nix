# AI Environment Configuration Module
# NixOS 25.11 Xantusia
# Purpose: Optional declarative AI environment hints for hosts.
#
# Usage:
#   imports = [ ./nixos-improvements/ai-env.nix ];
#   services.aiEnv = {
#     enable = true;
#     hostProfile = "personal";
#     aiProfile = "cpu_full";
#     stackProfile = "personal";
#     aidbProjectName = "NixOS-Dev-Quick-Deploy";
#   };
#

{ config, lib, pkgs, ... }:

let
  cfg = config.services.aiEnv;
in
{
  options.services.aiEnv = {
    enable = lib.mkEnableOption "write a small /etc/ai-env.conf for local AI tools and agents";

    hostProfile = lib.mkOption {
      type = lib.types.str;
      default = "personal";
      description = "High-level host role (personal, lab, guest, ci).";
    };

    aiProfile = lib.mkOption {
      type = lib.types.str;
      default = "cpu_full";
      description = "Edge AI profile for local LLM behavior (cpu_slim, cpu_full, off).";
    };

    stackProfile = lib.mkOption {
      type = lib.types.str;
      default = "personal";
      description = "AI stack profile (personal, guest, none).";
    };

    aidbProjectName = lib.mkOption {
      type = lib.types.str;
      default = "NixOS-Dev-Quick-Deploy";
      description = "Default AIDB project name to use on this host.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.etc."ai-env.conf".text = ''
      HOST_PROFILE=${cfg.hostProfile}
      AI_PROFILE=${cfg.aiProfile}
      AI_STACK_PROFILE=${cfg.stackProfile}
      AIDB_PROJECT_NAME=${cfg.aidbProjectName}
    '';
  };
}

