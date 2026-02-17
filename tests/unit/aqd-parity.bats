#!/usr/bin/env bats
#
# Unit tests for scripts/aqd CLI parity and wrapper behavior
#

load test_helper

AQD="$PROJECT_ROOT/scripts/aqd"
FIXTURE_VALID_SKILL="$PROJECT_ROOT/archive/test-fixtures/skill-reference-lint/valid-skill"

@test "aqd --version returns pinned wrapper version format" {
  run "$AQD" --version
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ ^aqd[[:space:]][0-9]+\.[0-9]+\.[0-9]+$ ]]
}

@test "aqd workflows list includes validation and evaluation workflows" {
  run "$AQD" workflows list
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ "skill quick-validate" ]]
  [[ "$output" =~ "mcp validate" ]]
  [[ "$output" =~ "mcp evaluate" ]]
}

@test "aqd skill quick-validate works for valid fixture skill" {
  run "$AQD" skill quick-validate "$FIXTURE_VALID_SKILL"
  [[ "$status" -eq 0 ]]
}

@test "aqd skill validate exit code matches direct governance scripts" {
  run bash -lc "cd '$PROJECT_ROOT' && ./scripts/check-skill-source-of-truth.sh && ./scripts/lint-skill-external-deps.sh && ./scripts/validate-skill-references.sh && ./scripts/lint-skill-template.sh"
  local direct_status="$status"

  run bash -lc "cd '$PROJECT_ROOT' && ./scripts/aqd skill validate"
  local aqd_status="$status"

  [[ "$aqd_status" -eq "$direct_status" ]]
}

@test "aqd mcp validate exit code matches direct mcp-server test for missing server" {
  run bash -lc "cd '$PROJECT_ROOT' && ./scripts/mcp-server test does-not-exist"
  local direct_status="$status"

  run bash -lc "cd '$PROJECT_ROOT' && ./scripts/aqd mcp validate does-not-exist"
  local aqd_status="$status"

  [[ "$aqd_status" -eq "$direct_status" ]]
}
