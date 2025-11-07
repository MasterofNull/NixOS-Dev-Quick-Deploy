# NixOS Dev Quick Deploy: Project Overview

## Quick Pitch

**NixOS Dev Quick Deploy**: One-command script that transforms a fresh NixOS install into a fully-configured AI development powerhouse in 20-120 minutes. 800+ packages, auto-GPU detection, 7 AI coding assistants, local LLMs, and complete ML stack—all declaratively managed and reproducible.

---

## What It Does

NixOS Dev Quick Deploy is a **fully-automated deployment framework** that solves the "day one productivity problem" for AI/ML developers on NixOS.

### Core Capabilities

- ⚡ **One-command deployment**: Single script execution sets up your entire dev environment
- 🎯 **800+ pre-configured packages**: Development tools, AI assistants, ML frameworks, and applications
- 🤖 **Complete AI toolchain**: Claude Code, Cursor, Ollama, Aider, Continue, Codeium, GPT CLI
- 🧠 **Full ML stack**: 60+ Python packages (PyTorch, TensorFlow, LangChain, Transformers, etc.)
- 🎨 **Modern desktop**: COSMIC Desktop from System76 (Rust-based)
- 🔄 **Fully reproducible**: Declarative configuration using Nix flakes
- 💾 **Resumable workflow**: 8-phase deployment survives interruptions
- 🖥️ **Hardware-aware**: Auto-detects NVIDIA/AMD/Intel GPUs and configures drivers

---

## The Problem It Solves

Setting up NixOS for AI development is notoriously complex. This framework eliminates:

1. **Configuration Complexity**: No need to learn Nix syntax and best practices from scratch
2. **Setup Time**: Reduces new machine onboarding from days to hours
3. **Dependency Hell**: Declarative approach prevents version conflicts
4. **Hardware Integration**: Automatically detects and configures GPU drivers
5. **Tool Fragmentation**: Pre-integrates 7+ AI coding assistants and ML frameworks

---

## Technology Stack

### Core Infrastructure

- **NixOS 25.05+**: Declarative Linux distribution with reproducible builds
- **Nix Flakes**: Modern dependency management and configuration
- **Home Manager**: User environment configuration (manages ~100 packages declaratively)
- **Bash**: 5,108 lines of modular shell scripts (main orchestrator + phases + libraries)

### Configuration Management

- **Templates**: Nix templates for system config (1,014 lines) and user config (3,067 lines)
- **Modular Libraries**: 20+ shared libraries (~350KB total) in `/lib` directory
- **State Management**: JSON-based state tracking for resumable deployments
- **Placeholder System**: Python-based utilities for template generation

### AI Tooling Stack

- **Claude Code**: VSCodium extension + npm CLI with smart Node.js wrapper
- **Cursor**: AI-first IDE via Flatpak
- **Ollama**: Local LLM runtime in Podman containers
- **Hugging Face TGI**: High-performance inference server (systemd service)
- **Open WebUI**: ChatGPT-like interface for local LLMs
- **Vector Databases**: Qdrant (systemd), ChromaDB, FAISS

### Container & Virtualization

- **Podman**: Daemonless containers with rootless security model
- **Podman Compose**: Docker Compose compatibility
- **Buildah & Skopeo**: Container building and registry management

---

## Architecture

### 8-Phase Workflow

```
Phase 1: System Initialization
├─> Validate NixOS requirements
├─> Check permissions, network, disk space
├─> Detect GPU/CPU hardware
└─> Install temporary tools (git, jq via nix-env)

Phase 2: System Backup
└─> Comprehensive backup of /etc/nixos and user configs

Phase 3: Configuration Generation
├─> Generate configuration.nix (system config)
├─> Generate home.nix (user packages)
└─> Generate flake.nix (dependency management)

Phase 4: Pre-Deployment Validation
├─> Validate Nix syntax
├─> Check for conflicts
└─> Dry-run build

Phase 5: Declarative Deployment
├─> Remove imperative nix-env packages
├─> Apply NixOS configuration (nixos-rebuild switch)
└─> Apply Home Manager configuration

Phase 6: Additional Tooling
├─> Install Claude Code CLI (npm)
├─> Install GPT CodeX, OpenAI, GooseAI CLIs
├─> Install Flatpak apps (Firefox, Obsidian, Cursor, etc.)
└─> Configure VSCodium extensions

Phase 7: Post-Deployment Validation
├─> Verify all packages are accessible
├─> Check systemd services
└─> Validate GPU configuration

Phase 8: Finalization & Report
├─> Generate deployment summary
├─> Create health check report
└─> Provide next steps
```

### File Structure

```
/home/user/NixOS-Dev-Quick-Deploy/
├── nixos-quick-deploy.sh       # Bootstrap orchestrator (1,027 lines)
├── phases/                     # 8-phase deployment workflow
│   ├── phase-01-system-initialization.sh
│   ├── phase-02-system-backup.sh
│   ├── phase-03-configuration-generation.sh
│   ├── phase-04-pre-deployment-validation.sh
│   ├── phase-05-declarative-deployment.sh
│   ├── phase-06-additional-tooling.sh
│   ├── phase-07-post-deployment-validation.sh
│   └── phase-08-finalization-and-report.sh
├── lib/                        # 20 modular libraries
│   ├── common.sh              # Utility functions
│   ├── gpu-detection.sh       # Hardware detection
│   ├── tools.sh               # Tool installation (45KB)
│   ├── validation.sh          # System validation
│   ├── state-management.sh    # Resume functionality
│   ├── backup.sh              # Backup operations
│   └── ... (14 more libraries)
├── templates/                  # Nix configuration templates
│   ├── configuration.nix      # System config (1,014 lines)
│   ├── home.nix              # User packages (3,067 lines)
│   ├── flake.nix             # Dependency management
│   └── python-overrides.nix  # Python package fixes
├── scripts/
│   ├── system-health-check.sh # Verification tool (50KB)
│   └── p10k-setup-wizard.sh   # Powerlevel10k theme setup
├── config/
│   ├── variables.sh           # Global configuration
│   ├── defaults.sh            # Default values
│   └── npm-packages.sh        # NPM package manifest
└── docs/                      # Comprehensive documentation
```

### Key Design Patterns

1. **Modular Library System**: Shared functionality extracted to `/lib` for reusability
2. **State-Based Resumption**: Each phase tracks completion in JSON state file
3. **Template + Placeholder System**: Configuration templates with runtime value substitution
4. **Error Handling**: ERR trap inheritance, automatic rollback on failures
5. **Declarative-First**: Prioritizes Nix declarative configs, uses imperative installs only when necessary
6. **Smart Wrappers**: Node.js wrappers for AI CLIs that dynamically find Node.js binary

---

## What Gets Installed

### Desktop Environment

- **COSMIC Desktop**: Modern Rust-based desktop from System76
- **Display Manager**: GDM (GNOME Display Manager)
- **Wayland Support**: Full Wayland compositor support

### Development Tools

**Editors & IDEs:**
- VSCodium (with 20+ extensions pre-configured)
- Neovim (with modern config)
- Cursor (AI-powered IDE via Flatpak)

**AI Coding Assistants:**
- Claude Code (VSCodium extension + CLI)
- Cursor
- Continue
- Codeium
- Aider
- Supermaven
- GPT CLI

**Version Control:**
- Git with GUI tools (GitKraken, GitButler)
- GitHub CLI

**Container Tools:**
- Podman (rootless)
- Podman Compose
- Buildah
- Skopeo

### AI/ML Infrastructure

**Local LLM Runtime:**
- Ollama (containerized)
- Hugging Face Text Generation Inference (systemd service)
- Open WebUI (ChatGPT-like interface)

**Vector Databases:**
- Qdrant (systemd service)
- ChromaDB
- FAISS

**Python ML Packages (60+):**
- **Deep Learning**: PyTorch, TensorFlow, JAX, Keras
- **LLM Frameworks**: LangChain, LangGraph, LlamaIndex
- **Transformers**: Hugging Face Transformers, Diffusers, Accelerate
- **Training Utils**: PEFT, BitsAndBytes, DeepSpeed
- **Vector/Embeddings**: Sentence-Transformers, OpenAI
- **Scientific**: NumPy, Pandas, Scikit-learn, Matplotlib, SciPy

### Programming Languages

- Python 3.11
- Node.js 22
- Go
- Rust
- Ruby

### Flatpak Applications

**Pre-installed (14):**
- Firefox
- Brave Browser
- Obsidian
- OnlyOffice
- Thunderbird
- LM Studio
- Alpaca
- Jan
- Postman
- DBeaver
- Flameshot
- Discord
- Slack
- Zoom

**Optional (50+):** Available via interactive installer

### System Utilities

- Terminal emulators: Kitty, Alacritty, Warp
- Shell: Zsh with Powerlevel10k theme
- File managers: Thunar, Nemo
- Media players: VLC, MPV
- Archive tools: 7zip, unrar, unzip
- Network tools: curl, wget, netcat, nmap
- System monitors: htop, btop, nvtop

---

## Hardware Support

### GPU Detection & Configuration

- **NVIDIA**: Proprietary drivers, CUDA toolkit, cuDNN, NVENC/NVDEC
- **AMD**: ROCm support, VA-API acceleration
- **Intel**: VA-API acceleration, compute runtime

### Multi-GPU Support

- Handles systems with integrated + dedicated GPUs
- Configures appropriate offloading and power management

---

## Deployment Strategies

### Binary Cache (Fast) - 20-40 minutes
- Uses pre-built packages from NixOS cache
- Recommended for most users
- Requires internet connection

### Source Build (Secure) - 60-120 minutes
- Builds everything from source
- For air-gapped or high-security environments
- No binary trust required

### Hybrid
- Binary cache for stable packages
- Source builds for custom configurations

---

## Resilience Features

- **Error Handling**: Automatic rollback on failures
- **State Persistence**: Survives system reboots
- **Pre-flight Validation**: Prevents partial deployments
- **Health Checks**: Validates 60+ packages and services post-deployment
- **Backup System**: Preserves existing configurations

---

## Key Innovations

1. **Hybrid Declarative/Imperative**: Nix for system stability, npm for rapidly-evolving AI tools
2. **Smart Node.js Wrappers**: Dynamically locate Node.js binary for VSCodium integration
3. **Hardware-Aware Templates**: Configuration generation adapts to detected GPU
4. **Comprehensive Validation**: 50KB health check validates entire stack
5. **Resumable Architecture**: JSON state tracking allows recovery from any phase

---

## Use Cases

- **Solo Developers**: Reproducible AI development environments
- **Development Teams**: Standardized tooling across machines
- **Researchers**: Consistent ML experiment environments
- **Educators**: Lab machine setup for AI courses
- **Enterprises**: Infrastructure-as-code for dev environments

---

## System Requirements

- NixOS 25.05 or later
- 50GB+ free disk space (100GB+ recommended)
- Internet connection (for package downloads)
- Sudo privileges
- x86_64 architecture

---

## Project Statistics

- **5,108 lines** of shell scripts
- **4,000+ lines** of Nix configurations
- **800+ managed packages**
- **20 reusable libraries**
- **8-phase deployment workflow**
- **60+ validated Python packages**
- **20+ modular components**

---

## Getting Started

```bash
# Clone the repository
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# Run the deployment
sudo ./nixos-quick-deploy.sh
```

The script will guide you through:
1. Initial validation and hardware detection
2. Configuration generation
3. Deployment execution
4. Post-deployment validation
5. Final system health check

---

## Perfect For

✅ AI/ML developers wanting NixOS reproducibility without complexity
✅ Teams needing identical dev environments across machines
✅ Anyone tired of spending days configuring new systems
✅ Developers wanting local LLM infrastructure
✅ Teams transitioning to declarative infrastructure

---

## License

[Check repository for license details]

---

## Contributing

The modular architecture makes extensions easy:
- Add new AI tools in `lib/tools.sh`
- Customize package selections in templates
- Contribute hardware detection improvements
- Enhance validation checks

---

## Repository

**GitHub**: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy

---

*This is a production-ready, enterprise-grade deployment framework specifically designed for AI/ML developers who want the power of NixOS without the complexity.*
