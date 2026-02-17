#!/usr/bin/env bats
#
# Unit tests for scripts/ai-stack-troubleshoot.sh
#

load test_helper

SCRIPT_UNDER_TEST="$PROJECT_ROOT/scripts/ai-stack-troubleshoot.sh"

@test "ai-stack-troubleshoot: generates diagnostics report" {
  run "$SCRIPT_UNDER_TEST"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Troubleshooting report written to:" ]]

  report_path="${output##*: }"
  [ -f "$report_path" ]
}
