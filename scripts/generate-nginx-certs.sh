#!/usr/bin/env bash
set -euo pipefail

# Configuration
CERT_DIR="ai-stack/compose/nginx/certs"
KEY_FILE="${CERT_DIR}/server.key"
CERT_FILE="${CERT_DIR}/server.crt"
DAYS_VALID=365

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting TLS Certificate Generation for AI Stack...${NC}"

# Ensure directory exists
if [ ! -d "$CERT_DIR" ]; then
    echo "Creating certificate directory: $CERT_DIR"
    mkdir -p "$CERT_DIR"
fi

# Check if openssl is installed
if ! command -v openssl &> /dev/null; then
    echo "Error: openssl is not installed."
    exit 1
fi

# Generate configuration for SANs (Subject Alternative Names)
# This is crucial for Chrome/modern browsers to accept localhost certs
CATFILE=$(mktemp)
cat > "$CATFILE" <<EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = US
ST = State
L = City
O = NixOS-AI-Stack
OU = LocalDev
CN = localhost

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

echo "Generating 4096-bit RSA key and self-signed certificate..."

openssl req -new -x509 -nodes -days "$DAYS_VALID" \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -config "$CATFILE"

# Set secure permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

rm "$CATFILE"

echo -e "${GREEN}✓ Certificates generated successfully!${NC}"
echo -e "  Key:  $KEY_FILE (0600)"
echo -e "  Cert: $CERT_FILE (0644)"
echo -e "${YELLOW}Next step: Restart Nginx container to apply changes.${NC}"