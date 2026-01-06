#!/usr/bin/env bash
# Verification script for NixOS Documentation MCP Server
# Run this after the build completes to verify everything works

set -e

echo "========================================="
echo "NixOS Docs MCP Server Verification"
echo "========================================="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if build is complete
echo "1. Checking if image was built..."
if podman images | grep -q "compose_nixos-docs"; then
    echo -e "${GREEN}✓${NC} Image 'compose_nixos-docs' found"
else
    echo -e "${RED}✗${NC} Image 'compose_nixos-docs' not found"
    echo "   Run: cd ai-stack/compose && podman-compose build nixos-docs"
    exit 1
fi
echo

# Check if container is running
echo "2. Checking container status..."
if podman ps --format "{{.Names}}" | grep -q "local-ai-nixos-docs"; then
    STATUS=$(podman ps -a --filter "name=local-ai-nixos-docs" --format "{{.Status}}")
    echo -e "${GREEN}✓${NC} Container running: $STATUS"
else
    echo -e "${YELLOW}!${NC} Container not running. Starting..."
    cd ai-stack/compose && podman-compose up -d nixos-docs
    sleep 5
fi
echo

# Check if port 8094 is listening
echo "3. Checking if port 8094 is listening..."
if timeout 2 bash -c 'cat < /dev/null > /dev/tcp/localhost/8094' 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Port 8094 is open"
else
    echo -e "${RED}✗${NC} Port 8094 is not responding"
    echo "   Checking logs..."
    podman logs --tail 20 local-ai-nixos-docs
    exit 1
fi
echo

# Test health endpoint
echo "4. Testing /health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8094/health)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}✓${NC} Health check passed"
    echo "   Response: $HEALTH_RESPONSE" | head -c 100
    echo
else
    echo -e "${RED}✗${NC} Health check failed"
    echo "   Response: $HEALTH_RESPONSE"
    exit 1
fi
echo

# Test package search
echo "5. Testing /packages/search endpoint..."
PACKAGE_RESPONSE=$(curl -s -X POST http://localhost:8094/packages/search \
  -H "Content-Type: application/json" \
  -d '{"name": "git"}')
if echo "$PACKAGE_RESPONSE" | grep -q '"total"'; then
    TOTAL=$(echo "$PACKAGE_RESPONSE" | grep -o '"total":[0-9]*' | cut -d':' -f2)
    echo -e "${GREEN}✓${NC} Package search works (found $TOTAL results for 'git')"
else
    echo -e "${YELLOW}!${NC} Package search returned unexpected response"
    echo "   Response: $PACKAGE_RESPONSE" | head -c 100
fi
echo

# Test documentation sources
echo "6. Testing /sources endpoint..."
SOURCES_RESPONSE=$(curl -s http://localhost:8094/sources)
if echo "$SOURCES_RESPONSE" | grep -q "nix.dev"; then
    echo -e "${GREEN}✓${NC} Sources endpoint works"
    echo "   Available sources: nix.dev, NixOS Manual, Nix Manual, etc."
else
    echo -e "${YELLOW}!${NC} Sources endpoint returned unexpected response"
fi
echo

# Check Redis connection
echo "7. Checking Redis connectivity..."
CACHE_STATS=$(curl -s http://localhost:8094/cache/stats)
if echo "$CACHE_STATS" | grep -q "redis"; then
    if echo "$CACHE_STATS" | grep -q '"connected":true'; then
        echo -e "${GREEN}✓${NC} Redis connected"
    else
        echo -e "${YELLOW}!${NC} Redis not connected (using disk cache only)"
    fi
else
    echo -e "${YELLOW}!${NC} Could not determine Redis status"
fi
echo

# Check container logs for errors
echo "8. Checking for errors in logs..."
ERROR_COUNT=$(podman logs local-ai-nixos-docs 2>&1 | grep -i error | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No errors found in logs"
else
    echo -e "${YELLOW}!${NC} Found $ERROR_COUNT error(s) in logs"
    echo "   Recent errors:"
    podman logs local-ai-nixos-docs 2>&1 | grep -i error | tail -3
fi
echo

# Summary
echo "========================================="
echo -e "${GREEN}✓ Verification Complete!${NC}"
echo "========================================="
echo
echo "NixOS Documentation MCP Server is running on:"
echo "  http://localhost:8094"
echo
echo "Test it with:"
echo "  curl http://localhost:8094/health"
echo "  curl -X POST http://localhost:8094/search -H 'Content-Type: application/json' -d '{\"query\":\"flakes\"}'"
echo "  curl -X POST http://localhost:8094/packages/search -H 'Content-Type: application/json' -d '{\"name\":\"neovim\"}'"
echo
