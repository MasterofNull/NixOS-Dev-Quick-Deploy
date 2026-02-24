#!/usr/bin/env bash
# AI Stack Container Registry
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Single source of truth for all AI stack container names
#
# Usage: source this file to get AI_STACK_CONTAINERS array
#
# All containers are mandatory - no optional profiles.
# The agentic system manages container lifecycle dynamically.

# Complete list of AI stack containers (Kubernetes deployments)
# Order matters: infrastructure first, then services, then agents
# shellcheck disable=SC2034
AI_STACK_CONTAINERS=(
    # Core Infrastructure
    local-ai-qdrant           # Vector database
    local-ai-postgres         # PostgreSQL + pgvector
    local-ai-redis            # Cache and session storage

    # AI Inference
    local-ai-embeddings       # Sentence transformers
    local-ai-llama-cpp        # Local LLM inference

    # User Interfaces
    local-ai-open-webui       # ChatGPT-like interface
    local-ai-nginx            # Reverse proxy
    local-ai-dashboard-api    # Dashboard backend

    # Observability
    local-ai-jaeger           # Distributed tracing
    local-ai-prometheus       # Metrics collection
    local-ai-grafana          # Metrics visualization

    # MCP Servers
    local-ai-aidb             # Context API and telemetry
    local-ai-hybrid-coordinator  # Context augmentation & learning
    local-ai-nixos-docs       # NixOS documentation knowledge base
    local-ai-container-engine # Container management MCP

    # Analytics
    local-ai-mindsdb          # Analytics and data integration

    # Agentic Coding Tools
    local-ai-aider            # AI pair programming
    local-ai-autogpt          # Autonomous goal decomposition
    local-ai-aider-wrapper    # Aider MCP wrapper
    local-ai-ralph-wiggum     # Continuous agent orchestrator

    # Self-Healing
    local-ai-health-monitor   # Infrastructure health monitoring
)

# Ports used by AI stack services
# shellcheck disable=SC2034
AI_STACK_PORTS=(
    6333   # Qdrant HTTP
    6334   # Qdrant gRPC
    5432   # PostgreSQL
    6379   # Redis
    8080   # llama.cpp
    8081   # Embeddings
    3001   # Open WebUI
    8889   # Dashboard API
    9090   # Prometheus
    3002   # Grafana
    8091   # AIDB
    8092   # Hybrid Coordinator
    8094   # NixOS Docs
    8095   # Container Engine
    8093   # Aider
    8097   # AutoGPT
    8098   # Ralph Wiggum
    8099   # Aider Wrapper
)

# Helper function: check if a container exists
ai_stack_container_exists() {
    local container="$1"
    podman ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"
}

# Helper function: check if a container is running
ai_stack_container_running() {
    local container="$1"
    podman ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"
}

# Helper function: get all running AI stack containers
ai_stack_running_containers() {
    podman ps --filter "label=nixos.quick-deploy.ai-stack=true" --format '{{.Names}}' 2>/dev/null
}

# Helper function: get all AI stack containers (running or stopped)
ai_stack_all_containers() {
    podman ps -a --filter "label=nixos.quick-deploy.ai-stack=true" --format '{{.Names}}' 2>/dev/null
}
