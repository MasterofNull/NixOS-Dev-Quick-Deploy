#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUBECTL="${KUBECTL:-kubectl}"

ISSUERS="${ISSUERS:-${SCRIPT_DIR}/ai-stack/kubernetes/tls/cluster-issuers.yaml}"
CERTS="${CERTS:-${SCRIPT_DIR}/ai-stack/kubernetes/tls/service-certificates.yaml}"
RENEWAL="${RENEWAL:-${SCRIPT_DIR}/ai-stack/kubernetes/tls/renewal-cronjob.yaml}"

if [[ ! -f "$ISSUERS" || ! -f "$CERTS" ]]; then
  echo "[ERROR] TLS manifests not found (issuers or certs)" >&2
  exit 1
fi

echo "[INFO] Applying TLS issuers"
"$KUBECTL" apply -f "$ISSUERS"

echo "[INFO] Applying service certificates"
"$KUBECTL" apply -f "$CERTS"

if [[ -f "$RENEWAL" ]]; then
  echo "[INFO] Applying renewal CronJob"
  "$KUBECTL" apply -f "$RENEWAL"
fi

echo "[OK] TLS manifests applied"
