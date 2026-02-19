{
  # Profile package names only. Core packages are declared in
  # nix/modules/core/base.nix, and final package selection is deduplicated.
  ai-dev = [
    "vscodium"
    "goose-cli"
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "kubectl"
    "sqlite"
    "wireshark"
    "tcpdump"
    "nmap"
    "mtr"
    "traceroute"
    "sops"
    "age"
    "buildah"
    "skopeo"
    "crun"
    "slirp4netns"
    "fuse-overlayfs"
    "btrfs-progs"
    "pciutils"
    # Local LLM desktop UI alongside the Ollama / Open WebUI stack.
    # base.nix resolves package names via builtins.hasAttr — if gpt4all is not
    # in the current nixpkgs channel the missing entry is silently skipped.
    "gpt4all"
  ];

  gaming = [
    "vscodium"
    "goose-cli"
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "kubectl"
    "sqlite"
    "buildah"
    "skopeo"
    "slirp4netns"
    "fuse-overlayfs"
    "btrfs-progs"
    "pciutils"
    "mangohud"
    "gamemode"
  ];

  minimal = [
    "vscodium"
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "kubectl"
  ];
}
