# NixOS Dev Quick Deploy

**Transform a fresh NixOS installation into a fully-configured AI development powerhouse in 20-40 minutes** (or 60-120 minutes if building from source).

---

## Canonical Deployment Path (Clean)

Use the clean flake-first entrypoint:

```bash
./scripts/deploy-clean.sh
```

For update/upgrade runs:

```bash
./scripts/deploy-clean.sh --update-lock
```

This path is the canonical workflow. Legacy phase/template flow remains migration debt.
See:
- `docs/CLEAN-SETUP.md`
- `docs/REPOSITORY-SCOPE-CONTRACT.md`
- `docs/AQD-CLI-USAGE.md`
- `docs/SKILL-BACKUP-POLICY.md`
- `docs/SKILL-MINIMUM-STANDARD.md`
- `docs/CONFIGURATION-REFERENCE.md`
- `docs/AI-STACK-DATA-FLOWS.md`
- `docs/AI-STACK-TROUBLESHOOTING-GUIDE.md`
- `docs/DEVELOPER-ONBOARDING.md`
- `docs/SECURITY-BEST-PRACTICES.md`

---

## 🚀 Quick Deploy (One Command)

```bash
curl -fsSL https://raw.githubusercontent.com/MasterofNull/NixOS-Dev-Quick-Deploy/main/nixos-quick-deploy.sh | bash
```

Or clone and run locally:

```bash
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git ~/NixOS-Dev-Quick-Deploy
cd ~/NixOS-Dev-Quick-Deploy
chmod +x nixos-quick-deploy.sh
./nixos-quick-deploy.sh
```

**That's it!** Answer a few simple questions (including choosing between binary caches, remote builders/private Cachix, or local source builds), wait 20-120 minutes depending on your choice, reboot, and you're done.

## 🧪 Quick-Deploy Script Modes

`nixos-quick-deploy.sh` now uses the flake-first declarative path by default:

```bash
./nixos-quick-deploy.sh --flake-first-profile ai-dev
```

Optional controls:

```bash
# Dry-run output only
./nixos-quick-deploy.sh --dry-run --skip-switch

# Explicit output target
./nixos-quick-deploy.sh --flake-first-target hyperd-gaming

# Legacy 9-phase pipeline (maintenance mode)
./nixos-quick-deploy.sh --legacy-phases
```

Current state: use `scripts/deploy-clean.sh` for standard operations.
Legacy phase/template mode is deprecated with planned removal on **July 1, 2026**.

## ✨ NEW in v6.0.0: Fully Integrated AI Stack

The AI stack is now a **first-class, public component** of this repository!

### Quick AI Stack Deployment

```bash
# Deploy NixOS + complete AI development environment (single path)
./nixos-quick-deploy.sh --with-k8s-stack
```

This single command gives you:

- ✅ **AIDB MCP Server** - PostgreSQL + TimescaleDB + Qdrant vector database
- ✅ **llama.cpp vLLM** - Local model inference (Qwen, DeepSeek, Phi, CodeLlama)
- ✅ **23 Agent Skills** - Specialized AI agents for code, deployment, testing, design
- ✅ **MCP Servers** - Model Context Protocol servers for AIDB, NixOS, GitHub
- ✅ **Embeddings Service** - Dedicated sentence-transformers API for fast RAG
- ✅ **Hybrid Coordinator** - Local/remote routing with telemetry-driven pattern extraction
- ✅ **Nginx TLS Gateway** - HTTPS termination on `https://localhost:8443`
- ✅ **Shared Data** - Persistent data that survives reinstalls (`~/.local/share/nixos-ai-stack`)

See [`ai-stack/README.md`](ai-stack/README.md) and [`/docs/AI-STACK-FULL-INTEGRATION.md`](/docs/AI-STACK-FULL-INTEGRATION.md) for complete documentation.

---

---

## 📋 What You Get

### Complete System Setup

- **COSMIC Desktop** - Modern, fast desktop environment from System76
- **Hyprland Wayland Session** - Latest Hyprland compositor alongside COSMIC for tiling workflows
- **Performance Kernel Track** - Prefers the tuned `linuxPackages_6_18` build, then falls back to TKG, XanMod, Liquorix, Zen, and finally `linuxPackages_latest`
- **225+ Packages** - Development tools, CLI utilities, and applications
- **Nix Flakes** - Enabled and configured for reproducible builds
- **K3s + containerd** - Kubernetes runtime for the integrated AI stack
- **Flatpak** - Sandboxed desktop applications with profile-aware provisioning and incremental updates
- **Home Manager** - Declarative user environment configuration
- **ZSH + Powerlevel10k** - Beautiful, fast terminal with auto-configuration

### Integrated AI Development Stack

**Fully Integrated Components (v6.0.0):**

<br>

| Component              | Location                        |   Status   | Purpose                                                                |
| :--------------------- | :------------------------------ | :--------: | :--------------------------------------------------------------------- |
| **AIDB MCP Server**    | `ai-stack/mcp-servers/aidb/`    | ✅ Active | PostgreSQL + TimescaleDB + Qdrant vector DB + FastAPI MCP server       |
| **llama.cpp vLLM**      | `ai-stack/kubernetes/`          | ✅ Active | Local OpenAI-compatible inference (Qwen, DeepSeek, Phi, CodeLlama)     |
| **23 Agent Skills**    | `ai-stack/agents/skills/`       | ✅ Active | nixos-deployment, webapp-testing, code-review, canvas-design, and more |
| **Embeddings Service** | `ai-stack/mcp-servers/`         | ✅ Active | Sentence-transformers API for embeddings                               |
| **Hybrid Coordinator** | `ai-stack/mcp-servers/`         | ✅ Active | Local/remote routing + telemetry-driven pattern extraction              |
| **NixOS Docs MCP**     | `ai-stack/mcp-servers/`         | ✅ Active | NixOS/Nix documentation search API                                     |
| **Nginx TLS Gateway**  | `ai-stack/kubernetes/`          | ✅ Active | HTTPS termination on `https://localhost:8443`                          |
| **MCP Servers**        | `ai-stack/mcp-servers/`         | ✅ Active | Model Context Protocol servers for AIDB, NixOS, GitHub                 |
| **Model Registry**     | `ai-stack/models/registry.json` | ✅ Active | Model catalog with metadata, VRAM, speed, quality scores               |
| **Vector Database**    | PostgreSQL + Qdrant             | ✅ Active | Semantic search and document embeddings                                |
| **Redis Cache**        | Redis + Redis Insight           | ✅ Active | High-performance caching layer                                         |

**AI Development Tools:**

| Tool            | Integration                      | Purpose                                                      |
| --------------- | -------------------------------- | ------------------------------------------------------------ |
| **Claude Code** | VSCodium extension + CLI wrapper | AI pair programming inside VSCodium                          |
| **Cursor**      | Flatpak + launcher               | AI-assisted IDE with GPT-4/Claude                            |
| **Continue**    | VSCodium extension               | In-editor AI completions                                     |
| **Codeium**     | VSCodium extension               | Free AI autocomplete                                         |
| **GPT CLI**     | Command-line tool                | Query OpenAI-compatible endpoints (local llama.cpp or remote) |
| **Aider**       | CLI code assistant               | AI pair programming from terminal                            |
| **LM Studio**   | Flatpak app                      | Desktop LLM manager                                          |

**Quick Start:**

```bash
./nixos-quick-deploy.sh --with-k8s-stack  # Deploy everything
kubectl get pods -n ai-stack             # Check status
python3 ai-stack/tests/test_hospital_e2e.py
```

### AI Stack Security Considerations

- **TLS by default**: External APIs are exposed via nginx at `https://localhost:8443` (self-signed cert).
- **API keys required**: Core APIs enforce `X-API-Key` from the encrypted secrets bundle (`ai-stack/kubernetes/secrets/secrets.sops.yaml`).
- **Local-only tools**: Open WebUI, MindsDB, and metrics UIs bind to `127.0.0.1`.
- **Privileged self-heal**: The health monitor runs only under the `self-heal` profile (opt-in).

### Pre-Installed Development Tools

**Languages & Runtimes:**

- Python 3.13 with 60+ AI/ML packages (PyTorch, TensorFlow, LangChain, etc.) and `uv` installed as a drop-in replacement for `pip` (aliases for `pip`/`pip3` point to `uv pip`).  
  <sub>Set `PYTHON_PREFER_PY314=1` before running the deployer to trial Python 3.14 once the compatibility mask is cleared.</sub>
- Node.js 22, Go, Rust, Ruby

**AI/ML Python Packages (Built-in):**

- **Deep Learning:** PyTorch, TensorFlow, Transformers, Diffusers
- **LLM Frameworks:** LangChain, LlamaIndex, OpenAI, Anthropic clients
- **Vector DBs:** ChromaDB, Qdrant client, FAISS, Sentence Transformers
- **Data Science:** Pandas, Polars, Dask, Jupyter Lab, Matplotlib
- **Code Quality:** Black, Ruff, Mypy, Pylint
- **Agent Ops & MCP:** LiteLLM, Tiktoken, FastAPI, Uvicorn, HTTPX, Pydantic, Typer, Rich, SQLAlchemy, DuckDB

**Editors & IDEs:**

- VSCodium Insiders (VS Code without telemetry, rolling build)
- Neovim (modern Vim)
- Cursor (AI-powered editor)

**Version Control:**

- Git, Git LFS, Lazygit
- GitLens, Git Graph (VSCodium extensions)

**Modern CLI Tools:**

- `ripgrep`, `fd`, `fzf` - Fast search tools
- `bat`, `eza` - Enhanced cat/ls with syntax highlighting
- `jq`, `yq` - JSON/YAML processors
- `htop`, `btop`, vendor-specific GPU monitors (e.g., `nvtop` when available) - System and GPU monitoring dashboards (AMD-specific tools auto-installed when detected)
- `Glances`, `Grafana`, `Prometheus`, `Loki`, `Promtail`, `Vector`, `Cockpit` - Full observability and logging stack
- `gnome-disk-utility`, `parted` - Disk formatting and partitioning
- `lazygit` - Terminal UI for Git
- `pnpm`, `biome`, `pixi`, `ast-grep`, `atuin`, `zellij`, `distrobox` - Faster package managers, JS formatter/linter, code-aware search, shell history sync, terminal multiplexing, and mutable container convenience
- `nix-fast-build`, `lorri`, `cachix` - Nix build acceleration and cache tooling
- `sccache`, `cargo-binstall`, `gofumpt`, `staticcheck` - Faster Rust/Go builds and linters

**Nix Ecosystem:**

- `nix-tree` - Visualize dependency trees
- `nixpkgs-fmt`, `alejandra` - Nix code formatters
- `statix` - Nix linter
- `nix-index` - File search in nixpkgs

**Container Tools:**

- K3s, kubectl, containerd

**AI Services (Systemd):**

- Qdrant (vector database, enabled by default)
- Hugging Face TGI (LLM inference server, manual enable)
- Jupyter Lab (web-based notebooks, user service)

### Flatpak Applications

Pick the profile that matches your workflow during Phase 6:

- **Core** – Balanced desktop with browsers, media tools, and developer essentials.
- **AI Workstation** – Core profile plus Postman, DBeaver, VS Code, Bitwarden, and other data tooling.
- **Minimal** – Lean recovery environment with Firefox, Obsidian, Flatseal.

The installer records your selection in `$STATE_DIR/preferences/flatpak-profile.env` and only applies deltas on future runs, dramatically cutting repeat deployment time. You can switch profiles any time—state is cached in `$STATE_DIR/preferences/flatpak-profile-state.env` so already-installed apps are preserved when possible.

**Need more?** Over 50 additional apps remain available on Flathub, and the provisioning service respects manual changes—only diverging packages in the active profile are synced.

---

## ⚡ Quick Start Guide

### Step 1: Run the Script

```bash
cd ~/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

### Step 2: Answer 4 Questions (plus build acceleration prompts)

1. **GitHub username** → For git config
2. **GitHub email** → For git config
3. **Editor preference** → vim/neovim/vscodium (choose 1-3)
4. **Replace config?** → Press Enter (yes)

After the initial survey, Phase 1 now asks how you want to accelerate builds:

1. **Binary caches** _(default)_ – Fastest path, uses NixOS/nix-community/CUDA caches.
2. **Build locally** – Compile everything on the target host for maximal control.
3. **Remote builders or private Cachix** – Layer SSH build farm(s) and/or authenticated Cachix caches on top of the binary caches option.

If you choose option 3, be ready to paste builder strings (e.g., `ssh://nix@builder.example.com x86_64-linux - 4 1`) and any Cachix cache names/keys. Secrets are stored under `$STATE_DIR/preferences/remote-builders.env` for reuse later.

### Step 3: Wait (20-35 minutes)

The script automatically:

- ✅ Updates NixOS system config (COSMIC, K3s, Flakes)
- ✅ Runs `sudo nixos-rebuild switch`
- ✅ Creates home-manager configuration (~100 packages)
- ✅ Runs `home-manager switch`
- ✅ Installs Flatpak apps (Flathub remote + selected profile)
- ✅ Builds flake development environment
- ✅ Installs Claude Code CLI + wrapper
- ✅ Configures VSCodium for AI development
- ✅ Sets up Powerlevel10k theme
- ✅ Verifies all packages are accessible

**No manual intervention needed** - everything is fully automated.

### Step 4: Reboot

```bash
sudo reboot
```

At login, select **"Cosmic"** from the session menu.

### Step 5: First Terminal Launch

When you open a terminal, **Powerlevel10k wizard runs automatically**:

- Choose prompt style
- Choose color scheme (High Contrast Dark recommended)
- Choose what to show (time, icons, path)
- Restart shell - beautiful prompt ready!

### Step 6: Verify Everything Works

**Run the automated health check:**

```bash
cd ~/NixOS-Dev-Quick-Deploy
./system-health-check.sh
```

The quick deploy runs this automatically after Phase 8, but you can rerun it anytime to confirm your setup.

This will verify:

- ✅ All core tools (k3s, kubectl, python3, node, etc.)
- ✅ Nix ecosystem (home-manager, flakes)
- ✅ AI tools (claude-wrapper, gpt-codex-wrapper, codex-wrapper, openai-wrapper, gooseai-wrapper, ollama, aider)
- ✅ **Python AI/ML packages (60+ packages)**:
  - Deep Learning: PyTorch, TensorFlow
  - LLM Frameworks: LangChain, LlamaIndex, OpenAI, Anthropic
  - Vector DBs: ChromaDB, Qdrant client, FAISS, Sentence Transformers
  - Data Science: Pandas, Polars, Dask, Jupyter Lab
  - Code Quality: Black, Ruff, Mypy
- ✅ Editors (VSCodium, Cursor, Neovim)
- ✅ Shell configuration (aliases, functions)
- ✅ Flatpak applications (including DBeaver)
- ✅ **AI Systemd Services** (Qdrant, Hugging Face TGI, Jupyter Lab, Gitea)
- ✅ Environment variables & PATH

### K3s Runtime (Single Path)

The AI stack runs on K3s + containerd. Verify the runtime is ready:

**Verify manually:**

```bash
# Check core tools
kubectl version --client
python3 --version
node --version
go version
cargo --version

# Check Nix tools
home-manager --version
nix flake --help

# Check AI tools
which claude-wrapper
which gpt-codex-wrapper
which codex-wrapper
which openai-wrapper
which gooseai-wrapper
ollama --version
aider --version

# Check editors
codium --version
code-cursor --help
nvim --version

# Enter development environment
aidb-dev

# Check Flatpak apps
flatpak list --user
```

**If any checks fail:**

```bash
# Attempt automatic fixes
./system-health-check.sh --fix

# Reload shell environment
source ~/.zshrc

# Or restart shell
exec zsh

# Re-apply home-manager config
cd ~/.dotfiles/home-manager
home-manager switch --flake .#$(whoami)
```

**All done!** Everything is installed and ready to use.

---

## 🛠️ Useful Commands

### System Health & Diagnostics

**Comprehensive health check for all packages and services:**

```bash
./system-health-check.sh           # Run full system health check
./system-health-check.sh --detailed  # Show detailed output with versions
./system-health-check.sh --fix     # Attempt automatic fixes
```

**Checks include:**

- Core system tools (k3s, kubectl, git, curl, etc.)
- Programming languages (Python, Node.js, Go, Rust)
- Nix ecosystem (home-manager, flakes)
- AI tools (Claude Code, llama.cpp, Aider)
- **60+ Python AI/ML packages** (PyTorch, TensorFlow, LangChain, etc.)
- Editors and IDEs (VSCodium, Neovim, Cursor)
- Shell configuration (ZSH, aliases, functions)
- Flatpak applications (Firefox, Obsidian, DBeaver, etc.)
- **AI systemd services** (Qdrant, Hugging Face TGI, Jupyter Lab)
- Environment variables and PATH configuration

### System Management

```bash
nrs              # Alias for: sudo nixos-rebuild switch
hms              # Alias for: home-manager switch
nfu              # Alias for: nix flake update
```

**Flake Update Procedure:**
```bash
cd ~/.dotfiles/home-manager
nix flake update                # or: nfu
sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager#$(hostname)
home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)
```

### Development Environments

```bash
aidb-dev         # Enter flake dev environment with all tools
aidb-shell       # Alternative way to enter dev environment
aidb-info        # Show environment information
aidb-update      # Update flake dependencies
```

**Note:** If `aidb-dev` is not found, reload your shell:

```bash
source ~/.zshrc  # Or: exec zsh
```

### AI Stack Management (K3s)

```bash
kubectl get pods -n ai-stack
kubectl rollout restart -n ai-stack deployment/aidb
kubectl logs -n ai-stack deploy/aidb
```

### CPU/iGPU-first model defaults

Quick Deploy defaults to CPU/iGPU-friendly models unless VRAM/RAM allow larger GGUFs. The CPU/iGPU baseline uses `qwen3-4b` for the coder model and `sentence-transformers/all-MiniLM-L6-v2` for embeddings.

Swap models at any time:

```bash
./scripts/swap-llama-cpp-model.sh Qwen3-4B-Instruct-2507-Q4_K_M.gguf
./scripts/swap-embeddings-model.sh BAAI/bge-small-en-v1.5
```

All other AI orchestration (vLLM endpoints, shared volumes, etc.) is managed by the ai-optimizer repository layered on top of this stack.

**CLI Tools:**

```bash
# Query LLMs from command line
gpt-cli "explain this code"

# Run aider (AI coding assistant)
aider

# Start Jupyter Lab manually
jupyter-lab

# Install Obsidian AI plugins
obsidian-ai-bootstrap
```

### Container Management

```bash
kubectl get pods -n ai-stack
kubectl get svc -n ai-stack
```

### VSCodium / AI CLI wrappers

**VSCodium Version Compatibility:**

- VSCodium Insiders (rolling build; installed by this script)
- Claude Code extension works with VSCodium and VS Code 1.85.0+
- Smart wrappers ensure Node.js is found correctly for each CLI

**Usage:**

```bash
# Launch VSCodium with Claude integration
codium

# Launch with environment debugging
CODIUM_DEBUG=1 codium

# Test wrappers directly
~/.npm-global/bin/claude-wrapper --version
~/.npm-global/bin/gpt-codex-wrapper --version
~/.npm-global/bin/codex-wrapper --version
~/.npm-global/bin/openai-wrapper --version
~/.npm-global/bin/gooseai-wrapper --version
goose --version

# Launch Goose Desktop (search "Goose Desktop" in your application menu)
# Provided by the declarative xdg.desktopEntries configuration

# Debug Claude wrapper
CLAUDE_DEBUG=1 ~/.npm-global/bin/claude-wrapper --version
# Debug GPT CodeX wrapper
GPT_CODEX_DEBUG=1 ~/.npm-global/bin/gpt-codex-wrapper --version
# Debug Codex wrapper
CODEX_DEBUG=1 ~/.npm-global/bin/codex-wrapper --version
# Debug OpenAI wrapper
OPENAI_DEBUG=1 ~/.npm-global/bin/openai-wrapper --version
# Debug GooseAI wrapper
GOOSEAI_DEBUG=1 ~/.npm-global/bin/gooseai-wrapper --version
```

### Cursor IDE

```bash
# Launch Cursor (prefers Flatpak, falls back to native)
code-cursor

# Launch specific project
code-cursor /path/to/project
```

**Note:** Cursor must be installed via Flatpak:

```bash
flatpak install flathub ai.cursor.Cursor
```

---

## 🔧 Configuration Files

| File                                    | Description            | Managed By                                                                     |
| --------------------------------------- | ---------------------- | ------------------------------------------------------------------------------ |
| `/etc/nixos/configuration.nix`          | System configuration   | Script auto-updates                                                            |
| `~/.dotfiles/home-manager/home.nix`     | User packages & config | Script auto-creates                                                            |
| `~/.dotfiles/home-manager/flake.nix`    | Home-manager flake     | Script auto-creates                                                            |
| `~/.config/VSCodium/User/settings.json` | VSCodium settings      | Home-manager (declarative)                                                     |
| `~/.config/p10k/theme.sh`               | Powerlevel10k theme    | Wizard auto-generates                                                          |
| `~/.zshrc`                              | ZSH configuration      | Home-manager (declarative)                                                     |
| `~/.npmrc`                              | NPM configuration      | Script auto-creates                                                            |
| `~/.npm-global/`                        | Global NPM packages    | AI CLI wrappers installed here (Claude, GPT CodeX, Codex IDE, OpenAI, GooseAI) |

---

## 📁 Required Paths & Overrides

These locations must be writable for a successful deploy. The script validates them at startup and will warn/fallback if overrides are unusable.

| Path / Variable | Default | Purpose |
| --- | --- | --- |
| `XDG_CACHE_HOME` | `$HOME/.cache` | Base for quick-deploy cache + logs |
| `XDG_STATE_HOME` | `$HOME/.local/state` | Base for AIDB runtime logs |
| `XDG_DATA_HOME` | `$HOME/.local/share` | Base for AI stack persistent data |
| `TMPDIR` | `/tmp` | Temporary files/logs during deploy & tooling |
| `${XDG_CACHE_HOME:-$HOME/.cache}/nixos-quick-deploy` | (derived) | Deploy state + logs |
| `${XDG_DATA_HOME:-$HOME/.local/share}/nixos-ai-stack` | (derived) | AI stack data (Qdrant, Postgres, Redis, etc.) |
| `${XDG_DATA_HOME:-$HOME/.local/share}/nixos-system-dashboard` | (derived) | Dashboard JSON data cache |
| `${XDG_STATE_HOME:-$HOME/.local/state}/nixos-ai-stack/aidb-mcp.log` | (derived) | AIDB MCP server log |

Overrides:
- Set `TMPDIR`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, or `XDG_DATA_HOME` before running the deploy script.
- Use `./nixos-quick-deploy.sh --prefix /path/to/dotfiles` to relocate the generated Home Manager/NixOS config workspace.
- For systemd templates that use `@PROJECT_ROOT@`/`@AI_STACK_DATA@`, run `scripts/apply-project-root.sh` before installing.

---

## 📁 Project Structure

```
NixOS-Dev-Quick-Deploy/
├── nixos-quick-deploy.sh          # Main deployment script (run this)
├── scripts/
│   ├── system-health-check.sh     # System health verification and repair tool
│   └── p10k-setup-wizard.sh       # Powerlevel10k configuration wizard
├── templates/
│   ├── configuration.nix          # NixOS system config template
│   ├── home.nix                   # Home-manager config template
│   └── flake.nix                  # Development flake template
├── docs/
│   ├── AIDB_SETUP.md              # AIDB setup and configuration guide
│   ├── AGENTS.md                  # AI agent workflow documentation
│   ├── CODE_REVIEW.md             # Code review and quality documentation
│   └── SAFE_IMPROVEMENTS.md       # Safe improvement guidelines
├── README.md                      # This file
└── LICENSE                        # MIT License
```

---

## 🎯 What Happens Step-by-Step

<details>
<summary><b>Click to expand detailed execution flow</b></summary>

### 1. Prerequisites Check

```
✓ Running as user (not root)
✓ NixOS detected
✓ Internet connection available
✓ sudo access confirmed
```

### 2. User Information Gathering

```
→ GitHub username: yourusername
→ GitHub email: you@example.com
→ Editor preference: 3 (vscodium)
```

### 3. System Configuration Update

```
✓ Backing up /etc/nixos/configuration.nix
✓ Adding COSMIC desktop configuration
✓ Adding K3s + containerd runtime support
✓ Enabling Nix flakes
✓ Allowing unfree packages
Running: sudo nixos-rebuild switch
✓ NixOS system configuration applied!
```

### 4. Home-Manager Setup

```
✓ Creating ~/.dotfiles/home-manager/
✓ Writing home.nix with ~150 packages
✓ Writing flake.nix
✓ Creating flake.lock
Running: home-manager switch
✓ Home-manager configuration applied!
✓ Updating current shell environment
✓ Verifying package installation
  ✓ python3 found at ~/.nix-profile/bin/python3
  ✓ All critical packages in PATH!
```

### 5. Flatpak Setup

```
✓ Flathub remote added
✓ Installing Firefox
✓ Installing Obsidian
✓ Installing Cursor
✓ Installing LM Studio
✓ Installing 7 more apps...
✓ All Flatpak applications installed!
```

Flatpak provisioning is now state-aware. The deployer inspects `~/.local/share/flatpak` before touching anything, keeps existing repositories intact, and only installs packages that are missing from your selected profile or the project’s core Flatpak set. To force a clean slate, pass `--flatpak-reinstall`; otherwise the run simply layers the new defaults onto your current desktop. Need to re-seed the Hugging Face caches used by the DeepSeek and Scout TGI services? Add `--force-hf-download` so Phase 5 wipes both caches and pulls fresh weights before the switch.

Need Qalculate? It now ships from `pkgs.qalculate-qt` in the declarative package set, so the Flatpak profile stays lean even when Flathub temporarily removes the app. Goose CLI/Desktop are likewise provided by `pkgs.goose-cli`, eliminating the brittle `.deb` download in Phase 6.

### 6. Flake Development Environment

```
✓ Nix flakes enabled
Building flake development environment...
✓ Flake built and cached
✓ Created aidb-dev-env activation script
✓ Added AIDB flake aliases to .zshrc
```

### 7. AI CLI Integration

```
✓ Installing Claude Code via native installer (https://claude.ai/install.sh)
✓ Installing @openai/codex (GPT CodeX CLI) via npm
✓ Installing openai via npm
✓ Goose CLI detected via nixpkgs (goose-cli)
✓ Claude Code native binary installed
✓ GPT CodeX wrapper created from @openai/codex
✓ OpenAI CLI npm package installed
ℹ Registering Goose Desktop launcher
✓ Goose Desktop launcher available via application menu
✓ Created smart Node.js wrapper at ~/.npm-global/bin/claude-wrapper
✓ Created smart Node.js wrapper at ~/.npm-global/bin/gpt-codex-wrapper
✓ Created smart Node.js wrapper at ~/.npm-global/bin/codex-wrapper
✓ Created smart Node.js wrapper at ~/.npm-global/bin/openai-wrapper
✓ Created smart Node.js wrapper at ~/.npm-global/bin/gooseai-wrapper
✓ Testing wrappers succeeded
✓ VSCodium wrapper configuration updated
✓ Claude Code configured in VSCodium
```

### 8. VSCodium Extensions

```
Installing Claude Code extension...
✓ Anthropic.claude-code installed
Installing additional extensions...
⚠ GPT CodeX and GooseAI extensions are not published on Open VSX (install from the VS Marketplace if you need them)
✓ Python, Pylance, Black Formatter
✓ Jupyter, Continue, Codeium
✓ GitLens, Git Graph, Error Lens
✓ Go, Rust Analyzer, YAML, TOML
✓ Docker, Terraform
✓ Remaining extensions installed!
```

### 9. Completion

```
============================================
✓ NixOS Quick Deploy COMPLETE!
============================================

Next steps:
  1. Reboot: sudo reboot
  2. Select "Cosmic" at login
  3. Open terminal (P10k wizard auto-runs)
  4. Verify: codium, claude --version, claude-wrapper --version, gpt-codex-wrapper --version, codex-wrapper --version, openai-wrapper --version, gooseai-wrapper --version, goose --version
```

</details>

---

## 🐛 Troubleshooting

### Claude Code Error 127 in VSCodium

**Symptom:** VSCodium shows "Error 127" when trying to use Claude Code

**Cause:** Claude wrapper can't find Node.js executable

**Solutions:**

1. **Run the diagnostic wrapper:**

   ```bash
   CLAUDE_DEBUG=1 ~/.npm-global/bin/claude-wrapper --version
   ```

   This shows exactly where it's searching for Node.js.

2. **Verify Node.js is installed:**

   ```bash
   which node
   node --version
   ```

   If this fails, Node.js wasn't installed properly.

3. **Restart your shell to refresh PATH:**

   ```bash
   exec zsh
   ```

4. **Re-apply home-manager config:**

   ```bash
   home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)
   ```

5. **Reinstall Claude Code (native installer):**

   ```bash
   curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash
   ```

6. **Check VSCodium settings:**

   ```bash
   cat ~/.config/VSCodium/User/settings.json | grep -A5 "claude-code"
   ```

### ImagePullBackOff in ai-stack pods

**Symptom:** `kubectl get pods -n ai-stack` shows `ImagePullBackOff` or `ErrImagePull`.

**Fix:**
```bash
ONLY_IMAGES=aidb BUILD_TOOL=buildah SKIP_K3S_IMPORT=true ./scripts/build-k3s-images.sh
ONLY_IMAGES=ai-stack-aidb CONTAINER_CLI=skopeo ./scripts/publish-local-registry.sh
kubectl -n ai-stack rollout restart deploy/aidb
```

### K3s API not reachable from pods (connection refused)

**Symptom:** Pods fail to access `https://kubernetes.default.svc/api` with connection refused.

**Fix:**
```bash
sudo iptables -I INPUT -p tcp -s 10.42.0.0/16 --dport 6443 -j ACCEPT
sudo iptables -I INPUT -p tcp -s 10.43.0.0/16 --dport 6443 -j ACCEPT
```
Then persist via NixOS rebuild (see `templates/configuration.nix` firewall allowlist notes).

### Dashboard server service exits with code 127

**Symptom:** `systemctl --user status dashboard-server.service` shows exit code 127.

**Fix:**
```bash
./scripts/setup-dashboard.sh
systemctl --user daemon-reload
systemctl --user restart dashboard-server.service
```

### Health check fails on optional Python packages

**Symptom:** Health check reports missing LlamaIndex/ChromaDB/Gradio.

**Fix:**
```bash
pip install -r ~/.config/ai-agents/requirements.txt
```

### Nix channel update fails with max-jobs=0

**Symptom:** `nix-channel --update` fails with “Unable to start any build”.

**Fix:**
```bash
NIX_CONFIG="max-jobs = 1" nix-channel --update
```
Then set `nix.settings.max-jobs = "auto"` in the generated configs.

   Should show `executablePath` pointing to `~/.npm-global/bin/claude-wrapper`

7. **Verify no Flatpak overrides exist:**
   ```bash
   flatpak info com.visualstudio.code 2>/dev/null || echo "No conflicting Flatpak"
   ```
   Remove any `com.visualstudio.code*` or `com.vscodium.codium*` Flatpak apps—they replace the declarative `programs.vscode` package and undo the managed settings/extensions.

### Claude Code "Prompt is too long" in VSCodium

**Symptom:** Claude Code stops with "Prompt is too long"

**Cause:** Context sharing can send too much workspace data or MCP context for the model window.

**Fix (default templates):** The templates now disable context sharing by default. Re-run deploy or update your settings:

```bash
rg '"claudeCode.enableContextSharing"' ~/.config/VSCodium/User/settings.json
```

Set it to `false`, then restart VSCodium.

### VSCodium Git Initialization Error

**Symptom:** VSCodium notifications show:

```
Unable to initialize Git; AggregateError(2)
    Error: Unable to find git
    Error: Unable to find git
```

**Cause:** GUI launches of VSCodium sometimes miss `~/.nix-profile/bin` on `PATH`, so the editor cannot locate the Git binary that Home Manager installs. Without explicit configuration, the built-in Git extension immediately fails.

**Fix (v4.2.0+):** The declarative settings now set `"git.path"` to the exact derivation path of `config.programs.git.package`. Re-run the deploy script or `home-manager switch` so `~/.config/VSCodium/User/settings.json` picks up that value.

**Manual verification:**

1. Confirm Git works in a terminal:
   ```bash
   git --version
   ```
2. Inspect the VSCodium settings file and ensure the stored path matches your `git` derivation:
   ```bash
   rg '"git.path"' ~/.config/VSCodium/User/settings.json
   ```
3. Relaunch VSCodium. The Git panel should populate without the AggregateError message.

### Flatpak Repository Creation Error

**Symptom:** Phase 6 logs show repeated errors when adding Flathub, for example:

```
ℹ Adding Flathub Flatpak remote...
    → error: Unable to create repository at $HOME/.local/share/flatpak/repo (Creating repo: mkdirat: No such file or directory)
```

**Cause:** When Phase 6 runs on its own (or after a cleanup flag), the user-level Flatpak directories may be missing or the repo path may be an empty placeholder without the expected `objects/` tree. In both cases `flatpak remote-add` fails before it can download anything.

**Fix (v4.2.1+):** The Flatpak automation now recreates `~/.local/share/flatpak` and `~/.config/flatpak`, verifies ownership, and removes empty repo stubs so Flatpak can bootstrap a fresh OSTree repository. Re-run the deploy script or restart Phase 6 and the remote should be added cleanly.

**Manual verification:**

1. Confirm the directories exist:
   ```bash
   ls -ld ~/.local/share/flatpak ~/.local/share/flatpak/repo ~/.config/flatpak
   ```
2. If you previously created `~/.local/share/flatpak/repo` manually and it’s missing the `objects/` directory, remove the empty stub and rerun Phase 6:
   ```bash
   rm -rf ~/.local/share/flatpak/repo
   ```
3. Retry the add manually if needed:
   ```bash
   flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
   ```

### VSCodium Settings Read-Only Error

**Symptom:** VSCodium shows error when trying to save settings:

```
Failed to save 'settings.json': Unable to write file (EROFS: read-only file system)
```

**Cause:** Home Manager renders `settings.json` inside `/nix/store` so it can symlink the file into `~/.config/VSCodium`. Editors therefore see a read-only filesystem and refuse to save.

**Fix (v4.0.0+):** The deployment now snapshots `~/.config/VSCodium/User/settings.json` before each Home Manager switch, reapplies the snapshot afterwards, and ensures the final file is a writable copy stored in:

```
~/.config/VSCodium/User/settings.json
~/.local/share/nixos-quick-deploy/state/vscodium/settings.json  # backup copy
```

VSCodium can now edit `settings.json` normally and your changes persist across rebuilds because the activation hook restores the snapshot after Home Manager finishes linking.

**Need reproducible settings?**

You can still keep long-term configuration in `templates/home.nix → programs.vscode.profiles.default.userSettings`. The declarative defaults are written into the store, and the activation hook will seed your mutable copy with those defaults whenever the backup is missing. A suggested workflow:

1. Make quick edits directly inside VSCodium (they land in the mutable file).
2. Periodically copy the keys you care about back into `templates/home.nix` so future machines inherit them.
3. Rerun the deploy script so the declarative defaults and your mutable copy stay in sync.

### Packages Not in PATH

**Issue:** `kubectl: command not found`, `home-manager: command not found`, or AI CLI wrappers (claude/gpt-codex/openai/gooseai) not found after installation

**Solution:**

```bash
# Run health check with automatic fixes
./system-health-check.sh --fix

# Restart shell to load new PATH
exec zsh

# Or manually source session vars
source ~/.nix-profile/etc/profile.d/hm-session-vars.sh

# Verify
which kubectl
which home-manager
which claude-wrapper
which gpt-codex-wrapper
which codex-wrapper
which openai-wrapper
which gooseai-wrapper
```

### Boot Fails With "Root Account Is Locked" / Emergency Mode Loop

**Symptom:** System drops into emergency mode with messages such as:

```

[FAILED] Failed to start Virtual Console Setup.
[FAILED] Failed to start Switch Root.
Cannot open access to console, the root account is locked.
See sulogin(8) man page for more details.
Press Enter to continue.

````

The system gets stuck in an endless "Press Enter to continue" loop.

**Cause:** The NixOS configuration did not define a root user password. When the system encounters boot issues and drops to emergency mode, it requires root access via `sulogin`. Without a root password configured, `sulogin` cannot provide a shell.

Additionally, the console font (`Lat2-Terminus16`) requires the `terminus_font` package, and without `console.earlySetup = true`, the Virtual Console Setup service fails during initrd.

**Fix (for existing installations):**

1. Boot from a NixOS live USB/ISO
2. Mount your root filesystem:
   ```bash
   sudo mount /dev/nvme0n1p2 /mnt  # Adjust device as needed
   sudo mount /dev/nvme0n1p1 /mnt/boot  # EFI partition
```

3. Enter a chroot environment:
   ```bash
   sudo nixos-enter --root /mnt
   ```
4. Set a root password:
   ```bash
   passwd root
   ```
5. Regenerate and rebuild:
   ```bash
   cd /path/to/NixOS-Dev-Quick-Deploy
   ./nixos-quick-deploy.sh --resume
   sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager#$(hostname)
   ```

**Prevention:** The deployment script now automatically syncs the root password with the primary user and configures the console with `earlySetup = true` and the required `terminus_font` package.

---

### Boot Fails With "Failed to mount /var/lib/containers/storage/overlay/..."

**Symptom:** System drops into emergency mode during boot with messages such as:

```
[FAILED] Failed to mount /var/lib/containers/storage/overlay/df4bd49...
[DEPEND] Dependency failed for Local File Systems
```

**Cause:** Older container deployments could leave stale storage configuration behind. The K3s path uses containerd, so legacy `/var/lib/containers` mounts should not be referenced by current runs. If you still see container storage mount failures, it usually means a legacy unit is still enabled.

**Fix:** Re-run Quick Deploy with `--reset-state`, then rebuild:
```bash
cd ~/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --reset-state
sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager
```

If the error persists, check for lingering units:
```bash
systemctl list-units | rg -i "containers"
```

### K3s Runtime Issues

**Symptom:** Pods stuck in `ImagePullBackOff` or `CrashLoopBackOff`.

**Fix:**
```bash
kubectl get pods -n ai-stack
kubectl describe pod -n ai-stack <pod>
kubectl logs -n ai-stack deploy/<service>
```

### COSMIC Desktop Not Appearing

**Issue:** Only GNOME/KDE shows at login screen

**Solution:**

```bash
# Verify COSMIC is in system config
grep -i cosmic /etc/nixos/configuration.nix

# Should show: services.desktopManager.cosmic.enable = true;

# If missing, rebuild
sudo nixos-rebuild switch
sudo reboot
```

### Home-Manager Conflicts

**Issue:** `home-manager switch` fails with "existing file conflicts"

**Solution:**

```bash
# Script automatically backs up conflicts to:
ls -la ~/.config-backups/

# If manual intervention needed, move conflicting files
mv ~/.config/problematic-file ~/.config-backups/
home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)
```

### Flatpak Apps Not Launching

**Issue:** Flatpak app installed but won't start

**Solution:**

```bash
# Check if app is actually installed
flatpak list --user | grep -i appname

# Try running from command line to see errors
flatpak run org.mozilla.firefox

# Reinstall if needed
flatpak uninstall org.mozilla.firefox
flatpak install flathub org.mozilla.firefox
```

### OpenSkills Custom Tooling Hook

Phase 6 now installs the upstream OpenSkills automation toolkit directly from `https://github.com/numman-ali/openskills.git` (via `npm install -g openskills`). After the CLI is installed or updated, the deployer runs `~/.config/openskills/install.sh` automatically so you can layer project-specific helpers on top.

**Note:** The deployer still creates `~/.config/openskills/install.sh` as an executable placeholder. Edit that file with the commands you want run during Phase 6 and keep your workflows reproducible.

### Flatpak Packages Removed Before Switch

**Issue:** Pre-switch cleanup wipes Flatpak apps (the directories under `.local/share/flatpak` or `.var/app` get deleted before `home-manager switch`).  
**Fix:** The deployer now preserves user Flatpak directories whenever it detects installed apps, cached profile state, or existing Flatpak data. Cleanup only happens if you explicitly opt in.

**Solution:**

```bash
# Default behavior: nothing to do, rerun the deployer and Flatpaks stay intact
./nixos-quick-deploy.sh

# Need a full reset? Opt in before running the deployer:
#   (1) CLI flag:
./nixos-quick-deploy.sh --flatpak-reinstall

# Force a clean Hugging Face cache for both TGI services
./nixos-quick-deploy.sh --force-hf-download
#   (2) Or environment variable:
RESET_FLATPAK_STATE_BEFORE_SWITCH=true ./nixos-quick-deploy.sh
```

### Multiple Flatpak Platform Runtimes

**Issue:** `flatpak list --user` shows multiple versions of Freedesktop Platform (24.08, 25.08, etc.)

**This is NORMAL!** Different Flatpak applications depend on different runtime versions. For example:

- Firefox might need Platform 24.08
- Cursor might need Platform 25.08
- Some apps need both stable and extra codecs

**Cleanup unused runtimes:**

```bash
# See what would be removed (safe, dry-run)
flatpak uninstall --unused

# Actually remove unused runtimes
flatpak uninstall --unused -y
```

**Note:** Only runtimes not needed by any installed app will be removed.

### Powerlevel10k Prompt Hard to Read

**Issue:** Text blends with background colors

**Solution:**

```bash
# Re-run wizard
rm ~/.config/p10k/.configured
exec zsh

# Choose option 1: High Contrast Dark
# Or option 7: Custom High Contrast
```

### MangoHud Overlay Appears Everywhere

**Issue:** MangoHud injects into every GUI/terminal session, covering windows you do not want to benchmark, including COSMIC desktop applets and system windows.

**Fix:** The shipped MangoHud presets now include the `no_display=1` option for the desktop profile and blacklist COSMIC system applications (Files, Terminal, Settings, Store, launcher, panel, etc.) for all other profiles. This prevents overlays from appearing on desktop utilities.

**Solution:** Fresh deployments now default to profile **4) desktop**, which keeps MangoHud inside the mangoapp desktop window so no other applications are wrapped. You only need the selector if you want to change this default.

**For existing systems with the overlay bug:** Run the fix script to update your MangoHud configuration:

```bash
./scripts/fix-mangohud-config.sh
# Then re-run the deployment to regenerate your configs with the corrected settings
./nixos-quick-deploy.sh
```

If you want to change the MangoHud profile:

```bash
# Run the interactive selector and pick the overlay mode you prefer
./scripts/mangohud-profile.sh

# Re-apply your Home Manager config so the new preference is enforced
cd ~/.dotfiles/home-manager
home-manager switch -b backup --flake .
```

- `1) disabled` removes MangoHud from every app.
- `2) light` and `3) full` keep the classic per-application overlays.
- `4) desktop` launches a transparent, movable mangoapp window so stats stay on the desktop instead of stacking on top of apps. (Default)
- `5) desktop-hybrid` auto-starts the mangoapp desktop window while still injecting MangoHud into supported games/apps.

The selected profile is cached at `~/.cache/nixos-quick-deploy/preferences/mangohud-profile.env`, so future deploy runs reuse your preference automatically.

> **Need a lean workstation build instead?** Set `ENABLE_GAMING_STACK=false` before running the deploy script to skip Gamemode, Gamescope, Steam, and the auxiliary tuning (zram overrides, `/etc/gamemode.ini`, etc.). The default `true` value keeps the full GLF gaming stack enabled so MangoHud, Steam, and Gamescope are ready immediately after install.

### GPU control with LACT

- `ENABLE_LACT=auto` (default) enables [LACT](https://github.com/ilya-zlobintsev/LACT) automatically when the hardware probe finds an AMD, Nvidia, or Intel GPU. Set the variable to `true` to force installation, or `false` to skip it entirely.
- When enabled, the generated configuration sets `services.lact.enable = true;`, which installs the GTK application and its system daemon. Launch **LACT** from the desktop to tune clocks, voltage offsets, or fan curves. The first time you save settings, the daemon writes `/etc/lact/config.yaml`; future tweaks can be made through the GUI or by editing that file.
- AMD users who plan to overclock/undervolt should also keep `hardware.amdgpu.overdrive.enable = true;` (already emitted when RDNA GPUs are detected) so LACT can apply the requested limits. See the upstream FAQ if you need additional kernel parameters for your card.

---

## 🚀 Advanced Usage

### Enable Additional Flatpak Apps

Edit your home-manager config:

```bash
nvim ~/.dotfiles/home-manager/home.nix
```

Find the `services.flatpak.packages` section and uncomment apps you want:

```nix
services.flatpak.packages = [
  # Uncomment to enable:
  # "org.libreoffice.LibreOffice"
  # "org.gimp.GIMP"
  # "org.inkscape.Inkscape"
  # "org.blender.Blender"
  "com.obsproject.Studio"    # OBS Studio (screen recording/streaming)
  # "com.discordapp.Discord"
  # "com.slack.Slack"
];
```

Apply changes:

```bash
home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)
```

### Customize Powerlevel10k Later

```bash
# Remove configuration marker
rm ~/.config/p10k/.configured

# Restart shell to trigger wizard
exec zsh
```

### Add Your Own Packages

Edit home-manager config:

```bash
nvim ~/.dotfiles/home-manager/home.nix
```

Add packages to `home.packages`:

```nix
home.packages = with pkgs; [
  # ... existing packages ...

  # Add your packages here:
  terraform
  kubectl
  k9s
];
```

Apply:

```bash
hms  # Alias for home-manager switch
```

### Enable Automatic Home Manager Updates

The deployment configures an optional auto-upgrade service that can automatically update your Home Manager configuration on a schedule.

To enable it, edit your home-manager config:

```bash
nvim ~/.dotfiles/home-manager/home.nix
```

Find the `services.home-manager.autoUpgrade` section and enable it:

```nix
services.home-manager.autoUpgrade = {
  enable = true;  # Change from false to true
  frequency = "daily";  # Options: "daily", "weekly", "monthly"
  useFlake = true;
  flakeDir = "${config.home.homeDirectory}/.config/home-manager";
};
```

Apply changes:

```bash
hms  # Alias for home-manager switch
```

The service will:

- Run daily at 03:00 by default
- Pull updates from your `~/.config/home-manager` flake
- Automatically rebuild your home environment
- Log output to systemd journal: `journalctl --user -u home-manager-autoUpgrade.service`

To check status:

```bash
systemctl --user status home-manager-autoUpgrade.timer
systemctl --user status home-manager-autoUpgrade.service
```

### Skip Certain Steps (Advanced)

Edit the main script:

```bash
nvim ~/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh
```

Find the `main()` function and comment out steps:

```bash
main() {
    check_prerequisites
    gather_user_info

    # update_nixos_system_config  # Skip NixOS rebuild
    create_home_manager_config
    apply_home_manager_config
    # setup_flake_environment      # Skip flake setup
    install_claude_code
    configure_vscodium_for_claude
    install_vscodium_extensions

    print_post_install
}
```

---

## 💡 Pro Tips

### 1. Use Aliases for Common Tasks

Already configured in your `.zshrc`:

```bash
nrs    # sudo nixos-rebuild switch
hms    # home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)
nfu    # nix flake update
lg     # lazygit
```

### 2. Quick Container AI Stack

```bash
# Check status
kubectl get pods -n ai-stack

# Access Open WebUI at http://localhost:3001
# Access llama.cpp at http://localhost:8080
# Access Qdrant at https://localhost:8443/qdrant (use -k for self-signed)
# Access AIDB MCP at https://localhost:8443/aidb (use -k for self-signed)
```

### 3. VSCodium vs Cursor - When to Use Each

- **VSCodium**: General development, Claude Code integration, Continue AI
- **Cursor**: Heavy AI pair programming, GPT-4 integration, AI-first workflows

### 4. Manage Node.js Packages Globally

```bash
# Always set NPM prefix before installing global packages
export NPM_CONFIG_PREFIX=~/.npm-global
npm install -g <package-name>

# Or add to ~/.npmrc (already done by script):
# prefix=$HOME/.npm-global
```

### 5. Keep Your System Up to Date

```bash
# Update NixOS system
sudo nixos-rebuild switch --upgrade

# Update home-manager packages
nix flake update ~/.dotfiles/home-manager
home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)

# Update Flatpak apps
flatpak update
```

---

## 🧭 Command Cheat Sheet

### Deployment & Maintenance

- `./nixos-quick-deploy.sh --resume` &mdash; continue the multi-phase installer from the last checkpoint.
- `./nixos-quick-deploy.sh --resume --phase 5` &mdash; rerun the declarative deployment phase after editing templates.
- `./nixos-quick-deploy.sh --rollback` &mdash; rollback to the last recorded generation (uses `rollback-info.json`).
- `./nixos-quick-deploy.sh --test-rollback` &mdash; run a rollback + restore validation cycle after deployment.
- `nrs` (`sudo nixos-rebuild switch`) &mdash; manual system rebuild; the deployer now pauses container services automatically when it runs this step.
- `hms` (`home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)`) &mdash; apply user environment changes.
- `nfu` (`nix flake update`) &mdash; refresh flake inputs before rebuilding.

### AI Runtime Orchestration

- `kubectl get pods -n ai-stack` &mdash; show container status.
- `kubectl rollout restart -n ai-stack deployment/<service>` &mdash; restart a service.
- `kubectl logs -n ai-stack deploy/<service>` &mdash; stream logs.
- `python3 ai-stack/tests/test_hospital_e2e.py` &mdash; run the K3s health suite.

### Diagnostics & Recovery

- `kubectl describe pod -n ai-stack <pod>` &mdash; show events + mount issues.
- `kubectl rollout restart -n ai-stack deployment/<service>` &mdash; bounce a service after config/image changes.
- **Rollback (manual):**
  - System: `sudo nixos-rebuild switch --rollback`
  - User: `home-manager --rollback` (or use the generation path stored in `~/.cache/nixos-quick-deploy/rollback-info.json`)
  - Boot fallback: select a previous generation from the boot menu

> ℹ️ **Automation note:** During Phase&nbsp;5 the deployer pauses managed services (systemd units and user-level container services), cleans stale container storage if needed, applies `nixos-rebuild switch`, and then restores everything it stopped. You no longer need to stop the AI stack manually before a rebuild.

---

## 🌟 World-Class NixOS Dev Environment Suggestions

### Additional Packages to Consider

**Database Tools:**

```nix
postgresql      # PostgreSQL database
redis           # Redis key-value store
mongodb         # MongoDB database
dbeaver         # Universal database IDE
```

**Cloud & Infrastructure:**

```nix
terraform       # Infrastructure as code
kubectl         # Kubernetes CLI
awscli2         # AWS command line
google-cloud-sdk  # Google Cloud CLI
azure-cli       # Azure command line
```

**Performance & Debugging:**

```nix
valgrind        # Memory debugging
gdb             # GNU debugger
lldb            # LLVM debugger
strace          # System call tracer
perf            # Linux profiling
```

**Documentation & Diagramming:**

```nix
graphviz        # Graph visualization
plantuml        # UML diagrams
mermaid-cli     # Mermaid diagrams from CLI
```

**Security Tools:**

```nix
nmap            # Network scanner
zenmap          # GUI frontend for nmap scans
wireshark       # Network protocol analyzer
hashcat         # Password cracker
john            # John the Ripper
```

### Recommended Flatpak Additions

**Creative Tools:**

- `org.blender.Blender` - 3D creation suite
- `org.inkscape.Inkscape` - Vector graphics
- `org.gimp.GIMP` - Image editor
- `org.kde.kdenlive` - Video editor

**Communication:**

- `com.discordapp.Discord` - Team chat
- `com.slack.Slack` - Team collaboration
- `org.telegram.desktop` - Messaging

**Productivity:**

- `org.libreoffice.LibreOffice` - Office suite
- `md.obsidian.Obsidian` - Note-taking (already included!)
- `com.notion.Notion` - Workspace

### VSCodium Extension Recommendations

Already installed but worth highlighting:

- **Claude Code** - AI pair programming
- **Continue** - In-editor AI completions
- **Codeium** - Free AI autocomplete
- **GitLens** - Supercharged Git
- **Error Lens** - Inline error highlighting
- **Todo Tree** - TODO comment tracking
- **Prettier** - Code formatter
- **Nix IDE** - Nix language support

### Environment Integrations

**Gitea AI Workflow** (already configured):

- Repository task runners
- Cursor integration for AI code generation
- Aider integration for AI code review
- GPT CLI for commit message generation

**Obsidian AI Plugins** (install with `obsidian-ai-bootstrap`):

- Smart Connections
- Text Generator
- Copilot
- AI Assistant

---

## 📚 Documentation & Resources

### This Repository

### Agent Docs Index

- [AGENTS.md](AGENTS.md) - Canonical agent onboarding and rules
- [docs/AGENTS.md](docs/AGENTS.md) - Mirror for quick reference
- [docs/agent-guides/00-SYSTEM-OVERVIEW.md](docs/agent-guides/00-SYSTEM-OVERVIEW.md) - System map for agents
- [docs/agent-guides/01-QUICK-START.md](docs/agent-guides/01-QUICK-START.md) - Task-ready checklist
- [ai-stack/agents/skills/AGENTS.md](ai-stack/agents/skills/AGENTS.md) - Skill usage and sync rules

### AI Stack Documentation (NEW in v6.0.0)

- [AI Stack Integration Guide](docs/AI-STACK-FULL-INTEGRATION.md) - Complete architecture and migration
- [AI Stack README](ai-stack/README.md) - AI stack overview and quick start
- [AIDB MCP Server](ai-stack/mcp-servers/aidb/README.md) - AIDB server documentation
- [Agent Skills](ai-stack/agents/README.md) - 29 specialized AI agent skills
- [AI Stack Architecture](ai-stack/docs/ARCHITECTURE.md) - Technical architecture details
- [Agent Workflows](AGENTS.md) - Canonical AI agent onboarding and standards
- [MCP Servers Guide](docs/MCP_SERVERS.md) - Model Context Protocol server docs

- [Build Optimization Guide](docs/BUILD_OPTIMIZATION.md) - Choose between binary caches (20-40 min) or source builds (60-120 min)
- [AIDB Setup Guide](docs/AIDB_SETUP.md) - Complete AIDB configuration walkthrough
- [AI Integration Guide](docs/AI_INTEGRATION.md) - Sync docs and leverage AI-Optimizer tooling
- [Local AI Starter Toolkit](docs/LOCAL-AI-STARTER.md) - Scaffold local agents/OpenSkills/MCP servers without private repos
- [Agent Workflows](AGENTS.md) - AI agent integration documentation
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Code Review Guide](docs/CODE_REVIEW.md) - Code quality and review process
- [Safe Improvements](docs/SAFE_IMPROVEMENTS.md) - Guidelines for safe changes
- [System Health Check](scripts/system-health-check.sh) - Verify and fix installation

### Official Docs

- [NixOS Manual](https://nixos.org/manual/nixos/stable/)
- [Home Manager Manual](https://nix-community.github.io/home-manager/)
- [Nix Package Search](https://search.nixos.org/packages)
- [COSMIC Desktop](https://system76.com/cosmic)

### AI Tools

- [Claude Code Docs](https://docs.anthropic.com/claude/docs)
- [Cursor Docs](https://docs.cursor.sh/)
- [Continue Docs](https://continue.dev/docs)
- [Aider Docs](https://aider.chat/)
- [llama.cpp Docs](https://github.com/ggerganov/llama.cpp)

### Learning Resources

- [Zero to Nix](https://zero-to-nix.com/) - Beginner-friendly Nix tutorial
- [Nix Pills](https://nixos.org/guides/nix-pills/) - Deep dive into Nix
- [NixOS & Flakes Book](https://nixos-and-flakes.thiscute.world/) - Modern Nix

---

## 🤝 Contributing

Found a bug or have a suggestion? Please open an issue or submit a pull request!

### Reporting Issues

When reporting problems, please include:

- NixOS version: `nixos-version`
- Script output or error messages
- Relevant logs from `${TMPDIR:-/tmp}/nixos-quick-deploy.log`

---

## Known Limitations

- **AI Stack requires K3s**: The integrated AI stack runs on Kubernetes (K3s). Legacy Podman-based deployments are deprecated.
- **Hardware requirements**: The full AI stack (with local LLM inference) needs at least 16 GB RAM and 50 GB free disk. GPU inference requires an NVIDIA GPU with 4+ GB VRAM.
- **Continuous learning is partial**: The Hybrid Coordinator collects interaction telemetry and extracts patterns, but automated model retraining and behavioral adaptation from feedback are not yet implemented.
- **Agent skills are pre-packaged**: The 23 agent skills are static skill definitions (prompt templates + scripts); they do not autonomously learn or update themselves.
- **NixOS only**: This project targets NixOS exclusively. It will not work on other Linux distributions, macOS, or WSL.
- **Build times**: First deployment with source builds (no binary cache) can take 60-120 minutes depending on hardware.
- **Python package overrides**: Some Python packages require Nix build overrides to compile. Updating nixpkgs may break overrides until they are re-adjusted.
- **Single-node K3s**: The AI stack runs on a single-node K3s cluster. Multi-node distributed deployment is not supported.
- **No automatic TLS renewal in dev mode**: Self-signed certificates are generated for local HTTPS but are not automatically renewed. See `scripts/renew-tls-certificate.sh` for manual renewal.

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

---

## ⭐ Acknowledgments

Built with these amazing technologies:

- [NixOS](https://nixos.org/) - Reproducible Linux distribution
- [Home Manager](https://github.com/nix-community/home-manager) - Declarative dotfile management
- [COSMIC](https://system76.com/cosmic) - Modern desktop environment
- [Anthropic Claude](https://anthropic.com/) - AI assistant
- [Cursor](https://cursor.sh/) - AI-powered code editor
- [K3s](https://k3s.io/) - Lightweight Kubernetes distribution
- [Powerlevel10k](https://github.com/romkatv/powerlevel10k) - Beautiful ZSH theme

---

**Ready to deploy?**

```bash
curl -fsSL https://raw.githubusercontent.com/MasterofNull/NixOS-Dev-Quick-Deploy/main/nixos-quick-deploy.sh | bash
```

Happy coding! 🚀
