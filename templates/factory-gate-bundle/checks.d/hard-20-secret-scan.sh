#!/usr/bin/env bash
set -euo pipefail
command_template='{{SECRET_SCAN_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_SECRET_SCAN_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: SECRET_SCAN explicitly disabled by FACTORY_SECRET_SCAN_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{SECRET_SCAN_CMD}} or explicitly set FACTORY_SECRET_SCAN_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
