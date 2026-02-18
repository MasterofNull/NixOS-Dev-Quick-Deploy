#!/usr/bin/env bats
#
# Unit tests for scripts/discover-system-facts.sh
#

load test_helper

DISCOVER_SCRIPT="$PROJECT_ROOT/scripts/discover-system-facts.sh"

setup() {
  export SCRIPT_DIR="$PROJECT_ROOT"
  TMP_FACTS_DIR="$(mktemp -d)"
  export TMP_FACTS_DIR
}

teardown() {
  rm -rf "$TMP_FACTS_DIR"
}

@test "discover-system-facts writes deterministic facts file" {
  local output_path="$TMP_FACTS_DIR/facts.nix"

  run env \
    HOSTNAME_OVERRIDE="test-host" \
    PRIMARY_USER_OVERRIDE="tester" \
    PROFILE_OVERRIDE="minimal" \
    CPU_VENDOR_OVERRIDE="amd" \
    GPU_VENDOR_OVERRIDE="amd" \
    IGPU_VENDOR_OVERRIDE="none" \
    STORAGE_TYPE_OVERRIDE="nvme" \
    SYSTEM_RAM_GB_OVERRIDE="32" \
    IS_MOBILE_OVERRIDE="true" \
    EARLY_KMS_POLICY_OVERRIDE="off" \
    ENABLE_HIBERNATION_OVERRIDE="false" \
    SWAP_SIZE_GB_OVERRIDE="0" \
    DISK_LAYOUT_OVERRIDE="gpt-efi-ext4" \
    DISK_DEVICE_OVERRIDE="/dev/vda" \
    DISK_LUKS_ENABLE_OVERRIDE="false" \
    SECUREBOOT_ENABLE_OVERRIDE="false" \
    FACTS_OUTPUT="$output_path" \
    "$DISCOVER_SCRIPT"
  [[ "$status" -eq 0 ]]
  [[ -f "$output_path" ]]

  run grep -nE 'hostName = "test-host";|primaryUser = "tester";|profile = "minimal";|gpuVendor = "amd";|igpuVendor = "none";|storageType = "nvme";|systemRamGb = 32;|isMobile = true;|earlyKmsPolicy = "off";|layout = "gpt-efi-ext4";|device = "/dev/vda";|luks.enable = false;|secureboot.enable = false;' "$output_path"
  [[ "$status" -eq 0 ]]

  run grep -nE 'rootFsckMode = "check";|initrdEmergencyAccess = true;' "$output_path"
  [[ "$status" -eq 0 ]]

  run env \
    HOSTNAME_OVERRIDE="test-host" \
    PRIMARY_USER_OVERRIDE="tester" \
    PROFILE_OVERRIDE="minimal" \
    CPU_VENDOR_OVERRIDE="amd" \
    GPU_VENDOR_OVERRIDE="amd" \
    IGPU_VENDOR_OVERRIDE="none" \
    STORAGE_TYPE_OVERRIDE="nvme" \
    SYSTEM_RAM_GB_OVERRIDE="32" \
    IS_MOBILE_OVERRIDE="true" \
    EARLY_KMS_POLICY_OVERRIDE="off" \
    ENABLE_HIBERNATION_OVERRIDE="false" \
    SWAP_SIZE_GB_OVERRIDE="0" \
    DISK_LAYOUT_OVERRIDE="gpt-efi-ext4" \
    DISK_DEVICE_OVERRIDE="/dev/vda" \
    DISK_LUKS_ENABLE_OVERRIDE="false" \
    SECUREBOOT_ENABLE_OVERRIDE="false" \
    FACTS_OUTPUT="$output_path" \
    "$DISCOVER_SCRIPT"
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ "No changes:" ]]
}

@test "discover-system-facts rejects invalid profile override" {
  run env \
    HOSTNAME_OVERRIDE="test-host" \
    PRIMARY_USER_OVERRIDE="tester" \
    PROFILE_OVERRIDE="bad-profile" \
    FACTS_OUTPUT="$TMP_FACTS_DIR/facts.nix" \
    "$DISCOVER_SCRIPT"
  [[ "$status" -ne 0 ]]
}

@test "discover-system-facts rejects invalid disk layout override" {
  run env \
    HOSTNAME_OVERRIDE="test-host" \
    PRIMARY_USER_OVERRIDE="tester" \
    PROFILE_OVERRIDE="minimal" \
    DISK_LAYOUT_OVERRIDE="invalid-layout" \
    FACTS_OUTPUT="$TMP_FACTS_DIR/facts.nix" \
    "$DISCOVER_SCRIPT"
  [[ "$status" -ne 0 ]]
}

@test "discover-system-facts rejects malformed hostname override" {
  run env \
    HOSTNAME_OVERRIDE="bad host" \
    PRIMARY_USER_OVERRIDE="tester" \
    PROFILE_OVERRIDE="minimal" \
    FACTS_OUTPUT="$TMP_FACTS_DIR/facts.nix" \
    "$DISCOVER_SCRIPT"
  [[ "$status" -ne 0 ]]
}
