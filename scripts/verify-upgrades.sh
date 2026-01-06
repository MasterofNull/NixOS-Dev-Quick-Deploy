#!/usr/bin/env bash
# Verify AI Stack Upgrades - December 2025
# Quick validation that all upgrades are properly configured

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   NixOS AI Stack - Upgrade Verification${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

pass=0
fail=0

check() {
    local name="$1"
    local test_cmd="$2"
    
    printf "%-50s " "$name"
    if eval "$test_cmd" &>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((pass++))
    else
        echo -e "${RED}✗${NC}"
        ((fail++))
    fi
}

# File checks
echo -e "${YELLOW}Configuration Files:${NC}"
check "docker-compose.yml (Vulkan support)" "grep -q 'LLAMA_VULKAN_ENABLE' ai-stack/compose/docker-compose.yml"
check ".env.example created" "[ -f ai-stack/compose/.env.example ]"
check "Vulkan device mount configured" "grep -q '/dev/dri:/dev/dri' ai-stack/compose/docker-compose.yml"
echo ""

# Script checks
echo -e "${YELLOW}New CLI Tools:${NC}"
check "llama-model CLI exists" "[ -f scripts/llama-model-cli.sh ]"
check "AI stack monitor exists" "[ -f scripts/ai-stack-monitor.sh ]"
check "Scripts are executable" "[ -x scripts/llama-model-cli.sh ]"
echo ""

# Documentation checks
echo -e "${YELLOW}Documentation:${NC}"
check "Upgrades guide created" "[ -f ai-stack/UPGRADES-2025.md ]"
check "Quick reference created" "[ -f ai-stack/QUICK-REFERENCE.md ]"
check "Upgrade summary created" "[ -f UPGRADE-SUMMARY-2025-12-31.md ]"
check "Auto-start guide created" "[ -f ai-stack/AUTO-START-GUIDE.md ]"
echo ""

# Auto-start configuration checks
echo -e "${YELLOW}Auto-Start Configuration:${NC}"
check "NixOS module exists" "[ -f templates/nixos-improvements/ai-stack-autostart.nix ]"
check "Restart policies configured" "grep -q 'restart: unless-stopped' ai-stack/compose/docker-compose.yml"
check "Monitor updated for nixos-docs" "grep -q 'local-ai-nixos-docs' scripts/ai-stack-monitor.sh"
echo ""

# Hardware checks
echo -e "${YELLOW}Hardware Support:${NC}"
check "GPU device exists" "[ -e /dev/dri ]"
check "Vulkan support available" "command -v vulkaninfo"
check "Podman installed" "command -v podman"
echo ""

# Container checks (optional)
echo -e "${YELLOW}Container Status (optional):${NC}"
check "llama-cpp container exists" "podman ps -a --format '{{.Names}}' | grep -q local-ai-llama-cpp"
check "AIDB container exists" "podman ps -a --format '{{.Names}}' | grep -q local-ai-aidb"
echo ""

# Summary
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "Results: ${GREEN}$pass passed${NC}, ${RED}$fail failed${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

if [ $fail -eq 0 ]; then
    echo -e "${GREEN}✓ All upgrades verified successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Copy .env.example to .env"
    echo "  2. Enable Vulkan: LLAMA_VULKAN_ENABLE=1"
    echo "  3. Restart llama-cpp container"
    echo "  4. Run: ./scripts/ai-stack-monitor.sh"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed (see above)${NC}"
    echo ""
    echo "This is normal if containers aren't running yet."
    echo "Review ai-stack/UPGRADES-2025.md for setup instructions."
    exit 1
fi
