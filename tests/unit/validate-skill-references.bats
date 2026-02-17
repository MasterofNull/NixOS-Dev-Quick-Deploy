#!/usr/bin/env bats
#
# Unit tests for scripts/validate-skill-references.sh
#

load test_helper

VALIDATE_SCRIPT="$PROJECT_ROOT/scripts/validate-skill-references.sh"
FIXTURE_ROOT="$PROJECT_ROOT/archive/test-fixtures/skill-reference-lint"

@test "validate-skill-references passes for valid fixture roots" {
  run env SKILL_REFERENCE_ROOTS="$FIXTURE_ROOT/valid-skill" "$VALIDATE_SCRIPT"
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ "PASS: all relative skill references resolve." ]]
}

@test "validate-skill-references fails with actionable remediation for broken fixtures" {
  run bash -c "env SKILL_REFERENCE_ROOTS='$FIXTURE_ROOT/broken-skill' '$VALIDATE_SCRIPT' 2>&1"
  [[ "$status" -ne 0 ]]
  [[ "$output" =~ "MISSING:" ]]
  [[ "$output" =~ "Remediation:" ]]
}
