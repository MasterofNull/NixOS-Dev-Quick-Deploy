# AIDB (AI Development Bench) Setup Guide

## Overview

AIDB is a comprehensive AI development environment that provides local and cloud-based LLM capabilities, integrated development tools, and a complete AI workflow platform. This guide will help you set up and configure AIDB components after running the NixOS Quick Deploy script.

---

## Table of Contents

1. [What is AIDB?](#what-is-aidb)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Component Setup](#component-setup)
5. [AIDB Packages](#aidb-packages)
6. [Integration Guide](#integration-guide)
7. [Troubleshooting](#troubleshooting)

---

## What is AIDB?

AIDB is a collection of tools and services that work together to provide a complete AI development environment:

- **Local LLM Runtime**: Ollama for running models locally
- **Web Interface**: Open WebUI for ChatGPT-like experience
- **Vector Database**: Qdrant for semantic search and RAG
- **IDE Integration**: Claude Code, Cursor, Continue
- **CLI Tools**: Aider, GPT CLI, custom scripts
- **Development Environment**: Nix flakes for reproducibility

---

## Prerequisites

Before setting up AIDB components, ensure you have completed the NixOS Quick Deploy:

```bash
# Verify core tools are installed
./system-health-check.sh

# Should show:
# ✓ Podman
# ✓ Python 3
# ✓ Node.js
# ✓ Home Manager
# ✓ Ollama
# ✓ Aider
```

---

## Quick Start

### 1. Enter the AIDB Development Environment

The NixOS Quick Deploy script creates several aliases for working with AIDB:

```bash
# Enter the AIDB development shell
aidb-dev

# Alternative method
aidb-shell

# Show AIDB environment info
aidb-info

# Update AIDB dependencies
aidb-update
```

**Note**: If `aidb-dev` is not found, reload your shell:

```bash
# Reload ZSH configuration
source ~/.zshrc

# Or restart your shell
exec zsh
```

### 2. Start Local AI Services

```bash
# Start Ollama (local LLM runtime)
systemctl --user start ollama

# Verify Ollama is running
ollama list

# Pull a model (example: llama3.2)
ollama pull llama3.2

# Test the model
ollama run llama3.2 "Hello, how are you?"
```

### 3. Start Open WebUI (Optional)

Open WebUI provides a ChatGPT-like interface for your local models:

```bash
# Using podman directly
podman run -d \
  --name open-webui \
  -p 8081:8080 \
  -v $HOME/.local/share/open-webui:/app/backend/data \
  --add-host=host.docker.internal:host-gateway \
  ghcr.io/open-webui/open-webui:main

# Access at http://localhost:8081
```

---

## Component Setup

### Ollama - Local LLM Runtime

Ollama is already installed via Home Manager. Here's how to use it:

**Start Ollama Service:**

```bash
# Enable and start Ollama service
systemctl --user enable ollama
systemctl --user start ollama

# Check status
systemctl --user status ollama
```

**Install Models:**

```bash
# List available models
ollama list

# Pull popular models
ollama pull llama3.2        # Meta's Llama 3.2 (4.7GB)
ollama pull phi4            # Microsoft Phi-4 (small, fast)
ollama pull mistral         # Mistral 7B (powerful, medium size)
ollama pull codellama       # Code-specialized Llama
ollama pull deepseek-coder  # DeepSeek Coder (excellent for code)

# Check downloaded models
ollama list
```

**Use Models:**

```bash
# Interactive chat
ollama run llama3.2

# One-shot query
ollama run llama3.2 "Explain what Nix flakes are"

# API usage
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Why is NixOS great for development?"
}'
```

**Environment Variables (already configured):**

- `OLLAMA_HOST=http://127.0.0.1:11434` - API endpoint

### Claude Code - AI Pair Programming in VSCodium

Claude Code is installed as a VSCodium extension and CLI wrapper.

**Verify Installation:**

```bash
# Check wrapper exists
which claude-wrapper
# Should show: /home/username/.npm-global/bin/claude-wrapper

# Test wrapper
claude-wrapper --version

# If not found, run health check
./system-health-check.sh --fix
```

**Configure API Key:**

1. Open VSCodium
2. Press `Ctrl+Shift+P` (Command Palette)
3. Type: "Claude: Set API Key"
4. Enter your Anthropic API key
5. Or set environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

**Usage in VSCodium:**

- Press `Ctrl+L` to open Claude chat
- Select code and press `Ctrl+K` for inline editing
- Ask Claude to write, explain, or refactor code

**VSCode/VSCodium Version Compatibility:**

The Claude Code extension works with:
- **VSCodium** 1.85.0+ (recommended - installed by this script)
- **VS Code** 1.85.0+ (Microsoft version with telemetry)
- **Cursor** (has built-in Claude support, extension not needed)

The `claude-wrapper` ensures the Claude CLI works correctly regardless of which editor you use.

### Cursor - AI-First IDE

Cursor is installed via Flatpak and provides deep AI integration.

**Launch Cursor:**

```bash
# Using the helper script
code-cursor

# Or directly via Flatpak
flatpak run ai.cursor.Cursor

# Open a project
code-cursor /path/to/project
```

**First-Time Setup:**

1. Launch Cursor
2. Sign in with GitHub/Google
3. Configure AI preferences:
   - Choose model: GPT-4, Claude, or local
   - Set keybindings
   - Enable/disable autocomplete

**Features:**

- `Ctrl+K`: AI inline editing
- `Ctrl+L`: AI chat panel
- `Tab`: AI autocomplete
- `@codebase`: Search entire codebase with AI

### Aider - AI Coding Assistant (CLI)

Aider provides AI pair programming from the command line.

**Basic Usage:**

```bash
# Start aider in current directory
aider

# Specify files to edit
aider src/main.rs src/lib.rs

# Use specific model
aider --model gpt-4o
aider --model claude-3-5-sonnet-20241022

# Use local model via Ollama
aider --model ollama/codellama
```

**Configuration:**

Aider is pre-configured via environment variables:

- `AIDER_DEFAULT_MODEL=gpt-4o-mini`
- `AIDER_LOG_DIR=$HOME/.local/share/aider/logs`

Create `~/.aider.conf.yml` for custom settings:

```yaml
model: gpt-4o
dark-mode: true
auto-commits: true
dirty-commits: false
```

**Tips:**

- `/add filename.py` - Add file to chat
- `/drop filename.py` - Remove file from chat
- `/commit` - Create git commit
- `/undo` - Undo last change
- `/help` - Show all commands

### GPT CLI - Command-Line LLM Queries

Query LLMs directly from the terminal:

```bash
# Query default model
gpt-cli "Explain Nix flakes in one sentence"

# Use specific model
gpt-cli --model gpt-4o "Write a Rust function to parse JSON"

# Use local model
gpt-cli --model ollama/llama3.2 "What is NixOS?"

# Pipe input
cat README.md | gpt-cli "Summarize this document"
```

**Environment Variables (already configured):**

- `GPT_CLI_DEFAULT_MODEL` - Default model to use
- `GPT_CLI_DEFAULT_PROVIDER=openai` - Provider (openai, anthropic, ollama)
- `GPT_CLI_BASE_URL` - API endpoint

---

## AIDB Packages

### Currently Installed (via Home Manager)

These packages are installed automatically by the NixOS Quick Deploy script:

**Core AI Tools:**
- `ollama` - Local LLM runtime
- `aider` - AI coding assistant
- Python packages for AI/ML (numpy, pandas, etc.)

**Development Tools:**
- `podman` - Container runtime for AI services
- `python3` - Python interpreter
- `nodejs_22` - Node.js for Claude wrapper
- `git` - Version control
- `neovim` - Text editor

**CLI Utilities:**
- `ripgrep` - Fast search
- `fd` - Fast find
- `bat` - Enhanced cat
- `jq` - JSON processor

### Future AIDB Packages (Recommended)

These packages are not yet installed but are recommended for AIDB workflows. Add them to `~/.dotfiles/home-manager/home.nix`:

#### Via Home Manager (Nix)

Add to the `home.packages` section in `~/.dotfiles/home-manager/home.nix`:

```nix
home.packages = with pkgs; [
  # Existing packages...

  # ====================================================================
  # AIDB Future Packages
  # ====================================================================

  # AI/ML Development
  jupyter                 # Jupyter notebooks for AI experiments
  jupyterlab              # JupyterLab interface

  # Vector Databases & Search
  # Note: qdrant available as container, not in nixpkgs

  # Python AI/ML Libraries (via python3.withPackages)
  (python3.withPackages (ps: with ps; [
    # Already included: numpy pandas matplotlib seaborn scikit-learn

    # Additional AI/ML packages
    torch                 # PyTorch
    tensorflow            # TensorFlow
    transformers          # Hugging Face transformers
    sentence-transformers # Sentence embeddings
    langchain             # LangChain framework
    openai                # OpenAI Python client
    anthropic             # Anthropic Python client
    faiss-cpu             # Facebook AI Similarity Search
    chromadb              # Chroma vector database
    pinecone-client       # Pinecone vector database

    # Data processing
    polars                # Fast DataFrame library
    dask                  # Parallel computing

    # NLP
    spacy                 # Industrial NLP
    nltk                  # Natural Language Toolkit

    # Visualization
    plotly                # Interactive plots
    dash                  # Plotly dashboards
  ]))

  # Code Quality & Analysis
  ruff                    # Fast Python linter (Rust-based)
  black                   # Python code formatter
  mypy                    # Python type checker

  # Database Tools
  sqlite                  # SQLite CLI
  postgresql              # PostgreSQL client

  # Documentation
  mdbook                  # Create books from markdown
  hugo                    # Static site generator
];
```

Then apply changes:

```bash
cd ~/.dotfiles/home-manager
home-manager switch --flake .
```

#### Via Flatpak

Some AIDB tools are better installed via Flatpak. Add to `services.flatpak.packages` in `home.nix`:

```nix
services.flatpak.packages = [
  # Existing packages...

  # ====================================================================
  # AIDB Future Flatpak Packages
  # ====================================================================

  # Development
  "com.github.marhkb.Pods"              # Podman containers GUI (alternative to Podman Desktop)

  # Data Science & Analysis
  "org.gnome.Calculator"                # Calculator app
  "io.github.nokse22.asciidraw"         # ASCII diagrams

  # Database Management
  "com.dbeaver.DBeaverCommunity"        # Universal database tool

  # AI-Specific
  # Note: Most AI tools run as containers or CLI, not Flatpak
];
```

#### Via Podman Containers

These AI services run best as containers:

```bash
# Qdrant - Vector Database
podman run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $HOME/.local/share/qdrant:/qdrant/storage:z \
  qdrant/qdrant

# Jupyter Lab
podman run -d \
  --name jupyter \
  -p 8888:8888 \
  -v $HOME/notebooks:/home/jovyan/work \
  jupyter/scipy-notebook

# Hugging Face TGI (Text Generation Inference)
podman run -d \
  --name tgi \
  -p 8080:80 \
  -v $HOME/.cache/huggingface:/data \
  --env HF_TOKEN=your_token_here \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Meta-Llama-3-8B-Instruct
```

---

## Integration Guide

### Integrating Claude Code with VSCodium

Claude Code is already configured, but here's how to verify:

**Check VSCodium Settings:**

```bash
cat ~/.config/VSCodium/User/settings.json | grep -A10 "claude"
```

Should show:

```json
"claudeCode.executablePath": "/home/username/.npm-global/bin/claude-wrapper",
"terminal.integrated.env.linux": {
  "PATH": "/home/username/.nix-profile/bin:...",
  "NODE_PATH": "/home/username/.npm-global/lib/node_modules"
}
```

**Test Integration:**

1. Open VSCodium
2. Press `Ctrl+Shift+P`
3. Type: "Claude: "
4. Should see Claude commands

**If Claude Error 127 Appears:**

```bash
# Run health check with fix
./system-health-check.sh --fix

# Or manually fix
cd ~/.dotfiles/home-manager
home-manager switch --flake .

# Reload shell
exec zsh
```

### Using Ollama with Aider

Aider can use local Ollama models:

```bash
# Use Ollama model
aider --model ollama/codellama

# Or set as default
export AIDER_DEFAULT_MODEL=ollama/codellama
aider
```

### Combining Tools in Workflows

**Example: AI Code Review Workflow**

```bash
# 1. Start aider for code changes
aider src/main.rs

# (In aider): "Add error handling to the parse function"

# 2. Review changes with Claude Code in VSCodium
codium src/main.rs

# (In VSCodium): Select code, Ctrl+L, ask Claude to review

# 3. Test changes
cargo test

# 4. Commit with AI-generated message
git add src/main.rs
gpt-cli "Generate a commit message for these changes: $(git diff --cached)" | \
  xargs -0 -I {} git commit -m {}
```

---

## Troubleshooting

### Common Issues

#### "aidb-dev: command not found"

**Cause:** Shell aliases not loaded.

**Fix:**

```bash
# Reload shell configuration
source ~/.zshrc

# Or restart shell
exec zsh

# Verify
type aidb-dev
```

#### "claude-wrapper: command not found"

**Cause:** NPM global bin not in PATH.

**Fix:**

```bash
# Run health check
./system-health-check.sh --fix

# Or manually
export PATH="$HOME/.npm-global/bin:$PATH"
source ~/.zshrc
```

#### "code-cursor: install the Cursor Flatpak"

**Cause:** Cursor Flatpak not installed.

**Fix:**

```bash
# Install Cursor
flatpak install flathub ai.cursor.Cursor

# Verify
flatpak list --user | grep Cursor
```

#### "Ollama service not running"

**Cause:** Ollama systemd service not started.

**Fix:**

```bash
# Start service
systemctl --user start ollama

# Enable on boot
systemctl --user enable ollama

# Check status
systemctl --user status ollama
```

#### "Multiple Flatpak Platform runtimes"

**Cause:** Different apps depend on different runtime versions (24.08, 25.08).

**This is normal!** Flatpak apps can depend on different runtime versions. To clean up unused runtimes:

```bash
# Remove unused runtimes
flatpak uninstall --unused -y

# Show what would be removed (dry run)
flatpak uninstall --unused
```

### Getting Help

**Run System Health Check:**

```bash
./system-health-check.sh --detailed
```

**Check Logs:**

```bash
# Home Manager log
journalctl --user -u home-manager-$USER.service

# Ollama log
journalctl --user -u ollama

# Claude wrapper debug
CLAUDE_DEBUG=1 claude-wrapper --version
```

**Report Issues:**

If you encounter bugs or have suggestions, please report them at:
https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues

---

## Next Steps

1. **Configure API Keys:**
   - Anthropic (for Claude): https://console.anthropic.com/
   - OpenAI (for GPT): https://platform.openai.com/
   - Hugging Face (for models): https://huggingface.co/settings/tokens

2. **Download Models:**
   ```bash
   ollama pull llama3.2
   ollama pull codellama
   ollama pull deepseek-coder
   ```

3. **Explore Tools:**
   - Try `aider` for AI coding
   - Test `code-cursor` for AI pair programming
   - Experiment with `gpt-cli` for quick queries

4. **Customize Configuration:**
   - Edit `~/.dotfiles/home-manager/home.nix`
   - Add your preferred AI models
   - Configure editor settings

5. **Join the Community:**
   - Share your AIDB workflows
   - Contribute improvements
   - Help others get started

---

## Resources

- [Ollama Documentation](https://ollama.ai/docs)
- [Aider Documentation](https://aider.chat/)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs)
- [Cursor Documentation](https://docs.cursor.sh/)
- [Home Manager Manual](https://nix-community.github.io/home-manager/)
- [NixOS Manual](https://nixos.org/manual/nixos/stable/)

---

**Happy AI Development!** 🚀🤖
