# AI-Stack Full Integration Plan
**Version:** 2.0 (Full Merge)
**Date:** 2025-12-12
**Purpose:** Complete integration of AI-Optimizer into NixOS-Dev-Quick-Deploy as a public, first-class component

---

## Executive Summary

This document outlines the plan to **fully merge** the AI-Optimizer stack into the NixOS-Dev-Quick-Deploy repository, making it a **public, documented, and declaratively managed** component of the base system.

**Key Changes:**
1. AI-Optimizer moves from `~/Documents/AI-Optimizer` (private) → integrated into `NixOS-Dev-Quick-Deploy/ai-stack/`
2. All AI components become public and fully documented
3. Single repository, single source of truth
4. Fully declarative deployment via NixOS phases
5. No external dependencies or private repos

---

## 1. Unified Repository Structure

```
NixOS-Dev-Quick-Deploy/                    # Single unified repository
├── nixos-quick-deploy.sh                  # Main entrypoint (8 phases)
│
├── config/                                # Global configuration
│   ├── variables.sh
│   ├── defaults.sh
│   └── ai-stack-defaults.sh               # NEW: AI stack defaults
│
├── lib/                                   # Shared libraries
│   ├── colors.sh
│   ├── logging.sh
│   ├── error-handling.sh
│   ├── state-management.sh
│   ├── common.sh
│   ├── ai-stack-core.sh                   # NEW: Core AI stack functions (merged from ai-optimizer.sh)
│   ├── ai-stack-models.sh                 # NEW: Model selection/management
│   ├── ai-stack-deployment.sh             # NEW: Deployment automation
│   └── ai-stack-health.sh                 # NEW: Health checks
│
├── phases/                                # Deployment phases
│   ├── phase-01-system-initialization.sh
│   ├── phase-02-system-backup.sh
│   ├── phase-03-configuration-generation.sh
│   ├── phase-04-pre-deployment-validation.sh
│   ├── phase-05-declarative-deployment.sh
│   ├── phase-06-additional-tooling.sh
│   ├── phase-07-post-deployment-validation.sh
│   ├── phase-08-finalization-and-report.sh
│   └── phase-09-ai-stack-deployment.sh    # NEW: Full AI stack deployment (replaces old prep+model phases)
│
├── ai-stack/                              # NEW: AI stack components (merged from AI-Optimizer)
│   ├── compose/
│   │   ├── docker-compose.yml             # Full production stack
│   │   ├── docker-compose.dev.yml         # Development override
│   │   ├── docker-compose.minimal.yml     # Minimal stack (Lemonade only)
│   │   └── .env.example                   # Environment template
│   │
│   ├── mcp-servers/                       # Model Context Protocol servers
│   │   ├── aidb/                          # AIDB MCP server
│   │   │   ├── Dockerfile
│   │   │   ├── pyproject.toml
│   │   │   ├── src/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── server.py
│   │   │   │   ├── models.py
│   │   │   │   ├── database.py
│   │   │   │   └── api/
│   │   │   └── README.md
│   │   │
│   │   ├── nixos/                         # NixOS-specific MCP server
│   │   │   └── (similar structure)
│   │   │
│   │   └── github/                        # GitHub integration MCP
│   │       └── (similar structure)
│   │
│   ├── agents/                            # Agentic AI skills (merged from .agent/skills/)
│   │   ├── README.md                      # Agent architecture documentation
│   │   ├── orchestrator/                  # Primary orchestrator agent
│   │   ├── skills/
│   │   │   ├── nixos-deployment/
│   │   │   ├── webapp-testing/
│   │   │   ├── canvas-design/
│   │   │   ├── code-review/
│   │   │   └── documentation/
│   │   └── shared/                        # Shared agent utilities
│   │
│   ├── models/                            # Model management
│   │   ├── registry.json                  # Available models catalog
│   │   ├── download.sh                    # Model download script
│   │   └── README.md                      # Model documentation
│   │
│   ├── database/                          # Database schemas and migrations
│   │   ├── postgres/
│   │   │   ├── migrations/
│   │   │   └── schemas/
│   │   ├── redis/
│   │   │   └── config/
│   │   └── qdrant/
│   │       └── collections/
│   │
│   └── docs/                              # AI stack documentation
│       ├── ARCHITECTURE.md
│       ├── API.md
│       ├── DEPLOYMENT.md
│       └── TROUBLESHOOTING.md
│
├── scripts/                               # Utility scripts
│   ├── system-health-check.sh
│   ├── ai-stack-manage.sh                 # AI stack management CLI (keep)
│   ├── ai-stack-migrate.sh                # NEW: Migrate from old AI-Optimizer install
│   ├── ai-stack-sync-docs.sh              # NEW: Sync docs to AIDB
│   ├── comprehensive-mcp-search.py        # Keep (useful for all users)
│   └── bootstrap_aidb_data.sh             # NEW: Bootstrap AIDB with sample data
│
├── templates/                             # NixOS templates
│   ├── flake.nix
│   ├── configuration.nix
│   ├── home.nix
│   └── nixos-improvements/
│       └── ai-stack.nix                   # NEW: AI stack NixOS module
│
├── docs/                                  # Main documentation
│   ├── README.md
│   ├── QUICK_START.md
│   ├── ARCHITECTURE.md                    # Update with AI stack
│   ├── AI_INTEGRATION.md                  # Rewrite for unified approach
│   ├── AI-STACK-FULL-INTEGRATION.md       # This document
│   ├── AGENTS.md                          # Merged from AI-Optimizer
│   ├── MCP_SERVERS.md
│   └── TROUBLESHOOTING.md
│
└── data/                                  # NEW: Default shared data location (user can override)
    └── .gitkeep                           # Keep directory in git

# Runtime directories (not in git)
~/.local/share/nixos-ai-stack/             # Shared data (Postgres, Redis, models, etc.)
~/.config/nixos-ai-stack/                  # Runtime config (.env, state)
~/.cache/nixos-ai-stack/                   # Logs, temp files
```

---

## 2. Migration Strategy

### 2.1 Repository Consolidation

**Step 1: Copy AI-Optimizer Components**

```bash
# From AI-Optimizer repo:
AI-Optimizer/
├── .agent/skills/          → NixOS-Dev-Quick-Deploy/ai-stack/agents/skills/
├── AGENTS.md               → NixOS-Dev-Quick-Deploy/docs/AGENTS.md
├── docker-compose.yml      → NixOS-Dev-Quick-Deploy/ai-stack/compose/docker-compose.yml
├── .env.example            → NixOS-Dev-Quick-Deploy/ai-stack/compose/.env.example
├── scripts/                → NixOS-Dev-Quick-Deploy/scripts/ (merge)
└── (MCP server code)       → NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/

# Consolidate libraries:
lib/ai-optimizer.sh         → lib/ai-stack-core.sh (refactor)
lib/ai-optimizer-hooks.sh   → lib/ai-stack-deployment.sh (refactor)
```

**Step 2: Update References**

- Search and replace `AI-Optimizer` → `NixOS-Dev-Quick-Deploy`
- Update paths from `~/Documents/AI-Optimizer` → `$SCRIPT_DIR/ai-stack`
- Update environment variables:
  - `AI_OPTIMIZER_DIR` → `AI_STACK_DIR="$SCRIPT_DIR/ai-stack"`
  - `AI_OPTIMIZER_DATA_ROOT` → `AI_STACK_DATA_ROOT`

**Step 3: Consolidate Documentation**

- Merge `AI-Optimizer/README.md` into main `README.md` (add AI Stack section)
- Move `AGENTS.md` to `docs/AGENTS.md`
- Update all cross-references

**Step 4: Update Phase 9**

Rename and expand:
- `phase-09-ai-optimizer-prep.sh` → `phase-09-ai-stack-deployment.sh`
- Combine old "prep" and "model deployment" into single comprehensive phase

### 2.2 Backward Compatibility (Migration from Old Setup)

**Script: `scripts/ai-stack-migrate.sh`**

```bash
#!/usr/bin/env bash
# Migrate from standalone AI-Optimizer to integrated NixOS-Dev-Quick-Deploy AI stack

set -Eeuo pipefail

OLD_AI_OPTIMIZER_DIR="$HOME/Documents/AI-Optimizer"
NEW_AI_STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/ai-stack"
SHARED_DATA_DIR="$HOME/.local/share/nixos-ai-stack"

migrate_from_standalone() {
    echo "╭────────────────────────────────────────────────────────────╮"
    echo "│ AI-Optimizer → NixOS-Dev-Quick-Deploy Migration           │"
    echo "╰────────────────────────────────────────────────────────────╯"
    echo ""

    # Check if old install exists
    if [[ ! -d "$OLD_AI_OPTIMIZER_DIR" ]]; then
        echo "✓ No standalone AI-Optimizer found. Nothing to migrate."
        return 0
    fi

    echo "Found standalone AI-Optimizer at: $OLD_AI_OPTIMIZER_DIR"
    echo ""

    read -p "Migrate data and configuration? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        echo "Migration cancelled."
        return 1
    fi

    # 1. Stop old services
    echo ""
    echo "→ Stopping old AI-Optimizer services..."
    (cd "$OLD_AI_OPTIMIZER_DIR" && docker compose down) || true

    # 2. Backup
    local backup_dir="$OLD_AI_OPTIMIZER_DIR/backups/pre-migration-$(date +%Y%m%d-%H%M%S)"
    echo "→ Creating backup at $backup_dir..."
    mkdir -p "$backup_dir"
    cp -a "$OLD_AI_OPTIMIZER_DIR/data" "$backup_dir/" 2>/dev/null || true
    cp -a "$OLD_AI_OPTIMIZER_DIR/.env" "$backup_dir/" 2>/dev/null || true

    # 3. Create new shared data directories
    echo "→ Creating shared data directories..."
    mkdir -p "$SHARED_DATA_DIR"/{postgres,redis,qdrant,lemonade-models,imports,exports,backups,logs}

    # 4. Migrate data
    echo "→ Migrating data..."
    if [[ -d "$OLD_AI_OPTIMIZER_DIR/data" ]]; then
        rsync -av --progress "$OLD_AI_OPTIMIZER_DIR/data/" "$SHARED_DATA_DIR/"
    fi

    # 5. Migrate config
    echo "→ Migrating configuration..."
    mkdir -p "$HOME/.config/nixos-ai-stack"
    if [[ -f "$OLD_AI_OPTIMIZER_DIR/.env" ]]; then
        cp "$OLD_AI_OPTIMIZER_DIR/.env" "$HOME/.config/nixos-ai-stack/.env"
        # Update paths in .env
        sed -i "s|$OLD_AI_OPTIMIZER_DIR|$SHARED_DATA_DIR|g" "$HOME/.config/nixos-ai-stack/.env"
    fi

    # 6. Archive old installation
    echo "→ Archiving old installation..."
    mv "$OLD_AI_OPTIMIZER_DIR" "$OLD_AI_OPTIMIZER_DIR.backup-$(date +%Y%m%d)"

    echo ""
    echo "✓ Migration complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Start AI stack: ./scripts/ai-stack-manage.sh up"
    echo "  2. Verify health: ./scripts/ai-stack-manage.sh status"
    echo "  3. Old backup: $OLD_AI_OPTIMIZER_DIR.backup-*"
    echo ""
}

migrate_from_standalone
```

---

## 3. Updated Deployment Flow

### 3.1 Fresh Installation

```bash
# Clone repository
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# Run deployment with AI stack
./nixos-quick-deploy.sh --with-ai-stack

# Or step-by-step:
./nixos-quick-deploy.sh                    # Phases 1-8: Base system
./nixos-quick-deploy.sh --with-ai-stack    # Phase 9: AI stack deployment
```

### 3.2 Phase 9: AI Stack Deployment (Unified)

**File: `phases/phase-09-ai-stack-deployment.sh`**

```bash
#!/usr/bin/env bash
# Phase 9: AI Stack Deployment
# Purpose: Deploy full AI stack (AIDB, Lemonade, MCP servers)

phase_09_ai_stack_deployment() {
    log_phase_start 9 "AI Stack Deployment"

    # Load AI stack libraries
    source "${SCRIPT_DIR}/lib/ai-stack-core.sh"
    source "${SCRIPT_DIR}/lib/ai-stack-models.sh"
    source "${SCRIPT_DIR}/lib/ai-stack-deployment.sh"
    source "${SCRIPT_DIR}/lib/ai-stack-health.sh"

    # 1. Check prerequisites
    if ! check_ai_stack_prerequisites; then
        log_error "AI stack prerequisites not met"
        show_prerequisite_help
        return 1
    fi

    # 2. Prompt user for AI stack installation
    if ! prompt_ai_stack_installation; then
        log_info "Skipping AI stack deployment"
        mark_phase_complete "phase-09"
        return 0
    fi

    # 3. Create shared data directories
    if ! create_ai_stack_directories; then
        log_error "Failed to create AI stack directories"
        return 1
    fi

    # 4. Interactive model selection
    local selected_model
    selected_model=$(select_ai_model_interactive)

    if [[ "$selected_model" == "SKIP" ]]; then
        log_info "AI model installation skipped"
        mark_phase_complete "phase-09"
        return 0
    fi

    # 5. Generate configuration
    if ! generate_ai_stack_config "$selected_model"; then
        log_error "Failed to generate AI stack configuration"
        return 1
    fi

    # 6. Deploy stack
    if ! deploy_ai_stack; then
        log_error "Failed to deploy AI stack"
        return 1
    fi

    # 7. Wait for services to be ready
    if ! wait_for_ai_stack_ready; then
        log_error "AI stack services failed to start"
        show_troubleshooting_help
        return 1
    fi

    # 8. Bootstrap AIDB with documentation
    if ! bootstrap_aidb_documentation; then
        log_warning "Failed to bootstrap AIDB documentation (non-fatal)"
    fi

    # 9. Health check
    if ! run_ai_stack_health_check; then
        log_warning "AI stack health check failed (services may need more time)"
    fi

    # 10. Display success message
    show_ai_stack_success_message

    mark_phase_complete "phase-09"
    return 0
}

# Helper functions

check_ai_stack_prerequisites() {
    local missing=()

    # Check container runtime
    if ! command -v docker &>/dev/null && ! command -v podman &>/dev/null; then
        missing+=("Docker or Podman")
    fi

    # Check compose
    if ! command -v docker &>/dev/null || ! docker compose version &>/dev/null; then
        if ! command -v podman-compose &>/dev/null; then
            missing+=("docker-compose or podman-compose")
        fi
    fi

    # Check jq (for config generation)
    if ! command -v jq &>/dev/null; then
        missing+=("jq")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing prerequisites: ${missing[*]}"
        return 1
    fi

    return 0
}

deploy_ai_stack() {
    log_info "Deploying AI stack services..."

    local compose_file="$SCRIPT_DIR/ai-stack/compose/docker-compose.yml"
    local env_file="$HOME/.config/nixos-ai-stack/.env"

    # Change to compose directory
    cd "$SCRIPT_DIR/ai-stack/compose"

    # Deploy with compose
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        docker compose --env-file "$env_file" up -d
    elif command -v podman-compose &>/dev/null; then
        podman-compose --env-file "$env_file" up -d
    else
        log_error "No compose command available"
        return 1
    fi

    return 0
}

show_ai_stack_success_message() {
    cat <<EOF

╭────────────────────────────────────────────────────────────────╮
│ AI Stack Deployment Complete!                                  │
╰────────────────────────────────────────────────────────────────╯

Services running:
  • AIDB MCP Server:  http://localhost:8091
  • Lemonade vLLM:    http://localhost:8080
  • PostgreSQL:       localhost:5432
  • Redis:            localhost:6379
  • Qdrant:           localhost:6333
  • Redis Insight:    http://localhost:5540

Management:
  • Status:   ./scripts/ai-stack-manage.sh status
  • Logs:     ./scripts/ai-stack-manage.sh logs
  • Stop:     ./scripts/ai-stack-manage.sh down
  • Restart:  ./scripts/ai-stack-manage.sh restart

Documentation:
  • Architecture: docs/ARCHITECTURE.md
  • Agents:       docs/AGENTS.md
  • MCP Servers:  docs/MCP_SERVERS.md
  • API Docs:     ai-stack/docs/API.md

Data locations:
  • Shared data:  $HOME/.local/share/nixos-ai-stack
  • Config:       $HOME/.config/nixos-ai-stack
  • Logs:         $HOME/.cache/nixos-ai-stack/logs

Next steps:
  1. Test AIDB: curl http://localhost:8091/health | jq
  2. Test model: curl http://localhost:8080/health | jq
  3. Explore agents: ls -la ai-stack/agents/skills/

EOF
}
```

### 3.3 Stack Management CLI (Updated)

**File: `scripts/ai-stack-manage.sh`**

```bash
#!/usr/bin/env bash
# AI Stack Management CLI
# Unified interface for managing the integrated AI stack

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_STACK_DIR="$SCRIPT_DIR/ai-stack"
COMPOSE_DIR="$AI_STACK_DIR/compose"
ENV_FILE="$HOME/.config/nixos-ai-stack/.env"

print_usage() {
    cat <<EOF
Usage: $(basename "$0") {up|down|restart|status|logs|sync|health|clean} [options]

Subcommands:
  up              Start the AI stack
  down            Stop the AI stack
  restart         Restart the AI stack
  status          Show service status
  logs [service]  Show logs (all services or specific service)
  sync            Sync documentation to AIDB
  health          Run health checks
  clean           Remove all data (DESTRUCTIVE!)

Options:
  -d, --detach    Run in background (default for up)
  -f, --follow    Follow logs (default for logs)
  --verbose       Verbose output

Examples:
  $(basename "$0") up              # Start all services
  $(basename "$0") logs lemonade   # View Lemonade logs
  $(basename "$0") restart         # Restart all services
  $(basename "$0") health          # Check service health

Environment:
  AI_STACK_DIR    AI stack directory (default: $SCRIPT_DIR/ai-stack)
  ENV_FILE        Environment file (default: ~/.config/nixos-ai-stack/.env)
EOF
}

find_compose_cmd() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v podman-compose >/dev/null 2>&1; then
        echo "podman-compose"
    else
        echo ""
    fi
}

cmd_compose() {
    local compose_cmd
    compose_cmd=$(find_compose_cmd)

    if [[ -z "$compose_cmd" ]]; then
        echo "[ERROR] Neither 'docker compose' nor 'podman-compose' available" >&2
        exit 1
    fi

    (cd "$COMPOSE_DIR" && $compose_cmd --env-file "$ENV_FILE" "$@")
}

cmd_up() {
    echo "→ Starting AI stack..."
    cmd_compose up -d
    echo "✓ AI stack started"
    echo ""
    echo "Check status: $(basename "$0") status"
    echo "View logs:    $(basename "$0") logs"
}

cmd_down() {
    echo "→ Stopping AI stack..."
    cmd_compose down
    echo "✓ AI stack stopped"
}

cmd_restart() {
    cmd_down
    sleep 2
    cmd_up
}

cmd_status() {
    cmd_compose ps
}

cmd_logs() {
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        cmd_compose logs -f "$service"
    else
        cmd_compose logs -f
    fi
}

cmd_sync() {
    local sync_script="$SCRIPT_DIR/scripts/ai-stack-sync-docs.sh"
    if [[ -x "$sync_script" ]]; then
        "$sync_script"
    else
        echo "[ERROR] Sync script not found: $sync_script" >&2
        exit 1
    fi
}

cmd_health() {
    local health_script="$SCRIPT_DIR/lib/ai-stack-health.sh"
    if [[ -f "$health_script" ]]; then
        source "$health_script"
        run_ai_stack_health_check --verbose
    else
        echo "[ERROR] Health check library not found: $health_script" >&2
        exit 1
    fi
}

cmd_clean() {
    echo "╭────────────────────────────────────────────────────────────╮"
    echo "│ WARNING: This will DELETE all AI stack data!              │"
    echo "│                                                            │"
    echo "│ This includes:                                             │"
    echo "│  • PostgreSQL databases                                   │"
    echo "│  • Redis persistence                                      │"
    echo "│  • Qdrant vector database                                 │"
    echo "│  • Downloaded models                                      │"
    echo "│  • Imported documents                                     │"
    echo "╰────────────────────────────────────────────────────────────╯"
    echo ""
    read -p "Type 'DELETE' to confirm: " confirm

    if [[ "$confirm" != "DELETE" ]]; then
        echo "Cancelled."
        return 1
    fi

    cmd_down

    local data_dir="$HOME/.local/share/nixos-ai-stack"
    echo "→ Removing data directory: $data_dir"
    rm -rf "$data_dir"

    echo "→ Removing config: $HOME/.config/nixos-ai-stack"
    rm -rf "$HOME/.config/nixos-ai-stack"

    echo "→ Removing cache: $HOME/.cache/nixos-ai-stack"
    rm -rf "$HOME/.cache/nixos-ai-stack"

    echo "✓ All AI stack data removed"
    echo ""
    echo "To reinstall: ./nixos-quick-deploy.sh --with-ai-stack"
}

main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        up)       cmd_up ;;
        down)     cmd_down ;;
        restart)  cmd_restart ;;
        status)   cmd_status ;;
        logs)     cmd_logs "$@" ;;
        sync)     cmd_sync ;;
        health)   cmd_health ;;
        clean)    cmd_clean ;;
        -h|--help|"") print_usage ;;
        *)
            echo "[ERROR] Unknown command: $cmd" >&2
            echo "" >&2
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
```

---

## 4. Benefits of Full Integration

### 4.1 Eliminates Original Issues

| Issue | Solution |
|-------|----------|
| **Dependency Hell** | All dependencies declaratively managed in NixOS flake |
| **Integration Complexity** | Single repository, single deployment workflow |
| **Deployment Fragmentation** | Unified phase-based deployment (Phase 9 = AI stack) |
| **Maintenance Burden** | Single update cycle, shared libraries, common tooling |
| **Documentation Sprawl** | All docs in one place, cross-referenced |

### 4.2 New Capabilities

1. **Fully Declarative AI Stack** – Everything in git, reproducible builds
2. **Public Documentation** – AI stack architecture fully documented
3. **Zero External Dependencies** – No private repos, no manual setup
4. **Integrated Testing** – AI stack tests run with system health checks
5. **Unified CLI** – Single entrypoint for all operations

### 4.3 Developer Ergonomics

- **Single `git clone`** – Get entire system
- **Single deployment command** – `./nixos-quick-deploy.sh --with-ai-stack`
- **Single documentation tree** – Browse `docs/` for everything
- **Single issue tracker** – Report bugs in one place
- **Single CI/CD pipeline** – Test everything together

---

## 5. Implementation Roadmap

### Phase 1: Repository Preparation (Week 1)
- [ ] Create `ai-stack/` directory structure
- [ ] Copy MCP server code from AI-Optimizer
- [ ] Copy agent skills to `ai-stack/agents/`
- [ ] Copy docker-compose files to `ai-stack/compose/`
- [ ] Merge documentation into `docs/`

### Phase 2: Library Consolidation (Week 1)
- [ ] Merge `lib/ai-optimizer.sh` → `lib/ai-stack-core.sh`
- [ ] Merge `lib/ai-optimizer-hooks.sh` → `lib/ai-stack-deployment.sh`
- [ ] Create `lib/ai-stack-models.sh` (model management)
- [ ] Create `lib/ai-stack-health.sh` (health checks)
- [ ] Update all library cross-references

### Phase 3: Phase 9 Rewrite (Week 2)
- [ ] Rewrite `phase-09-ai-stack-deployment.sh` (unified)
- [ ] Remove old `phase-09-ai-optimizer-prep.sh`
- [ ] Remove old `phase-09-ai-model-deployment.sh`
- [ ] Update main orchestrator to call new Phase 9

### Phase 4: Scripts Update (Week 2)
- [ ] Update `scripts/ai-stack-manage.sh` for new structure
- [ ] Create `scripts/ai-stack-migrate.sh` (migration tool)
- [ ] Create `scripts/ai-stack-sync-docs.sh`
- [ ] Update `scripts/bootstrap_aidb_data.sh`

### Phase 5: Documentation (Week 3)
- [ ] Update main `README.md` with AI stack section
- [ ] Merge `AGENTS.md` into `docs/`
- [ ] Update `docs/ARCHITECTURE.md`
- [ ] Rewrite `docs/AI_INTEGRATION.md`
- [ ] Create `ai-stack/docs/` (API, deployment guides)
- [ ] Update all cross-references

### Phase 6: Testing (Week 3)
- [ ] Test fresh installation
- [ ] Test migration from old AI-Optimizer
- [ ] Test all Phase 9 workflows
- [ ] Test health checks
- [ ] Test CLI commands

### Phase 7: Release (Week 4)
- [ ] Tag `v6.0.0` (breaking change - full integration)
- [ ] Update GitHub releases
- [ ] Archive old AI-Optimizer repo
- [ ] Announce integration
- [ ] Provide migration guide for existing users

---

## 6. Migration Guide for Existing Users

### 6.1 If You Have Standalone AI-Optimizer

```bash
# 1. Pull latest NixOS-Dev-Quick-Deploy
cd ~/Documents/NixOS-Dev-Quick-Deploy
git pull origin main

# 2. Run migration script
./scripts/ai-stack-migrate.sh

# 3. Verify migration
./scripts/ai-stack-manage.sh status
./scripts/ai-stack-manage.sh health

# 4. (Optional) Remove old backup after verification
rm -rf ~/Documents/AI-Optimizer.backup-*
```

### 6.2 If You Have `local-ai-stack`

```bash
# 1. Pull latest NixOS-Dev-Quick-Deploy
cd ~/Documents/NixOS-Dev-Quick-Deploy
git pull origin main

# 2. Run migration with flag
./scripts/ai-stack-migrate.sh --from-local-ai-stack

# 3. Verify migration
./scripts/ai-stack-manage.sh status
```

### 6.3 Fresh Installation (New Users)

```bash
# 1. Clone repository
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# 2. Run deployment with AI stack
./nixos-quick-deploy.sh --with-ai-stack

# 3. Done! AI stack is integrated.
```

---

## 7. Post-Integration Maintenance

### 7.1 Update Workflow

```bash
# Update system + AI stack
cd ~/Documents/NixOS-Dev-Quick-Deploy
git pull origin main
nix flake update
./nixos-quick-deploy.sh

# Update AI stack only
./scripts/ai-stack-manage.sh down
./scripts/ai-stack-manage.sh up
```

### 7.2 Adding New Models

```bash
# Edit config
vim ~/.config/nixos-ai-stack/.env
# Change LEMONADE_DEFAULT_MODEL=...

# Restart Lemonade
./scripts/ai-stack-manage.sh restart
```

### 7.3 Adding New MCP Servers

```bash
# Add server code to ai-stack/mcp-servers/new-server/
# Update docker-compose.yml
# Restart stack
./scripts/ai-stack-manage.sh restart
```

---

## 8. Success Criteria

✅ **Single repository** – No private AI-Optimizer repo needed
✅ **Public documentation** – All AI features fully documented
✅ **Zero manual steps** – `./nixos-quick-deploy.sh --with-ai-stack` does everything
✅ **Data persistence** – Shared data survives reinstalls
✅ **Clean migration** – Existing users can migrate without data loss
✅ **Declarative** – All configs in git, reproducible
✅ **Tested** – CI/CD pipeline validates all components

---

## Conclusion

This full integration transforms AI-Optimizer from a separate private project into a **first-class, public component** of NixOS-Dev-Quick-Deploy. By consolidating everything into a single repository with a unified deployment workflow, we eliminate all dependency, integration, deployment, and maintenance issues while making the AI stack accessible to all users.

**Next Step:** Begin Phase 1 implementation by creating the `ai-stack/` directory structure and copying components from AI-Optimizer.
