#!/usr/bin/env bash
# Generate self-signed TLS certificates for nginx
# For local development only - use Let's Encrypt for production
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="${CERT_DIR:-${PROJECT_ROOT}/ai-stack/compose/nginx/certs}"
CERT_FILE="${CERT_DIR}/localhost.crt"
KEY_FILE="${CERT_DIR}/localhost.key"
CERT_DAYS=365

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "${CERT_DIR}"

if [[ -f "${CERT_FILE}" && -f "${KEY_FILE}" ]]; then
  echo -e "${YELLOW}Certificates already exist at ${CERT_DIR}${NC}" >&2
  echo "To regenerate, delete existing certificates first:" >&2
  echo "  rm ${CERT_FILE} ${KEY_FILE}" >&2
  exit 0
fi

echo -e "${GREEN}Generating self-signed TLS certificate...${NC}"

# Generate with SAN (Subject Alternative Name) for modern browsers
openssl req -x509 -nodes -newkey rsa:4096 \
  -keyout "${KEY_FILE}" \
  -out "${CERT_FILE}" \
  -days ${CERT_DAYS} \
  -subj "/C=US/ST=Local/L=Development/O=NixOS AI Stack/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1" \
  -addext "basicConstraints=CA:FALSE" \
  -addext "keyUsage=digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" \
  2>/dev/null

# Set proper permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo -e "${GREEN}✓ Generated self-signed certificates in ${CERT_DIR}${NC}"
echo "  Certificate: ${CERT_FILE} (valid for ${CERT_DAYS} days)"
echo "  Private Key: ${KEY_FILE} (mode 600)"
echo ""
echo -e "${YELLOW}⚠️  These are SELF-SIGNED certificates for LOCAL DEVELOPMENT only${NC}"
echo "   Browsers will show security warnings until you trust the certificate"
echo "   For production, use Let's Encrypt: certbot --nginx"
