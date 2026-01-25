#!/usr/bin/env bash
#
# Generate API secrets for MCP services
# =======================================================================
# This script generates cryptographically secure API keys for all
# HTTP-based MCP servers and stores them as Docker secrets.
#
# Security features:
# - 32 bytes (256 bits) of cryptographic randomness per key
# - Stored as individual files in secrets/ directory
# - File permissions set to 600 (owner read/write only)
# - NOT stored in environment variables or .env file
# - Each service gets its own unique key
#
# Usage:
#   ./scripts/generate-api-secrets.sh
#
# Output:
#   - Creates secrets/ directory if it doesn't exist
#   - Generates one file per service in secrets/
#   - Prints summary of generated keys
#
# Date: January 2026
# Author: NixOS AI Stack Team
# =======================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SECRETS_DIR="/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/secrets"
KEY_LENGTH=32  # bytes (will be hex-encoded to 64 characters)

# Services that need API keys
declare -a SERVICES=(
    "aidb_api_key"
    "embeddings_api_key"
    "hybrid_coordinator_api_key"
    "nixos_docs_api_key"
    "container_engine_api_key"
    "ralph_wiggum_api_key"
    "aider_wrapper_api_key"
    "dashboard_api_key"
    "stack_api_key"  # Master key for inter-service communication
)

# Create secrets directory
mkdir -p "$SECRETS_DIR"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Generating API Secrets for MCP Services${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if secrets already exist
EXISTING_COUNT=0
for service in "${SERVICES[@]}"; do
    if [[ -f "$SECRETS_DIR/$service" ]]; then
        ((EXISTING_COUNT++))
    fi
done

# Warn if secrets exist
if [[ $EXISTING_COUNT -gt 0 ]]; then
    echo -e "${YELLOW}WARNING: $EXISTING_COUNT secret(s) already exist!${NC}"
    echo -e "${YELLOW}Regenerating will invalidate existing API keys.${NC}"
    echo ""
    read -p "Continue and regenerate all secrets? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
    echo ""
fi

# Generate secrets
echo -e "${GREEN}Generating secrets...${NC}"
echo ""

GENERATED=0
for service in "${SERVICES[@]}"; do
    secret_file="$SECRETS_DIR/$service"

    # Generate cryptographically secure random key
    api_key=$(python3 -c "import secrets; print(secrets.token_hex($KEY_LENGTH))")

    # Write to file
    echo -n "$api_key" > "$secret_file"

    # Set restrictive permissions (owner read/write only)
    chmod 600 "$secret_file"

    # Display summary (show only first 16 chars for security)
    prefix="${api_key:0:16}"
    echo -e "  ${GREEN}✓${NC} $service: ${prefix}... (${#api_key} chars)"

    ((GENERATED++))
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Success! Generated $GENERATED API secrets${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${BLUE}Security Information:${NC}"
echo -e "  • Location: $SECRETS_DIR"
echo -e "  • Permissions: 600 (owner read/write only)"
echo -e "  • Key length: $((KEY_LENGTH * 2)) hex characters ($((KEY_LENGTH * 8)) bits of entropy)"
echo -e "  • Format: Hexadecimal"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo -e "  • These secrets will be mounted to containers at /run/secrets/"
echo -e "  • Services read keys from files, NOT environment variables"
echo -e "  • Add secrets/ directory to .gitignore to prevent accidental commits"
echo -e "  • Backup secrets securely (encrypted storage)"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Update docker-compose.yml to reference these secrets"
echo -e "  2. Update service code to read from /run/secrets/<secret_name>"
echo -e "  3. Restart services to apply new authentication"
echo ""

# Check .gitignore
if ! grep -q "^secrets/\$" /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/.gitignore 2>/dev/null; then
    echo -e "${YELLOW}⚠ Warning: secrets/ not found in .gitignore${NC}"
    echo -e "${YELLOW}  Run: echo 'ai-stack/compose/secrets/' >> .gitignore${NC}"
    echo ""
fi

echo -e "${GREEN}Done!${NC}"
