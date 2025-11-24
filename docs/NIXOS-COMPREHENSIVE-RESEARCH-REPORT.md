# Comprehensive NixOS System Architecture Research Report

**Generated:** 2025-11-21
**Purpose:** Review and optimization of NixOS-Dev-Quick-Deploy script
**Scope:** Complex NixOS systems with AI/ML workloads, containers, and advanced deployment patterns

---

## Table of Contents

1. [Awesome-Nix Repository Summary](#1-awesome-nix-repository-summary)
2. [NixOS with Home Manager](#2-nixos-with-home-manager)
3. [Flakes Architecture](#3-flakes-architecture)
4. [Container Solutions on NixOS](#4-container-solutions-on-nixos)
5. [Flatpak Integration](#5-flatpak-integration)
6. [Locally Hosted AI Agents](#6-locally-hosted-ai-agents)
7. [MCP (Model Context Protocol) Servers](#7-mcp-model-context-protocol-servers)
8. [Stock Trading API Integration](#8-stock-trading-api-integration)
9. [Complex NixOS System Architecture](#9-complex-nixos-system-architecture)
10. [Recommendations for NixOS-Dev-Quick-Deploy](#10-recommendations-for-nixos-dev-quick-deploy)

---

## 1. Awesome-Nix Repository Summary

### Overview
The `nix-community/awesome-nix` repository is the definitive curated collection of resources and tools for the Nix ecosystem, maintained by the community. It serves as a comprehensive guide for both newcomers and experienced users.

**Repository:** https://github.com/nix-community/awesome-nix

### Key Resources

#### Learning Resources
- **Nix Pills**: Best way to learn with examples
- **nix.dev**: Opinionated guide for developers
- **Official Manuals**: Stable documentation for Nix, NixOS, and Nixpkgs
- **Interactive Tutorials**: Explainix for visual syntax explanation, Tour of Nix for interactive learning

#### Discovery Tools
- **Home Manager Option Search**: Discover configuration options
- **Noogle**: API-based function searching
- **Searchix**: Cross-platform package and option searches
- **nix-search-tv**: CLI fuzzy finder

#### Installation & Deployment
- **nix-installer**: Alternative to official installation scripts
- **nixos-anywhere**: Remote SSH installation
- **nixos-generators**: Create various image types
- **nixos-infect**: Convert existing systems to NixOS

#### Command-Line Tools
- **alejandra**: Opinionated Nix code formatter optimized for speed
- **deadnix**: Scans for unused code
- **nix-index**: Locates packages containing specific files
- **statix**: Linter for antipatterns in Nix code
- **nvd**: Compares package versions between store paths

#### Development Frameworks
- **devenv**: Creates developer shell environments quickly and reproducibly
- **flake-utils**: Utility functions for Nix flakes
- **flake.parts**: Minimal modules framework for flakes
- **lorri**: Enhanced alternative to nix-shell with direnv integration

### Programming Language Support

**Python**
- `poetry2nix`: Builds directly from Poetry lock files
- `uv2nix`: Handles workspace conversions

**Rust**
- `crane`: Incremental artifact caching
- `naersk`: Builds from Cargo.lock
- `fenix`: Provides Rust toolchains

**Node.js**
- `napalm`: Lightweight npm registry support
- `npmlock2nix`: Generates expressions from package-lock.json

**Haskell**
- `haskell.nix`: Alternative infrastructure
- `cabal2nix`: Converts Cabal files

**Other Languages**: Ruby (Bundix), PHP (composer2nix), Scala (sbt-derivation)

### NixOS Modules & Configuration

#### Key Ecosystem Components
- **Home Manager**: Manages user configuration just like NixOS
- **nix-darwin**: Extends NixOS principles to macOS
- **impermanence**: Enables selective file persistence across reboots
- **Stylix**: System-wide colorscheming and typography
- **nixvim**: NeoVim distribution built with Nix modules

### DevOps Tools
- **Makes**: Nix-based CI/CD framework
- **Colmena**: Simple, stateless NixOS deployment tool
- **nixidy**: Kubernetes GitOps with Argo CD integration
- **NixOps**: Multi-cloud deployments

### Best Practices from Awesome-Nix

1. **Reproducibility First**: All tools emphasize reproducible, declarative configuration
2. **Language Agnostic**: Comprehensive support across diverse programming ecosystems
3. **Active Maintenance**: Curated collection prioritizes well-maintained tools
4. **Modular Design**: Strong emphasis on composable, reusable components

### 2025 Highlights from Awesome-Nix

- **Virtualisation Section Refresh (Nov 2025)** – explicitly calls out `extra-container`, `microvm`, and `nixos-shell` as first-class solutions for declarative microVMs and disposable dev environments. Each ships with flake templates so the quick deploy stack can expose them as optional profiles.  
  _Source: [awesome-nix – Virtualisation](https://github.com/nix-community/awesome-nix#virtualisation)_
- **Development & DevOps Additions** – new entries such as `compose2nix`, `flake-utils-plus`, `services-flake`, and `treefmt-nix` document opinionated flake structures used in larger monorepos. Pairing these with `colmena`, `nixidy`, or `Makes` matches the multi-host ambitions of the quick deployer.  
  _Source: [awesome-nix – Development/DevOps](https://github.com/nix-community/awesome-nix#development)_
- **MCP Ecosystem Awareness** – the list now includes [MCP-NixOS](https://github.com/utensils/mcp-nixos), an MCP server that exposes NixOS, nix-darwin, and Home Manager options to AI assistants. It demonstrates how to surface local flakes/modules as searchable MCP resources—exactly what the AI-Optimizer MCP server should ingest.

---

## 2. NixOS with Home Manager

### Core Concepts

Home Manager is a Nix-powered tool for managing user home directories reproducibly. It handles programs, configuration files, environment variables, and arbitrary files.

**Official Documentation:** https://nix-community.github.io/home-manager/

### Integration Patterns with NixOS

#### Three Primary Deployment Modes

1. **Standalone Tool**: Manages home directory independently of system
   - Recommended for NixOS/Darwin users wanting user-level independence
   - Allows per-user customization without system rebuilds

2. **NixOS Module Integration**: Builds user profiles with system
   - Import with: `imports = [ <home-manager/nixos> ];`
   - Enables synchronized rebuilds via `nixos-rebuild`
   - Configuration under `home-manager.users.username`

3. **nix-darwin Module**: Similar integration for macOS

### Module Organization Best Practices (2024-2025)

#### File Structure
```
~/.config/home-manager/
├── flake.nix                 # Flake entry point (modern approach)
├── flake.lock                # Locked dependencies
├── home.nix                  # Main configuration
└── modules/                  # Optional modular organization
    ├── development.nix
    ├── desktop.nix
    └── services.nix
```

#### Configuration Patterns

**Version Pinning with Flakes:**
```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.05";
      inputs.nixpkgs.follows = "nixpkgs";  # Keep versions consistent
    };
  };
}
```

**NixOS Module Integration:**
```nix
{
  home-manager.useGlobalPkgs = true;      # Better integration
  home-manager.useUserPackages = true;
  home-manager.users.username = { pkgs, ... }: {
    home.packages = with pkgs; [ package1 package2 ];
    programs.bash.enable = true;
  };
}
```

### Advanced Use Cases

#### State Management
- `home.stateVersion`: Must match original installation version, NOT current version
- Ensures backward compatibility across releases
- Never update unless accounting for breaking changes

#### Rollback Capability
```bash
home-manager switch --rollback
```
- Reverts to previous generation
- Lightweight operation switching store references

#### Collision Detection
- Prevents overwriting existing user files
- Activation terminates before making changes if conflicts detected
- Clear messaging about conflicts

#### Non-NixOS GPU Support
- `targets.genericLinux.gpu` module manages graphics libraries
- Options: modify host system or use NixGL wrappers

### Key 2024-2025 Changes

1. **Default Configuration Location Changed**:
   - Old: `~/.config/nixpkgs/home.nix`
   - New: `~/.config/home-manager/home.nix`
   - Flake location: `~/.config/home-manager/flake.nix`

2. **systemd.user.startServices**:
   - Now defaults to `true`
   - Services automatically restart as needed on activation
   - "Legacy" alternative removed

3. **Current Release**: Targets NixOS 25.05 (stable in May 2025)

### Security Considerations

**Secret Management Integration:**
- Works with `sops-nix` for encrypted secrets using PGP/SSH keys
- Secrets decrypted on activation
- Per-user secret management alongside system secrets

**User-Level Package Management:**
- Packages installed to `~/.nix-profile` instead of system-wide
- Provides isolation and per-user customization
- Shell environment managed via `hm-session-vars.sh`

### Best Practices

1. **Start Simple**: Begin with small configuration, gradually expand
2. **Use Flakes**: Modern approach for better reproducibility
3. **Modularize**: Split large configurations into logical modules
4. **Secret Handling**: Never commit unencrypted secrets to flake files
5. **Opt-in Persistence**: Use with `impermanence` module for selective file persistence
6. **Documentation**: Consult Appendix A (Configuration Options) for discovering options
7. **Templates**: Use `nix-starter-configs` for boilerplate

---

## 3. Flakes Architecture

### Overview

Nix flakes is an experimental feature (introduced in Nix 2.4, November 2021) that provides a standard way to write Nix expressions with version-pinned dependencies in a lock file, dramatically improving reproducibility.

**Official Wiki:** https://wiki.nixos.org/wiki/Flakes

### Core Structure

#### Top-Level Attributes

A `flake.nix` file contains four essential components:

1. **description**: String summarizing the flake's purpose
2. **inputs**: Dependency specifications with version pinning
3. **outputs**: Function receiving resolved inputs and returning attribute set
4. **nixConfig**: Configuration values reflecting `nix.conf` settings

#### Output Schema

Standardized output types:

```nix
{
  packages.<system>.<name>          # nix build .#<name>
  apps.<system>.<name>              # nix run .#<name>
  devShells.<system>.<name>         # nix develop
  nixosConfigurations.<hostname>    # NixOS system configs
  overlays.<name>                   # Package overlays
  templates.<name>                  # Project templates
}
```

### Best Practices (2024-2025)

#### Multi-System Configuration

**Directory Structure:**
```
repo/
├── flake.nix
├── flake.lock
├── host/
│   ├── desktop/
│   ├── laptop/
│   └── server/
├── home/
│   └── user/
└── modules/
    └── custom/
```

**Multi-Architecture Support:**
```nix
let
  systems = [ "x86_64-linux" "aarch64-linux" ];
  forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
in {
  packages = forAllSystems (system: {
    # Per-architecture packages
  });
}
```

**Helper Libraries:**
- `flake-utils`: Avoid boilerplate for multi-system support
- `flake-parts`: Minimal modules framework

#### Modular Organization Pattern

```nix
{
  description = "Multi-machine NixOS configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    home-manager = {
      url = "github:nix-community/home-manager/release-24.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, ... }: {
    nixosConfigurations = {
      desktop = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          ./host/desktop/configuration.nix
          home-manager.nixosModules.home-manager
        ];
      };

      laptop = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          ./host/laptop/configuration.nix
          home-manager.nixosModules.home-manager
        ];
      };
    };
  };
}
```

### Security Model

#### Critical Warnings

1. **No Unencrypted Secrets**: Never put secrets in flake files
   - Contents copied to world-readable `/nix/store`
   - Use `sops-nix` or `agenix` for secret management

2. **Git Integration**: Only files added via `git add` are included
   - Ensures reproducibility
   - Requires explicit file tracking
   - Uncommitted files are invisible to builds

#### Secret Management

**sops-nix** (recommended):
```nix
{
  inputs.sops-nix.url = "github:Mic92/sops-nix";

  outputs = { sops-nix, ... }: {
    nixosConfigurations.host = {
      modules = [
        sops-nix.nixosModules.sops
        {
          sops.defaultSopsFile = ./secrets.yaml;
          sops.secrets.database-password = {};
        }
      ];
    };
  };
}
```

**agenix** (alternative):
```nix
{
  inputs.agenix.url = "github:ryantm/agenix";

  outputs = { agenix, ... }: {
    nixosConfigurations.host = {
      modules = [
        agenix.nixosModules.default
        {
          age.secrets.api-key.file = ./secrets/api-key.age;
        }
      ];
    };
  };
}
```

### Development Workflow Features

#### Performance Optimizations

1. **Evaluation Caching**: Nix caches evaluations
   - Repeated `nix develop` invocations much faster than `nix-shell`

2. **nix-direnv Integration**: Automatic shell switching
   - Enters dev environment when `cd` into directory
   - Persistent evaluation cache

3. **Rapid Iteration**: `--redirect` flag
   - Enables mutable dependency development
   - No rebuilding required during development

#### Multi-Channel Imports

Import multiple nixpkgs versions through overlays:

```nix
{
  inputs = {
    nixpkgs-stable.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { nixpkgs-stable, nixpkgs-unstable, ... }: {
    nixosConfigurations.host = nixpkgs-stable.lib.nixosSystem {
      modules = [{
        nixpkgs.overlays = [
          (final: prev: {
            unstable = import nixpkgs-unstable {
              system = final.system;
            };
          })
        ];
      }];
    };
  };
}
```

### Enabling Flakes

**Temporarily:**
```bash
nix --experimental-features 'nix-command flakes' build
```

**Permanently (NixOS):**
```nix
{
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
}
```

**Environment Variable:**
```bash
export NIX_CONFIG="experimental-features = nix-command flakes"
```

### Multi-Machine Benefits

1. **Reproducibility**: Rebuild any machine from scratch quickly
2. **Consistency**: Identical user environments across machines
3. **Version Control**: Track every system change in git
4. **Role-Based Architecture**: Separate concerns between system/user levels

### Integration with Home Manager

**As NixOS Module:**
```nix
{
  home-manager.useGlobalPkgs = true;
  home-manager.users.user = { ... };
}
```

**Standalone:**
```nix
{
  outputs = { home-manager, ... }: {
    homeConfigurations.user = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [ ./home.nix ];
    };
  };
}
```

### Best Practices Summary

1. **Use Flakes for Modern Deployments**: Better reproducibility than channels
2. **Pin All Inputs**: Leverage `flake.lock` for version control
3. **Modularize Configurations**: Separate host/user/role configurations
4. **Follow `.follows` Pattern**: Keep nixpkgs versions consistent
5. **Use Helper Libraries**: `flake-utils` or `flake-parts` for multi-system
6. **Secure Secret Management**: Never commit secrets, use `sops-nix`/`agenix`
7. **Git Discipline**: Only committed files are included in builds

---

## 4. Container Solutions on NixOS

### Overview

NixOS provides multiple approaches to containerization, from native OCI containers to declarative Podman/Docker management, with emphasis on reproducibility and declarative configuration.

**Official Wiki:** https://wiki.nixos.org/wiki/Podman

### Podman Integration

#### Rootless Configuration

**Basic NixOS Setup:**
```nix
{
  virtualisation.containers.enable = true;
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;              # Docker CLI compatibility
    defaultNetwork.settings.dns_enabled = true;  # Inter-container networking
  };
}
```

#### Storage Drivers

**Key Considerations (2024-2025):**

1. **VFS Driver**: Universal fallback, slower but compatible
2. **Btrfs Driver**: Fast snapshots, requires Btrfs filesystem
3. **ZFS Driver**: Native ZFS support, requires `acltype=posixacl`
4. **Overlay Driver**: Legacy, deprecated for rootless

**ZFS Configuration:**
```nix
{
  virtualisation.containers.storage.settings = {
    storage.driver = "zfs";
  };
}
```

**Important**: Rootless overlay needs POSIX ACL:
```bash
zfs set acltype=posixacl tank/var/lib/containers
```

#### Systemd Integration (Declarative Services)

**System-Level Containers:**
```nix
{
  virtualisation.oci-containers.backend = "podman";
  virtualisation.oci-containers.containers.myapp = {
    image = "nginx:latest";
    autoStart = true;
    ports = [ "127.0.0.1:8080:80" ];
    volumes = [ "/data:/usr/share/nginx/html:ro" ];
    environment = {
      TZ = "UTC";
    };
  };
}
```

#### Rootless Podman with Home Manager (2024 Best Practice)

**Modern Approach using Home Manager:**
```nix
{
  services.podman = {
    enable = true;
    containers = {
      myapp = {
        image = "docker.io/library/nginx:latest";
        autoStart = true;
        ports = [ "8080:80" ];
      };
    };
  };
}
```

**User Storage Configuration:**
```nix
{
  xdg.configFile."containers/storage.conf".text = ''
    [storage]
    driver = "vfs"

    [storage.options]

    [storage.options.vfs]
    ignore_chown_errors = "true"
  '';
}
```

#### Podman Compose & CLI Tooling (NixOS Wiki, Nov 2025)

The current [Podman wiki page](https://nixos.wiki/wiki/Podman) emphasises enabling the shared `virtualisation.containers.enable` block so that `/etc/containers` is always provisioned and `podman-compose` networking works out of the box. The recommended snippet mirrors what we ship, but adds CLI helpers for day‑to‑day observability:

- `dive` to inspect OCI layer diffs during optimization loops.
- `podman-tui` for a curses dashboard when diagnosing GPU passthrough issues without a GUI.
- `docker-compose` **or** `podman-compose` so developer laptops can run the same compose files that production pods eventually translate to `quadlet` units.

Keeping these tools in the system profile (not user-level) ensures `ai-servicectl` and the MCP server can call them even when Home Manager has not been activated for the operator yet.

#### Quadlet-Nix Module (Modern Declarative Approach)

**GitHub:** https://github.com/SEIAROTg/quadlet-nix

Manages Podman containers via systemd quadlet files:
- Supports rootful and rootless (via Home Manager)
- Unified interface for both modes
- Declarative pod/container/network management

### Docker on NixOS

**Basic Configuration:**
```nix
{
  virtualisation.docker = {
    enable = true;
    enableOnBoot = true;
    autoPrune = {
      enable = true;
      dates = "weekly";
    };
  };
}
```

**Rootless Docker:**
```nix
{
  virtualisation.docker.rootless = {
    enable = true;
    setSocketVariable = true;
  };
}
```

#### Docker Group Management (NixOS Wiki, Nov 2025)

The [Docker wiki entry](https://nixos.wiki/wiki/Docker) still calls out two mandatory steps the deployer should codify:

1. `virtualisation.docker.enable = true;` inside `configuration.nix` (already provided).
2. Assigning users to the `docker` group so the Unix socket is writable after reboot:
   ```nix
   users.users.${config.services.aidb.user}.extraGroups = [ "docker" ];
   ```

This lets locally hosted AI agents (running as that user) build or inspect containers without root escalation while keeping the socket locked down for other accounts.

### Container Orchestration Options

#### Native NixOS Containers

**Declarative Container Definition:**
```nix
{
  containers.webserver = {
    autoStart = true;
    privateNetwork = true;
    hostAddress = "10.250.0.1";
    localAddress = "10.250.0.2";

    config = { pkgs, ... }: {
      services.nginx.enable = true;
      networking.firewall.allowedTCPPorts = [ 80 ];
    };
  };
}
```

#### Kubernetes Integration

**MicroK8s on NixOS:**
```nix
{
  services.kubernetes = {
    roles = [ "master" "node" ];
    masterAddress = "apiserver.local";
  };
}
```

**K3s (Lightweight Kubernetes):**
```nix
{
  services.k3s = {
    enable = true;
    role = "server";
  };
}
```

#### Docker Compose with Podman

**Using podman-compose:**
```nix
{
  environment.systemPackages = with pkgs; [
    podman-compose
  ];
}
```

**Using compose2nix:**
```bash
compose2nix docker-compose.yaml > compose-generated.nix
```

Converts `docker-compose.yaml` to `virtualisation.oci-containers` config.

### Volume Management and Persistence

#### Named Volumes
```nix
{
  systemd.tmpfiles.rules = [
    "d /var/lib/containers/volumes 0755 root root -"
  ];

  virtualisation.oci-containers.containers.db = {
    volumes = [
      "postgres-data:/var/lib/postgresql/data"
    ];
  };
}
```

#### Bind Mounts
```nix
{
  virtualisation.oci-containers.containers.app = {
    volumes = [
      "/host/path:/container/path:rw"
      "/read-only:/data:ro"
    ];
  };
}
```

#### State Management with Impermanence

```nix
{
  environment.persistence."/persist" = {
    directories = [
      "/var/lib/containers"
    ];
  };
}
```

### OCI Image Building with Nix

#### dockerTools.buildLayeredImage (Recommended)

**Modern Approach:**
```nix
{ pkgs ? import <nixpkgs> {} }:

pkgs.dockerTools.buildLayeredImage {
  name = "myapp";
  tag = "latest";

  contents = pkgs.buildEnv {
    name = "image-root";
    paths = [ pkgs.myPackage pkgs.cacert ];
    pathsToLink = [ "/bin" ];
  };

  config = {
    Cmd = [ "${pkgs.myPackage}/bin/myapp" ];
    ExposedPorts = {
      "8080/tcp" = {};
    };
    Env = [
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
  };

  maxLayers = 120;  # Optimize layer sharing
}
```

#### dockerTools.streamLayeredImage

**For Streaming (no intermediate storage):**
```nix
pkgs.dockerTools.streamLayeredImage {
  name = "myapp";
  tag = "latest";
  contents = [ pkgs.myPackage ];
  config.Cmd = [ "${pkgs.myPackage}/bin/myapp" ];
}
```

**Load directly:**
```bash
nix build .#myapp
./result | docker load
# or
./result | podman load
```

#### ociTools

**OCI Specification v1.0.0:**
```nix
pkgs.ociTools.buildContainer {
  args = [ "${pkgs.hello}/bin/hello" ];
}
```

### Performance and Optimization Considerations

#### Image Layer Optimization

1. **Use `buildEnv`**: Avoid file duplication
2. **Set `maxLayers`**: Typically 120 for optimal caching
3. **Minimal Base Images**: Only include necessary dependencies
4. **Multi-stage Builds**: Use Nix derivations as build stages

#### Podman Storage Sizing

**For AI/ML Workloads:**
- Minimum: 150 GiB
- Recommended: 200-300 GiB
- Consider Btrfs for deduplication and snapshots

**Btrfs Setup:**
```bash
sudo truncate -s 300G /var/lib/containers.btrfs
sudo mkfs.btrfs -L podman /var/lib/containers.btrfs
echo "/var/lib/containers.btrfs /var/lib/containers btrfs loop,compress=zstd,ssd,noatime 0 0" | sudo tee -a /etc/fstab
sudo mount -a
```

#### Network Performance

**Enable DNS for compose:**
```nix
{
  virtualisation.podman.defaultNetwork.settings.dns_enabled = true;
}
```

### Security Considerations

#### Rootless Containers

**Benefits:**
- No root daemon required
- User namespace isolation
- Reduced attack surface

**Requirements:**
- `newuidmap` from shadow package
- Proper subuid/subgid mappings

#### SELinux/AppArmor Integration

```nix
{
  virtualisation.podman.enableAppArmor = true;
}
```

#### Secret Management

```nix
{
  virtualisation.oci-containers.containers.app = {
    environmentFiles = [ "/run/secrets/app.env" ];
  };

  sops.secrets."app.env" = {
    sopsFile = ./secrets.yaml;
    path = "/run/secrets/app.env";
  };
}
```

### Best Practices (2024-2025)

1. **Rootless First**: Use rootless Podman via Home Manager for user workloads
2. **Declarative Configuration**: Define containers in NixOS config, not imperative `podman run`
3. **Storage Driver Selection**: Match driver to filesystem (btrfs→btrfs, zfs→zfs, fallback→vfs)
4. **Use streamLayeredImage**: Better caching and no intermediate storage
5. **Volume Persistence**: Plan for data persistence with `impermanence` or explicit mounts
6. **Quadlet for Systemd**: Modern approach for declarative Podman services
7. **Network Planning**: Enable DNS for container-to-container communication
8. **Security**: Leverage rootless, AppArmor, and secret management
9. **Monitoring**: Integrate with systemd journals for centralized logging

### Development Tools

**Recommended Packages:**
```nix
{
  environment.systemPackages = with pkgs; [
    podman-compose    # Docker Compose compatibility
    podman-tui        # Terminal UI for Podman
    dive              # Image layer analysis
    buildah           # Build OCI images
    skopeo            # Work with remote images
  ];
}
```

### Common Pitfalls

1. **Overlay on ZFS**: Requires `acltype=posixacl`, deprecated for rootless
2. **Missing Dependencies**: Add `iana-etc` for network resolution, `cacert` for TLS
3. **KVM Requirements**: Use `buildLayeredImage`/`streamLayeredImage` to avoid KVM dependency
4. **Storage Conflicts**: System and rootless Podman use different storage locations

---

## 5. Flatpak Integration

### Overview

Flatpak provides sandboxed desktop applications with universal Linux compatibility. NixOS supports both imperative and declarative Flatpak management.

**Official Wiki:** https://wiki.nixos.org/wiki/Flatpak

### Declarative Flatpak Management

#### Two Main Solutions (2024-2025)

1. **nix-flatpak** (Recommended)
   - **GitHub:** https://github.com/gmodena/nix-flatpak
   - Inspired by nix-darwin's homebrew module
   - Convergent mode: only manages declared packages
   - Systemd oneshot service installation
   - Both NixOS and home-manager modules

2. **declarative-flatpak**
   - **GitHub:** https://github.com/in-a-dil-emma/declarative-flatpak
   - Congruent approach: atomic changes
   - Temporary installation then overwrite

### NixOS System-Level Integration

**Basic Flatpak Enable:**
```nix
{
  services.flatpak.enable = true;
}
```

**With nix-flatpak (NixOS module):**
```nix
{
  inputs.nix-flatpak.url = "github:gmodena/nix-flatpak";

  outputs = { nix-flatpak, ... }: {
    nixosConfigurations.host = {
      modules = [
        nix-flatpak.nixosModules.nix-flatpak
        {
          services.flatpak.packages = [
            "org.mozilla.firefox"
            "org.videolan.VLC"
          ];

          services.flatpak.remotes = [{
            name = "flathub";
            location = "https://dl.flathub.org/repo/flathub.flatpakrepo";
          }];
        }
      ];
    };
  };
}
```

### Home-Manager Integration

**Preferred Method (2024-2025):**
```nix
{
  inputs.nix-flatpak.url = "github:gmodena/nix-flatpak";

  outputs = { home-manager, nix-flatpak, ... }: {
    homeConfigurations.user = home-manager.lib.homeManagerConfiguration {
      modules = [
        nix-flatpak.homeManagerModules.nix-flatpak
        {
          services.flatpak = {
            enable = true;
            packages = [
              "org.mozilla.firefox"
              "md.obsidian.Obsidian"
              "com.visualstudio.code"
            ];
          };
        }
      ];
    };
  };
}
```

### Best Practices for Mixed Package Management

#### Separation of Concerns

**System Packages (NixOS/nixpkgs):**
- Core system utilities
- Development tools
- Command-line applications
- Services and daemons

**User Packages (Home Manager):**
- User-specific applications
- Development environments
- Shell configurations
- Dotfiles management

**Flatpak Applications:**
- Desktop GUI applications
- Proprietary software not in nixpkgs
- Applications requiring sandboxing
- Software needing frequent updates outside NixOS release cycle

#### Profile-Based Provisioning

**Example Multi-Profile Setup:**
```nix
{
  services.flatpak.packages =
    # Core profile
    [
      "org.mozilla.firefox"
      "md.obsidian.Obsidian"
    ]
    # AI Workstation profile additions
    ++ lib.optionals (config.profiles.aiWorkstation) [
      "com.getpostman.Postman"
      "io.dbeaver.DBeaverCommunity"
      "com.visualstudio.code"
    ]
    # Minimal recovery profile
    ++ lib.optionals (config.profiles.minimal) [
      "com.github.tchx84.Flatseal"
      "io.podman_desktop.PodmanDesktop"
    ];
}
```

### State Management

#### nix-flatpak Convergent Mode

**Key Behavior:**
- Only manages packages declared in `services.flatpak.packages`
- Command-line installed packages unaffected
- Flatpak app stores work independently
- No automatic removal of undeclared packages

**Advantages:**
1. No surprises: explicit control
2. Coexists with manual Flatpak usage
3. Gradual migration from imperative to declarative

#### Caching and Incremental Updates

**State Preservation:**
```bash
# State cached in:
~/.local/share/nixos-quick-deploy/preferences/flatpak-profile-state.env

# Profile selection:
~/.local/share/nixos-quick-deploy/preferences/flatpak-profile.env
```

### Desktop Session Path Fixes (NixOS Wiki, Nov 2025)

The [Flatpak wiki entry](https://nixos.wiki/wiki/Flatpak) now explicitly documents that sway/greetd sessions do **not** automatically append Flatpak export directories to `XDG_DATA_DIRS`. When the quick deployer provisions the Minimal profile (which defaults to sway), also drop a `.profile` snippet so CLI and AI tooling can locate `.desktop` files:

```bash
export XDG_DATA_DIRS=$XDG_DATA_DIRS:/usr/share:/var/lib/flatpak/exports/share:$HOME/.local/share/flatpak/exports/share
```

Without this, GUI applications installed for only one user never appear in launchers, which is exactly the failure operators have been seeing when toggling between flatpak profiles via `./scripts/flatpak-profile.sh`.

**Switching Profiles:**
- Only installs missing packages from new profile
- Preserves already-installed apps
- Dramatically reduces repeat deployment time

### Runtime Management

#### Multiple Platform Runtimes

**Normal Behavior:**
- Different apps require different runtime versions
- Multiple Freedesktop Platform versions (24.08, 25.08) expected
- Each provides different API compatibility levels

**Cleanup Unused Runtimes:**
```bash
# Dry run
flatpak uninstall --unused

# Actually remove
flatpak uninstall --unused -y
```

#### Codecs and Extensions

**Common Runtime Extensions:**
```
org.freedesktop.Platform.GL.default
org.freedesktop.Platform.ffmpeg-full
org.freedesktop.Platform.openh264
```

**Automatically Installed:** Based on application requirements

### Security and Permissions

#### Flatseal Integration

**Declarative Flatseal Install:**
```nix
{
  services.flatpak.packages = [
    "com.github.tchx84.Flatseal"
  ];
}
```

**Purpose:** GUI for managing Flatpak permissions

#### Override Permissions

**System-Level:**
```nix
{
  services.flatpak.overrides = {
    global = {
      Context.filesystems = [ "xdg-data/themes:ro" ];
    };

    "org.mozilla.firefox" = {
      Context.sockets = [ "wayland" "!x11" ];
    };
  };
}
```

**User-Level:**
```bash
flatpak override --user --filesystem=host org.mozilla.firefox
```

### Integration Patterns

#### XDG Desktop Entries

**Automatic Integration:**
- Desktop files in `~/.local/share/flatpak/exports/share/applications/`
- Icons in `~/.local/share/flatpak/exports/share/icons/`
- Mime types registered automatically

**Custom Launchers:**
```nix
{
  xdg.desktopEntries.cursor = {
    name = "Cursor";
    exec = "flatpak run ai.cursor.Cursor %U";
    icon = "ai.cursor.Cursor";
    categories = [ "Development" "IDE" ];
  };
}
```

#### Theme Integration

**NixOS System Themes:**
```nix
{
  services.flatpak.overrides.global = {
    Context.filesystems = [
      "xdg-data/themes:ro"
      "xdg-data/icons:ro"
    ];
  };
}
```

#### Font Integration

**Make System Fonts Available:**
```nix
{
  fonts.fontconfig.enable = true;
  services.flatpak.overrides.global.Context.filesystems = [
    "/run/current-system/sw/share/X11/fonts:ro"
    "~/.local/share/fonts:ro"
  ];
}
```

### Performance Considerations

#### First-Run Performance

**Initial Setup Time:**
- Runtime downloads: 500MB - 2GB per runtime
- Base app downloads: 100MB - 1GB per app
- Can be parallelized with `--noninteractive`

**Optimization:**
```bash
# Parallel installation
flatpak install -y --noninteractive flathub \
  org.mozilla.firefox \
  md.obsidian.Obsidian \
  com.visualstudio.code
```

#### Update Strategy

**System Updates vs Flatpak Updates:**
- NixOS updates: `nixos-rebuild switch --upgrade`
- Flatpak updates: `flatpak update` (independent)

**Automatic Updates:**
```nix
{
  services.flatpak.update = {
    enable = true;
    onCalendar = "weekly";
  };
}
```

### Common Issues and Solutions

#### Repository Creation Errors

**Issue:** Empty repo directory causes remote-add failures

**Solution (Automatic in modern deployments):**
```bash
mkdir -p ~/.local/share/flatpak ~/.config/flatpak
rm -rf ~/.local/share/flatpak/repo  # Remove empty stub
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

#### Portal Integration

**Required for File Picker, etc:**
```nix
{
  xdg.portal = {
    enable = true;
    extraPortals = with pkgs; [
      xdg-desktop-portal-gtk
      xdg-desktop-portal-wlr  # For Wayland compositors
    ];
  };
}
```

### Best Practices Summary

1. **Declarative First**: Use nix-flatpak for reproducibility
2. **Profile-Based**: Organize apps by use case (core/workstation/minimal)
3. **Selective Application**: Use Flatpak for GUI apps, nixpkgs for CLI
4. **State Preservation**: Leverage caching to avoid re-downloads
5. **Security**: Review permissions with Flatseal
6. **Portal Integration**: Enable xdg-desktop-portal for proper integration
7. **Theme/Font Access**: Grant read-only filesystem access for consistency
8. **Independent Updates**: Keep Flatpak update schedule separate from NixOS
9. **Convergent Mode**: Allow coexistence with manual Flatpak usage

---

## 6. Locally Hosted AI Agents

### Overview

NixOS provides comprehensive support for locally hosted AI infrastructure, including LLM runtimes, vector databases, and web interfaces, all manageable through declarative configuration.

### Ollama Deployment

#### Official NixOS Module

**Basic Configuration:**
```nix
{
  services.ollama = {
    enable = true;
    acceleration = "rocm";  # or "cuda", null for CPU-only
    host = "127.0.0.1";
    port = 11434;
  };
}
```

**With Pre-loaded Models:**
```nix
{
  services.ollama = {
    enable = true;
    loadModels = [ "llama3.2:3b" "deepseek-r1:1.5b" ];
  };
}
```

#### GPU Acceleration

**AMD ROCm:**
```nix
{
  services.ollama.acceleration = "rocm";
  services.ollama.rocmOverrideGfx = "11.0.0";  # For specific GPUs
  services.ollama.environmentVariables = {
    HSA_OVERRIDE_GFX_VERSION = "11.0.0";
  };
}
```

**NVIDIA CUDA:**
```nix
{
  services.ollama.acceleration = "cuda";
  hardware.nvidia-container-toolkit.enable = true;
}
```

#### Environment Variables

**Common Configuration:**
```nix
{
  services.ollama.environmentVariables = {
    OLLAMA_ORIGINS = "*";  # Allow all origins (development only)
    OLLAMA_NUM_PARALLEL = "4";
    OLLAMA_MAX_LOADED_MODELS = "2";
  };
}
```

### Open WebUI Setup

#### NixOS Module (Available in nixpkgs)

**Configuration:**
```nix
{
  services.open-webui = {
    enable = true;
    host = "127.0.0.1";
    port = 8080;
    environment = {
      OLLAMA_API_BASE_URL = "http://127.0.0.1:11434";
      WEBUI_AUTH = "False";  # Disable auth for local use
    };
  };
}
```

#### Podman Deployment (Alternative)

**Using oci-containers:**
```nix
{
  virtualisation.oci-containers.containers.open-webui = {
    image = "ghcr.io/open-webui/open-webui:main";
    autoStart = true;
    ports = [ "127.0.0.1:8080:8080" ];
    volumes = [ "open-webui:/app/backend/data" ];
    environment = {
      OLLAMA_BASE_URL = "http://host.containers.internal:11434";
    };
    extraOptions = [
      "--add-host=host.containers.internal:host-gateway"
    ];
  };
}
```

### Vector Databases

#### Qdrant

**NixOS Service:**
```nix
{
  services.qdrant = {
    enable = true;
    settings = {
      storage = {
        storage_path = "/var/lib/qdrant/storage";
        snapshots_path = "/var/lib/qdrant/snapshots";
      };
      service = {
        http_port = 6333;
        grpc_port = 6334;
      };
      cluster = {
        enabled = false;  # Single-node
      };
    };
  };
}
```

**Client Access:**
```bash
# HTTP API
curl http://localhost:6333/collections

# gRPC: localhost:6334
```

**2025 Features:**
- Asymmetric quantization: 24x compression ratios
- Hybrid Cloud deployment support
- Advanced RBAC with OAuth2/OIDC

#### ChromaDB

**NixOS Service:**
```nix
{
  services.chromadb = {
    enable = true;
    host = "127.0.0.1";
    port = 8000;
  };
}
```

**Python Client:**
```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.create_collection("documents")
```

**2025 Rust Rewrite:**
- 4x faster writes and queries
- Multithreading support (no GIL)
- Better for local/small-scale RAG systems

#### Comparison: Qdrant vs ChromaDB

**Choose Qdrant if:**
- Deploying at scale
- Need fast filtered search
- Production workloads
- Horizontal scaling required
- Distributed deployments

**Choose ChromaDB if:**
- Experimenting locally
- Building local AI apps
- Want fast setup
- Small-scale RAG systems
- Single-node sufficient

### LLM Inference Optimization

#### Text Generation Inference (TGI)

**Systemd Service Configuration:**
```nix
{
  systemd.user.services.huggingface-tgi = {
    description = "Hugging Face Text Generation Inference";
    after = [ "network.target" ];

    serviceConfig = {
      Type = "simple";
      ExecStart = ''
        ${pkgs.text-generation-inference}/bin/text-generation-launcher \
          --model-id meta-llama/Llama-2-7b-chat-hf \
          --port 8080 \
          --max-batch-prefill-tokens 4096
      '';
      Environment = [
        "HUGGING_FACE_HUB_TOKEN=hf_xxxxxxxxxxxxx"
      ];
    };
  };
}
```

**Optimization Algorithms:**
- Flash Attention
- Paged Attention
- CUDA/HIP graph optimization
- Tensor parallel multi-GPU

#### GPU Acceleration Considerations

**ROCm (AMD):**
```nix
{
  hardware.graphics.extraPackages = with pkgs; [
    rocmPackages.clr.icd
  ];

  services.ollama.environmentVariables = {
    HCC_AMDGPU_TARGET = "gfx1100";  # RDNA 3
    HSA_OVERRIDE_GFX_VERSION = "11.0.0";
  };
}
```

**CUDA (NVIDIA):**
```nix
{
  hardware.nvidia = {
    modesetting.enable = true;
    powerManagement.enable = true;
    open = false;  # Use proprietary driver
  };

  nixpkgs.config.cudaSupport = true;
}
```

**Performance Tips (2024-2025):**
1. Use latest drivers (mismatched drivers cause suboptimal performance)
2. PyTorch/TensorFlow depend heavily on CUDA/ROCm
3. NVIDIA safer choice for mature CUDA ecosystem
4. AMD provides more VRAM per dollar on Linux

### MindsDB Integration

#### Overview

MindsDB is a federated query engine for AI, enabling SQL-like queries across data sources with embedded ML models.

**GitHub:** https://github.com/mindsdb/mindsdb

#### Deployment Options

**Docker (Recommended):**
```nix
{
  virtualisation.oci-containers.containers.mindsdb = {
    image = "mindsdb/mindsdb:latest";
    autoStart = true;
    ports = [ "47334:47334" "47335:47335" ];
    volumes = [ "mindsdb-data:/root/mindsdb" ];
  };
}
```

**Python Package:**
```bash
pip install mindsdb
mindsdb --api http --port 47334
```

#### MCP Support (2025)

**Key Features:**
- MCP support immediately available in open source and enterprise editions
- Federated data access for Model Context Protocol
- Reduces data sprawl
- 300+ data connectors

#### Integration Example

**Connect to PostgreSQL + Ollama:**
```sql
-- Create database connection
CREATE DATABASE postgres_db
WITH ENGINE = "postgres",
PARAMETERS = {
    "host": "localhost",
    "port": 5432,
    "database": "mydb"
};

-- Create ML model using Ollama
CREATE MODEL sentiment_model
PREDICT sentiment
USING
    engine = 'ollama',
    model_name = 'llama2',
    prompt_template = 'Analyze sentiment: {{text}}';

-- Query data with ML prediction
SELECT text, sentiment_model.sentiment
FROM postgres_db.reviews;
```

### Local AI Stack Architecture

#### Recommended Stack

```
┌─────────────────────────────────┐
│     Open WebUI (Port 8080)      │  Web Interface
├─────────────────────────────────┤
│      Ollama (Port 11434)        │  LLM Runtime
├─────────────────────────────────┤
│     Qdrant (Port 6333)          │  Vector DB
├─────────────────────────────────┤
│     MindsDB (Port 47334)        │  ML Query Engine
└─────────────────────────────────┘
```

#### Declarative Full Stack

```nix
{
  services.ollama = {
    enable = true;
    acceleration = "rocm";
    loadModels = [ "llama3.2:3b" ];
  };

  services.open-webui = {
    enable = true;
    port = 8080;
    environment.OLLAMA_API_BASE_URL = "http://127.0.0.1:11434";
  };

  services.qdrant = {
    enable = true;
    settings.service.http_port = 6333;
  };

  virtualisation.oci-containers.containers.mindsdb = {
    image = "mindsdb/mindsdb:latest";
    autoStart = true;
    ports = [ "47334:47334" ];
  };
}
```

### Performance and Optimization

#### Model Caching

**Hugging Face Cache:**
```nix
{
  environment.variables = {
    HF_HOME = "/var/cache/huggingface";
    TRANSFORMERS_CACHE = "/var/cache/huggingface/transformers";
  };

  systemd.tmpfiles.rules = [
    "d /var/cache/huggingface 0755 ollama ollama -"
  ];
}
```

#### Memory Management

**Ollama Configuration:**
```nix
{
  services.ollama.environmentVariables = {
    OLLAMA_MAX_LOADED_MODELS = "2";
    OLLAMA_NUM_PARALLEL = "4";
    OLLAMA_NUM_GPU = "1";
  };
}
```

#### Storage Requirements

**Typical Sizes:**
- 7B parameter model: 4-8 GB
- 13B parameter model: 8-16 GB
- 70B parameter model: 40-80 GB

**Recommended Storage:**
- Minimum: 100 GB for experimentation
- Recommended: 500 GB for multiple models
- Enterprise: 1+ TB with SSD for performance

### Security Considerations

#### Network Isolation

**Localhost Only (Default):**
```nix
{
  services.ollama.host = "127.0.0.1";
  services.open-webui.host = "127.0.0.1";
}
```

**Network Access (with firewall):**
```nix
{
  services.ollama.host = "0.0.0.0";
  networking.firewall.allowedTCPPorts = [ 11434 ];
}
```

#### Authentication

**Open WebUI with Auth:**
```nix
{
  services.open-webui.environment = {
    WEBUI_AUTH = "True";
    WEBUI_SECRET_KEY = "change-this-to-random-value";
  };
}
```

### Best Practices

1. **GPU Acceleration**: Always enable when available (10-100x speedup)
2. **Model Selection**: Start with smaller models (7B) for testing
3. **Resource Monitoring**: Monitor RAM/VRAM usage with `nvtop`/`radeontop`
4. **Caching**: Configure persistent cache for Hugging Face models
5. **Network Security**: Keep services on localhost unless explicitly needed
6. **Declarative Config**: Use NixOS services over manual container management
7. **Health Monitoring**: Enable systemd journal logging for troubleshooting
8. **Storage Planning**: Allocate sufficient space for model storage
9. **Version Pinning**: Pin model versions for reproducibility

### Troubleshooting

#### AMD GPU Not Detected

**Check logs:**
```bash
journalctl -u ollama -f
```

**Common fixes:**
```nix
{
  services.ollama.rocmOverrideGfx = "11.0.0";
  services.ollama.environmentVariables.HSA_OVERRIDE_GFX_VERSION = "11.0.0";
}
```

#### Out of Memory

**Reduce concurrent models:**
```nix
{
  services.ollama.environmentVariables.OLLAMA_MAX_LOADED_MODELS = "1";
}
```

#### Slow Inference

**Enable GPU acceleration:**
```bash
ollama run llama2 --verbose
# Check for "Using GPU" in output
```

---

## 7. MCP (Model Context Protocol) Servers

### Overview

The Model Context Protocol (MCP) is an open-source standard introduced by Anthropic in November 2024 to standardize how AI systems connect to external tools, data sources, and services.

**Official Site:** https://modelcontextprotocol.io/
**GitHub:** https://github.com/modelcontextprotocol

### Architecture

#### Core Concepts

**Three System Roles:**
1. **Host**: Application hosting the AI (e.g., Claude Desktop, IDEs)
2. **Client**: MCP client within the host application
3. **Server**: Exposes tools, resources, and prompts to clients

**Communication:**
- JSON-RPC 2.0 over stdio or HTTP
- Secure client-server architecture
- Stateless design for scalability

#### Protocol Components

**Servers Expose:**
- **Tools**: Functions the AI can call
- **Resources**: Data sources (files, databases, APIs)
- **Prompts**: Pre-defined prompt templates

**Clients Request:**
- Tool execution
- Resource access
- Prompt templates

### Progressive Tool Discovery

#### Dynamic Tool Discovery

**Key Feature:** Tools discovered at runtime, not hardcoded

**Implementation Pattern:**
```typescript
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_documents",
        description: "Search through document database",
        inputSchema: {
          type: "object",
          properties: {
            query: { type: "string" },
            limit: { type: "number", default: 10 }
          }
        }
      }
    ]
  };
});
```

#### Progressive Disclosure

**Concept:** Advanced tools become available as user demonstrates expertise

**Example:**
```typescript
// Basic user: limited tools
if (userLevel === "basic") {
  return { tools: [readTool, searchTool] };
}

// Advanced user: additional tools
if (userLevel === "advanced") {
  return { tools: [readTool, searchTool, writeTool, deleteTool] };
}
```

### Server Implementation

#### TypeScript SDK

**Installation:**
```bash
npm install @modelcontextprotocol/sdk
```

**Basic Server:**
```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server(
  {
    name: "example-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

// Register tool
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "search") {
    const { query } = request.params.arguments;
    const results = await performSearch(query);
    return { content: [{ type: "text", text: JSON.stringify(results) }] };
  }
  throw new Error("Unknown tool");
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
```

**Template Generation:**
```bash
npx create-typescript-server my-mcp-server
cd my-mcp-server
npm install
npm run build
```

#### Python SDK

**Installation:**
```bash
pip install mcp
```

**Basic Server:**
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("example-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search",
            description="Search documents",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search":
        results = await perform_search(arguments["query"])
        return [TextContent(type="text", text=str(results))]
    raise ValueError(f"Unknown tool: {name}")

if __name__ == "__main__":
    stdio_server(app)
```

### MCP Reference Implementations from Awesome-Nix

- **MCP-NixOS** ([repo](https://github.com/utensils/mcp-nixos)) surfaces NixOS, nix-darwin, and Home Manager options plus rendered documentation directly over MCP. It is listed in `awesome-nix` → Development and mirrors the AI-Optimizer goal: expose declarative state, nix-shell helpers, and evaluation results as MCP resources so Claude, Cursor, or VS Code clients can query the local machine.
- **Operational takeaway:** run the AIDB MCP service side-by-side with `ai-servicectl`. When the deployer writes updated flakes into `~/.dotfiles/home-manager`, the MCP server should watch those paths and rebuild its resource catalog, just like MCP-NixOS reloads option indexes.

### Documentation Pointers for Future Work

The [Model Context Protocol docs](https://modelcontextprotocol.io/docs/learn/architecture) now clarify transport expectations (stdio for IDE plugins, HTTP/WebSockets for remote hosts) and capability negotiation (clients must explicitly opt into streaming tool output). Use those notes when extending `scripts/deploy-aidb-mcp-server.sh` so the service can expose both transports and advertise progressive-disclosure tool groups per the spec.

### Database Backends

#### Popular Backend Solutions

**ContextForge (Gateway + Registry):**
- JWT bearer tokens, Basic Auth, custom headers
- AES encryption schemes at gateway layer
- Per-tool secret management
- Backend support: SQLite, MySQL, PostgreSQL
- Horizontal scaling and backup strategies

**Neo4j (Graph Database):**
- First MCP server for Neo4j (December 2024)
- Cypher query support
- Knowledge graph storage for memories
- Aura API control

**MindsDB (Federated Query Engine):**
- MCP support in open source and enterprise editions
- 300+ data connectors
- Unified interface to disparate data sources

#### Database Integration Pattern

**PostgreSQL Example:**
```typescript
import { Client } from 'pg';

const dbClient = new Client({
  host: 'localhost',
  database: 'mcp_data',
  user: 'mcp_user',
  password: process.env.DB_PASSWORD
});

await dbClient.connect();

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "query_database") {
    const { sql } = request.params.arguments;
    const result = await dbClient.query(sql);
    return {
      content: [{
        type: "text",
        text: JSON.stringify(result.rows)
      }]
    };
  }
});
```

### Client Integration

#### Claude Desktop Configuration

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["/path/to/filesystem-server/dist/index.js"],
      "env": {
        "ALLOWED_DIRECTORIES": "/home/user/projects,/home/user/documents"
      }
    },
    "database": {
      "command": "python",
      "args": ["/path/to/db-server/server.py"],
      "env": {
        "DATABASE_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

#### VS Code / IDEs

**Cline Extension (VS Code):**
```json
{
  "mcp.servers": {
    "my-server": {
      "command": "node",
      "args": ["path/to/server.js"]
    }
  }
}
```

### Official Reference Servers

**Anthropic Maintains:**
- **Everything**: Reference/test server
- **Fetch**: Web content fetching
- **Filesystem**: Secure file operations
- **Git**: Repository tools
- **Memory**: Knowledge graph-based system
- **Sequential Thinking**: Structured reasoning

**Community Contributions:**
- GitHub, Slack, Google Drive integration
- Postgres, MySQL database servers
- Puppeteer for browser automation
- 1000+ servers as of early 2025

### Security Model

#### Authentication & Authorization

**JWT Bearer Tokens:**
```typescript
import jwt from 'jsonwebtoken';

server.setRequestHandler(CallToolRequestSchema, async (request, extra) => {
  const token = extra.headers?.authorization?.split(' ')[1];

  if (!token) {
    throw new Error("Unauthorized");
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    // Proceed with authorized request
  } catch (error) {
    throw new Error("Invalid token");
  }
});
```

#### Secret Management

**Environment Variables:**
```bash
# .env file (never commit!)
DATABASE_URL=postgresql://user:pass@localhost/db
API_KEY=sk_test_xxxxxxxxxxxxx
```

**Loading in server:**
```typescript
import dotenv from 'dotenv';
dotenv.config();

const apiKey = process.env.API_KEY;
```

#### Sandboxing

**Filesystem Access Control:**
```typescript
const ALLOWED_PATHS = process.env.ALLOWED_DIRECTORIES?.split(',') || [];

function isPathAllowed(requestedPath: string): boolean {
  const absolute = path.resolve(requestedPath);
  return ALLOWED_PATHS.some(allowed =>
    absolute.startsWith(path.resolve(allowed))
  );
}
```

### Industry Adoption (2024-2025)

**Major Adoptions:**
- **OpenAI** (March 2025): ChatGPT desktop, Agents SDK, Responses API
- **Google DeepMind** (April 2025): Gemini models and infrastructure
- **Early Adopters**: Block, Apollo, Zed, Replit, Codeium, Sourcegraph

**Community Growth:**
- 1000+ MCP servers by early 2025
- SDKs for all major languages
- Industry standard for AI tool connectivity

### NixOS Integration

#### Declarative MCP Server Deployment

**Systemd Service:**
```nix
{
  systemd.user.services.mcp-server = {
    description = "MCP Server for Document Search";
    after = [ "network.target" ];

    serviceConfig = {
      Type = "simple";
      ExecStart = "${pkgs.nodejs}/bin/node /path/to/mcp-server/dist/index.js";
      Environment = [
        "DATABASE_URL=postgresql://localhost/documents"
        "ALLOWED_DIRECTORIES=/home/user/documents"
      ];
      Restart = "on-failure";
    };

    wantedBy = [ "default.target" ];
  };
}
```

#### Development Environment

```nix
{
  devShells.default = pkgs.mkShell {
    packages = with pkgs; [
      nodejs_22
      python312
      postgresql
    ];

    shellHook = ''
      export MCP_SERVER_PORT=3000
      echo "MCP development environment ready"
    '';
  };
}
```

### Best Practices

1. **Progressive Disclosure**: Start with basic tools, expand based on user capability
2. **Security First**: Always validate inputs, use authentication, sandbox file access
3. **Dynamic Discovery**: Implement `listTools` dynamically, not static definitions
4. **Error Handling**: Provide clear error messages for debugging
5. **Logging**: Use structured logging for monitoring and troubleshooting
6. **Stateless Design**: Keep servers stateless for horizontal scaling
7. **Secret Management**: Never hardcode secrets, use environment variables
8. **Version Pinning**: Pin SDK versions for reproducibility
9. **Documentation**: Provide clear tool descriptions for AI interpretation
10. **Testing**: Write integration tests for each tool

### Code Examples Repository

**GitHub:** https://github.com/kaianuar/mcp-server-guide
Comprehensive guide with TypeScript and Python examples

### Performance Considerations

**Caching:**
```typescript
import NodeCache from 'node-cache';
const cache = new NodeCache({ stdTTL: 600 });

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const cacheKey = JSON.stringify(request.params);

  let result = cache.get(cacheKey);
  if (result === undefined) {
    result = await expensiveOperation(request.params);
    cache.set(cacheKey, result);
  }

  return result;
});
```

**Connection Pooling:**
```typescript
import { Pool } from 'pg';

const pool = new Pool({
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Use pool.query() instead of client.query()
```

---

## 8. Stock Trading API Integration

### Overview

Python provides robust libraries for algorithmic trading with real-time market data access, backtesting, and execution capabilities.

### Python Trading Libraries and APIs

#### Alpaca (Recommended for 2024-2025)

**Official SDK:** `alpaca-py`
**GitHub:** https://github.com/alpacahq/alpaca-trade-api-python

**Features:**
- Commission-free trading API
- Real-time and historical market data
- Paper trading for testing
- Both REST and WebSocket APIs
- Supports stocks, crypto, and options

**Installation:**
```bash
pip install alpaca-py
```

**Basic Setup:**
```python
from alpaca.trading.client import TradingClient
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

# Initialize clients
trading_client = TradingClient(
    api_key='YOUR_API_KEY',
    secret_key='YOUR_SECRET_KEY',
    paper=True  # Use paper trading
)

data_client = StockHistoricalDataClient(
    api_key='YOUR_API_KEY',
    secret_key='YOUR_SECRET_KEY'
)

# Get historical bars
request_params = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Day,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 12, 31)
)

bars = data_client.get_stock_bars(request_params)
```

### Market Data APIs for Trading Metrics (Nov 2025 Update)

The refreshed [Alpaca Market Data docs](https://docs.alpaca.markets/reference/market-data-api-stock-pricing-historical-1) highlight two features the quick deploy environment should expose to AI agents and the MCP server:

1. **Aggregated bars endpoint** – `/v2/stocks/{symbol}/bars` supports 1s to 1D buckets with OHLCV data plus VWAP and trade counts. Persist these series in DuckDB/TimescaleDB so agents can compute Sharpe, downside deviation, and drawdowns without paying for a separate vendor feed.
2. **Real-time streams** – `StockDataStream` now pushes quotes, trades, and bars on the same WebSocket connection. Feed those into Qdrant to build embeddings of intraday regimes, or publish to Redis streams so AI agents can react to price events via MCP tool calls.

Combining historic bars with the low-latency stream gives locally hosted models enough context to make paper trades, monitor positions, and push alerts into Open WebUI.

**Market Data Features:**
- **Basic Plan**: Limited real-time (IEX exchange only)
- **Algo Trader Plus**: Complete market coverage (stocks + options)
- **Data Sources**: CTA (NYSE) and UTP (Nasdaq) - 100% market volume
- **Historical Data**: 5+ years available

#### Polygon.io (Now Massive.com)

**Features:**
- Real-time and historical market data
- REST and WebSocket APIs
- Extensive data coverage

**Pricing (2024-2025):**
- Delayed feeds: $699/month
- Real-time (5 exchanges): $2,000/month
- Real-time (all US exchanges): $4,000/month

**Note:** Alpaca discontinued Polygon data offering as of Feb 26, 2021

#### Interactive Brokers (IB)

**Official Python API:** `ibapi`
**Third-party:** `ib_insync` (more Pythonic)

**Features:**
- Direct broker integration
- Multi-asset support (stocks, options, futures, forex)
- Advanced order types
- Global market access

**Installation:**
```bash
pip install ib_insync
```

**Example:**
```python
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Request market data
contract = Stock('AAPL', 'SMART', 'USD')
ticker = ib.reqMktData(contract)
ib.sleep(2)

print(f"Last price: {ticker.last}")
```

### Real-Time Market Data Integration

#### WebSocket Streaming (Alpaca)

```python
from alpaca.data.live import StockDataStream

wss_client = StockDataStream(
    api_key='YOUR_API_KEY',
    secret_key='YOUR_SECRET_KEY'
)

async def quote_data_handler(data):
    print(f"Quote: {data.symbol} - Bid: {data.bid_price}, Ask: {data.ask_price}")

async def trade_data_handler(data):
    print(f"Trade: {data.symbol} - Price: {data.price}, Size: {data.size}")

# Subscribe to real-time data
wss_client.subscribe_quotes(quote_data_handler, "AAPL")
wss_client.subscribe_trades(trade_data_handler, "AAPL")

wss_client.run()
```

#### Data Processing Pipeline

```python
import pandas as pd
from collections import deque

class RealtimeProcessor:
    def __init__(self, window_size=100):
        self.prices = deque(maxlen=window_size)
        self.volumes = deque(maxlen=window_size)

    def process_trade(self, trade_data):
        self.prices.append(trade_data.price)
        self.volumes.append(trade_data.size)

        # Calculate real-time metrics
        df = pd.DataFrame({
            'price': list(self.prices),
            'volume': list(self.volumes)
        })

        sma_20 = df['price'].rolling(20).mean().iloc[-1]
        vwap = (df['price'] * df['volume']).sum() / df['volume'].sum()

        return {
            'sma_20': sma_20,
            'vwap': vwap,
            'current_price': trade_data.price
        }
```

### Trading Metrics and Analytics

#### Common Metrics

**1. Technical Indicators:**
```python
import talib

def calculate_indicators(bars):
    close = bars['close'].values
    high = bars['high'].values
    low = bars['low'].values
    volume = bars['volume'].values

    # Moving averages
    sma_20 = talib.SMA(close, timeperiod=20)
    ema_50 = talib.EMA(close, timeperiod=50)

    # Momentum indicators
    rsi = talib.RSI(close, timeperiod=14)
    macd, signal, hist = talib.MACD(close)

    # Volatility
    bbands_upper, bbands_middle, bbands_lower = talib.BBANDS(close)
    atr = talib.ATR(high, low, close, timeperiod=14)

    # Volume
    obv = talib.OBV(close, volume)

    return {
        'sma_20': sma_20,
        'ema_50': ema_50,
        'rsi': rsi,
        'macd': macd,
        'atr': atr,
        'obv': obv
    }
```

**2. Performance Metrics:**
```python
import numpy as np

def calculate_performance_metrics(returns):
    """Calculate key performance metrics"""
    # Sharpe Ratio (assuming 252 trading days, 0% risk-free rate)
    sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()

    # Maximum Drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    # Win Rate
    win_rate = (returns > 0).sum() / len(returns)

    # Profit Factor
    gross_profit = returns[returns > 0].sum()
    gross_loss = abs(returns[returns < 0].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

    return {
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_return': cumulative.iloc[-1] - 1
    }
```

### Database Design for Trading Data

#### TimescaleDB Schema (Recommended)

**Why TimescaleDB:**
- PostgreSQL extension for time-series data
- Automatic partitioning by time
- Hypertables for optimal query performance
- Native compression and data retention policies
- 0.04ms query response times for 10 years of data (30B records)

**Installation on NixOS:**
```nix
{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    extraPlugins = with pkgs.postgresql_16.pkgs; [ timescaledb ];
    settings = {
      shared_preload_libraries = "timescaledb";
    };
  };
}
```

**Schema Design:**
```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Stock prices table (OHLCV data)
CREATE TABLE stock_prices (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    open        DECIMAL(10, 2),
    high        DECIMAL(10, 2),
    low         DECIMAL(10, 2),
    close       DECIMAL(10, 2),
    volume      BIGINT,
    vwap        DECIMAL(10, 2),
    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable (automatic time-based partitioning)
SELECT create_hypertable('stock_prices', 'time');

-- Create indexes
CREATE INDEX idx_symbol_time ON stock_prices (symbol, time DESC);

-- Trades table (tick data)
CREATE TABLE trades (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    price       DECIMAL(10, 4),
    size        INTEGER,
    exchange    TEXT,
    conditions  TEXT[],
    tape        CHAR(1)
);

SELECT create_hypertable('trades', 'time');
CREATE INDEX idx_trades_symbol_time ON trades (symbol, time DESC);

-- Quotes table (bid/ask)
CREATE TABLE quotes (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    bid_price   DECIMAL(10, 4),
    bid_size    INTEGER,
    ask_price   DECIMAL(10, 4),
    ask_size    INTEGER,
    exchange    TEXT
);

SELECT create_hypertable('quotes', 'time');
CREATE INDEX idx_quotes_symbol_time ON quotes (symbol, time DESC);

-- Continuous aggregates (materialized views)
CREATE MATERIALIZED VIEW stock_prices_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume
FROM stock_prices
GROUP BY bucket, symbol;

-- Refresh policy (automatic)
SELECT add_continuous_aggregate_policy('stock_prices_1hour',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Data retention policy (optional)
SELECT add_retention_policy('trades', INTERVAL '90 days');

-- Compression policy
ALTER TABLE stock_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('stock_prices', INTERVAL '7 days');
```

**Python Integration:**
```python
import psycopg2
from psycopg2.extras import execute_values

conn = psycopg2.connect(
    host="localhost",
    database="trading",
    user="trader",
    password="password"
)

def insert_bars(bars):
    """Efficiently insert OHLCV data"""
    with conn.cursor() as cur:
        data = [
            (bar.timestamp, bar.symbol, bar.open, bar.high,
             bar.low, bar.close, bar.volume, bar.vwap)
            for bar in bars
        ]

        execute_values(
            cur,
            """
            INSERT INTO stock_prices
            (time, symbol, open, high, low, close, volume, vwap)
            VALUES %s
            ON CONFLICT (time, symbol) DO NOTHING
            """,
            data
        )
    conn.commit()

def query_recent_bars(symbol, hours=24):
    """Query recent bars with time-series optimization"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT time, open, high, low, close, volume
            FROM stock_prices
            WHERE symbol = %s
              AND time > NOW() - INTERVAL '%s hours'
            ORDER BY time DESC
        """, (symbol, hours))

        return cur.fetchall()
```

### Risk Management Systems

#### Position Sizing

```python
class RiskManager:
    def __init__(self, account_value, max_risk_per_trade=0.02):
        self.account_value = account_value
        self.max_risk_per_trade = max_risk_per_trade

    def calculate_position_size(self, entry_price, stop_loss_price):
        """Calculate position size based on risk"""
        risk_per_share = abs(entry_price - stop_loss_price)
        max_risk_amount = self.account_value * self.max_risk_per_trade

        position_size = max_risk_amount / risk_per_share

        # Don't exceed account value
        max_shares = self.account_value / entry_price
        position_size = min(position_size, max_shares)

        return int(position_size)

    def calculate_kelly_criterion(self, win_rate, avg_win, avg_loss):
        """Kelly Criterion for optimal position sizing"""
        if avg_loss == 0:
            return 0

        win_loss_ratio = avg_win / abs(avg_loss)
        kelly_percentage = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

        # Use half-Kelly for safety
        return max(0, kelly_percentage * 0.5)
```

#### Portfolio Risk Metrics

```python
import numpy as np
import pandas as pd

class PortfolioRiskAnalyzer:
    def __init__(self, returns_df):
        """
        returns_df: DataFrame with columns as assets, rows as dates
        """
        self.returns = returns_df
        self.cov_matrix = returns_df.cov()

    def calculate_var(self, confidence=0.95):
        """Value at Risk"""
        portfolio_returns = self.returns.sum(axis=1)
        var = np.percentile(portfolio_returns, (1 - confidence) * 100)
        return var

    def calculate_cvar(self, confidence=0.95):
        """Conditional Value at Risk (Expected Shortfall)"""
        portfolio_returns = self.returns.sum(axis=1)
        var = self.calculate_var(confidence)
        cvar = portfolio_returns[portfolio_returns <= var].mean()
        return cvar

    def calculate_portfolio_volatility(self, weights):
        """Portfolio volatility given weights"""
        weights = np.array(weights)
        portfolio_variance = np.dot(weights.T, np.dot(self.cov_matrix, weights))
        portfolio_std = np.sqrt(portfolio_variance) * np.sqrt(252)  # Annualized
        return portfolio_std

    def optimize_max_sharpe(self, target_return=None):
        """Optimize portfolio for maximum Sharpe ratio"""
        from scipy.optimize import minimize

        n_assets = len(self.returns.columns)

        def neg_sharpe(weights):
            portfolio_return = np.sum(self.returns.mean() * weights) * 252
            portfolio_std = self.calculate_portfolio_volatility(weights)
            return -portfolio_return / portfolio_std

        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
        ]

        if target_return:
            constraints.append({
                'type': 'eq',
                'fun': lambda w: np.sum(self.returns.mean() * w) * 252 - target_return
            })

        bounds = tuple((0, 1) for _ in range(n_assets))
        initial_guess = np.array([1/n_assets] * n_assets)

        result = minimize(
            neg_sharpe,
            initial_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x
```

### Best Practices (2024-2025)

#### API Management

1. **Rate Limiting:**
```python
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=200, period=60)  # 200 calls per minute
def api_call():
    # Your API call here
    pass
```

2. **Error Handling:**
```python
from requests.exceptions import RequestException
import time

def robust_api_call(func, max_retries=3, backoff=2):
    for attempt in range(max_retries):
        try:
            return func()
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(backoff ** attempt)
```

3. **Secret Management (NixOS):**
```nix
{
  sops.secrets."trading/alpaca-api-key" = {
    sopsFile = ./secrets.yaml;
    owner = "trader";
  };

  systemd.services.trading-bot = {
    serviceConfig = {
      EnvironmentFile = config.sops.secrets."trading/alpaca-api-key".path;
    };
  };
}
```

#### Data Management

1. **Use TimescaleDB** for time-series data
2. **Implement continuous aggregates** for common queries
3. **Set up compression policies** for older data
4. **Use data retention policies** to manage storage
5. **Index by (symbol, time)** for optimal query performance

#### Strategy Development

1. **Backtest thoroughly** before live trading
2. **Use paper trading** to validate strategies
3. **Implement proper risk management** (position sizing, stop losses)
4. **Monitor performance metrics** (Sharpe, drawdown, win rate)
5. **Log all trades** for analysis and auditing

---

## 9. Complex NixOS System Architecture

### Modular Configuration Strategies

#### Constellation Pattern

**Concept:** Modular system eliminating configuration duplication while maintaining per-host flexibility.

**Architecture:**
```
repo/
├── flake.nix                    # Entry point
├── flake.lock                   # Locked dependencies
├── hosts/
│   ├── desktop/
│   │   └── configuration.nix    # Host-specific config
│   ├── laptop/
│   │   └── configuration.nix
│   └── server/
│       └── configuration.nix
├── modules/
│   ├── hardware/
│   │   ├── amd-gpu.nix
│   │   └── nvidia-gpu.nix
│   ├── desktop/
│   │   ├── cosmic.nix
│   │   └── hyprland.nix
│   ├── services/
│   │   ├── ai-stack.nix
│   │   └── databases.nix
│   └── users/
│       └── default-user.nix
├── overlays/
│   └── custom-packages.nix
└── profiles/
    ├── development.nix
    ├── gaming.nix
    └── minimal.nix
```

**Implementation Pattern:**
```nix
# flake.nix
{
  outputs = { self, nixpkgs, ... }: {
    nixosConfigurations = {
      desktop = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          ./hosts/desktop/configuration.nix
          ./modules/hardware/amd-gpu.nix
          ./modules/desktop/cosmic.nix
          ./modules/services/ai-stack.nix
          ./profiles/development.nix
        ];
      };

      laptop = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          ./hosts/laptop/configuration.nix
          ./modules/hardware/amd-gpu.nix
          ./modules/desktop/hyprland.nix
          ./profiles/minimal.nix
        ];
      };
    };
  };
}
```

**Module with Defaults and Overrides:**
```nix
# modules/services/ai-stack.nix
{ config, lib, pkgs, ... }:

{
  options.services.aiStack = {
    enable = lib.mkEnableOption "AI stack services";

    ollama = {
      models = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ "llama3.2:3b" ];
        description = "Models to preload";
      };

      acceleration = lib.mkOption {
        type = lib.types.nullOr (lib.types.enum [ "cuda" "rocm" ]);
        default = null;
        description = "GPU acceleration type";
      };
    };
  };

  config = lib.mkIf config.services.aiStack.enable {
    services.ollama = {
      enable = true;
      acceleration = config.services.aiStack.ollama.acceleration;
      loadModels = config.services.aiStack.ollama.models;
    };

    services.qdrant.enable = lib.mkDefault true;
    services.open-webui.enable = lib.mkDefault true;
  };
}

# hosts/desktop/configuration.nix
{
  services.aiStack = {
    enable = true;
    ollama.acceleration = "rocm";
    ollama.models = [ "llama3.2:3b" "deepseek-r1:7b" ];
  };

  # Override default
  services.qdrant.enable = lib.mkForce false;
}
```

### State Management

#### Ephemeral Root with Impermanence

**Concept:** Root filesystem wiped on reboot, selective persistence

**Benefits:**
- Fresh system every boot
- No accumulation of cruft
- Explicit state management
- Enhanced security

**Setup:**
```nix
{
  imports = [ "${impermanence}/nixos.nix" ];

  # Tmpfs root
  fileSystems."/" = {
    device = "none";
    fsType = "tmpfs";
    options = [ "defaults" "size=2G" "mode=755" ];
  };

  # Persistent storage
  fileSystems."/persist" = {
    device = "/dev/disk/by-label/persist";
    fsType = "btrfs";
    options = [ "subvol=persist" ];
  };

  # NixOS essentials
  fileSystems."/nix" = {
    device = "/dev/disk/by-label/persist";
    fsType = "btrfs";
    options = [ "subvol=nix" ];
  };

  fileSystems."/boot" = {
    device = "/dev/disk/by-label/boot";
    fsType = "vfat";
  };

  # Selective persistence
  environment.persistence."/persist" = {
    directories = [
      "/etc/nixos"
      "/var/log"
      "/var/lib/systemd"
      "/var/lib/nixos"
      "/var/lib/containers"
    ];

    files = [
      "/etc/machine-id"
      "/etc/ssh/ssh_host_ed25519_key"
      "/etc/ssh/ssh_host_rsa_key"
    ];

    users.myuser = {
      directories = [
        "Documents"
        "Downloads"
        "Pictures"
        ".ssh"
        ".gnupg"
        { directory = ".local/share/keyrings"; mode = "0700"; }
      ];

      files = [
        ".zsh_history"
      ];
    };
  };
}
```

**Warning:** All data in tmpfs stored in RAM only - downloads/large files can cause OOM

#### Stateful Services

**Database Persistence:**
```nix
{
  environment.persistence."/persist" = {
    directories = [
      "/var/lib/postgresql"
      "/var/lib/redis"
      "/var/lib/qdrant"
    ];
  };

  # Backup before switch
  system.activationScripts.backupDatabases = ''
    ${pkgs.postgresql}/bin/pg_dumpall -U postgres > /persist/backups/pg-$(date +%Y%m%d).sql
  '';
}
```

### Deployment Automation

#### NixOps (Multi-Machine Deployments)

**Configuration:**
```nix
# network.nix
{
  network.description = "AI Infrastructure";

  webserver = { config, pkgs, ... }: {
    deployment.targetHost = "web.example.com";
    services.nginx.enable = true;
  };

  database = { config, pkgs, ... }: {
    deployment.targetHost = "db.example.com";
    services.postgresql.enable = true;
  };

  compute = { config, pkgs, ... }: {
    deployment.targetHost = "compute.example.com";
    services.ollama.enable = true;
    services.qdrant.enable = true;
  };
}
```

**Deployment:**
```bash
nixops create -d ai-infra network.nix
nixops deploy -d ai-infra
```

#### Colmena (Stateless Deployment Tool)

**Configuration:**
```nix
# flake.nix
{
  outputs = { nixpkgs, colmena, ... }: {
    colmena = {
      meta = {
        nixpkgs = import nixpkgs {
          system = "x86_64-linux";
        };
      };

      webserver = { name, nodes, ... }: {
        deployment = {
          targetHost = "web.example.com";
          targetUser = "deploy";
          buildOnTarget = true;
        };

        imports = [ ./hosts/webserver.nix ];
      };

      database = { name, nodes, ... }: {
        deployment.targetHost = "db.example.com";
        imports = [ ./hosts/database.nix ];
      };
    };
  };
}
```

**Deployment:**
```bash
colmena apply
colmena apply --on webserver  # Deploy specific host
```

#### nixos-anywhere (Remote Installation)

**Install NixOS on remote machine over SSH:**
```bash
nixos-anywhere --flake .#hostname root@remote-ip
```

**Disk Configuration:**
```nix
{
  disko.devices = {
    disk.main = {
      device = "/dev/sda";
      type = "disk";
      content = {
        type = "gpt";
        partitions = {
          boot = {
            size = "1G";
            type = "EF00";
            content = {
              type = "filesystem";
              format = "vfat";
              mountpoint = "/boot";
            };
          };
          root = {
            size = "100%";
            content = {
              type = "btrfs";
              subvolumes = {
                "/nix" = { mountpoint = "/nix"; };
                "/persist" = { mountpoint = "/persist"; };
              };
            };
          };
        };
      };
    };
  };
}
```

### Testing and Validation

#### NixOS Tests

**VM-based Integration Tests:**
```nix
import <nixpkgs/nixos/tests/make-test-python.nix> {
  name = "ai-stack-test";

  nodes = {
    machine = { config, pkgs, ... }: {
      services.ollama.enable = true;
      services.qdrant.enable = true;
      services.open-webui.enable = true;
    };
  };

  testScript = ''
    machine.start()
    machine.wait_for_unit("ollama.service")
    machine.wait_for_unit("qdrant.service")
    machine.wait_for_unit("open-webui.service")

    # Test Ollama API
    machine.succeed("curl -f http://localhost:11434/api/tags")

    # Test Qdrant API
    machine.succeed("curl -f http://localhost:6333/collections")

    # Test Open WebUI
    machine.succeed("curl -f http://localhost:8080")
  '';
}
```

**Run Tests:**
```bash
nix-build -A nixosTests.ai-stack-test
```

#### Dry Builds and Validation

**Pre-deployment Checks:**
```bash
# Dry build system configuration
nixos-rebuild dry-build --flake .#hostname

# Show what would change
nixos-rebuild dry-activate --flake .#hostname

# Build without switching
nixos-rebuild build --flake .#hostname
./result/bin/switch-to-configuration test  # Test without boot entry
```

### Rollback Strategies

#### Generation Management

**List Generations:**
```bash
sudo nix-env --list-generations --profile /nix/var/nix/profiles/system
```

**Rollback:**
```bash
# Rollback to previous generation
sudo nixos-rebuild switch --rollback

# Rollback to specific generation
sudo nix-env --rollback --profile /nix/var/nix/profiles/system
sudo nix-env --switch-generation 42 --profile /nix/var/nix/profiles/system
sudo /nix/var/nix/profiles/system-42-link/bin/switch-to-configuration switch
```

**Automatic Rollback on Failure:**
```nix
{
  system.activationScripts.healthCheck = ''
    if ! systemctl is-active --quiet critical-service; then
      echo "Critical service failed, rolling back..."
      /run/current-system/bin/switch-to-configuration switch --rollback
      exit 1
    fi
  '';
}
```

#### Bootloader Integration

**Select Generation at Boot:**
- GRUB shows all generations
- Select previous generation to boot
- Make permanent: `sudo nixos-rebuild switch --rollback`

**Auto-rollback on Boot Failure:**
```nix
{
  boot.loader.grub.configurationLimit = 10;  # Keep last 10 generations
}
```

### System Health Monitoring

#### Prometheus + Grafana Stack

**Configuration:**
```nix
{
  services.prometheus = {
    enable = true;
    port = 9090;

    exporters = {
      node = {
        enable = true;
        enabledCollectors = [ "systemd" "cpu" "meminfo" ];
      };

      postgres = {
        enable = true;
        dataSourceName = "user=prometheus database=postgres host=/run/postgresql sslmode=disable";
      };
    };

    scrapeConfigs = [
      {
        job_name = "node";
        static_configs = [{
          targets = [ "localhost:9100" ];
        }];
      }
      {
        job_name = "ollama";
        static_configs = [{
          targets = [ "localhost:11434" ];
        }];
      }
    ];
  };

  services.grafana = {
    enable = true;
    settings = {
      server = {
        http_addr = "127.0.0.1";
        http_port = 3000;
      };
    };

    provision = {
      enable = true;
      datasources.settings.datasources = [{
        name = "Prometheus";
        type = "prometheus";
        url = "http://localhost:9090";
      }];
    };
  };
}
```

#### Systemd Journal Monitoring

**Centralized Logging:**
```nix
{
  services.loki = {
    enable = true;
    configuration = {
      server.http_listen_port = 3100;

      ingester = {
        lifecycler = {
          address = "127.0.0.1";
          ring.kvstore.store = "inmemory";
        };
        chunk_idle_period = "1h";
        max_chunk_age = "1h";
      };
    };
  };

  services.promtail = {
    enable = true;
    configuration = {
      server = {
        http_listen_port = 9080;
        grpc_listen_port = 0;
      };

      clients = [{
        url = "http://localhost:3100/loki/api/v1/push";
      }];

      scrape_configs = [{
        job_name = "journal";
        journal = {
          max_age = "12h";
          labels = {
            job = "systemd-journal";
            host = "hostname";
          };
        };
        relabel_configs = [{
          source_labels = [ "__journal__systemd_unit" ];
          target_label = "unit";
        }];
      }];
    };
  };
}
```

#### Health Check Scripts

**Declarative Health Checks:**
```nix
{
  systemd.services.health-check = {
    description = "System Health Check";

    serviceConfig = {
      Type = "oneshot";
      ExecStart = pkgs.writeScript "health-check" ''
        #!${pkgs.bash}/bin/bash

        # Check critical services
        for service in ollama qdrant postgresql; do
          if ! systemctl is-active --quiet $service; then
            echo "CRITICAL: $service is not running"
            exit 1
          fi
        done

        # Check disk space
        if [ $(df / | tail -1 | awk '{print $5}' | sed 's/%//') -gt 90 ]; then
          echo "WARNING: Root filesystem >90% full"
        fi

        # Check load average
        if [ $(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $1}' | xargs) -gt 8 ]; then
          echo "WARNING: High load average"
        fi

        echo "Health check passed"
      '';
    };
  };

  systemd.timers.health-check = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnCalendar = "hourly";
      Persistent = true;
    };
  };
}
```

### Best Practices Summary

1. **Modular Configuration**: Separate concerns into reusable modules
2. **Use lib.mkDefault**: Allow easy overrides without lib.mkForce
3. **Impermanence**: Consider ephemeral root for security and cleanliness
4. **State Management**: Explicitly declare what should persist
5. **Deployment Automation**: Use Colmena/NixOps for multi-machine setups
6. **Testing**: Write NixOS tests for critical infrastructure
7. **Rollback Strategy**: Keep sufficient generations, test rollback procedures
8. **Monitoring**: Deploy Prometheus/Grafana/Loki for observability
9. **Health Checks**: Automate validation of critical services
10. **Documentation**: Document module options and architecture decisions

---

## 10. Recommendations for NixOS-Dev-Quick-Deploy

Based on the comprehensive research above, here are specific recommendations for reviewing and optimizing the NixOS-Dev-Quick-Deploy script:

### Architecture Review

#### Current Strengths (Observed in codebase)

1. **8-Phase Modular Architecture** (v4.0.0)
   - Well-organized phase separation
   - Clear dependency tracking
   - Resume/restart capabilities
   - State management with JSON tracking

2. **Library Modularity**
   - 20+ specialized library files
   - Clear separation of concerns
   - Reusable functions across phases

3. **Comprehensive Feature Set**
   - COSMIC Desktop + Hyprland
   - Podman rootless containers
   - Flatpak with profile management
   - AI stack (Ollama, Open WebUI, Qdrant, TGI)
   - Home Manager integration
   - GPU detection and configuration

### Recommended Enhancements

#### 1. Flakes Migration (High Priority)

**Current:** Script generates `configuration.nix` and `home.nix` files
**Recommendation:** Migrate to full flake-based architecture

**Benefits:**
- Version-pinned dependencies (flake.lock)
- Better reproducibility
- Multi-machine configuration support
- Standard NixOS/Home Manager integration pattern

**Implementation:**
```nix
# templates/flake.nix
{
  description = "NixOS configuration with AI development stack";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

    home-manager = {
      url = "github:nix-community/home-manager/release-25.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-flatpak.url = "github:gmodena/nix-flatpak";

    impermanence.url = "github:nix-community/impermanence";
  };

  outputs = { self, nixpkgs, home-manager, nix-flatpak, impermanence, ... }: {
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        impermanence.nixosModules.impermanence

        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.username = import ./home.nix;
          home-manager.sharedModules = [
            nix-flatpak.homeManagerModules.nix-flatpak
          ];
        }
      ];
    };
  };
}
```

#### 2. Declarative Flatpak Management

**Current:** Imperative Flatpak installation in Phase 6
**Recommendation:** Use `nix-flatpak` module

**Benefits:**
- Reproducible Flatpak installations
- State tracking in flake.lock
- Convergent mode (doesn't remove manual installs)
- Profile-based provisioning

**Implementation in home.nix:**
```nix
{
  services.flatpak = {
    enable = true;

    remotes = [{
      name = "flathub";
      location = "https://dl.flathub.org/repo/flathub.flatpakrepo";
    }];

    packages =
      # Core profile
      [
        "org.mozilla.firefox"
        "md.obsidian.Obsidian"
        "com.github.tchx84.Flatseal"
      ]
      # AI Workstation additions
      ++ lib.optionals (config.profiles.aiWorkstation or false) [
        "com.getpostman.Postman"
        "io.dbeaver.DBeaverCommunity"
        "ai.cursor.Cursor"
      ];
  };
}
```

#### 3. Enhanced Container Management

**Current:** Manual Podman container setup
**Recommendation:** Declarative container services

**Quadlet Integration:**
```nix
{
  imports = [ inputs.quadlet-nix.homeManagerModules.default ];

  services.quadlet = {
    enable = true;

    containers.ollama = {
      image = "docker.io/ollama/ollama:latest";
      autoStart = true;
      ports = [ "11434:11434" ];
      volumes = [ "ollama-data:/root/.ollama" ];
    };

    containers.open-webui = {
      image = "ghcr.io/open-webui/open-webui:main";
      autoStart = true;
      ports = [ "8080:8080" ];
      environment = {
        OLLAMA_BASE_URL = "http://ollama:11434";
      };
      dependsOn = [ "ollama" ];
    };
  };
}
```

**System-Level (configuration.nix):**
```nix
{
  virtualisation.oci-containers = {
    backend = "podman";

    containers.qdrant = {
      image = "qdrant/qdrant:latest";
      autoStart = true;
      ports = [ "6333:6333" "6334:6334" ];
      volumes = [ "qdrant-data:/qdrant/storage" ];
    };
  };
}
```

#### 4. Secret Management Integration

**Current:** API keys likely stored in environment variables
**Recommendation:** Integrate `sops-nix`

**Setup:**
```nix
# flake.nix
{
  inputs.sops-nix.url = "github:Mic92/sops-nix";

  outputs = { sops-nix, ... }: {
    nixosConfigurations.hostname = {
      modules = [
        sops-nix.nixosModules.sops
        ./configuration.nix
      ];
    };
  };
}

# configuration.nix
{
  sops = {
    defaultSopsFile = ./secrets.yaml;
    age.keyFile = "/persist/var/lib/sops-nix/key.txt";

    secrets = {
      "api-keys/anthropic" = {
        owner = "username";
      };
      "api-keys/openai" = {
        owner = "username";
      };
      "database/postgres-password" = {
        owner = "postgres";
      };
    };
  };

  # Use secrets in services
  systemd.services.ai-agent = {
    serviceConfig = {
      EnvironmentFile = config.sops.secrets."api-keys/anthropic".path;
    };
  };
}
```

#### 5. Impermanence Integration (Optional)

**For Advanced Users:**
```nix
{
  imports = [ inputs.impermanence.nixosModules.impermanence ];

  # Tmpfs root
  fileSystems."/" = {
    device = "none";
    fsType = "tmpfs";
    options = [ "defaults" "size=4G" "mode=755" ];
  };

  # Persistent storage
  environment.persistence."/persist" = {
    hideMounts = true;
    directories = [
      "/etc/nixos"
      "/var/log"
      "/var/lib/nixos"
      "/var/lib/systemd"
      "/var/lib/containers"
      "/var/lib/ollama"
      "/var/lib/qdrant"
    ];

    files = [
      "/etc/machine-id"
      "/etc/ssh/ssh_host_ed25519_key"
      "/etc/ssh/ssh_host_rsa_key"
    ];

    users.username = {
      directories = [
        "Documents"
        "Downloads"
        "Pictures"
        ".ssh"
        ".gnupg"
        { directory = ".local/share/containers"; mode = "0700"; }
      ];
    };
  };
}
```

#### 6. NixOS Tests for Validation

**Phase 7 Enhancement:**
```nix
# tests/system-test.nix
import <nixpkgs/nixos/tests/make-test-python.nix> {
  name = "nixos-dev-quick-deploy-test";

  nodes.machine = { config, pkgs, ... }: {
    imports = [ ../configuration.nix ];
  };

  testScript = ''
    machine.start()

    # Test core services
    machine.wait_for_unit("ollama.service")
    machine.wait_for_unit("qdrant.service")
    machine.wait_for_unit("open-webui.service")

    # Test APIs
    machine.succeed("curl -f http://localhost:11434/api/tags")
    machine.succeed("curl -f http://localhost:6333/collections")
    machine.succeed("curl -f http://localhost:8080")

    # Test user environment
    machine.succeed("su - username -c 'which podman'")
    machine.succeed("su - username -c 'which python3'")
    machine.succeed("su - username -c 'python3 -c \"import torch\"'")
  '';
}
```

#### 7. TimescaleDB Integration for Trading/Analytics

**Add to AI stack configuration:**
```nix
{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;

    extraPlugins = with pkgs.postgresql_16.pkgs; [
      timescaledb
    ];

    settings = {
      shared_preload_libraries = "timescaledb";
      max_connections = 200;
      shared_buffers = "4GB";
      effective_cache_size = "12GB";
      work_mem = "16MB";
    };

    ensureDatabases = [ "trading" "analytics" ];
    ensureUsers = [{
      name = "trader";
      ensureDBOwnership = true;
    }];
  };

  # Automatic backups
  services.postgresqlBackup = {
    enable = true;
    databases = [ "trading" "analytics" ];
    startAt = "*-*-* 02:00:00";
  };
}
```

#### 8. MCP Server Template Generation

**Add to Phase 6:**
```bash
# Generate MCP server template
create_mcp_server_template() {
    local mcp_dir="$HOME/mcp-servers"
    mkdir -p "$mcp_dir"

    cat > "$mcp_dir/example-server/package.json" <<'EOF'
{
  "name": "example-mcp-server",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0"
  }
}
EOF

    cat > "$mcp_dir/example-server/index.js" <<'EOF'
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "example-server",
  version: "1.0.0"
}, {
  capabilities: { tools: {} }
});

// Register tools here

const transport = new StdioServerTransport();
await server.connect(transport);
EOF
}
```

#### 9. Enhanced GPU Detection and Configuration

**Expand GPU detection logic:**
```nix
{
  # Automatic GPU configuration based on detection
  hardware.nvidia = lib.mkIf (builtins.elem "nvidia" detectedGpus) {
    modesetting.enable = true;
    powerManagement.enable = true;
    open = false;
  };

  hardware.amdgpu = lib.mkIf (builtins.elem "amd" detectedGpus) {
    opencl.enable = true;
    amdvlk.enable = true;
  };

  # ROCm for AMD
  systemd.tmpfiles.rules = lib.mkIf (builtins.elem "amd" detectedGpus) [
    "L+ /opt/rocm/hip - - - - ${pkgs.rocmPackages.clr}"
  ];

  # CUDA for NVIDIA
  nixpkgs.config.cudaSupport = builtins.elem "nvidia" detectedGpus;
}
```

#### 10. Comprehensive Health Monitoring

**Enhanced system-health-check.sh:**
```bash
#!/usr/bin/env bash

# Add MCP server checks
check_mcp_servers() {
    local config="$HOME/.config/Claude/claude_desktop_config.json"

    if [[ -f "$config" ]]; then
        jq -r '.mcpServers | keys[]' "$config" | while read server; do
            echo "Checking MCP server: $server"
            # Test server connectivity
        done
    fi
}

# Add TimescaleDB checks
check_timescaledb() {
    if systemctl is-active postgresql.service; then
        psql -U postgres -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';" 2>&1
    fi
}

# Add container health checks
check_container_health() {
    podman ps --format "{{.Names}}: {{.Status}}" | while read line; do
        if [[ "$line" =~ "Unhealthy" ]]; then
            echo "WARNING: Container unhealthy: $line"
        fi
    done
}
```

### Documentation Improvements

#### Add New Docs

1. **docs/FLAKES_MIGRATION_GUIDE.md**: Step-by-step flakes migration
2. **docs/MCP_SETUP.md**: MCP server configuration and examples (exists)
3. **docs/SECRETS_MANAGEMENT.md**: sops-nix setup and usage
4. **docs/IMPERMANENCE_GUIDE.md**: Optional impermanence configuration
5. **docs/TRADING_STACK_SETUP.md**: TimescaleDB + trading APIs
6. **docs/ADVANCED_CONTAINERS.md**: Quadlet, compose2nix patterns

#### Update Existing Docs

1. **README.md**: Add flakes benefits, update architecture diagram
2. **TROUBLESHOOTING.md**: Add flakes-specific troubleshooting
3. **QUICK_START.md**: Simplify with flakes-first approach

### Code Quality Enhancements

#### Static Analysis

**Add to Phase 4 (pre-deployment validation):**
```bash
# Nix code validation
statix check /etc/nixos
alejandra --check /etc/nixos
deadnix /etc/nixos

# Shell script validation
shellcheck scripts/*.sh
```

#### Pre-commit Hooks

**Add .pre-commit-config.yaml:**
```yaml
repos:
  - repo: https://github.com/cachix/pre-commit-hooks.nix
    rev: master
    hooks:
      - id: alejandra
      - id: statix
      - id: deadnix
      - id: shellcheck
```

### Performance Optimizations

#### Build Acceleration

1. **Binary Cache Usage**: Already implemented
2. **Parallel Builds**: Increase `max-jobs` dynamically
   ```nix
   nix.settings.max-jobs = "auto";
   nix.settings.cores = 0;  # Use all cores
   ```

3. **Remote Builders**: Template for adding remote builders
   ```nix
   nix.buildMachines = [{
     hostName = "builder.example.com";
     system = "x86_64-linux";
     maxJobs = 8;
     speedFactor = 2;
     supportedFeatures = [ "nixos-test" "benchmark" "big-parallel" "kvm" ];
   }];

   nix.distributedBuilds = true;
   ```

### Testing Strategy

#### Continuous Integration

**Add .github/workflows/test.yml:**
```yaml
name: NixOS Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: cachix/install-nix-action@v26
        with:
          extra_nix_config: |
            experimental-features = nix-command flakes

      - name: Check formatting
        run: |
          nix develop --command alejandra --check .

      - name: Run linters
        run: |
          nix develop --command statix check .
          nix develop --command deadnix .

      - name: Build system configuration
        run: nix build .#nixosConfigurations.example.config.system.build.toplevel

      - name: Run NixOS tests
        run: nix build .#nixosTests.system-test
```

### Migration Path

**Phased Approach:**

**Phase 1: Flakes Foundation (v5.0.0)**
- Migrate to flakes-based architecture
- Maintain backward compatibility
- Update templates

**Phase 2: Declarative Services (v5.1.0)**
- Integrate nix-flatpak
- Declarative Podman containers
- Enhanced GPU configuration

**Phase 3: Security & State (v5.2.0)**
- sops-nix integration
- Optional impermanence support
- Enhanced secret management

**Phase 4: Testing & Monitoring (v5.3.0)**
- NixOS tests integration
- Enhanced health checks
- CI/CD pipeline

**Phase 5: Advanced Features (v6.0.0)**
- MCP server templates
- TimescaleDB integration
- Multi-machine support

---

## Summary

This comprehensive research report provides detailed documentation on:

1. **Awesome-Nix Ecosystem**: Curated tools and best practices
2. **Home Manager**: Advanced configuration patterns and integration
3. **Flakes Architecture**: Modern reproducible builds and multi-system support
4. **Container Solutions**: Podman, Docker, OCI image building
5. **Flatpak Integration**: Declarative desktop application management
6. **AI Agents**: Ollama, vector databases, GPU acceleration
7. **MCP Servers**: Model Context Protocol implementation
8. **Trading APIs**: Real-time market data and risk management
9. **System Architecture**: Modular configs, state management, deployment

The recommendations section provides a clear roadmap for evolving the NixOS-Dev-Quick-Deploy script toward modern best practices while maintaining its comprehensive feature set.

**Key Takeaways:**
- Migrate to flakes for better reproducibility
- Use declarative configuration wherever possible
- Integrate proper secret management
- Add comprehensive testing and validation
- Enhance monitoring and observability
- Maintain modularity and flexibility

All sources are from 2024-2025 authoritative documentation and represent current best practices in the NixOS ecosystem.
