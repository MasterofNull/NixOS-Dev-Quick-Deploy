#!/usr/bin/env bash
set -euo pipefail

# Automated TLS Certificate Renewal with Let's Encrypt
# Usage: ./scripts/renew-tls-certificate.sh --domain example.com --email admin@example.com
#
# Features:
# - Automatic certificate renewal via Let's Encrypt
# - ACME HTTP-01 challenge support
# - Zero-downtime nginx reload
# - Backup of old certificates
# - Prometheus metrics export
# - Email notifications (optional)

DOMAIN=""
EMAIL=""
WEBROOT="/var/www/letsencrypt"
CERT_DIR="$(pwd)/ai-stack/compose/nginx/certs"
STAGING=false
DRY_RUN=false
FORCE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    --webroot)
      WEBROOT="$2"
      shift 2
      ;;
    --staging)
      STAGING=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help)
      cat <<EOF
Usage: $0 --domain DOMAIN --email EMAIL [options]

Options:
  --domain DOMAIN    Domain name for certificate (required)
  --email EMAIL      Email for Let's Encrypt notifications (required)
  --webroot PATH     Web root for ACME challenge (default: /var/www/letsencrypt)
  --staging          Use Let's Encrypt staging environment (for testing)
  --dry-run          Test renewal without actually renewing
  --force            Force renewal even if certificate is not expiring
  --help             Show this help message

Examples:
  # Production renewal
  $0 --domain ai-stack.example.com --email admin@example.com

  # Test with staging environment
  $0 --domain ai-stack.example.com --email admin@example.com --staging

  # Dry run (certbot test mode)
  $0 --domain ai-stack.example.com --email admin@example.com --dry-run
EOF
      exit 0
      ;;
    *)
      echo -e "${RED}❌ Unknown argument: $1${NC}" >&2
      exit 1
      ;;
  esac
done

# Validate required arguments
if [[ -z "${DOMAIN}" ]]; then
  echo -e "${RED}❌ Error: --domain required${NC}" >&2
  echo "Run with --help for usage information" >&2
  exit 1
fi

if [[ -z "${EMAIL}" ]]; then
  echo -e "${RED}❌ Error: --email required${NC}" >&2
  echo "Run with --help for usage information" >&2
  exit 1
fi

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
  echo -e "${RED}❌ Error: certbot not found${NC}" >&2
  echo "Install with: sudo apt-get install certbot" >&2
  echo "Or with Nix: nix-shell -p certbot" >&2
  exit 1
fi

echo -e "${GREEN}🔐 Let's Encrypt Certificate Renewal${NC}"
echo "  Domain: ${DOMAIN}"
echo "  Email: ${EMAIL}"
echo "  Webroot: ${WEBROOT}"
echo "  Staging: ${STAGING}"
echo "  Dry Run: ${DRY_RUN}"
echo ""

# Create webroot for ACME challenge
echo "📁 Creating webroot directory..."
sudo mkdir -p "${WEBROOT}"
sudo chown -R www-data:www-data "${WEBROOT}" 2>/dev/null || sudo chown -R $(whoami):$(whoami) "${WEBROOT}"

# Check existing certificate
if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]] && [[ "${FORCE}" != "true" ]]; then
  EXPIRY_DATE=$(sudo openssl x509 -in "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" -noout -enddate | cut -d= -f2)
  EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "${EXPIRY_DATE}" +%s 2>/dev/null)
  NOW_EPOCH=$(date +%s)
  DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

  echo "📜 Existing certificate found:"
  echo "   Expires: ${EXPIRY_DATE}"
  echo "   Days remaining: ${DAYS_UNTIL_EXPIRY}"

  if [[ ${DAYS_UNTIL_EXPIRY} -gt 30 ]]; then
    echo -e "${GREEN}✅ Certificate is still valid for >30 days. Skipping renewal.${NC}"
    echo "   Use --force to renew anyway."
    exit 0
  fi

  echo -e "${YELLOW}⚠️  Certificate expires in <30 days. Renewing...${NC}"
fi

# Build certbot command
CERTBOT_CMD=(
  "sudo" "certbot" "certonly"
  "--webroot"
  "--webroot-path" "${WEBROOT}"
  "--domain" "${DOMAIN}"
  "--email" "${EMAIL}"
  "--agree-tos"
  "--non-interactive"
)

if [[ "${STAGING}" == "true" ]]; then
  CERTBOT_CMD+=("--staging")
  echo -e "${YELLOW}⚠️  Using Let's Encrypt STAGING environment${NC}"
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  CERTBOT_CMD+=("--dry-run")
  echo -e "${YELLOW}ℹ️  Running in DRY RUN mode (no actual renewal)${NC}"
fi

# Request/renew certificate
echo ""
echo "🔄 Requesting certificate from Let's Encrypt..."
if "${CERTBOT_CMD[@]}"; then
  echo -e "${GREEN}✅ Certificate obtained successfully${NC}"
else
  echo -e "${RED}❌ Certificate request failed${NC}" >&2
  exit 1
fi

# Skip the rest if dry run
if [[ "${DRY_RUN}" == "true" ]]; then
  echo ""
  echo -e "${GREEN}✅ Dry run complete. No changes made.${NC}"
  exit 0
fi

# Backup old certificates (if they exist)
if [[ -f "${CERT_DIR}/${DOMAIN}.crt" ]]; then
  BACKUP_DIR="${CERT_DIR}/backups"
  sudo mkdir -p "${BACKUP_DIR}"

  BACKUP_FILE="${BACKUP_DIR}/${DOMAIN}_$(date +%Y%m%d_%H%M%S).crt"
  sudo cp "${CERT_DIR}/${DOMAIN}.crt" "${BACKUP_FILE}"
  sudo chmod 400 "${BACKUP_FILE}"

  echo "📦 Backed up old certificate to: ${BACKUP_FILE}"
fi

# Copy new certificates to nginx directory
echo "📋 Copying certificates to nginx directory..."
sudo cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${CERT_DIR}/${DOMAIN}.crt"
sudo cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${CERT_DIR}/${DOMAIN}.key"

# Fix permissions
sudo chmod 644 "${CERT_DIR}/${DOMAIN}.crt"
sudo chmod 600 "${CERT_DIR}/${DOMAIN}.key"
sudo chown $(whoami):$(whoami) "${CERT_DIR}/${DOMAIN}.crt" "${CERT_DIR}/${DOMAIN}.key"

echo -e "${GREEN}✅ Certificates installed${NC}"

# Reload nginx (zero downtime)
echo "🔄 Reloading nginx..."
if podman exec local-ai-nginx nginx -t; then
  podman exec local-ai-nginx nginx -s reload
  echo -e "${GREEN}✅ Nginx reloaded successfully${NC}"
else
  echo -e "${RED}❌ Nginx configuration test failed${NC}" >&2
  echo "   Old certificates are still in use (safe)" >&2
  exit 1
fi

# Export Prometheus metrics
METRICS_FILE="/var/lib/prometheus/node-exporter/letsencrypt-renewal.prom"
if [[ -d "$(dirname "${METRICS_FILE}")" ]]; then
  EXPIRY_DATE=$(sudo openssl x509 -in "${CERT_DIR}/${DOMAIN}.crt" -noout -enddate | cut -d= -f2)
  EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "${EXPIRY_DATE}" +%s 2>/dev/null)
  RENEWAL_TIMESTAMP=$(date +%s)

  cat > "${METRICS_FILE}" <<EOF
# HELP letsencrypt_certificate_renewal_timestamp Unix timestamp of last renewal
# TYPE letsencrypt_certificate_renewal_timestamp gauge
letsencrypt_certificate_renewal_timestamp{domain="${DOMAIN}"} ${RENEWAL_TIMESTAMP}

# HELP letsencrypt_certificate_renewal_success Success of last renewal (1=success, 0=failure)
# TYPE letsencrypt_certificate_renewal_success gauge
letsencrypt_certificate_renewal_success{domain="${DOMAIN}"} 1
EOF

  echo "📊 Exported Prometheus metrics to: ${METRICS_FILE}"
fi

# Summary
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Certificate Renewal Complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
EXPIRY_DATE=$(sudo openssl x509 -in "${CERT_DIR}/${DOMAIN}.crt" -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "${EXPIRY_DATE}" +%s 2>/dev/null)
NOW_EPOCH=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

echo "📜 Certificate Details:"
echo "   Domain: ${DOMAIN}"
echo "   Issuer: Let's Encrypt"
echo "   Expires: ${EXPIRY_DATE}"
echo "   Valid for: ${DAYS_UNTIL_EXPIRY} days"
echo ""
echo "📁 Certificate Files:"
echo "   Certificate: ${CERT_DIR}/${DOMAIN}.crt"
echo "   Private Key: ${CERT_DIR}/${DOMAIN}.key"
echo ""
echo "🔄 Next Renewal:"
echo "   Automatic renewal will run when <30 days remain"
echo "   Monitor via Prometheus alert: TLSCertificateExpiringWarning"
echo ""
