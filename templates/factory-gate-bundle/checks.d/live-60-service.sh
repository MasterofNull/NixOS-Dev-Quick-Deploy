#!/usr/bin/env bash
set -euo pipefail
command_template='{{LIVE_SERVICE_CHECK_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_LIVE_SERVICE_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: LIVE_SERVICE explicitly disabled by FACTORY_LIVE_SERVICE_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{LIVE_SERVICE_CHECK_CMD}} or explicitly set FACTORY_LIVE_SERVICE_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
