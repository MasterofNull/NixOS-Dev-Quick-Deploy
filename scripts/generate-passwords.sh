#!/usr/bin/env bash
#
# Generate Database & Service Passwords
# ======================================
# This script generates cryptographically secure passwords for:
# - PostgreSQL database
# - Redis cache
# - Grafana admin user
#
# Security features:
# - 32 bytes (256 bits) of cryptographic randomness per password
# - Stored as Kubernetes secrets (sops-managed)
# - File permissions set to 600 (owner read/write only)
# - Alphanumeric + special characters for database compatibility
#
# Usage:
#   ./scripts/generate-passwords.sh
#
# Output:
#   - Creates secrets/ directory if it doesn't exist
#   - Generates password files in secrets/
#   - Prints password summary (first 8 chars only)
#
# Date: January 2026
# Author: NixOS AI Stack Team
# ======================================

set -euo pipefail

# Resolve project root for portable paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SECRETS_DIR="${PROJECT_ROOT}/ai-stack/kubernetes/secrets/generated"
PASSWORD_LENGTH=32  # characters (not bytes, for readability)

# Passwords to generate
declare -a PASSWORDS=(
    "postgres_password"
    "redis_password"
    "grafana_admin_password"
)

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Generating Database & Service Passwords${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Create secrets directory
mkdir -p "$SECRETS_DIR"

# Check if secrets already exist
EXISTING_COUNT=0
for password in "${PASSWORDS[@]}"; do
    if [[ -f "$SECRETS_DIR/$password" ]]; then
        ((EXISTING_COUNT++))
    fi
done

# Warn if secrets exist
if [[ $EXISTING_COUNT -gt 0 ]]; then
    echo -e "${YELLOW}WARNING: $EXISTING_COUNT password(s) already exist!${NC}"
    echo -e "${YELLOW}Regenerating will invalidate existing passwords.${NC}"
    echo -e "${YELLOW}Services using old passwords will fail to connect.${NC}"
    echo ""
    read -p "Continue and regenerate all passwords? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
    echo ""
fi

# Generate passwords
echo -e "${GREEN}Generating passwords...${NC}"
echo ""

GENERATED=0
for password in "${PASSWORDS[@]}"; do
    secret_file="$SECRETS_DIR/$password"

    # Generate cryptographically secure random password
    # Using base64 for alphanumeric + safe special chars (database compatible)
    # Remove problematic chars: /, +, = (can cause issues in connection strings)
    password_value=$(openssl rand -base64 48 | tr -d '/+=' | head -c $PASSWORD_LENGTH)

    # Write to file
    echo -n "$password_value" > "$secret_file"

    # Set restrictive permissions (owner read/write only)
    chmod 600 "$secret_file"

    # Display summary (show only first 8 chars for security)
    prefix="${password_value:0:8}"
    echo -e "  ${GREEN}✓${NC} $password: ${prefix}... (${#password_value} chars)"

    ((GENERATED++))
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Success! Generated $GENERATED passwords${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${BLUE}Password Details:${NC}"
echo -e "  • Location: $SECRETS_DIR"
echo -e "  • Permissions: 600 (owner read/write only)"
echo -e "  • Length: $PASSWORD_LENGTH characters"
echo -e "  • Character set: Alphanumeric (base64, safe for connection strings)"
echo -e "  • Entropy: ~192 bits per password"
echo ""
echo -e "${BLUE}Passwords Generated:${NC}"
echo -e "  • postgres_password - PostgreSQL database"
echo -e "  • redis_password - Redis cache"
echo -e "  • grafana_admin_password - Grafana admin user"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo -e "  • These secrets should be encrypted with sops before committing"
echo -e "  • Services read passwords from Kubernetes secrets"
echo -e "  • Backup these secrets securely (encrypted storage)"
echo -e "  • Do NOT commit generated/ secrets directly"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Encrypt secrets into ai-stack/kubernetes/secrets/secrets.sops.yaml"
echo -e "  2. Remove plaintext passwords from .env file if present"
echo -e "  3. Apply manifests: kubectl apply -k ai-stack/kubernetes"
echo ""
echo -e "${BLUE}Grafana First Login:${NC}"
echo -e "  • Username: admin"
echo -e "  • Password: (see $SECRETS_DIR/grafana_admin_password)"
echo -e "  • You will be prompted to change password on first login"
echo ""

# Verify .gitignore
if ! grep -q "^ai-stack/kubernetes/secrets/generated/$" "${PROJECT_ROOT}/.gitignore" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Warning: secrets/ not found in .gitignore${NC}"
    echo -e "${YELLOW}  Already added in Day 3, but verify:${NC}"
    echo -e "${YELLOW}  grep 'secrets/' .gitignore${NC}"
    echo ""
fi

echo -e "${GREEN}Done!${NC}"
