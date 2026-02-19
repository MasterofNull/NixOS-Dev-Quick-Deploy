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
