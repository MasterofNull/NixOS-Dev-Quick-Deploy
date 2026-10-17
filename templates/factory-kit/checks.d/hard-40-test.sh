#!/usr/bin/env bash
set -euo pipefail
command_template='{{TEST_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_TEST_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: TEST explicitly disabled by FACTORY_TEST_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{TEST_CMD}} or explicitly set FACTORY_TEST_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
