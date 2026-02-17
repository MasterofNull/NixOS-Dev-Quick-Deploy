#!/usr/bin/env bats
#
# Unit tests for scripts/validate-config-settings.sh
#

load test_helper

SCRIPT_UNDER_TEST="$PROJECT_ROOT/scripts/validate-config-settings.sh"

@test "validate-config-settings: default settings pass" {
  run "$SCRIPT_UNDER_TEST"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Configuration validation passed." ]]
}

@test "validate-config-settings: invalid namespace fails" {
  run env AI_STACK_NAMESPACE="bad_namespace!" "$SCRIPT_UNDER_TEST"
  [ "$status" -ne 0 ]
}

@test "validate-config-settings: invalid port fails" {
  run env AIDB_PORT="70000" "$SCRIPT_UNDER_TEST"
  [ "$status" -ne 0 ]
}
