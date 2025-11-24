#!/usr/bin/env bash
# Migration script: Move AI stack from system-level to user-level (home-manager)
# This ensures no port conflicts and uses rootless podman for better security

set -euo pipefail

echo "==================================================================="
echo "AI Stack Migration: System-level → User-level (home-manager)"
echo "==================================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check current status
echo -e "${YELLOW}Step 1: Checking current service status...${NC}"
echo ""
echo "System-level services (root):"
sudo systemctl status ollama.service --no-pager | head -3 || true
sudo systemctl status qdrant.service --no-pager | head -3 || true
echo ""

echo "User-level services (home-manager):"
systemctl --user status podman-local-ai-ollama.service --no-pager 2>&1 | head -3 || true
systemctl --user status podman-local-ai-qdrant.service --no-pager 2>&1 | head -3 || true
echo ""

# Confirm migration
echo -e "${YELLOW}This script will:${NC}"
echo "  1. Stop and disable system-level ollama.service"
echo "  2. Stop and disable system-level qdrant.service"
echo "  3. Clean up any data if requested"
echo "  4. Enable user-level services via home-manager"
echo ""
read -p "Continue with migration? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

# Step 2: Stop system services
echo -e "${YELLOW}Step 2: Stopping system-level services...${NC}"
sudo systemctl stop ollama.service || true
sudo systemctl stop qdrant.service || true
echo -e "${GREEN}✓ Services stopped${NC}"

# Step 3: Disable system services
echo -e "${YELLOW}Step 3: Disabling system-level services...${NC}"
sudo systemctl disable ollama.service || true
sudo systemctl disable qdrant.service || true
echo -e "${GREEN}✓ Services disabled${NC}"

# Step 4: Optional data cleanup
echo ""
echo -e "${YELLOW}Step 4: Data cleanup (optional)${NC}"
echo "System-level data locations:"
echo "  - Ollama: /var/lib/ollama/ (if exists)"
echo "  - Qdrant: /var/lib/qdrant/"
echo ""
read -p "Do you want to remove system-level data? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo rm -rf /var/lib/qdrant/ || true
    sudo rm -rf /var/lib/ollama/ || true
    echo -e "${GREEN}✓ System-level data removed${NC}"
else
    echo "Data preserved (can be manually removed later)"
fi

# Step 5: Verify ports are free
echo ""
echo -e "${YELLOW}Step 5: Verifying ports are now available...${NC}"
sleep 2
if ss -tlnp | grep -E ':(6333|6334|11434)' >/dev/null 2>&1; then
    echo -e "${RED}⚠ Warning: Ports still in use. Check:${NC}"
    ss -tlnp | grep -E ':(6333|6334|11434)' || true
    echo ""
    echo "You may need to wait a few seconds or reboot for ports to be released."
else
    echo -e "${GREEN}✓ All ports are now available (6333, 6334, 11434)${NC}"
fi

# Step 6: Start user-level services
echo ""
echo -e "${YELLOW}Step 6: Starting user-level services via home-manager...${NC}"
systemctl --user start podman-local-ai-network.service || true
systemctl --user start podman-local-ai-ollama.service || true
systemctl --user start podman-local-ai-qdrant.service || true
systemctl --user start podman-local-ai-open-webui.service || true
systemctl --user start podman-local-ai-mindsdb.service || true

# Step 7: Check status
echo ""
echo -e "${YELLOW}Step 7: Checking user-level service status...${NC}"
sleep 3
echo ""
systemctl --user status podman-local-ai-ollama.service --no-pager | head -10 || true
echo ""
systemctl --user status podman-local-ai-qdrant.service --no-pager | head -10 || true

# Summary
echo ""
echo "==================================================================="
echo -e "${GREEN}Migration Complete!${NC}"
echo "==================================================================="
echo ""
echo "User-level services are now managed by home-manager:"
echo "  - Ollama:      http://127.0.0.1:11434"
echo "  - Qdrant:      http://127.0.0.1:6333 (HTTP), 6334 (gRPC)"
echo "  - Open WebUI:  http://127.0.0.1:8081"
echo "  - MindsDB:     http://127.0.0.1:7735 (GUI), 47334 (API)"
echo ""
echo "Data location: ~/.local/share/podman-ai-stack/"
echo ""
echo "Manage services:"
echo "  systemctl --user status podman-local-ai-ollama.service"
echo "  systemctl --user restart podman-local-ai-ollama.service"
echo "  journalctl --user -u podman-local-ai-ollama.service -f"
echo ""
echo "To disable AI stack: Set 'localAiStackEnabled = false;' in home.nix"
echo ""
