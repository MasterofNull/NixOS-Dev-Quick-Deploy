#!/usr/bin/env bats
#
# Unit tests for filesystem integrity helper scripts.
#

load test_helper

FS_CHECK_SCRIPT="$PROJECT_ROOT/scripts/fs-integrity-check.sh"
RECOVERY_GUIDE_SCRIPT="$PROJECT_ROOT/scripts/recovery-offline-fsck-guide.sh"

@test "fs-integrity-check exits non-zero when failure signatures are present" {
  run env \
    FS_INTEGRITY_LOG_TEXT="Failed to start File System Check on /dev/disk/by-uuid/abcd" \
    ROOT_UUID_OVERRIDE="1111-2222" \
    "$FS_CHECK_SCRIPT"

  [[ "$status" -eq 2 ]]
  [[ "$output" == *"CRITICAL: filesystem integrity signatures detected."* ]]
  [[ "$output" == *"/dev/disk/by-uuid/1111-2222"* ]]
}

@test "fs-integrity-check passes when no failure signatures are present" {
  run env \
    FS_INTEGRITY_LOG_TEXT="system boot healthy" \
    "$FS_CHECK_SCRIPT"

  [[ "$status" -eq 0 ]]
  [[ "$output" == *"No filesystem integrity failure signatures detected"* ]]
}

@test "recovery guide prints UUID-based offline fsck command when UUID is known" {
  run env \
    HOSTNAME_OVERRIDE="test-host" \
    ROOT_SOURCE_OVERRIDE="/dev/mapper/root" \
    ROOT_UUID_OVERRIDE="abcd-1234" \
    "$RECOVERY_GUIDE_SCRIPT"

  [[ "$status" -eq 0 ]]
  [[ "$output" == *"Current host: test-host"* ]]
  [[ "$output" == *"Current root UUID: abcd-1234"* ]]
  [[ "$output" == *"e2fsck -f -y /dev/disk/by-uuid/abcd-1234"* ]]
  [[ "$output" == *"./scripts/deploy-clean.sh --host test-host --profile ai-dev"* ]]
}
