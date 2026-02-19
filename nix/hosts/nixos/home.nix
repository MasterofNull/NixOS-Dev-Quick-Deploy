{ lib, pkgs, config, ... }:
# ---------------------------------------------------------------------------
# Per-host Home Manager module for the "nixos" host.
#
# Adds packages and configuration that the legacy templates/home.nix provided
# but which are missing from the minimal nix/home/base.nix base module.
# ---------------------------------------------------------------------------
let
  aiderPackage =
    if pkgs ? aider-chat then [ pkgs.aider-chat ]
    else if pkgs ? aider then [ pkgs.aider ]
    else [ ];
in
{
  # ---- Additional packages --------------------------------------------------
  home.packages = with pkgs;
    [
      # Gitea + Tea CLI for local forge workflows
      gitea
      tea

      # Nix development / linting
      statix deadnix alejandra nixpkgs-fmt nil

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

  # ---- VSCodium declarative settings ----------------------------------------
  # Create the config directory and a baseline settings.json so the health
  # check passes even before the first manual launch of VSCodium.
  home.file.".config/VSCodium/User/settings.json" = {
    text = builtins.toJSON {
      "editor.fontSize" = 14;
      "editor.tabSize" = 2;
      "editor.formatOnSave" = true;
      "editor.minimap.enabled" = false;
      "editor.wordWrap" = "on";
      "files.trimTrailingWhitespace" = true;
      "files.insertFinalNewline" = true;
      "terminal.integrated.defaultProfile.linux" = "zsh";
      "nix.enableLanguageServer" = true;
      "nix.serverPath" = "nil";
      "nix.serverSettings".nil.formatting.command = [ "alejandra" ];
    };
  };

  # ---- NPM global prefix (needed for AI CLI wrappers) ----------------------
  home.sessionVariables = {
    NPM_CONFIG_PREFIX = "$HOME/.npm-global";
    # AI tool defaults
    AIDER_DEFAULT_MODEL = "gpt-4o-mini";
    AIDER_LOG_DIR = "$HOME/.local/share/aider/logs";
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
