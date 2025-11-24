# Modular AI Model System Architecture

**Version**: 1.0
**Date**: 2025-11-20
**Purpose**: Generic, modular system for easy AI model experimentation

---

## Overview

This document describes a modular architecture for managing multiple AI models across TGI (Text Generation Inference) and other locally hosted AI agent containers. The system allows easy swapping of models, configurations, and experimentation without code changes.

## Architecture Principles

1. **Model-Agnostic Containers**: Containers don't hardcode model names
2. **Configuration-Driven**: All model specifications in config files
3. **Profile-Based**: Pre-configured profiles for common models
4. **Hot-Swappable**: Change models without rebuilding containers
5. **Multi-Instance**: Run multiple TGI instances with different models simultaneously
6. **Experiment Tracking**: Track which models work well for which tasks

---

## System Components

### 1. Model Configuration System

**Location**: `~/.config/ai-models/`

```
~/.config/ai-models/
├── profiles/                  # Pre-configured model profiles
│   ├── coding/
│   │   ├── deepseek-coder.yaml
│   │   ├── codellama.yaml
│   │   └── starcoder2.yaml
│   ├── chat/
│   │   ├── llama3.yaml
│   │   ├── mistral.yaml
│   │   └── phi4.yaml
│   ├── reasoning/
│   │   ├── deepseek-r1.yaml
│   │   └── qwen-reasoning.yaml
│   └── embedding/
│       ├── bge-large.yaml
│       └── nomic-embed.yaml
├── active/                    # Symlinks to active profiles
│   ├── tgi-primary.yaml -> ../profiles/coding/deepseek-coder.yaml
│   ├── tgi-secondary.yaml -> ../profiles/chat/llama3.yaml
│   └── ollama-default.yaml -> ../profiles/reasoning/phi4.yaml
├── custom/                    # User custom configurations
│   └── my-experimental.yaml
└── experiments/               # Experiment tracking logs
    └── 2025-11-20-coding-test.json
```

### 2. TGI Multi-Instance Architecture

**Support for multiple TGI containers**:
- **tgi-primary**: Main coding/development model (port 8080)
- **tgi-secondary**: Alternative model for comparison (port 8085)
- **tgi-experimental**: Testing new models (port 8090)

Each instance:
- Independent port assignment
- Separate model cache
- Individual resource limits
- Hot-swappable configuration

### 3. Model Management CLI

**Tool**: `ai-model-manager` (or `amm`)

```bash
# List available models
amm list

# Show active models
amm status

# Switch models
amm switch tgi-primary deepseek-coder
amm switch ollama llama3.2

# Create new profile
amm create-profile my-model --base llama --size 7b

# Start experiment
amm experiment start "Testing Qwen for code generation"

# Load profile
amm load-profile coding/starcoder2

# Compare models
amm compare tgi-primary tgi-secondary --task coding

# Show model info
amm info deepseek-coder
```

---

## Model Profile Format

### YAML Schema

```yaml
# ~/.config/ai-models/profiles/coding/deepseek-coder.yaml
name: deepseek-coder-7b
description: DeepSeek Coder 7B - Specialized for code generation
category: coding
version: "1.0"

# Model source
source:
  type: huggingface  # huggingface, ollama, local
  model_id: deepseek-ai/DeepSeek-Coder-V2-Instruct
  revision: main  # or specific commit hash

# Container configuration
container:
  runtime: tgi  # tgi, ollama, vllm, custom
  image: ghcr.io/huggingface/text-generation-inference:latest

# Model parameters
parameters:
  max_input_length: 8192
  max_total_tokens: 16384
  quantization: bitsandbytes-nf4  # or awq, gptq, none
  dtype: float16

# Resource requirements
resources:
  gpu_memory_min: 8GB
  gpu_memory_recommended: 12GB
  cpu_cores: 4
  ram: 16GB

# Performance settings
performance:
  max_batch_size: 32
  max_concurrent_requests: 128
  waiting_served_ratio: 1.2

# Specific for TGI
tgi:
  sharded: false
  num_shard: 1
  trust_remote_code: true

# Tags for organization
tags:
  - coding
  - python
  - javascript
  - 7b
  - instruct

# Experiment notes
notes: |
  Works well for:
  - Python code generation
  - Code explanation
  - Debugging assistance

  Known issues:
  - Slower on very long contexts (>8k tokens)

# Benchmarks (optional)
benchmarks:
  humaneval: 0.73
  mbpp: 0.68
  inference_speed_tokens_per_sec: 45
```

### Ollama Profile Example

```yaml
# ~/.config/ai-models/profiles/chat/llama3.yaml
name: llama3.2-3b
description: Llama 3.2 3B - Fast chat model
category: chat
version: "1.0"

source:
  type: ollama
  model_id: llama3.2:3b

container:
  runtime: ollama

parameters:
  temperature: 0.7
  top_p: 0.9
  top_k: 40
  repeat_penalty: 1.1

resources:
  gpu_memory_min: 4GB
  cpu_cores: 2
  ram: 8GB

tags:
  - chat
  - general
  - 3b
  - fast
```

---

## Implementation Files

### 1. Model Manager Script

**File**: `~/.local/bin/ai-model-manager`

```bash
#!/usr/bin/env bash
# AI Model Manager - Modular model configuration system
# Version: 1.0.0

set -euo pipefail

# Directories
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ai-models"
PROFILES_DIR="$CONFIG_DIR/profiles"
ACTIVE_DIR="$CONFIG_DIR/active"
CUSTOM_DIR="$CONFIG_DIR/custom"
EXPERIMENTS_DIR="$CONFIG_DIR/experiments"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Initialize directory structure
init_dirs() {
    mkdir -p "$PROFILES_DIR"/{coding,chat,reasoning,embedding,custom}
    mkdir -p "$ACTIVE_DIR"
    mkdir -p "$CUSTOM_DIR"
    mkdir -p "$EXPERIMENTS_DIR"
}

# List available models
list_models() {
    local category="${1:-all}"

    echo -e "${BLUE}=== Available Model Profiles ===${NC}\n"

    if [[ "$category" == "all" ]]; then
        for cat_dir in "$PROFILES_DIR"/*; do
            if [[ -d "$cat_dir" ]]; then
                local cat_name=$(basename "$cat_dir")
                echo -e "${GREEN}${cat_name}:${NC}"
                for profile in "$cat_dir"/*.yaml; do
                    if [[ -f "$profile" ]]; then
                        local name=$(basename "$profile" .yaml)
                        local desc=$(yq eval '.description' "$profile" 2>/dev/null || echo "No description")
                        echo "  - $name: $desc"
                    fi
                done
                echo
            fi
        done
    else
        if [[ -d "$PROFILES_DIR/$category" ]]; then
            echo -e "${GREEN}${category}:${NC}"
            for profile in "$PROFILES_DIR/$category"/*.yaml; do
                if [[ -f "$profile" ]]; then
                    local name=$(basename "$profile" .yaml)
                    local desc=$(yq eval '.description' "$profile" 2>/dev/null || echo "No description")
                    echo "  - $name: $desc"
                fi
            done
        fi
    fi
}

# Show active models
show_status() {
    echo -e "${BLUE}=== Active Model Configuration ===${NC}\n"

    if [[ -d "$ACTIVE_DIR" ]]; then
        for link in "$ACTIVE_DIR"/*.yaml; do
            if [[ -L "$link" ]]; then
                local service=$(basename "$link" .yaml)
                local target=$(readlink "$link")
                local model_name=$(yq eval '.name' "$link" 2>/dev/null || echo "Unknown")
                local runtime=$(yq eval '.container.runtime' "$link" 2>/dev/null || echo "unknown")

                echo -e "${GREEN}${service}${NC} → ${YELLOW}${model_name}${NC} (${runtime})"
                echo "  Profile: $target"

                # Check if service is running
                if systemctl --user is-active "podman-${service}.service" &>/dev/null; then
                    echo -e "  Status: ${GREEN}✓ Running${NC}"
                else
                    echo -e "  Status: ${RED}✗ Stopped${NC}"
                fi
                echo
            fi
        done
    fi

    # Show Ollama models
    echo -e "${BLUE}=== Ollama Models ===${NC}\n"
    if command -v ollama &>/dev/null; then
        ollama list 2>/dev/null || echo "Ollama not running"
    else
        echo "Ollama not available"
    fi
}

# Switch model for a service
switch_model() {
    local service="$1"
    local profile_path="$2"

    # Find the profile
    local full_path=""
    if [[ -f "$profile_path" ]]; then
        full_path="$profile_path"
    elif [[ -f "$PROFILES_DIR/$profile_path" ]]; then
        full_path="$PROFILES_DIR/$profile_path"
    elif [[ -f "$PROFILES_DIR/$profile_path.yaml" ]]; then
        full_path="$PROFILES_DIR/$profile_path.yaml"
    else
        # Search for it
        full_path=$(find "$PROFILES_DIR" -name "$profile_path.yaml" -o -name "$profile_path" | head -1)
    fi

    if [[ -z "$full_path" || ! -f "$full_path" ]]; then
        echo -e "${RED}Error: Profile '$profile_path' not found${NC}"
        return 1
    fi

    local link_path="$ACTIVE_DIR/${service}.yaml"

    echo -e "${BLUE}Switching $service to $(yq eval '.name' "$full_path")...${NC}"

    # Create symlink
    ln -sf "$full_path" "$link_path"

    # Restart service if running
    if systemctl --user is-active "podman-${service}.service" &>/dev/null; then
        echo "Restarting service..."
        systemctl --user restart "podman-${service}.service"
    fi

    echo -e "${GREEN}✓ Model switched successfully${NC}"
}

# Show model info
show_info() {
    local profile_path="$1"

    # Find the profile
    local full_path=""
    if [[ -f "$profile_path" ]]; then
        full_path="$profile_path"
    else
        full_path=$(find "$PROFILES_DIR" "$ACTIVE_DIR" -name "$profile_path.yaml" -o -name "$profile_path" | head -1)
    fi

    if [[ -z "$full_path" || ! -f "$full_path" ]]; then
        echo -e "${RED}Error: Profile '$profile_path' not found${NC}"
        return 1
    fi

    echo -e "${BLUE}=== Model Information ===${NC}\n"

    yq eval '.' "$full_path"
}

# Create new profile
create_profile() {
    local name="$1"
    shift
    local category="custom"
    local base=""
    local size=""

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --category) category="$2"; shift 2 ;;
            --base) base="$2"; shift 2 ;;
            --size) size="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local profile_path="$CUSTOM_DIR/${name}.yaml"

    cat > "$profile_path" <<EOF
name: ${name}
description: Custom model profile
category: ${category}
version: "1.0"

source:
  type: huggingface
  model_id: ${base:-model/name}
  revision: main

container:
  runtime: tgi
  image: ghcr.io/huggingface/text-generation-inference:latest

parameters:
  max_input_length: 4096
  max_total_tokens: 8192
  quantization: bitsandbytes-nf4
  dtype: float16

resources:
  gpu_memory_min: 8GB
  cpu_cores: 4
  ram: 16GB

tags:
  - custom
  - ${size}

notes: |
  Custom profile created on $(date)
  Edit this file to customize settings.
EOF

    echo -e "${GREEN}✓ Profile created: $profile_path${NC}"
    echo "Edit it with: \$EDITOR $profile_path"
}

# Start experiment tracking
start_experiment() {
    local description="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local exp_file="$EXPERIMENTS_DIR/${timestamp}.json"

    cat > "$exp_file" <<EOF
{
  "id": "$timestamp",
  "description": "$description",
  "started": "$(date -Iseconds)",
  "models": {},
  "results": {},
  "notes": []
}
EOF

    echo "$timestamp" > "$EXPERIMENTS_DIR/.active"
    echo -e "${GREEN}✓ Experiment started: $timestamp${NC}"
    echo "File: $exp_file"
}

# Main command dispatcher
main() {
    init_dirs

    local command="${1:-help}"
    shift || true

    case "$command" in
        list|ls) list_models "$@" ;;
        status|st) show_status ;;
        switch|sw) switch_model "$@" ;;
        info) show_info "$@" ;;
        create|new) create_profile "$@" ;;
        experiment|exp) start_experiment "$@" ;;
        help|--help|-h)
            cat <<EOF
AI Model Manager - Modular model configuration system

Usage:
  ai-model-manager <command> [options]

Commands:
  list [category]           List available model profiles
  status                    Show active model configuration
  switch <service> <profile> Switch model for a service
  info <profile>            Show detailed profile information
  create <name> [opts]      Create new custom profile
  experiment <description>  Start experiment tracking

Examples:
  ai-model-manager list coding
  ai-model-manager switch tgi-primary deepseek-coder
  ai-model-manager info coding/starcoder2
  ai-model-manager create my-model --base llama --size 7b

Aliases: amm
EOF
            ;;
        *)
            echo -e "${RED}Unknown command: $command${NC}"
            echo "Run 'ai-model-manager help' for usage"
            return 1
            ;;
    esac
}

main "$@"
```

### 2. TGI Container Generator

**File**: `lib/tgi-generator.sh`

```bash
#!/usr/bin/env bash
# TGI Container Configuration Generator
# Generates Podman quadlet configurations from model profiles

generate_tgi_service() {
    local service_name="$1"
    local profile_path="$2"
    local port="$3"

    # Read profile
    local model_id=$(yq eval '.source.model_id' "$profile_path")
    local quantization=$(yq eval '.parameters.quantization' "$profile_path")
    local max_input=$(yq eval '.parameters.max_input_length' "$profile_path")
    local max_total=$(yq eval '.parameters.max_total_tokens' "$profile_path")
    local dtype=$(yq eval '.parameters.dtype' "$profile_path")

    # Generate quadlet config
    cat <<EOF
# Generated TGI service for: $service_name
# Model: $model_id
# Profile: $profile_path

[Unit]
Description=TGI Service - $service_name
After=podman-local-ai-network.service
Wants=podman-local-ai-network.service

[Container]
Image=ghcr.io/huggingface/text-generation-inference:latest
ContainerName=$service_name
AutoUpdate=local

# Model configuration
Environment=MODEL_ID=$model_id
Environment=QUANTIZE=$quantization
Environment=MAX_INPUT_LENGTH=$max_input
Environment=MAX_TOTAL_TOKENS=$max_total
Environment=DTYPE=$dtype

# HuggingFace cache
Volume=%h/.cache/huggingface:/data:rw

# Network
Network=local-ai.network
PublishPort=$port:80

# Resources
Memory=16G
CPUQuota=400%

[Service]
Restart=on-failure
TimeoutStartSec=600

[Install]
WantedBy=default.target
EOF
}
```

---

## Updated home.nix Configuration

### Modular TGI Services

```nix
# Multi-instance TGI support with profile-based configuration
let
  tgiInstances = [
    {
      name = "tgi-primary";
      port = 8080;
      description = "Primary TGI instance for coding tasks";
      profileLink = "\${config.home.homeDirectory}/.config/ai-models/active/tgi-primary.yaml";
    }
    {
      name = "tgi-secondary";
      port = 8085;
      description = "Secondary TGI instance for experimentation";
      profileLink = "\${config.home.homeDirectory}/.config/ai-models/active/tgi-secondary.yaml";
    }
    {
      name = "tgi-experimental";
      port = 8090;
      description = "Experimental TGI instance for testing";
      profileLink = "\${config.home.homeDirectory}/.config/ai-models/active/tgi-experimental.yaml";
      autoStart = false;  # Don't start by default
    }
  ];

  # Generate TGI service for each instance
  mkTgiService = inst: {
    "${inst.name}" = {
      image = "ghcr.io/huggingface/text-generation-inference:latest";
      description = inst.description;
      autoStart = inst.autoStart or false;
      autoUpdate = "local";

      environment = {
        # Model ID read from profile at runtime
        MODEL_ID = "\${MODEL_ID:-deepseek-ai/DeepSeek-Coder-V2-Instruct}";
        QUANTIZE = "\${QUANTIZE:-bitsandbytes-nf4}";
        MAX_INPUT_LENGTH = "\${MAX_INPUT_LENGTH:-8192}";
        MAX_TOTAL_TOKENS = "\${MAX_TOTAL_TOKENS:-16384}";
        DTYPE = "\${DTYPE:-float16}";
        TRUST_REMOTE_CODE = "true";
        HUGGING_FACE_HUB_TOKEN = "\$(cat ~/.config/huggingface/token 2>/dev/null || echo '')";
      };

      volumes = [
        "\${HOME}/.cache/huggingface:/data:rw"
      ];

      ports = [
        "\${toString inst.port}:80"
      ];

      network = [ "local-ai.network" ];

      # Resource limits
      extraOptions = [
        "--memory=16g"
        "--cpus=4"
      ];
    };
  };

in {
  # Generate all TGI services
  services.podman.containers = lib.mkMerge (map mkTgiService tgiInstances);

  # Model manager tool
  home.packages = with pkgs; [
    yq-go  # For YAML parsing in ai-model-manager
  ];

  # Model configuration directory structure
  home.file.".config/ai-models/README.md".text = ''
    # AI Model Configuration Directory

    This directory contains modular AI model profiles.
    Use 'ai-model-manager' (alias: amm) to manage models.

    See: ~/Documents/NixOS-Dev-Quick-Deploy/AI-MODEL-MODULAR-SYSTEM.md
  '';
}
```

---

## Model Profile Examples

### Example 1: DeepSeek Coder

```yaml
# ~/.config/ai-models/profiles/coding/deepseek-coder.yaml
name: deepseek-coder-7b-instruct
description: DeepSeek Coder 7B Instruct - Optimized for code generation
category: coding
version: "1.0"

source:
  type: huggingface
  model_id: deepseek-ai/deepseek-coder-7b-instruct-v1.5
  revision: main

container:
  runtime: tgi
  image: ghcr.io/huggingface/text-generation-inference:2.0

parameters:
  max_input_length: 16384
  max_total_tokens: 32768
  quantization: bitsandbytes-nf4
  dtype: float16

resources:
  gpu_memory_min: 8GB
  gpu_memory_recommended: 12GB
  cpu_cores: 4
  ram: 16GB

performance:
  max_batch_size: 32
  max_concurrent_requests: 128

tgi:
  trust_remote_code: true

tags:
  - coding
  - python
  - javascript
  - 7b
  - instruct
  - fill-in-middle

notes: |
  Excellent for:
  - Code completion (FIM mode)
  - Code explanation
  - Bug fixing
  - Test generation
```

### Example 2: Llama 3.2 Vision

```yaml
# ~/.config/ai-models/profiles/chat/llama3.2-vision.yaml
name: llama3.2-11b-vision
description: Llama 3.2 11B Vision - Multimodal chat with image understanding
category: chat
version: "1.0"

source:
  type: huggingface
  model_id: meta-llama/Llama-3.2-11B-Vision-Instruct
  revision: main

container:
  runtime: tgi
  image: ghcr.io/huggingface/text-generation-inference:2.0

parameters:
  max_input_length: 8192
  max_total_tokens: 16384
  quantization: bitsandbytes-nf4
  dtype: bfloat16

resources:
  gpu_memory_min: 12GB
  gpu_memory_recommended: 16GB
  cpu_cores: 4
  ram: 24GB

capabilities:
  - text
  - vision
  - multimodal

tags:
  - chat
  - vision
  - multimodal
  - 11b
  - instruct

notes: |
  Features:
  - Image understanding
  - Visual question answering
  - OCR capabilities
  - General chat

  Limitations:
  - Slower than text-only models
  - Requires more VRAM
```

### Example 3: Qwen2.5 Coder

```yaml
# ~/.config/ai-models/profiles/coding/qwen-coder.yaml
name: qwen2.5-coder-7b
description: Qwen2.5 Coder 7B - Strong coding model with multilingual support
category: coding
version: "1.0"

source:
  type: ollama
  model_id: qwen2.5-coder:7b

container:
  runtime: ollama

parameters:
  temperature: 0.7
  top_p: 0.9
  repeat_penalty: 1.1
  context_length: 32768

resources:
  gpu_memory_min: 6GB
  cpu_cores: 4
  ram: 12GB

tags:
  - coding
  - multilingual
  - 7b
  - long-context

notes: |
  Strengths:
  - Multiple programming languages
  - Long context (32k tokens)
  - Fast inference with Ollama
  - Good for Asian languages
```

---

## Usage Workflows

### Quick Model Switch

```bash
# Switch primary TGI to DeepSeek Coder
amm switch tgi-primary coding/deepseek-coder

# Switch Ollama default to Qwen
amm switch ollama-default coding/qwen-coder

# Check status
amm status
```

### Experiment Workflow

```bash
# Start experiment
amm experiment start "Comparing code generation quality"

# Test Model 1
amm switch tgi-primary coding/deepseek-coder
# ... run tests ...

# Test Model 2
amm switch tgi-primary coding/starcoder2
# ... run tests ...

# Compare results
amm compare tgi-primary --history 2
```

### Multi-Model Testing

```bash
# Run multiple models simultaneously
amm switch tgi-primary coding/deepseek-coder
amm switch tgi-secondary coding/starcoder2
amm switch tgi-experimental chat/llama3

# All three models now running on different ports:
# - tgi-primary: http://localhost:8080
# - tgi-secondary: http://localhost:8085
# - tgi-experimental: http://localhost:9090
```

---

## Integration with AIDB

### AIDB Model Selection

AIDB can read the active model configuration:

```python
# AIDB code example
import yaml
from pathlib import Path

def get_active_model(service="tgi-primary"):
    config_path = Path.home() / ".config/ai-models/active" / f"{service}.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config

# Use in AIDB
model_config = get_active_model("tgi-primary")
api_url = f"http://localhost:8080"  # Or read from config
```

### AIDB Experiment Integration

```python
# Track experiments
def log_experiment_result(model_name, task, score):
    exp_id = Path.home() / ".config/ai-models/experiments/.active"
    exp_file = Path.home() / ".config/ai-models/experiments" / f"{exp_id.read_text().strip()}.json"

    # Update experiment file
    # ...
```

---

## Benefits

1. **No Code Changes**: Switch models via configuration only
2. **Easy Experimentation**: Test multiple models quickly
3. **Reproducible**: Profile files track exact model configurations
4. **Organized**: Category-based organization
5. **Multi-Model**: Run multiple models simultaneously
6. **Portable**: Configuration files can be shared
7. **Tracked**: Experiment logs for comparison
8. **Flexible**: Works with TGI, Ollama, vLLM, custom containers

---

## Next Steps

1. Implement `ai-model-manager` script
2. Create initial model profiles
3. Update `home.nix` with modular TGI configuration
4. Test model switching workflow
5. Integrate with AIDB
6. Document common model profiles
7. Create benchmark comparison system

---

**Status**: Design Complete - Ready for Implementation
