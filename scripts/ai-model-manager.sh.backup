#!/usr/bin/env bash
# AI Model Manager - Modular model configuration system
# Version: 1.0.0
# Purpose: Manage AI models across TGI, Ollama, and other runtimes

set -euo pipefail

# Directories
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ai-models"
PROFILES_DIR="$CONFIG_DIR/profiles"
ACTIVE_DIR="$CONFIG_DIR/active"
CUSTOM_DIR="$CONFIG_DIR/custom"
EXPERIMENTS_DIR="$CONFIG_DIR/experiments"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ai-models"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Version
readonly VERSION="1.0.0"

# Logging
log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*" >&2
}

# Initialize directory structure
init_dirs() {
    mkdir -p "$PROFILES_DIR"/{coding,chat,reasoning,embedding,custom}
    mkdir -p "$ACTIVE_DIR"
    mkdir -p "$CUSTOM_DIR"
    mkdir -p "$EXPERIMENTS_DIR"
    mkdir -p "$STATE_DIR"

    # Create README if it doesn't exist
    if [[ ! -f "$CONFIG_DIR/README.md" ]]; then
        cat > "$CONFIG_DIR/README.md" <<'EOF'
# AI Model Configuration Directory

This directory contains modular AI model profiles for easy experimentation.

## Structure

- `profiles/` - Pre-configured model profiles organized by category
- `active/` - Symlinks to currently active profiles
- `custom/` - Your custom model profiles
- `experiments/` - Experiment tracking logs

## Usage

Use the `ai-model-manager` (or `amm`) command to manage models:

```bash
# List available models
amm list

# Show active configuration
amm status

# Switch models
amm switch tgi-primary coding/deepseek-coder

# Create custom profile
amm create my-model

# Get help
amm help
```

See: ~/Documents/NixOS-Dev-Quick-Deploy/AI-MODEL-MODULAR-SYSTEM.md
EOF
    fi
}

# Check dependencies
check_deps() {
    local missing=()

    if ! command -v yq &>/dev/null; then
        missing+=("yq")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing[*]}"
        log_info "Install with: nix-env -iA nixpkgs.yq-go"
        return 1
    fi
}

# List available models
list_models() {
    local category="${1:-all}"
    local filter="${2:-}"

    echo -e "${BOLD}${BLUE}═══ Available Model Profiles ═══${NC}\n"

    if [[ "$category" == "all" ]]; then
        for cat_dir in "$PROFILES_DIR"/*; do
            if [[ -d "$cat_dir" ]]; then
                local cat_name=$(basename "$cat_dir")
                local count=$(find "$cat_dir" -maxdepth 1 -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l)

                if [[ $count -eq 0 ]]; then
                    continue
                fi

                echo -e "${BOLD}${GREEN}$cat_name${NC} ($count profiles)"
                for profile in "$cat_dir"/*.yaml *.yml 2>/dev/null; do
                    [[ -f "$profile" ]] || continue
                    list_profile_summary "$profile" "$filter"
                done
                echo
            fi
        done
    else
        if [[ -d "$PROFILES_DIR/$category" ]]; then
            echo -e "${BOLD}${GREEN}$category${NC}"
            for profile in "$PROFILES_DIR/$category"/*.yaml *.yml 2>/dev/null; do
                [[ -f "$profile" ]] || continue
                list_profile_summary "$profile" "$filter"
            done
        else
            log_error "Category '$category' not found"
            return 1
        fi
    fi

    # Show custom profiles
    local custom_count=$(find "$CUSTOM_DIR" -maxdepth 1 -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l)
    if [[ $custom_count -gt 0 ]]; then
        echo -e "${BOLD}${GREEN}custom${NC} ($custom_count profiles)"
        for profile in "$CUSTOM_DIR"/*.yaml *.yml 2>/dev/null; do
            [[ -f "$profile" ]] || continue
            list_profile_summary "$profile" "$filter"
        done
    fi
}

# List single profile summary
list_profile_summary() {
    local profile="$1"
    local filter="${2:-}"

    local name=$(yq eval '.name' "$profile" 2>/dev/null || echo "unknown")
    local desc=$(yq eval '.description' "$profile" 2>/dev/null || echo "No description")
    local runtime=$(yq eval '.container.runtime' "$profile" 2>/dev/null || echo "unknown")
    local tags=$(yq eval '.tags[]' "$profile" 2>/dev/null | tr '\n' ' ' || echo "")

    # Apply filter if specified
    if [[ -n "$filter" ]]; then
        if ! echo "$name $desc $tags" | grep -qi "$filter"; then
            return
        fi
    fi

    echo -e "  ${CYAN}$(basename "$profile" .yaml)${NC}"
    echo -e "    Name: $name"
    echo -e "    Runtime: $runtime"
    echo -e "    Description: $desc"
    if [[ -n "$tags" ]]; then
        echo -e "    Tags: $tags"
    fi
}

# Show active models
show_status() {
    echo -e "${BOLD}${BLUE}═══ Active Model Configuration ═══${NC}\n"

    local found_active=false

    if [[ -d "$ACTIVE_DIR" ]]; then
        for link in "$ACTIVE_DIR"/*.yaml *.yml 2>/dev/null; do
            [[ -L "$link" ]] || continue
            found_active=true

            local service=$(basename "$link" | sed 's/\.\(yaml\|yml\)$//')
            local target=$(readlink "$link")
            local rel_target=$(realpath --relative-to="$CONFIG_DIR" "$link")

            local model_name=$(yq eval '.name' "$link" 2>/dev/null || echo "Unknown")
            local runtime=$(yq eval '.container.runtime' "$link" 2>/dev/null || echo "unknown")
            local model_id=$(yq eval '.source.model_id' "$link" 2>/dev/null || echo "N/A")

            echo -e "${BOLD}${GREEN}${service}${NC}"
            echo -e "  Model: ${YELLOW}${model_name}${NC}"
            echo -e "  Runtime: $runtime"
            echo -e "  Model ID: $model_id"
            echo -e "  Profile: $rel_target"

            # Check if service is running
            if systemctl --user is-active "podman-${service}.service" &>/dev/null 2>&1; then
                local port=$(yq eval '.port // 8080' "$link" 2>/dev/null)
                echo -e "  Status: ${GREEN}✓ Running${NC} (port: $port)"
            else
                echo -e "  Status: ${YELLOW}⚠ Stopped${NC}"
            fi
            echo
        done
    fi

    if ! $found_active; then
        log_warn "No active model configurations found"
        echo -e "\nUse: ${CYAN}amm switch <service> <profile>${NC} to activate a model"
    fi

    # Show Ollama models
    echo -e "${BOLD}${BLUE}═══ Ollama Models ═══${NC}\n"
    if command -v podman &>/dev/null; then
        if podman exec local-ai-ollama ollama list 2>/dev/null; then
            :
        else
            log_warn "Ollama container not running"
        fi
    else
        log_warn "Podman not available"
    fi
}

# Switch model for a service
switch_model() {
    local service="$1"
    local profile_path="$2"

    if [[ -z "$service" || -z "$profile_path" ]]; then
        log_error "Usage: amm switch <service> <profile>"
        return 1
    fi

    # Find the profile
    local full_path=""
    if [[ -f "$profile_path" ]]; then
        full_path="$profile_path"
    elif [[ -f "$PROFILES_DIR/$profile_path" ]]; then
        full_path="$PROFILES_DIR/$profile_path"
    elif [[ -f "$PROFILES_DIR/$profile_path.yaml" ]]; then
        full_path="$PROFILES_DIR/$profile_path.yaml"
    elif [[ -f "$CUSTOM_DIR/$profile_path.yaml" ]]; then
        full_path="$CUSTOM_DIR/$profile_path.yaml"
    else
        # Search for it
        full_path=$(find "$PROFILES_DIR" "$CUSTOM_DIR" -name "$profile_path.yaml" -o -name "$profile_path.yml" 2>/dev/null | head -1)
    fi

    if [[ -z "$full_path" || ! -f "$full_path" ]]; then
        log_error "Profile '$profile_path' not found"
        log_info "Use 'amm list' to see available profiles"
        return 1
    fi

    local model_name=$(yq eval '.name' "$full_path" 2>/dev/null || echo "unknown")
    local link_path="$ACTIVE_DIR/${service}.yaml"

    log_info "Switching $service to $model_name..."

    # Create symlink
    ln -sf "$full_path" "$link_path"

    log_success "Model linked successfully"

    # Check if service exists and restart if running
    if systemctl --user list-unit-files "podman-${service}.service" &>/dev/null 2>&1; then
        if systemctl --user is-active "podman-${service}.service" &>/dev/null 2>&1; then
            log_info "Restarting service..."
            systemctl --user restart "podman-${service}.service" || log_warn "Service restart failed"
            sleep 2
            if systemctl --user is-active "podman-${service}.service" &>/dev/null 2>&1; then
                log_success "Service restarted successfully"
            fi
        else
            log_info "Service is not running. Start it with: systemctl --user start podman-${service}.service"
        fi
    else
        log_warn "Service 'podman-${service}.service' not found"
        log_info "The profile has been set, but you may need to configure the service"
    fi

    log_success "Model switch complete"
}

# Show model info
show_info() {
    local profile_path="$1"

    if [[ -z "$profile_path" ]]; then
        log_error "Usage: amm info <profile>"
        return 1
    fi

    # Find the profile
    local full_path=""
    if [[ -f "$profile_path" ]]; then
        full_path="$profile_path"
    else
        full_path=$(find "$PROFILES_DIR" "$ACTIVE_DIR" "$CUSTOM_DIR" \
            -name "$profile_path.yaml" -o -name "$profile_path.yml" -o -name "$profile_path" 2>/dev/null | head -1)
    fi

    if [[ -z "$full_path" || ! -f "$full_path" ]]; then
        log_error "Profile '$profile_path' not found"
        return 1
    fi

    echo -e "${BOLD}${BLUE}═══ Model Profile Information ═══${NC}\n"
    echo -e "${YELLOW}Profile:${NC} $(realpath --relative-to="$CONFIG_DIR" "$full_path")\n"

    yq eval '.' "$full_path" 2>/dev/null || cat "$full_path"
}

# Create new profile
create_profile() {
    local name="$1"
    shift || true

    if [[ -z "$name" ]]; then
        log_error "Usage: amm create <name> [options]"
        return 1
    fi

    local category="custom"
    local runtime="tgi"
    local model_id=""
    local description=""

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --category|-c) category="$2"; shift 2 ;;
            --runtime|-r) runtime="$2"; shift 2 ;;
            --model-id|-m) model_id="$2"; shift 2 ;;
            --description|-d) description="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local profile_path="$CUSTOM_DIR/${name}.yaml"

    if [[ -f "$profile_path" ]]; then
        log_error "Profile already exists: $profile_path"
        log_info "Remove it first or use a different name"
        return 1
    fi

    cat > "$profile_path" <<EOF
name: ${name}
description: ${description:-Custom model profile}
category: ${category}
version: "1.0"
created: $(date -Iseconds)

source:
  type: ${runtime}
  model_id: ${model_id:-model/name}
  revision: main

container:
  runtime: ${runtime}
  image: ${runtime == "tgi" && "ghcr.io/huggingface/text-generation-inference:latest" || "docker.io/ollama/ollama:latest"}

parameters:
  max_input_length: 4096
  max_total_tokens: 8192
  quantization: ${runtime == "tgi" && "bitsandbytes-nf4" || "null"}
  dtype: float16

resources:
  gpu_memory_min: 8GB
  cpu_cores: 4
  ram: 16GB

tags:
  - custom
  - ${category}

notes: |
  Custom profile created on $(date)
  Edit this file to customize settings.

  Location: $profile_path
EOF

    log_success "Profile created: $profile_path"
    echo -e "\n${CYAN}Edit with:${NC} \$EDITOR $profile_path"
    echo -e "${CYAN}Activate with:${NC} amm switch <service> custom/${name}"
}

# Start experiment tracking
start_experiment() {
    local description="${1:-Unnamed experiment}"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local exp_file="$EXPERIMENTS_DIR/${timestamp}.json"

    cat > "$exp_file" <<EOF
{
  "id": "$timestamp",
  "description": "$description",
  "started": "$(date -Iseconds)",
  "active_models": {},
  "results": {},
  "notes": []
}
EOF

    echo "$timestamp" > "$EXPERIMENTS_DIR/.active"

    log_success "Experiment started: $timestamp"
    echo -e "  Description: $description"
    echo -e "  File: $exp_file"
    echo -e "\n${CYAN}Log results:${NC} echo 'note' >> $exp_file"
}

# Show help
show_help() {
    cat <<EOF
${BOLD}AI Model Manager${NC} - Modular model configuration system
Version: $VERSION

${BOLD}Usage:${NC}
  ai-model-manager <command> [options]
  amm <command> [options]  # Short alias

${BOLD}Commands:${NC}
  ${CYAN}list${NC} [category] [filter]    List available model profiles
  ${CYAN}status${NC}                       Show active model configuration
  ${CYAN}switch${NC} <service> <profile>   Switch model for a service
  ${CYAN}info${NC} <profile>               Show detailed profile information
  ${CYAN}create${NC} <name> [opts]         Create new custom profile
  ${CYAN}experiment${NC} <description>     Start experiment tracking
  ${CYAN}help${NC}                         Show this help message
  ${CYAN}version${NC}                      Show version information

${BOLD}Examples:${NC}
  # List all available models
  ${GREEN}amm list${NC}

  # List coding models only
  ${GREEN}amm list coding${NC}

  # Show current configuration
  ${GREEN}amm status${NC}

  # Switch TGI primary to DeepSeek Coder
  ${GREEN}amm switch tgi-primary coding/deepseek-coder${NC}

  # Show profile details
  ${GREEN}amm info coding/starcoder2${NC}

  # Create custom profile
  ${GREEN}amm create my-model --runtime tgi --model-id deepseek-ai/deepseek-coder-7b${NC}

  # Start experiment
  ${GREEN}amm experiment "Testing code generation quality"${NC}

${BOLD}Service Names:${NC}
  - tgi-primary         Main TGI instance (port 8080)
  - tgi-secondary       Secondary TGI instance (port 8085)
  - tgi-experimental    Experimental TGI instance (port 8090)
  - ollama-default      Default Ollama model

${BOLD}Profile Categories:${NC}
  - coding       Code generation models
  - chat         General chat models
  - reasoning    Reasoning and planning models
  - embedding    Embedding models
  - custom       Your custom profiles

${BOLD}Configuration:${NC}
  Profiles: $PROFILES_DIR
  Active:   $ACTIVE_DIR
  Custom:   $CUSTOM_DIR

${BOLD}Documentation:${NC}
  ~/Documents/NixOS-Dev-Quick-Deploy/AI-MODEL-MODULAR-SYSTEM.md

${BOLD}Report Issues:${NC}
  https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues
EOF
}

# Show version
show_version() {
    echo "AI Model Manager version $VERSION"
}

# Main command dispatcher
main() {
    init_dirs

    if [[ $# -eq 0 ]]; then
        show_help
        return 0
    fi

    local command="$1"
    shift || true

    case "$command" in
        list|ls)
            check_deps || return 1
            list_models "$@"
            ;;
        status|st|stat)
            check_deps || return 1
            show_status
            ;;
        switch|sw)
            check_deps || return 1
            switch_model "$@"
            ;;
        info|show)
            check_deps || return 1
            show_info "$@"
            ;;
        create|new)
            check_deps || return 1
            create_profile "$@"
            ;;
        experiment|exp)
            start_experiment "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        version|--version|-v)
            show_version
            ;;
        *)
            log_error "Unknown command: $command"
            echo "Run 'amm help' for usage information"
            return 1
            ;;
    esac
}

main "$@"
