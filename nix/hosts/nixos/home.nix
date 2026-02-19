{ lib, pkgs, ... }:
# ---------------------------------------------------------------------------
# Per-host Home Manager module for the "nixos" host.
#
# Base module (nix/home/base.nix) already provides:
#   - VSCodium with extensions, settings, wrapper, Continue.dev config
#   - nil, alejandra, deadnix, statix, shellcheck, glow
#   - Python AI toolchain, zsh, starship, direnv, ssh, git
#
# This file adds only packages and config that are specific to this host.
# ---------------------------------------------------------------------------
let
  aiderPackage =
    if pkgs ? aider-chat then [ pkgs.aider-chat ]
    else if pkgs ? aider then [ pkgs.aider ]
    else [ ];
in
{
  # ---- Host-specific packages -----------------------------------------------
  home.packages = with pkgs;
    [
      # Gitea + Tea CLI for local forge workflows
      gitea
      tea

      # Additional Nix formatter (alejandra is in base; nixpkgs-fmt for compat)
      nixpkgs-fmt

      # Modern CLI replacements
      fzf bat eza dust duf

      # Container / image tooling (complements system podman)
      podman-tui

      # Git power-tools
      tig lazygit git-lfs git-crypt

      # Secrets
      age sops
    ]
    ++ aiderPackage;

  # ---- NPM global prefix (needed for AI CLI wrappers) ----------------------
  home.sessionVariables = {
    NPM_CONFIG_PREFIX = "$HOME/.npm-global";
    # AI tool defaults
    AIDER_DEFAULT_MODEL = "gpt-4o-mini";
    AIDER_LOG_DIR = "$HOME/.local/share/aider/logs";
    # Point AI tools at local llama.cpp inference server
    OPENAI_API_BASE = "http://127.0.0.1:8080/v1";
    OPENAI_API_KEY  = "dummy";  # llama-server requires a key header but ignores the value
  };

  # ---- Session PATH additions -----------------------------------------------
  home.sessionPath = [
    "$HOME/.npm-global/bin"
    "$HOME/.local/bin"
  ];

  # ---- NPM config (.npmrc) --------------------------------------------------
  home.file.".npmrc".text = "prefix=\${HOME}/.npm-global\n";

  # ---- Aider default config -------------------------------------------------
  home.file.".config/aider/config.toml".text = ''
    # Aider configuration tailored for NixOS & Gitea workflows
    [core]
    auto_commits = false
    dirty_commits = false
    auto_lint = true
  '';
}
