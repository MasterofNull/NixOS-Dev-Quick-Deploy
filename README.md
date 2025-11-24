# NixOS Dev Quick Deploy

**Transform a fresh NixOS installation into a fully-configured AI development powerhouse in 20-40 minutes** (or 60-120 minutes if building from source).

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

---

## 📋 What You Get

### Complete System Setup
- **COSMIC Desktop** - Modern, fast desktop environment from System76
- **Hyprland Wayland Session** - Latest Hyprland compositor alongside COSMIC for tiling workflows
- **Performance Kernel Track** - Prefers the tuned `linuxPackages_6_17` build, then falls back to TKG, XanMod, Liquorix, Zen, and finally `linuxPackages_latest`
- **800+ Packages** - Development tools, CLI utilities, and applications
- **Nix Flakes** - Enabled and configured for reproducible builds
- **Podman** - Rootless container runtime for local AI services
- **Flatpak** - Sandboxed desktop applications with profile-aware provisioning and incremental updates
- **Home Manager** - Declarative user environment configuration
- **ZSH + Powerlevel10k** - Beautiful, fast terminal with auto-configuration

### AI Development Stack
| Tool | Integration | Purpose |
|------|-------------|---------|
| **Claude Code** | VSCodium extension + CLI wrapper | AI pair programming inside VSCodium |
| **Cursor** | Flatpak + launcher | AI-assisted IDE with GPT-4/Claude |
| **Continue** | VSCodium extension | In-editor AI completions |
| **Codeium** | VSCodium extension | Free AI autocomplete |
| **GPT CLI** | Command-line tool | Query OpenAI/Ollama from terminal |
| **Aider** | CLI code assistant | AI pair programming from terminal |
| **Ollama** | Podman container | Local LLM runtime |
| **Open WebUI** | Podman container | ChatGPT-like interface for local LLMs |
| **Hugging Face TGI** | Systemd service | High-performance LLM inference |
| **LM Studio** | Flatpak app | Desktop LLM manager |

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
- VSCodium (VS Code without telemetry)
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
- Podman, Podman Compose
- Buildah, Skopeo
- Podman Desktop (Flatpak GUI)

**AI Services (Systemd):**
- Qdrant (vector database, enabled by default)
- Hugging Face TGI (LLM inference server, manual enable)
- Jupyter Lab (web-based notebooks, user service)

### Flatpak Applications

Pick the profile that matches your workflow during Phase 6:

- **Core** – Balanced desktop with browsers, media tools, and developer essentials.
- **AI Workstation** – Core profile plus Postman, DBeaver, VS Code, Bitwarden, and other data tooling.
- **Minimal** – Lean recovery environment with Firefox, Obsidian, Flatseal, and Podman Desktop.

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

1. **Binary caches** *(default)* – Fastest path, uses NixOS/nix-community/CUDA caches.
2. **Build locally** – Compile everything on the target host for maximal control.
3. **Remote builders or private Cachix** – Layer SSH build farm(s) and/or authenticated Cachix caches on top of the binary caches option.

If you choose option 3, be ready to paste builder strings (e.g., `ssh://nix@builder.example.com x86_64-linux - 4 1`) and any Cachix cache names/keys. Secrets are stored under `$STATE_DIR/preferences/remote-builders.env` for reuse later.

### Step 3: Wait (20-35 minutes)

The script automatically:
- ✅ Updates NixOS system config (COSMIC, Podman, Flakes)
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
- ✅ All core tools (podman, python3, node, etc.)
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

### Podman Storage: Btrfs Recommended for AI-Optimizer

The deployer will prompt for the Podman storage driver. For AI-Optimizer workloads (see `~/Documents/AI-Optimizer`), use **Btrfs** when possible for fast snapshots and deduplication.

- **Sizing:** Minimum 150 GiB; **recommended 200–300 GiB** if you expect multiple large model images.
- **Prepare a Btrfs data root** (if your root FS isn’t already Btrfs):
  ```bash
  sudo mkdir -p /var/lib/containers
  sudo truncate -s 300G /var/lib/containers.btrfs
  sudo mkfs.btrfs -L podman /var/lib/containers.btrfs
  echo "/var/lib/containers.btrfs /var/lib/containers btrfs loop,compress=zstd,ssd,noatime 0 0" | sudo tee -a /etc/fstab
  sudo mount -a
  ```
- **During the prompt:** select `btrfs`. If the backing FS is not Btrfs, you’ll see a warning reminding you to create the volume above.

**Or verify manually:**

```bash
# Check core tools
podman --version
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
- Core system tools (podman, git, curl, etc.)
- Programming languages (Python, Node.js, Go, Rust)
- Nix ecosystem (home-manager, flakes)
- AI tools (Claude Code, Ollama, Aider)
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

### AI Stack Management

The local AI stack (Ollama, Open WebUI, Qdrant, MindsDB) now runs via the rootless Podman helper `podman-ai-stack`, which keeps everything isolated under `~/.local/share/podman-ai-stack/`. Use the helper to control the stack:

```bash
# Start or stop the entire stack
podman-ai-stack up
podman-ai-stack down

# Check status or tail logs
podman-ai-stack status
podman-ai-stack logs

# Restart if you change ai-optimizer configs
podman-ai-stack restart
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
podman pod ps       # List running pods
podman ps           # List running containers
podman-compose up   # Start services from compose file
```

### VSCodium / AI CLI wrappers

**VSCodium Version Compatibility:**
- VSCodium 1.85.0+ (installed by this script)
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

| File | Description | Managed By |
|------|-------------|------------|
| `/etc/nixos/configuration.nix` | System configuration | Script auto-updates |
| `~/.dotfiles/home-manager/home.nix` | User packages & config | Script auto-creates |
| `~/.dotfiles/home-manager/flake.nix` | Home-manager flake | Script auto-creates |
| `~/.config/VSCodium/User/settings.json` | VSCodium settings | Home-manager (declarative) |
| `~/.config/p10k/theme.sh` | Powerlevel10k theme | Wizard auto-generates |
| `~/.zshrc` | ZSH configuration | Home-manager (declarative) |
| `~/.npmrc` | NPM configuration | Script auto-creates |
| `~/.npm-global/` | Global NPM packages | AI CLI wrappers installed here (Claude, GPT CodeX, Codex IDE, OpenAI, GooseAI) |

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
✓ Adding Podman virtualization
✓ Enabling Nix flakes
✓ Allowing unfree packages
Running: sudo nixos-rebuild switch
✓ NixOS system configuration applied!
```

### 4. Home-Manager Setup
```
✓ Creating ~/.dotfiles/home-manager/
✓ Writing home.nix with ~100 packages
✓ Writing flake.nix
✓ Creating flake.lock
Running: home-manager switch
✓ Home-manager configuration applied!
✓ Updating current shell environment
✓ Verifying package installation
  ✓ podman found at ~/.nix-profile/bin/podman
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
✓ Installing Podman Desktop
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
✓ Installing @anthropic-ai/claude-code via npm
✓ Installing @openai/codex (GPT CodeX CLI) via npm
✓ Installing openai via npm
✓ Goose CLI detected via nixpkgs (goose-cli)
✓ Claude Code npm package installed
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
  4. Verify: codium, claude-wrapper --version, gpt-codex-wrapper --version, codex-wrapper --version, openai-wrapper --version, gooseai-wrapper --version, goose --version
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

5. **Reinstall Claude Code:**
   ```bash
   export NPM_CONFIG_PREFIX=~/.npm-global
   npm install -g @anthropic-ai/claude-code
   ```

6. **Check VSCodium settings:**
   ```bash
   cat ~/.config/VSCodium/User/settings.json | grep -A5 "claude-code"
   ```
   Should show `executablePath` pointing to `~/.npm-global/bin/claude-wrapper`

7. **Verify no Flatpak overrides exist:**
   ```bash
   flatpak info com.visualstudio.code 2>/dev/null || echo "No conflicting Flatpak"
   ```
   Remove any `com.visualstudio.code*` or `com.vscodium.codium*` Flatpak apps—they replace the declarative `programs.vscode` package and undo the managed settings/extensions.

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
    → error: Unable to create repository at /home/$USER/.local/share/flatpak/repo (Creating repo: mkdirat: No such file or directory)
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

**Issue:** `podman: command not found`, `home-manager: command not found`, or AI CLI wrappers (claude/gpt-codex/openai/gooseai) not found after installation

**Solution:**
```bash
# Run health check with automatic fixes
./system-health-check.sh --fix

# Restart shell to load new PATH
exec zsh

# Or manually source session vars
source ~/.nix-profile/etc/profile.d/hm-session-vars.sh

# Verify
which podman
which home-manager
which claude-wrapper
which gpt-codex-wrapper

### Boot Fails With "Failed to mount /var/lib/containers/storage/overlay/..."

**Symptom:** System drops into emergency mode during boot with messages such as:

```
[FAILED] Failed to mount /var/lib/containers/storage/overlay/df4bd49...
[DEPEND] Dependency failed for Local File Systems
```

**Cause:** Upstream Podman (and earlier revisions of this deploy script) defaulted to the kernel overlay driver, which is unsupported on filesystems such as ZFS. If an older configuration or manual override still points at `overlay`, systemd attempts to mount it during boot and fails before `local-fs.target` completes. Current releases fall back to the more conservative `vfs` driver when no filesystem-specific driver is detected, but lingering `overlay` entries from prior runs can still trigger the failure until the configuration is regenerated.

**Fix:** The generator now inspects the filesystem that backs `/var/lib/containers` and sets `virtualisation.containers.storage.settings.storage.driver` (for example `zfs`) so NixOS renders a compatible `/etc/containers/storage.conf`. When the existing file still pins a conflicting driver (for example a legacy `overlay` entry) the detector attempts to rewrite `/etc/containers/storage.conf` in place—saving a timestamped `.bak` next to the file **and** archiving a copy under `~/.cache/nixos-quick-deploy/backups/<timestamp>/etc/containers/storage.conf`—so the system starts using the new driver immediately. If permissions block the repair it prints a warning so you can regenerate before rebooting. Regenerate your configuration and rebuild:

1. Confirm the backing filesystem (optional):
   ```bash
   findmnt -no FSTYPE,SOURCE /var/lib/containers
   ```
2. Regenerate configs so the new storage detection runs:
   ```bash
   cd ~/NixOS-Dev-Quick-Deploy
   ./nixos-quick-deploy.sh --resume
   ```
3. Rebuild and activate the system profile:
   ```bash
   sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager
   ```
4. Verify Podman is using the new driver:
   ```bash
   sudo podman info --format '{{.Store.GraphDriverName}}'
   ```

On the next reboot the mount units no longer reference overlay paths, so the system reaches the login screen normally.

**Update:** Overlay storage support has been removed from the generator. Phase 1
now enforces `vfs`, `btrfs`, or `zfs` and refuses to reintroduce legacy overlay
entries, so regenerated configurations stop creating overlay mount units and
systemd boots normally after the next rebuild.

**Tip:** The deployment script now re-checks the container storage backend each time it regenerates `configuration.nix`, so resumed runs or flake edits pick up the correct driver automatically. Set `FORCE_CONTAINER_STORAGE_REDETECT=true` if you want to force a fresh probe, adjust the fallback with `DEFAULT_PODMAN_STORAGE_DRIVER=<driver>`, or export `PODMAN_STORAGE_DRIVER_OVERRIDE=<driver>` to bypass auto-detection intentionally. Set `PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF=false` to skip the automatic `/etc/containers/storage.conf` rewrite and keep the warning-only behaviour. Phase 1 now prompts for the Podman storage driver (default: `vfs`) so you can pick `vfs`, `btrfs`, `zfs`, or `auto` on each run without persisting the choice.

When you force a driver, the detector still reports the filesystem that backs `/var/lib/containers` and warns if the override does not match the recommended driver for that filesystem. Review the warning output before rebuilding so you do not carry an incompatible combination into the generated configuration.
which codex-wrapper
which openai-wrapper
which gooseai-wrapper
```

### Podman Service Fails With `overlay: unknown option vfs.ignore_chown_errors`

**Symptom:** `nixos-rebuild switch` aborts while restarting `podman.service` and logs:

```
ERRO[0000] User-selected graph driver "vfs" overwritten by graph driver "overlay" from database
Error: configure storage: overlay: unknown option vfs.ignore_chown_errors
```

**Cause:** Earlier deployments may have initialized `/var/lib/containers/storage` with the kernel `overlay` driver. Even after the generator switches to `vfs`, Podman keeps the old driver recorded in its BoltDB metadata and refuses to start because the VFS-only `ignore_chown_errors` option now appears alongside the overlay runtime.

**Fix (current builds):** Phase 5 now runs `sudo podman info --format '{{.Store.GraphDriverName}}'` before `nixos-rebuild`. If the probe fails or reports a driver that differs from the generated value, the phase aborts early, runs the automated cleanup (`podman system reset --force`, `sudo podman system reset --force`, and `/var/lib/containers/storage` purges), and prints explicit remediation commands instead of letting `switch-to-configuration` hit the opaque systemd failure.

**Manual reset (if the automated pass still reports a mismatch):**

```bash
sudo systemctl stop podman.service podman.socket || true
podman system reset --force && rm -rf ~/.local/share/containers/storage ~/.local/share/containers/cache
sudo podman system reset --force
sudo rm -rf /var/lib/containers/storage
```

Rerun `./nixos-quick-deploy.sh --resume` afterwards so Phase 5 re-probes the driver. Once the probe and configuration agree on `vfs`, Podman restarts cleanly and the generator re-adds the `ignore_chown_errors` flag only when the driver is actually `vfs`.

### Rootless Podman Reports Driver Mismatch or Overlay Failures

**Symptom:** Running `podman ps` or `podman info` as a non-root user prints messages such as:

```
ERRO[0000] User-selected graph driver "overlay" overwritten by graph driver "btrfs" from database
Error: configure storage: "/home/<user>/.local/share/containers/storage/btrfs" is not on a btrfs filesystem
```

**Cause:** Earlier versions mirrored the system storage driver (for example `btrfs` or `zfs`) into `/etc/containers/storage.conf`. Rootless Podman reuses that driver for `~/.local/share/containers`, so a home directory on ext4/xfs would hit catastrophic driver mismatches.

**Fix:** The generator now writes `~/.config/containers/storage.conf` via Home Manager. It compares the home filesystem with the system driver and falls back to `vfs` whenever the filesystem cannot host the selected native driver. Regenerate your configuration and reset the rootless store so the new override takes effect:

1. Render the updated configs:
   ```bash
   cd ~/NixOS-Dev-Quick-Deploy
   ./nixos-quick-deploy.sh --resume
   ```
2. Remove stale rootless storage metadata (only affects the current user's Podman images):
   ```bash
   rm -rf ~/.local/share/containers/storage ~/.local/share/containers/cache
   ```
   # or: podman system reset --force
3. Apply the Home Manager profile and restart the shell to pick up the new `storage.conf`:
   ```bash
   cd ~/.dotfiles/home-manager
   home-manager switch --flake .#$(whoami)
   exec zsh
   ```
4. Confirm the driver now matches the override or the enforced fallback:
   ```bash
   podman info --format '{{.Store.GraphDriverName}}'
   ```

**If still not working:**
```bash
# Re-apply home-manager configuration
cd ~/.dotfiles/home-manager
home-manager switch --flake .#$(whoami)

# Restart shell
exec zsh
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
  docker-compose
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
# Start all AI services at once (system + stack containers)
ai-servicectl start all

# Or focus on the user-space Podman stack only
ai-servicectl start stack
# (equivalent to podman-ai-stack up for advanced workflows)

# Access Open WebUI at http://localhost:8081
# Access Ollama API at http://localhost:11434
# Access Hugging Face TGI at http://localhost:8080
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
# prefix=/home/username/.npm-global
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
- `nrs` (`sudo nixos-rebuild switch`) &mdash; manual system rebuild; the deployer now pauses container services automatically when it runs this step.
- `hms` (`home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)`) &mdash; apply user environment changes.
- `nfu` (`nix flake update`) &mdash; refresh flake inputs before rebuilding.

### AI Runtime Orchestration
- `ai-servicectl start|stop|restart all` &mdash; manage system Gitea **and** the Podman AI stack in one shot.
- `ai-servicectl start stack` &mdash; bring up only the user-space Podman network (Ollama/Open WebUI/Qdrant/MindsDB).
- `ai-servicectl status system` &mdash; quick health summary for the declarative services (currently just Gitea).
- `ai-servicectl logs stack` &mdash; stream Podman AI stack logs from journald via one command.
- `podman-ai-stack up|down|status|logs` &mdash; raw helper for advanced Podman scenarios; `ai-servicectl` wraps it for most workflows.

### Diagnostics & Recovery
- `ai-servicectl stop all && ai-servicectl start all` &mdash; bounce every AI-centric service after changing models or GPU drivers.
- `podman system reset --force` / `sudo podman system reset --force` &mdash; manual fallback for storage corruption (the deployer now attempts this automatically when stale overlay layers are detected).
- `journalctl --user -u podman-local-ai-*.service -f` &mdash; detailed logs for the rootless containers when `ai-servicectl status` reports a failure.

> ℹ️ **Automation note:** During Phase&nbsp;5 the deployer pauses managed services (systemd units and user-level Podman quadlets), cleans stale Podman storage if needed, applies `nixos-rebuild switch`, and then restores everything it stopped. You no longer need to stop the AI stack manually before a rebuild.

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
- [Build Optimization Guide](docs/BUILD_OPTIMIZATION.md) - Choose between binary caches (20-40 min) or source builds (60-120 min)
- [AIDB Setup Guide](docs/AIDB_SETUP.md) - Complete AIDB configuration walkthrough
- [AI Integration Guide](docs/AI_INTEGRATION.md) - Sync docs and leverage AI-Optimizer tooling
- [Local AI Starter Toolkit](docs/LOCAL-AI-STARTER.md) - Scaffold local agents/OpenSkills/MCP servers without private repos
- [Agent Workflows](docs/AGENTS.md) - AI agent integration documentation
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
- [Ollama Docs](https://ollama.ai/docs)

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
- Relevant logs from `/tmp/nixos-quick-deploy.log`

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
- [Podman](https://podman.io/) - Daemonless container engine
- [Powerlevel10k](https://github.com/romkatv/powerlevel10k) - Beautiful ZSH theme

---

**Ready to deploy?**

```bash
curl -fsSL https://raw.githubusercontent.com/MasterofNull/NixOS-Dev-Quick-Deploy/main/nixos-quick-deploy.sh | bash
```

Happy coding! 🚀
