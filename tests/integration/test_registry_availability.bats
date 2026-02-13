#!/usr/bin/env bats

setup() {
  if [ "${RUN_K3S_INTEGRATION:-}" != "true" ]; then
    skip "Set RUN_K3S_INTEGRATION=true to enable K3s integration checks"
  fi
}

@test "Local registry reachable" {
  if [ "${RUN_REGISTRY_TEST:-}" != "true" ]; then
    skip "Set RUN_REGISTRY_TEST=true to enable registry availability test"
  fi

  registry_url="${REGISTRY_URL:-http://localhost:5000}"
  run curl -sf --max-time 5 --connect-timeout 3 "${registry_url}/v2/_catalog"
  [ "$status" -eq 0 ]
}
