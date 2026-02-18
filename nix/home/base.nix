{ lib, pkgs, config, ... }:
# ---------------------------------------------------------------------------
# Home Manager base module — applies to every user on every host.
#
# Provides:
#   - Shell: zsh with history, completion, aliases, and starship prompt
#   - Core dev tools: git, ripgrep, fd, jq, btop, nix utilities
#   - XDG user directories
#   - Direnv: automatic .envrc / nix develop shell loading
#   - SSH client defaults
#
# Per-host customisation goes in nix/hosts/<host>/home.nix.
# ---------------------------------------------------------------------------
{
  home.stateVersion = "25.11";
  programs.home-manager.enable = true;

  # ---- XDG user directories -----------------------------------------------
  xdg = {
    enable = true;
    userDirs = {
      enable            = true;
      createDirectories = true;
      desktop    = "${config.home.homeDirectory}/Desktop";
      documents  = "${config.home.homeDirectory}/Documents";
      download   = "${config.home.homeDirectory}/Downloads";
      music      = "${config.home.homeDirectory}/Music";
      pictures   = "${config.home.homeDirectory}/Pictures";
      publicShare = "${config.home.homeDirectory}/Public";
      templates  = "${config.home.homeDirectory}/Templates";
      videos     = "${config.home.homeDirectory}/Videos";
    };
  };

  # ---- Core user packages -------------------------------------------------
  home.packages = with pkgs; [
    # Search / text processing
    ripgrep fd jq yq-go

    # Archives
    unzip p7zip

    # Network
    wget curl socat

    # System inspection
    htop btop lsof pciutils usbutils nvme-cli smartmontools

    # Dev
    git gh tree file xxd

    # Nix utilities
    nix-tree nix-diff nvd

    # Lightweight fallback editor (override in per-host home.nix)
    micro
  ];

  # ---- Git -----------------------------------------------------------------
  programs.git = {
    enable = true;
    settings = {
      user.name = lib.mkDefault "NixOS User";
      user.email = lib.mkDefault "user@localhost";
      init.defaultBranch = "main";
      pull.rebase = true;
      push.autoSetupRemote = true;
      core.autocrlf = "input";
      diff.colorMoved = "default";
    };
  };

  # ---- Zsh ----------------------------------------------------------------
  programs.zsh = {
    enable                    = true;
    autosuggestion.enable     = true;
    syntaxHighlighting.enable = true;
    enableCompletion          = true;
    history = {
      size       = 50000;
      save       = 50000;
      ignoreDups = true;
      share      = true;
      extended   = true;
    };
    shellAliases = {
      ll  = "ls -lah";
      la  = "ls -A";
      gs  = "git status";
      gd  = "git diff";
      gl  = "git log --oneline --graph --decorate -20";
      # NixOS rebuild shortcuts
      nrs = "sudo nixos-rebuild switch --flake .";
      nrb = "sudo nixos-rebuild boot --flake .";
      nrd = "sudo nixos-rebuild dry-build --flake .";
      hms = "home-manager switch --flake .";
    };
  };

  # ---- Starship prompt ----------------------------------------------------
  programs.starship = {
    enable = true;
    settings = {
      add_newline      = true;
      command_timeout  = 1000;
      character = {
        success_symbol = "[➜](bold green)";
        error_symbol   = "[✗](bold red)";
      };
      nix_shell.disabled = false;
    };
  };

  # ---- Direnv: auto-activate nix develop environments --------------------
  programs.direnv = {
    enable            = true;
    nix-direnv.enable = true;
  };

  # ---- SSH client ---------------------------------------------------------
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks."*" = {
      addKeysToAgent = "yes";
      serverAliveInterval = 60;
      serverAliveCountMax = 3;
      extraOptions = {
        HashKnownHosts = "yes";
      };
    };
  };

  # ---- Session variables --------------------------------------------------
  home.sessionVariables = {
    EDITOR  = "micro";
    VISUAL  = "micro";
    PAGER   = "less";
    LESS    = "-FRX";
  };
}
