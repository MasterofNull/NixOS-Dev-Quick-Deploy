#!/usr/bin/env bash
# Diagnose and optionally repair unattended sudo readiness prerequisites.
# Usage:
#   scripts/governance/remediate-unattended-sudo-readiness.sh
#   scripts/governance/remediate-unattended-sudo-readiness.sh --print-repair

set -euo pipefail

PRINT_REPAIR=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-repair)
      PRINT_REPAIR=true
      shift
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/governance/remediate-unattended-sudo-readiness.sh [--print-repair]

Diagnoses unattended sudo readiness and prints the minimal manual repair
commands when the live system has drifted from the expected sudo timestamp
directory ownership.
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

print_repair() {
  cat <<'EOF'
[sudo-remediate] Manual repair commands:
  sudo chown root:root /run/sudo/ts
  sudo chmod 0700 /run/sudo/ts
  sudo systemd-tmpfiles --create /etc/tmpfiles.d /run/tmpfiles.d
  bash scripts/governance/check-unattended-sudo-readiness.sh
  bash scripts/governance/tier0-validation-gate.sh --pre-deploy
EOF
}

echo "[sudo-remediate] Diagnosing unattended sudo readiness..."
if bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-unattended-sudo-readiness.sh"; then
  echo "[sudo-remediate] No repair needed."
  exit 0
fi

echo "[sudo-remediate] Live unattended sudo readiness is degraded."
print_repair

if [[ "${PRINT_REPAIR}" == true ]]; then
  exit 0
fi

exit 1
