# NixOS AI Development System - Package Guide

> **Complete user guide and reference for all packages, services, and tools included in your AI development environment**

---

## Table of Contents

1. [Quick Start & Setup](#quick-start--setup)
2. [System Services](#system-services)
   - [AI & LLM Services](#ai--llm-services)
   - [Development Services](#development-services)
   - [Monitoring & Observability](#monitoring--observability)
   - [Optional Services](#optional-services)
3. [Desktop Environment](#desktop-environment)
4. [Development Tools](#development-tools)
   - [Editors & IDEs](#editors--ides)
   - [Version Control](#version-control)
   - [Nix Development](#nix-development)
   - [Programming Languages](#programming-languages)
5. [AI/ML Development](#aiml-development)
   - [LLM Runtimes](#llm-runtimes)
   - [Python AI Environment](#python-ai-environment)
   - [Vector Databases](#vector-databases)
   - [ML Operations](#ml-operations)
6. [Command Line Tools](#command-line-tools)
   - [Modern CLI Replacements](#modern-cli-replacements)
   - [Terminal Tools](#terminal-tools)
   - [File Management](#file-management)
   - [Network Tools](#network-tools)
7. [Security & Privacy](#security--privacy)
8. [Container & Virtualization](#container--virtualization)
9. [Desktop Applications (Flatpak)](#desktop-applications-flatpak)
10. [System Utilities](#system-utilities)

---

## Quick Start & Setup

### Initial System Setup

After deploying your NixOS system with `nixos-quick-deploy.sh`, complete these setup steps:

> **Note**: Flathub repository is **automatically configured** during deployment. Flatpak apps are installed via Home Manager on first login.

1. **Configure Git Identity**
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

2. **Configure Hugging Face** (optional, required for gated models)
   ```bash
   # Get your token from https://huggingface.co/settings/tokens
   sudo install -o root -g root -m 700 -d /var/lib/nixos-quick-deploy/secrets
   sudo tee /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env >/dev/null <<'EOF'
HF_TOKEN=hf_your_token_here
HUGGINGFACEHUB_API_TOKEN=hf_your_token_here
EOF
   sudo chmod 600 /var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env
   ```

3. **Verify Flatpak Setup** (optional)
   ```bash
   # Check that Flathub remote was added automatically
   flatpak remotes --user
   # Should show: flathub and flathub-beta
   ```

4. **Start AI Services** (optional)
   ```bash
   # Start Ollama (enabled by default)
   sudo systemctl status ollama

   # Enable Hugging Face TGI (after configuring the token file)
   sudo systemctl enable --now huggingface-tgi

   # Qdrant Vector DB (auto-starts; verify status or restart)
   sudo systemctl status qdrant
   sudo systemctl restart qdrant
   ```

5. **Restart Your Shell**
   ```bash
   exec zsh
   # Run the Powerlevel10k configuration wizard on first launch
   ```

### Quick Command Reference

```bash
# System Management
nrs           # Rebuild NixOS (sudo nixos-rebuild switch)
hms           # Rebuild Home Manager
nfu           # Update flakes

# AI Services
ollama list            # List installed models
ollama run llama3      # Run a model
hf-start              # Start Hugging Face TGI
open-webui-up         # Start Open WebUI

# Development
lg                    # Launch lazygit
code-cursor           # AI-powered code editor
nix-ai-help           # Show AI deployment help
```

---

## System Services

### AI & LLM Services

#### **Ollama**
Local LLM runtime for running large language models on your machine.

- **Status**: Enabled by default
- **Usage**:
  ```bash
  ollama list                    # List installed models
  ollama pull llama3            # Download Llama 3 model
  ollama run llama3             # Run model interactively
  ollama serve                  # Start server (automatic via systemd)
  ```
- **Config**: Models stored in `~/.ollama`
- **Links**:
  - [Official Documentation](https://github.com/ollama/ollama)
  - [Model Library](https://ollama.com/library)
  - [API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)

#### **Hugging Face Text Generation Inference (TGI)**
High-performance text generation server for deploying LLMs.

- **Status**: Disabled by default (requires GPU)
- **Port**: 8080
- **Enable**:
  ```bash
  sudo systemctl enable --now huggingface-tgi
  sudo systemctl status huggingface-tgi
  journalctl -u huggingface-tgi -f  # View logs
  ```
- **Default Model**: `meta-llama/Meta-Llama-3-8B-Instruct`
- **Data Directory**: `/var/lib/huggingface`
- **Links**:
  - [TGI Documentation](https://huggingface.co/docs/text-generation-inference)
  - [Supported Models](https://huggingface.co/docs/text-generation-inference/supported_models)
  - [API Reference](https://huggingface.co/docs/text-generation-inference/basic_tutorials/consuming_tgi)

#### **Qdrant Vector Database**
High-performance vector similarity search engine for AI applications.

- **Status**: Enabled by default (starts on rebuild)
- **Ports**: 6333 (HTTP), 6334 (gRPC)
- **Manage**:
  ```bash
  sudo systemctl status qdrant
  sudo systemctl restart qdrant
  ```
- **Access**: `http://localhost:6333/dashboard`
- **Storage**: `/var/lib/qdrant/storage`
- **Links**:
  - [Qdrant Documentation](https://qdrant.tech/documentation/)
  - [Quick Start](https://qdrant.tech/documentation/quick-start/)
  - [Python Client](https://github.com/qdrant/qdrant-client)

### Development Services

#### **Gitea**
Self-hosted Git service with built-in CI/CD (Actions).

- **Status**: Enabled by default
- **Ports**:
  - HTTP: 3000 (`http://localhost:3000`)
  - SSH: 2222
- **Features**:
  - Git repository hosting
  - Issue tracking
  - Pull requests
  - Actions (CI/CD)
  - Package registry
  - LFS support
- **Admin Setup**: Configured during deployment
- **Links**:
  - [Gitea Documentation](https://docs.gitea.com/)
  - [Gitea Actions](https://docs.gitea.com/usage/actions/overview)
  - [API Documentation](https://docs.gitea.com/api/1.20/)

### Monitoring & Observability

#### **Netdata**
Real-time performance monitoring with zero-config auto-discovery.

- **Status**: Enabled by default
- **Port**: 19999
- **Access**: `http://localhost:19999`
- **Features**:
  - CPU, RAM, disk monitoring
  - Container metrics
  - GPU monitoring (if available)
  - Network statistics
  - ML anomaly detection
  - Built-in alerts
- **Resource Usage**: ~100-150MB RAM, <3% CPU
- **Links**:
  - [Netdata Documentation](https://learn.netdata.cloud/)
  - [Dashboard Guide](https://learn.netdata.cloud/docs/dashboard-and-charts)
  - [Alerts Configuration](https://learn.netdata.cloud/docs/alerting/health-configuration-reference)

### Optional Services

#### **PostgreSQL 16**
Production-grade relational database for AI applications.

- **Status**: Disabled by default
- **Port**: 5432
- **Enable**: Set `services.postgresql.enable = true` in `/etc/nixos/configuration.nix`
- **Default DB**: `aidb` (user: `aidb`, password: `changeme`)
- **Links**:
  - [PostgreSQL Documentation](https://www.postgresql.org/docs/16/)
  - [NixOS PostgreSQL Options](https://search.nixos.org/options?query=services.postgresql)

#### **Redis**
In-memory data store for caching and message queues.

- **Status**: Disabled by default
- **Port**: 6379
- **Enable**: Set `services.redis.servers."default".enable = true`
- **Max Memory**: 512MB (LRU eviction)
- **Links**:
  - [Redis Documentation](https://redis.io/docs/)
  - [Redis Commands](https://redis.io/commands/)

#### **Nginx**
High-performance web server and reverse proxy.

- **Status**: Disabled by default
- **Use Case**: Proxy AI services, serve static files
- **Links**:
  - [Nginx Documentation](https://nginx.org/en/docs/)
  - [NixOS Nginx Guide](https://nixos.wiki/wiki/Nginx)

#### **Prometheus & Grafana**
Metrics collection and visualization platform.

- **Status**: Disabled by default
- **Ports**:
  - Prometheus: 9090
  - Grafana: 3001 (`http://localhost:3001`)
- **Default Credentials**: admin/changeme (change immediately!)
- **Links**:
  - [Prometheus Documentation](https://prometheus.io/docs/)
  - [Grafana Documentation](https://grafana.com/docs/)
  - [Grafana Dashboards](https://grafana.com/grafana/dashboards/)

---

## Desktop Environment

### **COSMIC Desktop**
Modern Wayland-native desktop environment built in Rust.

- **Based on**: System76's COSMIC
- **Display Protocol**: Wayland (100% native, no X11)
- **Key Features**:
  - Tiling window manager
  - Modern compositor
  - Auto day/night theme switching
  - Built-in clipboard manager
- **Applications** (included):
  - COSMIC Settings
  - COSMIC Files (file manager)
  - COSMIC Edit (text editor)
  - COSMIC Terminal
  - COSMIC Store (app store with Flatpak support)
- **Settings**: Launch via `cosmic-settings` or app menu
- **Links**:
  - [COSMIC Desktop](https://github.com/pop-os/cosmic-epoch)
  - [COSMIC Guide](https://github.com/pop-os/cosmic-epoch/wiki)

### **Key Environment Variables**

All applications are configured for Wayland by default:
- `QT_QPA_PLATFORM=wayland` - Qt apps use Wayland
- `SDL_VIDEODRIVER=wayland` - SDL2 apps use Wayland
- `MOZ_ENABLE_WAYLAND=1` - Firefox uses Wayland
- `NIXOS_OZONE_WL=1` - Electron apps (VSCodium) use Wayland

---

## Development Tools

### Editors & IDEs

#### **VSCodium**
Open-source build of VS Code without Microsoft telemetry.

- **Configured Extensions**:
  - **Nix**: `nix-ide`, `nix-env-selector`
  - **Python**: `python`, `pylance`, `black-formatter`
  - **Jupyter**: Full notebook support
  - **Git**: `gitlens`
  - **AI Assistants**: `continue`, `codeium`, `chatgpt`
- **Python Environment**: Pre-configured with AI/ML interpreter
- **AI Endpoints**:
  - Ollama: `http://localhost:11434`
  - Hugging Face TGI: `http://localhost:8080`
- **Launch**:
  ```bash
  codium              # Launch VSCodium
  code-cursor         # Launch AI-powered Cursor IDE
  ```
- **Settings**: `~/.config/VSCodium/User/settings.json` (managed declaratively)
- **Links**:
  - [VSCodium](https://vscodium.com/)
  - [VS Code Docs](https://code.visualstudio.com/docs)
  - [Continue.dev](https://continue.dev/docs)
  - [Codeium](https://codeium.com/vscode_tutorial)

#### **Neovim**
Modern Vim fork with async support and Lua configuration.

- **Launch**: `nvim`
- **Features**: Async plugins, LSP support, TreeSitter
- **Links**:
  - [Neovim Documentation](https://neovim.io/doc/)
  - [Awesome Neovim](https://github.com/rockerBOO/awesome-neovim)

#### **Code Cursor**
AI-powered code editor with built-in AI pair programming.

- **Launch**: `code-cursor` or `cursor`
- **Features**: AI autocomplete, chat, code generation
- **Links**:
  - [Cursor Documentation](https://docs.cursor.com/)

### Version Control

#### **Git**
Distributed version control system.

- **Configured Aliases**:
  - `git st` → status
  - `git visual` → graph log
  - `git unstage` → reset HEAD
- **LFS Support**: Enabled (required for Hugging Face model repos)
- **Shell Aliases**:
  ```bash
  gs    # git status
  ga    # git add
  gc    # git commit
  gp    # git push
  gl    # git pull
  gd    # git diff
  ```
- **Links**:
  - [Git Documentation](https://git-scm.com/doc)
  - [Pro Git Book](https://git-scm.com/book/en/v2)
  - [Git LFS](https://git-lfs.github.com/)

#### **Lazygit**
Terminal UI for Git with an intuitive interface.

- **Launch**: `lazygit` or `lg`
- **Features**:
  - Visual commit graph
  - Interactive rebase
  - Stash management
  - Branch operations
- **Links**:
  - [Lazygit Documentation](https://github.com/jesseduffield/lazygit)
  - [Keybindings](https://github.com/jesseduffield/lazygit/blob/master/docs/keybindings/Keybindings_en.md)

#### **Tig**
Text-mode interface for Git repositories.

- **Launch**: `tig`
- **Usage**: `tig [options] [args]`
- **Links**:
  - [Tig Manual](https://jonas.github.io/tig/doc/tig.1.html)

#### **Tea**
Official Gitea CLI for automation and workflows.

- **Usage**:
  ```bash
  tea repos ls              # List repositories
  tea issues ls             # List issues
  tea pulls create          # Create pull request
  ```
- **Links**:
  - [Tea Documentation](https://gitea.com/gitea/tea)
  - [Tea Commands](https://gitea.com/gitea/tea#usage)

### Nix Development

#### **Nix Package Tools**

| Tool | Description | Usage |
|------|-------------|-------|
| **nix-tree** | Visualize Nix dependency trees | `nix-tree /nix/store/...` |
| **nix-index** | Fast package file search | `nix-locate bin/python` |
| **nix-prefetch-git** | Prefetch git repos for Nix | `nix-prefetch-git https://...` |
| **nixpkgs-fmt** | Nix code formatter | `nixpkgs-fmt file.nix` |
| **alejandra** | Alternative Nix formatter | `alejandra file.nix` |
| **statix** | Nix linter with suggestions | `statix check` |
| **deadnix** | Find unused Nix code | `deadnix .` |
| **nix-output-monitor** | Better build output | `nom build` |
| **nix-du** | Nix store disk usage | `nix-du` |
| **nixpkgs-review** | Review nixpkgs PRs | `nixpkgs-review pr 12345` |
| **nix-diff** | Compare derivations | `nix-diff drv1 drv2` |

**Shell Aliases**:
```bash
nrs          # sudo nixos-rebuild switch
nrt          # sudo nixos-rebuild test
hms          # home-manager switch
nfu          # nix flake update
nfc          # nix flake check
nfb          # nix build
nfd          # nix develop
```

**Links**:
- [Nix Manual](https://nixos.org/manual/nix/stable/)
- [NixOS Manual](https://nixos.org/manual/nixos/stable/)
- [Nix Pills](https://nixos.org/guides/nix-pills/)
- [Home Manager](https://nix-community.github.io/home-manager/)

### Programming Languages

#### **Python 3.13 (AI/ML Environment)**
Comprehensive Python environment for AI/ML development.

- **Interpreter Path**: Available via `python3` or `pythonAiEnv`
- **Included Libraries**: See [Python AI Environment](#python-ai-environment)
- **Jupyter**: Integrated with VSCodium and standalone
- **Links**:
  - [Python Documentation](https://docs.python.org/3.13/)
  - [Python Package Index](https://pypi.org/)

#### **Node.js 22**
JavaScript runtime for web development.

- **Usage**: `node`, `npm`, `npx`
- **Global Packages**: Installed to `~/.npm-global`
- **Links**:
  - [Node.js Documentation](https://nodejs.org/docs/latest/api/)
  - [NPM Documentation](https://docs.npmjs.com/)

#### **Go**
Systems programming language by Google.

- **Usage**: `go build`, `go run`, `go test`
- **Links**:
  - [Go Documentation](https://go.dev/doc/)
  - [Go by Example](https://gobyexample.com/)

#### **Rust**
Safe systems programming language.

- **Tools**: `rustc` (compiler), `cargo` (package manager)
- **Usage**:
  ```bash
  cargo new myproject    # Create new project
  cargo build           # Build project
  cargo run             # Run project
  cargo test            # Run tests
  ```
- **Links**:
  - [Rust Book](https://doc.rust-lang.org/book/)
  - [Rust Documentation](https://www.rust-lang.org/learn)
  - [Cargo Guide](https://doc.rust-lang.org/cargo/)

#### **Ruby**
Dynamic programming language.

- **Usage**: `ruby`, `gem`, `irb`
- **Links**:
  - [Ruby Documentation](https://www.ruby-lang.org/en/documentation/)

---

## AI/ML Development

### LLM Runtimes

#### **GPT4All**
Run LLMs locally with a desktop interface.

- **Launch**: Via application menu or `gpt4all`
- **Features**:
  - Desktop GUI for LLMs
  - Model downloader
  - Chat interface
  - Local inference
- **Model Storage**: `~/.local/share/nomic.ai/GPT4All`
- **Links**:
  - [GPT4All Documentation](https://docs.gpt4all.io/)
  - [Model Downloads](https://gpt4all.io/index.html)

#### **llama.cpp**
Efficient C++ implementation for running LLMs.

- **Usage**:
  ```bash
  llama-cli -m model.gguf -p "Your prompt"
  llama-server -m model.gguf    # Start API server
  ```
- **Supported Formats**: GGUF, GGML
- **Links**:
  - [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
  - [Model Conversion](https://github.com/ggerganov/llama.cpp/blob/master/docs/build.md)

### Python AI Environment

Complete Python environment with AI/ML libraries pre-installed.

#### **Core ML Frameworks**

| Library | Description | Documentation |
|---------|-------------|---------------|
| **PyTorch** | Deep learning framework | [pytorch.org](https://pytorch.org/docs/) |
| **TensorFlow** | ML platform by Google | [tensorflow.org](https://www.tensorflow.org/api_docs) |
| **scikit-learn** | Classical ML algorithms | [scikit-learn.org](https://scikit-learn.org/stable/) |
| **transformers** | Hugging Face transformers | [huggingface.co/docs/transformers](https://huggingface.co/docs/transformers) |

#### **LLM Frameworks**

| Library | Description | Documentation |
|---------|-------------|---------------|
| **LangChain** | LLM application framework | [python.langchain.com](https://python.langchain.com/) |
| **LangChain-OpenAI** | OpenAI integration | [docs](https://python.langchain.com/docs/integrations/platforms/openai) |
| **LangChain-Community** | Community integrations | [docs](https://python.langchain.com/docs/integrations/platforms/) |
| **Llama-Index** | Data framework for LLMs | [docs.llamaindex.ai](https://docs.llamaindex.ai/) |
| **llama-cpp-python** | Python bindings for llama.cpp | [github.com](https://github.com/abetlen/llama-cpp-python) |

#### **Data Science & Analysis**

| Library | Description | Documentation |
|---------|-------------|---------------|
| **pandas** | Data manipulation | [pandas.pydata.org](https://pandas.pydata.org/docs/) |
| **numpy** | Numerical computing | [numpy.org](https://numpy.org/doc/) |
| **polars** | Fast DataFrame library (Rust) | [pola-rs.github.io](https://pola-rs.github.io/polars-book/) |
| **matplotlib** | Plotting library | [matplotlib.org](https://matplotlib.org/stable/contents.html) |
| **seaborn** | Statistical visualization | [seaborn.pydata.org](https://seaborn.pydata.org/) |

#### **Jupyter & Notebooks**

| Tool | Description | Documentation |
|------|-------------|---------------|
| **JupyterLab** | Web-based notebook IDE | [jupyterlab.readthedocs.io](https://jupyterlab.readthedocs.io/) |
| **IPython** | Interactive Python shell | [ipython.readthedocs.io](https://ipython.readthedocs.io/) |
| **ipykernel** | IPython kernel for Jupyter | [docs](https://ipython.readthedocs.io/en/stable/install/kernel_install.html) |
| **ipywidgets** | Interactive widgets | [ipywidgets.readthedocs.io](https://ipywidgets.readthedocs.io/) |

**Launch Jupyter**:
```bash
jupyter lab               # Launch JupyterLab
jupyter notebook          # Launch classic notebook
ipython                   # Interactive Python shell
```

#### **Hugging Face Ecosystem**

| Library | Description | Documentation |
|---------|-------------|---------------|
| **transformers** | Pre-trained models | [huggingface.co/docs/transformers](https://huggingface.co/docs/transformers) |
| **datasets** | Dataset library | [huggingface.co/docs/datasets](https://huggingface.co/docs/datasets) |
| **accelerate** | Distributed training | [huggingface.co/docs/accelerate](https://huggingface.co/docs/accelerate) |
| **diffusers** | Diffusion models | [huggingface.co/docs/diffusers](https://huggingface.co/docs/diffusers) |
| **peft** | Parameter-efficient fine-tuning | [huggingface.co/docs/peft](https://huggingface.co/docs/peft) |
| **tokenizers** | Fast tokenizers | [huggingface.co/docs/tokenizers](https://huggingface.co/docs/tokenizers) |
| **evaluate** | Model evaluation | [huggingface.co/docs/evaluate](https://huggingface.co/docs/evaluate) |
| **gradio** | ML app interfaces | [gradio.app/docs](https://www.gradio.app/docs) |

#### **API Clients**

| Library | Description | Documentation |
|---------|-------------|---------------|
| **openai** | OpenAI API client | [platform.openai.com](https://platform.openai.com/docs/api-reference) |
| **anthropic** | Anthropic (Claude) API | [docs.anthropic.com](https://docs.anthropic.com/) |

#### **Agent Orchestration & MCP**

| Library | Purpose | Documentation |
|---------|---------|---------------|
| **litellm** | Unified LLM router with cost controls | [docs.litellm.ai](https://docs.litellm.ai/) |
| **tiktoken** | Fast token counting utilities | [github.com/openai/tiktoken](https://github.com/openai/tiktoken) |
| **fastapi** | Async API framework for tool servers | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| **uvicorn** | ASGI server for FastAPI apps | [www.uvicorn.org](https://www.uvicorn.org/) |
| **httpx** | Async HTTP client for integrations | [www.python-httpx.org](https://www.python-httpx.org/) |
| **pydantic** | Data validation for tool schemas | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| **typer** | CLI interface builder for agents | [typer.tiangolo.com](https://typer.tiangolo.com/) |
| **rich** | Terminal formatting for agent logs | [rich.readthedocs.io](https://rich.readthedocs.io/) |
| **sqlalchemy** | Structured data storage backend | [docs.sqlalchemy.org](https://docs.sqlalchemy.org/) |
| **duckdb** | In-process analytics database | [duckdb.org/docs](https://duckdb.org/docs/) |

#### **Code Quality & Formatting**

| Tool | Description | Documentation |
|------|-------------|---------------|
| **black** | Python code formatter | [black.readthedocs.io](https://black.readthedocs.io/) |
| **ruff** | Fast Python linter | [docs.astral.sh/ruff](https://docs.astral.sh/ruff/) |
| **mypy** | Static type checker | [mypy.readthedocs.io](https://mypy.readthedocs.io/) |
| **pylint** | Code analysis tool | [pylint.pycqa.org](https://pylint.pycqa.org/) |

### Vector Databases

#### **ChromaDB**
Embedding database for AI applications.

- **Python Usage**:
  ```python
  import chromadb
  client = chromadb.Client()
  collection = client.create_collection("docs")
  ```
- **Links**:
  - [ChromaDB Documentation](https://docs.trychroma.com/)
  - [Python Client](https://docs.trychroma.com/reference/py-client)

#### **Qdrant Client**
Python client for Qdrant vector database.

- **Usage**:
  ```python
  from qdrant_client import QdrantClient
  client = QdrantClient("localhost", port=6333)
  ```
- **Links**:
  - [Qdrant Client Docs](https://qdrant.github.io/qdrant/redoc/index.html)
  - [Python Examples](https://qdrant.tech/documentation/examples/)

#### **Pinecone Client**
Client for Pinecone cloud vector database.

- **Links**:
  - [Pinecone Documentation](https://docs.pinecone.io/)

#### **FAISS**
Facebook AI Similarity Search - efficient similarity search library.

- **Usage**: Optimized vector similarity search
- **Links**:
  - [FAISS GitHub](https://github.com/facebookresearch/faiss)
  - [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)

#### **Sentence Transformers**
Framework for sentence/text embeddings.

- **Python Usage**:
  ```python
  from sentence_transformers import SentenceTransformer
  model = SentenceTransformer('all-MiniLM-L6-v2')
  embeddings = model.encode(sentences)
  ```
- **Links**:
  - [Documentation](https://www.sbert.net/)
  - [Pretrained Models](https://www.sbert.net/docs/pretrained_models.html)

### ML Operations

#### **DVC (Data Version Control)**
Version control for ML projects and datasets.

- **Usage**:
  ```bash
  dvc init                  # Initialize DVC
  dvc add data/dataset.csv  # Track dataset
  dvc push                  # Push to remote storage
  dvc pull                  # Pull data
  ```
- **Links**:
  - [DVC Documentation](https://dvc.org/doc)
  - [Get Started](https://dvc.org/doc/start)

#### **DuckDB**
Fast analytical database for data analysis.

- **Usage**:
  ```bash
  duckdb                    # Start DuckDB CLI
  duckdb mydb.db            # Open database
  ```
- **Python**:
  ```python
  import duckdb
  duckdb.sql("SELECT * FROM 'data.parquet'")
  ```
- **Links**:
  - [DuckDB Documentation](https://duckdb.org/docs/)
  - [Python API](https://duckdb.org/docs/api/python/overview)

#### **Aider**
AI pair programming in the terminal.

- **Usage**:
  ```bash
  aider                     # Start in current git repo
  aider file1.py file2.py   # Work on specific files
  ```
- **Environment**: Pre-configured with local LLM endpoints
- **Links**:
  - [Aider Documentation](https://aider.chat/)
  - [Usage Guide](https://aider.chat/docs/usage.html)

---

## Command Line Tools

### Modern CLI Replacements

Traditional tools replaced with modern, faster alternatives:

| Traditional | Modern | Description | Links |
|-------------|--------|-------------|-------|
| `grep` | **ripgrep (rg)** | Fastest recursive grep | [github.com/BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) |
| `find` | **fd** | Fast and user-friendly find | [github.com/sharkdp/fd](https://github.com/sharkdp/fd) |
| `cat` | **bat** | Cat with syntax highlighting | [github.com/sharkdp/bat](https://github.com/sharkdp/bat) |
| `ls` | **eza** | Modern ls with icons | [eza.rocks](https://eza.rocks/) |
| `du` | **dust** | Intuitive disk usage | [github.com/bootandy/dust](https://github.com/bootandy/dust) |
| `df` | **duf** | Better disk usage viewer | [github.com/muesli/duf](https://github.com/muesli/duf) |
| `dig` | **dog** | Modern DNS lookup | [dns.lookup.dog](https://dns.lookup.dog/) |

**Shell Aliases**:
```bash
ll     # eza -l --icons
la     # eza -la --icons
lt     # eza --tree --icons
cat    # bat (with syntax highlighting)
du     # dust
df     # duf
ff     # fd (find files)
rg     # ripgrep --smart-case
```

### Additional CLI Tools

#### **fzf - Fuzzy Finder**
- **Usage**: `CTRL+R` (history), `CTRL+T` (files), `ALT+C` (directories)
- **Commands**: `fzf`, or pipe any list into it
- **Links**: [github.com/junegunn/fzf](https://github.com/junegunn/fzf)

#### **jq - JSON Processor**
- **Usage**: `cat data.json | jq '.field'`
- **Links**: [jqlang.github.io/jq](https://jqlang.github.io/jq/)

#### **yq - YAML Processor**
- **Usage**: `cat config.yaml | yq '.field'`
- **Links**: [mikefarah.gitbook.io/yq](https://mikefarah.gitbook.io/yq/)

#### **broot - Tree Navigation**
- **Usage**: `broot` or `br`
- **Features**: Navigate large directory trees efficiently
- **Links**: [dystroy.org/broot](https://dystroy.org/broot/)

#### **direnv - Environment Manager**
- **Usage**: Create `.envrc` in project, run `direnv allow`
- **Integration**: Automatically loads/unloads environment variables
- **Nix**: Use `use flake` in `.envrc` for automatic dev shells
- **Links**: [direnv.net](https://direnv.net/)

#### **mcfly - Smart History Search**
- **Usage**: `CTRL+R` (enhanced history search with AI)
- **Features**: Learns from your command patterns
- **Links**: [github.com/cantino/mcfly](https://github.com/cantino/mcfly)

### Terminal Tools

#### **Zellij**
Modern terminal workspace (alternative to tmux).

- **Usage**:
  ```bash
  zellij           # Start new session
  zellij attach    # Reconnect to session
  zellij ls        # List sessions
  ```
- **Default Keybindings**: `Ctrl+g` then command key
- **Links**:
  - [Zellij Documentation](https://zellij.dev/documentation/)
  - [Layouts](https://zellij.dev/documentation/layouts.html)

#### **tmux**
Traditional terminal multiplexer.

- **Usage**: `tmux new -s session_name`
- **Links**:
  - [tmux GitHub](https://github.com/tmux/tmux/wiki)
  - [tmux Cheat Sheet](https://tmuxcheatsheet.com/)

#### **screen**
Classic terminal session manager.

- **Usage**: `screen`, `screen -r` (reattach)
- **Links**: [GNU Screen Manual](https://www.gnu.org/software/screen/manual/screen.html)

#### **Alacritty**
GPU-accelerated terminal emulator.

- **Config**: `~/.config/alacritty/alacritty.yml`
- **Font**: MesloLGS NF (Powerline compatible)
- **Links**: [github.com/alacritty/alacritty](https://github.com/alacritty/alacritty)

#### **asciinema**
Record and share terminal sessions.

- **Usage**:
  ```bash
  asciinema rec session.cast   # Record
  asciinema play session.cast  # Play back
  asciinema upload session.cast # Share online
  ```
- **Links**: [asciinema.org](https://asciinema.org/)

### File Management

#### **ranger**
Vi-like file manager for the console.

- **Usage**: `ranger`
- **Navigation**: Vi keys (`hjkl`)
- **Links**: [github.com/ranger/ranger](https://github.com/ranger/ranger)

#### **Archive Tools**

| Tool | Description | Usage |
|------|-------------|-------|
| **p7zip** | 7-Zip archiver | `7z x archive.7z` |
| **unrar** | Extract RAR archives | `unrar x archive.rar` |
| **zip/unzip** | ZIP archives | `zip -r archive.zip dir/` |
| **dos2unix** | Convert line endings | `dos2unix file.txt` |

#### **File Transfer**

| Tool | Description | Usage |
|------|-------------|-------|
| **rsync** | Incremental file transfer | `rsync -av src/ dest/` |
| **rclone** | Cloud storage sync | `rclone sync local remote:` |

**Links**:
- [rsync Manual](https://download.samba.org/pub/rsync/rsync.1)
- [rclone Documentation](https://rclone.org/docs/)

### Network Tools

#### **HTTP Clients**

| Tool | Description | Usage |
|------|-------------|-------|
| **httpie** | User-friendly HTTP client | `http GET example.com` |
| **curl** | Transfer data with URLs | `curl https://example.com` |
| **wget** | Network downloader | `wget https://example.com/file` |

#### **Network Diagnostics**

| Tool | Description | Usage |
|------|-------------|-------|
| **mtr** | Network diagnostic tool | `mtr google.com` |
| **nmap** | Network scanner | `nmap -A 192.168.1.0/24` |
| **zenmap** | GUI frontend for nmap scans | `zenmap` |
| **wireshark** | GUI network protocol analyzer (ships `tshark` CLI) | `wireshark` |
| **netcat** | TCP/UDP networking | `nc -l 8080` |
| **socat** | Multipurpose relay | `socat TCP-LISTEN:8080 -` |

#### **gRPC Tools**

| Tool | Description | Usage |
|------|-------------|-------|
| **grpcurl** | cURL for gRPC | `grpcurl -plaintext localhost:50051 list` |

**Links**:
- [httpie.io](https://httpie.io/docs)
- [curl Manual](https://curl.se/docs/manual.html)
- [nmap Documentation](https://nmap.org/docs.html)
- [Zenmap User Guide](https://nmap.org/book/zenmap-manual.html)
- [Wireshark Docs](https://www.wireshark.org/docs/)

Zenmap installs automatically whenever the channel provides it, so you always have a point-and-click interface for building complex scans. Wireshark brings both the desktop analyzer and the `tshark` CLI helper, making it easy to pivot between GUI and scripted workflows.

---

## Security & Privacy

### Encryption & Secrets

#### **GnuPG (GPG)**
GNU Privacy Guard for encryption.

- **Usage**:
  ```bash
  gpg --gen-key                    # Generate key
  gpg --encrypt file.txt           # Encrypt file
  gpg --decrypt file.txt.gpg       # Decrypt file
  gpg --sign file.txt              # Sign file
  ```
- **Agent**: `gpg-agent` enabled with SSH support
- **Links**:
  - [GnuPG Documentation](https://gnupg.org/documentation/)
  - [GPG Tutorial](https://www.gnupg.org/gph/en/manual.html)

#### **pass (password-store)**
Standard Unix password manager.

- **Usage**:
  ```bash
  pass init <gpg-key-id>           # Initialize
  pass insert email/work           # Add password
  pass email/work                  # Retrieve password
  pass generate email/work 20      # Generate password
  ```
- **Storage**: `~/.local/share/password-store`
- **Links**:
  - [passwordstore.org](https://www.passwordstore.org/)

#### **KeePassXC**
Cross-platform password manager (GUI).

- **Launch**: Via application menu
- **Features**:
  - Encrypted database
  - Browser integration
  - SSH agent
  - TOTP support
- **Links**:
  - [keepassxc.org](https://keepassxc.org/docs/)

#### **age**
Modern encryption tool for files.

- **Usage**:
  ```bash
  age-keygen -o key.txt            # Generate key
  age -r <recipient> file.txt      # Encrypt
  age -d -i key.txt file.txt.age   # Decrypt
  ```
- **Links**:
  - [github.com/FiloSottile/age](https://github.com/FiloSottile/age)

#### **sops**
Encrypted configuration files.

- **Usage**:
  ```bash
  sops secrets.yaml                # Edit encrypted file
  sops -d secrets.yaml             # Decrypt and print
  ```
- **Supports**: YAML, JSON, ENV, INI
- **Links**:
  - [github.com/getsops/sops](https://github.com/getsops/sops)

### Security Scanning

#### **ClamAV**
Open-source antivirus engine.

- **Usage**:
  ```bash
  sudo freshclam                   # Update virus definitions
  clamscan -r /path/to/scan        # Scan directory
  clamscan -i -r /home             # Scan home (infected only)
  ```
- **GUI**: `clamtk` (ClamTK)
- **Links**:
  - [ClamAV Documentation](https://docs.clamav.net/)

#### **Lynis**
Security auditing tool for Unix systems.

- **Usage**:
  ```bash
  sudo lynis audit system          # Full system audit
  ```
- **Features**: Rootkit detection, security hardening suggestions
- **Links**:
  - [cisofy.com/lynis](https://cisofy.com/lynis/)

#### **AIDE**
Advanced Intrusion Detection Environment.

- **Usage**:
  ```bash
  sudo aide --init                 # Initialize database
  sudo aide --check                # Check for changes
  ```
- **Purpose**: File integrity monitoring, rootkit detection
- **Links**:
  - [aide.github.io](https://aide.github.io/)

#### **Trivy**
Vulnerability scanner for containers and dependencies.

- **Usage**:
  ```bash
  trivy image nginx:latest         # Scan container image
  trivy fs .                       # Scan filesystem
  trivy repo https://...           # Scan git repo
  ```
- **Links**:
  - [aquasecurity.github.io/trivy](https://aquasecurity.github.io/trivy/)

#### **cosign**
Container signing and verification.

- **Usage**:
  ```bash
  cosign generate-key-pair         # Generate keys
  cosign sign image:tag            # Sign image
  cosign verify image:tag          # Verify signature
  ```
- **Links**:
  - [docs.sigstore.dev/cosign](https://docs.sigstore.dev/cosign/overview/)

---

## Container & Virtualization

### **Podman**
Daemonless container engine (Docker-compatible).

- **Usage**:
  ```bash
  podman run -it ubuntu bash       # Run container
  podman ps                        # List containers
  podman images                    # List images
  podman build -t myapp .          # Build image
  podman-compose up                # Docker-compose equivalent
  ```
- **Socket**: Compatible with Docker CLI and docker-compose
- **Rootless**: Runs without root privileges
- **Links**:
  - [Podman Documentation](https://docs.podman.io/)
  - [Podman Desktop](https://podman-desktop.io/) (Flatpak app)

### **Podman Utilities**

| Tool | Description | Links |
|------|-------------|-------|
| **podman-compose** | Docker-compose alternative | [github.com](https://github.com/containers/podman-compose) |
| **podman-tui** | Terminal UI for Podman | [github.com](https://github.com/containers/podman-tui) |
| **buildah** | Build OCI containers | [buildah.io](https://buildah.io/) |
| **skopeo** | Inspect and copy images | [github.com](https://github.com/containers/skopeo) |
| **crun** | Fast OCI runtime | [github.com](https://github.com/containers/crun) |

### **QEMU**
Machine emulator and virtualizer.

- **Usage**:
  ```bash
  qemu-system-x86_64 -cdrom os.iso -m 2048
  ```
- **Features**: Full system emulation, KVM acceleration
- **Links**:
  - [QEMU Documentation](https://www.qemu.org/documentation/)

### **virtiofsd**
VirtIO filesystem daemon for VM file sharing.

- **Links**: [gitlab.com/virtio-fs](https://gitlab.com/virtio-fs/virtiofsd)

---

## Desktop Applications (Flatpak)

All desktop applications are installed via Flatpak for better sandboxing and security.

### System Tools

#### **Flatseal**
Manage Flatpak permissions.

- **App ID**: `com.github.tchx84.Flatseal`
- **Launch**: Via app menu
- **Purpose**: Review and modify Flatpak app permissions
- **Links**: [github.com/tchx84/Flatseal](https://github.com/tchx84/Flatseal)

#### **Resources**
System monitor (CPU, GPU, RAM, network).

- **App ID**: `net.nokyan.Resources`
- **Launch**: Via app menu
- **Features**:
  - Real-time monitoring
  - GPU utilization
  - Network stats
  - Process management
- **Links**: [github.com/nokyan/resources](https://github.com/nokyan/resources)

#### **File Roller**
Archive manager (zip, tar, 7z, rar).

- **App ID**: `org.gnome.FileRoller`
- **Launch**: Right-click archive files
- **Links**: [gitlab.gnome.org/GNOME/file-roller](https://gitlab.gnome.org/GNOME/file-roller)

### Media

#### **VLC**
Universal media player.

- **App ID**: `org.videolan.VLC`
- **Features**: Plays virtually any video/audio format
- **Links**: [videolan.org/vlc](https://www.videolan.org/vlc/)

#### **MPV**
Minimalist video player.

- **App ID**: `io.mpv.Mpv`
- **Features**: Lightweight, keyboard-driven, scriptable
- **Links**: [mpv.io](https://mpv.io/)

### Browsers

#### **Firefox**
Privacy-focused web browser.

- **App ID**: `org.mozilla.firefox`
- **Wayland**: Native support enabled
- **Links**: [mozilla.org/firefox](https://www.mozilla.org/en-US/firefox/)

### Productivity

#### **Obsidian**
Markdown-based note-taking and knowledge base.

- **App ID**: `md.obsidian.Obsidian`
- **Features**:
  - Local-first markdown notes
  - Graph view
  - Plugins ecosystem
  - Vault synchronization
- **AI Integration**: Bootstrap script available (`obsidian-ai`)
- **Links**:
  - [obsidian.md](https://obsidian.md/)
  - [Help Documentation](https://help.obsidian.md/)
  - [Community Plugins](https://obsidian.md/plugins)

### Development

#### **Podman Desktop**
GUI for managing Podman containers.

- **App ID**: `io.podman_desktop.PodmanDesktop`
- **Features**:
  - Container management
  - Image builder
  - Kubernetes support
  - Extension system
- **Links**: [podman-desktop.io](https://podman-desktop.io/)

### Gaming

#### **Prism Launcher**
Modern Minecraft launcher with multi-instance support.

- **App ID**: `org.prismlauncher.PrismLauncher`
- **Features**:
  - Manage multiple profiles with isolated mods and resource packs
  - Download any official Minecraft version, including snapshots
  - Built-in modrinth/CurseForge browser and automatic dependency resolution
  - Export and import curated instances for quick sharing
- **Links**: [prismlauncher.org](https://prismlauncher.org/)

### Database Tools

#### **SQLite Browser**
GUI for SQLite databases.

- **App ID**: `org.sqlitebrowser.sqlitebrowser`
- **Features**:
  - Browse and edit SQLite databases
  - Execute SQL queries
  - Import/export data
- **Links**: [sqlitebrowser.org](https://sqlitebrowser.org/)

#### **DBeaver Community**
Universal database tool.

- **App ID**: `com.dbeaver.DBeaverCommunity`
- **Supports**: PostgreSQL, MySQL, SQLite, MongoDB, and 80+ databases
- **Features**:
  - SQL editor
  - ER diagrams
  - Data export/import
  - Query builder
- **Links**: [dbeaver.io](https://dbeaver.io/)

---

## System Utilities

### Monitoring

#### **htop**
Interactive process viewer.

- **Usage**: `htop`
- **Features**: CPU, RAM, process tree
- **Links**: [htop.dev](https://htop.dev/)

#### **btop**
Resource monitor with modern UI.

- **Usage**: `btop`
- **Features**: CPU, RAM, disk, network, processes
- **Links**: [github.com/aristocratos/btop](https://github.com/aristocratos/btop)

#### **glances**
System monitoring dashboard.

- **Usage**: `glances`
- **Features**: Comprehensive system overview
- **Links**: [nicolargo.github.io/glances](https://nicolargo.github.io/glances/)

### Disk Management

#### **GNOME Disks**
GUI disk manager and formatter.

- **Launch**: Via app menu (`gnome-disk-utility`)
- **Features**: Partition, format, benchmark disks
- **Links**: [wiki.gnome.org/Apps/Disks](https://wiki.gnome.org/Apps/Disks)

#### **parted**
Command-line partitioning tool.

- **Usage**: `sudo parted /dev/sdX`
- **Links**: [GNU Parted Manual](https://www.gnu.org/software/parted/manual/)

#### **efibootmgr**
Modify EFI boot entries.

- **Usage**: `sudo efibootmgr -v`
- **Links**: [linux.die.net/man/8/efibootmgr](https://linux.die.net/man/8/efibootmgr)

### Documentation

#### **tldr**
Simplified man pages with examples.

- **Usage**: `tldr command`
- **Example**: `tldr tar`
- **Links**: [tldr.sh](https://tldr.sh/)

#### **cht.sh**
Community cheat sheets.

- **Usage**: `cht.sh python/list` or `curl cht.sh/python/list`
- **Links**: [cht.sh](https://cht.sh/)

#### **navi**
Interactive cheatsheet tool.

- **Usage**: `navi` or `CTRL+G`
- **Links**: [github.com/denisidoro/navi](https://github.com/denisidoro/navi)

### Miscellaneous

#### **pandoc**
Universal document converter.

- **Usage**: `pandoc input.md -o output.pdf`
- **Formats**: Markdown, HTML, PDF, DOCX, and more
- **Links**: [pandoc.org](https://pandoc.org/)

#### **Visualization Tools**

| Tool | Description | Usage |
|------|-------------|-------|
| **mermaid-cli** | Generate diagrams from text | `mmdc -i diagram.mmd -o diagram.png` |
| **graphviz** | Graph visualization | `dot -Tpng graph.dot -o graph.png` |
| **plantuml** | UML diagrams | `plantuml diagram.puml` |

**Links**:
- [mermaid.js.org](https://mermaid.js.org/)
- [graphviz.org](https://graphviz.org/)
- [plantuml.com](https://plantuml.com/)

#### **Performance Tools**

| Tool | Description | Usage |
|------|-------------|-------|
| **hyperfine** | Command-line benchmarking | `hyperfine 'command1' 'command2'` |
| **k6** | Load testing | `k6 run script.js` |

**Links**:
- [github.com/sharkdp/hyperfine](https://github.com/sharkdp/hyperfine)
- [k6.io](https://k6.io/docs/)

---

## Additional Resources

### NixOS Learning Resources

- **Official Manuals**:
  - [Nix Manual](https://nixos.org/manual/nix/stable/)
  - [NixOS Manual](https://nixos.org/manual/nixos/stable/)
  - [Nixpkgs Manual](https://nixos.org/manual/nixpkgs/stable/)
  - [Home Manager Manual](https://nix-community.github.io/home-manager/)

- **Tutorials**:
  - [Nix Pills](https://nixos.org/guides/nix-pills/) - In-depth tutorial series
  - [Zero to Nix](https://zero-to-nix.com/) - Beginner-friendly guide
  - [NixOS Wiki](https://nixos.wiki/) - Community documentation

- **Package Search**:
  - [search.nixos.org/packages](https://search.nixos.org/packages) - Search packages
  - [search.nixos.org/options](https://search.nixos.org/options) - Search configuration options

### AI/ML Resources

- **Hugging Face**:
  - [Models Hub](https://huggingface.co/models)
  - [Datasets Hub](https://huggingface.co/datasets)
  - [Learn NLP](https://huggingface.co/learn)

- **LangChain**:
  - [Documentation](https://python.langchain.com/)
  - [LangSmith](https://www.langchain.com/langsmith) - Debugging and monitoring

- **Llama-Index**:
  - [Documentation](https://docs.llamaindex.ai/)
  - [Examples](https://github.com/run-llama/llama_index/tree/main/docs/examples)

- **Vector Databases**:
  - [Qdrant Learn](https://qdrant.tech/documentation/tutorials/)
  - [ChromaDB Cookbook](https://docs.trychroma.com/guides)

### Community & Support

- **NixOS Discourse**: [discourse.nixos.org](https://discourse.nixos.org/)
- **NixOS Reddit**: [r/NixOS](https://www.reddit.com/r/NixOS/)
- **GitHub Issues**: [NixOS-Dev-Quick-Deploy Issues](https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues)

---

## Quick Reference Commands

### System Management
```bash
# Rebuild system
sudo nixos-rebuild switch

# Rebuild home-manager
home-manager switch

# Update flake inputs
nix flake update

# Garbage collection
sudo nix-collect-garbage -d
nix-collect-garbage -d  # User profile
```

### AI Services
```bash
# Ollama
ollama list
ollama pull llama3
ollama run llama3

# Hugging Face TGI
sudo systemctl start huggingface-tgi
journalctl -u huggingface-tgi -f

# Qdrant
sudo systemctl status qdrant
sudo systemctl restart qdrant
curl http://localhost:6333/dashboard
```

### Development
```bash
# Git shortcuts
gs    # git status
ga    # git add
gc    # git commit
gp    # git push
lg    # lazygit

# Nix development
nix develop       # Enter dev shell
direnv allow      # Auto-load environment
```

### Monitoring
```bash
# System monitoring
htop              # Process viewer
btop              # Modern resource monitor
glances           # System dashboard
netdata           # http://localhost:19999

# Container monitoring
podman ps         # List containers
podman-tui        # TUI for containers
```

---

**Document Version**: 1.0
**System**: NixOS 25.05+ AI Development Environment
**Last Updated**: 2025-11-04

For additional help, run: `nix-ai-help`
