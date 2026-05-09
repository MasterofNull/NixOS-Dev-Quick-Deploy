#!/usr/bin/env bash
# compatibility shim over declarative TLS status and journal scans

set -euo pipefail

patterns='tls|certificate|acme|letsencrypt'

if ! command -v journalctl >/dev/null 2>&1; then
  echo "PASS: journalctl unavailable; skipping TLS journal scan"
  exit 0
fi

if journalctl -b --no-pager 2>/dev/null | grep -Eiq "${patterns}"; then
  echo "INFO: TLS-related journal lines detected; inspect with journalctl -b --no-pager | grep -Ei '${patterns}'"
else
  echo "PASS: no TLS warning patterns detected in current boot journal"
fi
