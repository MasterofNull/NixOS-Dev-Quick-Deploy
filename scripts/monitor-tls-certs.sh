#!/usr/bin/env bash
set -euo pipefail

# Monitor TLS certificate expiration and expose metrics for Prometheus
# Usage:
#   ./monitor-tls-certs.sh [--cert-path PATH] [--metrics-file PATH]
#
# This script:
# 1. Checks TLS certificate expiration
# 2. Exports Prometheus metrics to a file
# 3. Can be run via cron or as a sidecar container

CERT_DIR="${CERT_DIR:-ai-stack/compose/nginx/certs}"
METRICS_FILE="${METRICS_FILE:-/var/lib/prometheus/node-exporter/tls-certs.prom}"
CERT_FILE="${CERT_FILE:-${CERT_DIR}/localhost.crt}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cert-path)
      CERT_FILE="$2"
      shift 2
      ;;
    --metrics-file)
      METRICS_FILE="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [--cert-path PATH] [--metrics-file PATH]"
      echo "  --cert-path     Path to certificate file (default: ${CERT_DIR}/localhost.crt)"
      echo "  --metrics-file  Path to write Prometheus metrics (default: ${METRICS_FILE})"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Check if certificate exists
if [[ ! -f "${CERT_FILE}" ]]; then
  echo "❌ Certificate not found: ${CERT_FILE}" >&2
  exit 1
fi

# Extract certificate information
CERT_INFO=$(openssl x509 -in "${CERT_FILE}" -noout -subject -enddate -issuer 2>/dev/null)
if [[ $? -ne 0 ]]; then
  echo "❌ Failed to read certificate: ${CERT_FILE}" >&2
  exit 1
fi

# Extract expiration date
EXPIRY_DATE=$(echo "${CERT_INFO}" | grep "notAfter=" | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "${EXPIRY_DATE}" +%s 2>/dev/null)

if [[ -z "${EXPIRY_EPOCH}" ]]; then
  echo "❌ Failed to parse expiration date: ${EXPIRY_DATE}" >&2
  exit 1
fi

# Calculate days until expiration
NOW_EPOCH=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

# Extract CN (Common Name)
CN=$(echo "${CERT_INFO}" | grep "subject=" | sed -n 's/.*CN=\([^,]*\).*/\1/p' | tr -d ' ')
if [[ -z "${CN}" ]]; then
  CN="localhost"
fi

# Extract issuer
ISSUER=$(echo "${CERT_INFO}" | grep "issuer=" | sed -n 's/.*CN=\([^,]*\).*/\1/p' | tr -d ' ')
if [[ -z "${ISSUER}" ]]; then
  ISSUER="self-signed"
fi

# Determine status
STATUS="ok"
if [[ ${DAYS_UNTIL_EXPIRY} -lt 7 ]]; then
  STATUS="critical"
elif [[ ${DAYS_UNTIL_EXPIRY} -lt 30 ]]; then
  STATUS="warning"
fi

# Output human-readable status
echo "📜 Certificate: ${CN}"
echo "   Issuer: ${ISSUER}"
echo "   Expires: ${EXPIRY_DATE}"
echo "   Days remaining: ${DAYS_UNTIL_EXPIRY}"
echo "   Status: ${STATUS}"

if [[ "${STATUS}" == "critical" ]]; then
  echo "   ⚠️  CRITICAL: Certificate expires in <7 days!"
elif [[ "${STATUS}" == "warning" ]]; then
  echo "   ⚠️  WARNING: Certificate expires in <30 days"
fi

# Write Prometheus metrics (if metrics file specified and directory exists)
if [[ -n "${METRICS_FILE}" ]]; then
  METRICS_DIR=$(dirname "${METRICS_FILE}")
  if [[ ! -d "${METRICS_DIR}" ]]; then
    echo "   Creating metrics directory: ${METRICS_DIR}"
    mkdir -p "${METRICS_DIR}"
  fi

  cat > "${METRICS_FILE}" <<EOF
# HELP nginx_ssl_certificate_expiry_seconds Unix timestamp when the certificate expires
# TYPE nginx_ssl_certificate_expiry_seconds gauge
nginx_ssl_certificate_expiry_seconds{cn="${CN}",issuer="${ISSUER}",cert_file="${CERT_FILE}"} ${EXPIRY_EPOCH}

# HELP nginx_ssl_certificate_days_until_expiry Days until certificate expires
# TYPE nginx_ssl_certificate_days_until_expiry gauge
nginx_ssl_certificate_days_until_expiry{cn="${CN}",issuer="${ISSUER}",cert_file="${CERT_FILE}"} ${DAYS_UNTIL_EXPIRY}

# HELP nginx_ssl_certificate_status Certificate status (0=ok, 1=warning, 2=critical)
# TYPE nginx_ssl_certificate_status gauge
nginx_ssl_certificate_status{cn="${CN}",issuer="${ISSUER}",cert_file="${CERT_FILE}"} $(
  case "${STATUS}" in
    ok) echo 0 ;;
    warning) echo 1 ;;
    critical) echo 2 ;;
  esac
)
EOF

  echo "   ✅ Wrote metrics to: ${METRICS_FILE}"
fi

# Exit with appropriate code
case "${STATUS}" in
  ok)
    exit 0
    ;;
  warning)
    exit 0  # Warning but not blocking
    ;;
  critical)
    exit 2  # Critical - should trigger alerts
    ;;
esac
