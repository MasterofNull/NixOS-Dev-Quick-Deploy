#!/usr/bin/env bash
# AI Stack Monitoring Dashboard
# Inspired by Docker Model Runner monitoring
# Version: 1.0.0 (December 2025)

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; NC='\033[0m'

clear
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    NixOS AI Stack - Live Monitoring Dashboard${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Check container status
check_container() {
    local name=$1
    if podman ps --format '{{.Names}}' | grep -q "^${name}$"; then
        echo -e "${GREEN}●${NC} $name"
        # Show basic stats
        podman stats --no-stream --format "   CPU: {{.CPUPerc}}  MEM: {{.MemUsage}}" "$name"
    else
        echo -e "${RED}○${NC} $name (stopped)"
    fi
}

echo -e "${YELLOW}Core Services:${NC}"
check_container "local-ai-qdrant"
check_container "local-ai-llama-cpp"
check_container "local-ai-postgres"
check_container "local-ai-redis"
echo ""

echo -e "${YELLOW}MCP Servers:${NC}"
check_container "local-ai-aidb"
check_container "local-ai-hybrid-coordinator"
check_container "local-ai-nixos-docs"
check_container "local-ai-ralph-wiggum"
echo ""

echo -e "${YELLOW}Monitoring:${NC}"
check_container "local-ai-health-monitor"
echo ""

# llama.cpp metrics
if podman ps --format '{{.Names}}' | grep -q "^local-ai-llama-cpp$"; then
    echo -e "${YELLOW}llama.cpp Metrics:${NC}"
    curl -s http://localhost:8080/metrics 2>/dev/null | grep -E "^(llamacpp|prompt)" | head -10 || echo "  Metrics not available"
fi

echo ""
echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
echo "Press Ctrl+C to exit. Refreshing every 5 seconds..."
echo ""

sleep 5
exec "$0"  # Restart to refresh
