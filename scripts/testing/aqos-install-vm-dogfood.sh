#!/usr/bin/env bash
set -euo pipefail

# aqos-install-vm-dogfood.sh — disko disk/install MECHANICS harness
# (slice s1a, .agents/plans/aqos-installer-experience/
# END-TO-END-BARE-METAL-PLAN.md).
#
# Proves, ROOTLESS and entirely inside qemu, that our NixOS config can
# PARTITION a virtual disk, INSTALL the golden aqos-workstation profile onto
# it, and BOOT the result — for both a plain (gpt-efi-ext4) and a
# LUKS-encrypted (gpt-luks-ext4) layout. Uses disko's own rootless in-VM
# test framework (inputs.disko.lib.testLib.makeDiskoTest, wired as flake
# checks in flake.nix: checks.x86_64-linux.aqos-install-vm-disko-{plain,luks}).
#
# This is NOT scripts/testing/aqos-vm-dogfood.sh: that harness proves only
# BOOT, via `nixos-rebuild build-vm`'s own self-synthesized disk — it never
# partitions anything. This harness proves the disk/install PLUMBING itself.
# No sudo anywhere; disks are qcow2 files created inside the Nix build
# sandbox by disko's own test framework.
#
# Usage:
#   scripts/testing/aqos-install-vm-dogfood.sh                       # Step A only (fast gate, both layouts)
#   scripts/testing/aqos-install-vm-dogfood.sh --full                # Step A + Step B, both layouts
#   scripts/testing/aqos-install-vm-dogfood.sh --full --layout plain # Step A + Step B, one layout only
#
# Env overrides:
#   AQOS_INSTALL_VM_EVAL_TIMEOUT    seconds allowed per `nix eval` (default: 300)
#   AQOS_INSTALL_VM_BUILD_TIMEOUT   seconds allowed per disko-test `nix build` (default: 3600)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

EVAL_TIMEOUT="${AQOS_INSTALL_VM_EVAL_TIMEOUT:-300}"
BUILD_TIMEOUT="${AQOS_INSTALL_VM_BUILD_TIMEOUT:-3600}"

ALL_LAYOUTS=(plain luks)
LAYOUTS=("${ALL_LAYOUTS[@]}")
FULL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --full)
      FULL=1
      shift
      ;;
    --layout)
      if [ $# -lt 2 ]; then
        echo "[FAIL] --layout requires an argument (plain|luks)" >&2
        exit 2
      fi
      case "$2" in
        plain|luks) LAYOUTS=("$2") ;;
        *)
          echo "[FAIL] unknown layout: $2 (expected plain or luks)" >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    -h|--help)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "[FAIL] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
info() { echo "[INFO] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }
skip() { echo "[SKIP] $*"; }

declare -A STEP_A_STATUS
declare -A STEP_B_STATUS
for l in "${ALL_LAYOUTS[@]}"; do
  STEP_A_STATUS["$l"]="not-run"
  STEP_B_STATUS["$l"]="not-run"
done

# ---------------------------------------------------------------------------
# Step A (cheap, always): .#nixosConfigurations.aqos-install-vm-<layout> must
# EVALUATE as a real nixosConfiguration with the requested disko layout —
# proves the mySystem.disk.layout + golden-profile wiring resolves, before
# paying for the heavy partition/install/boot proof in Step B.
# ---------------------------------------------------------------------------
step_a() {
  local layout="$1" host="aqos-install-vm-${layout}"
  local target=".#nixosConfigurations.${host}"

  if ! command -v nix >/dev/null 2>&1; then
    skip "step A (${layout}): 'nix' not found on PATH — cannot evaluate ${target}"
    STEP_A_STATUS["$layout"]="skip"
    return 0
  fi

  info "step A (${layout}): evaluating ${target}.config.system.build.toplevel.drvPath (timeout ${EVAL_TIMEOUT}s)"
  local drv_path errfile
  errfile=$(mktemp)
  if ! drv_path=$(timeout "${EVAL_TIMEOUT}" nix eval --raw \
        "${target}.config.system.build.toplevel.drvPath" 2>"${errfile}"); then
    STEP_A_STATUS["$layout"]="fail"
    local errtext; errtext=$(cat "${errfile}"); rm -f "${errfile}"
    fail "step A (${layout}): ${target} does NOT evaluate.
--- nix eval error ---
${errtext}
--- end error ---"
  fi
  rm -f "${errfile}"
  pass "step A (${layout}): ${target} evaluates -> ${drv_path}"
  STEP_A_STATUS["$layout"]="pass"
}

# ---------------------------------------------------------------------------
# Step B (heavy, --full only): run disko's rootless in-VM test for this
# layout — partitions a real virtual disk, installs the golden profile onto
# it via nixos-enter, reboots from the freshly-written disk, and asserts the
# layout-specific structural checks (LUKS present, root mounted) plus our
# own boot marker. Never requires sudo. Skips cleanly (not a failure) if
# nix or qemu are unavailable.
# ---------------------------------------------------------------------------
step_b() {
  local layout="$1" check="aqos-install-vm-disko-${layout}"
  local target=".#checks.x86_64-linux.${check}"

  if [ "${FULL}" -ne 1 ]; then
    skip "step B (${layout}): not requested (pass --full to partition+install+boot)"
    STEP_B_STATUS["$layout"]="skip"
    return 0
  fi
  if ! command -v nix >/dev/null 2>&1; then
    skip "step B (${layout}): 'nix' not found on PATH — cannot build ${target}"
    STEP_B_STATUS["$layout"]="skip"
    return 0
  fi
  if ! command -v qemu-system-x86_64 >/dev/null 2>&1 && ! command -v qemu-kvm >/dev/null 2>&1; then
    skip "step B (${layout}): no qemu binary found on PATH — cannot run ${target}"
    STEP_B_STATUS["$layout"]="skip"
    return 0
  fi

  local work_dir
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aqos-install-vm-dogfood.XXXXXX")"
  trap 'rm -rf "${work_dir}"' RETURN

  local result_link="${work_dir}/result"
  info "step B (${layout}): nix build ${target} (timeout ${BUILD_TIMEOUT}s, no sudo, rootless disko in-VM partition+install+boot test)"
  if ! timeout "${BUILD_TIMEOUT}" nix build "${target}" -o "${result_link}" \
        >"${work_dir}/build.log" 2>&1; then
    STEP_B_STATUS["$layout"]="fail"
    tail -n 80 "${work_dir}/build.log" >&2 || true
    fail "step B (${layout}): partition/install/boot test FAILED or timed out — see log above (${work_dir}/build.log)."
  fi
  pass "step B (${layout}): partition -> install -> boot proof passed -> ${result_link}"
  STEP_B_STATUS["$layout"]="pass"
}

for layout in "${LAYOUTS[@]}"; do
  step_a "${layout}"
  step_b "${layout}"
done

for layout in "${ALL_LAYOUTS[@]}"; do
  echo "ACTIVATION-AUDIT: aqos-install-vm-dogfood layout=${layout} step_a=${STEP_A_STATUS[$layout]} step_b=${STEP_B_STATUS[$layout]} sudo=never disposable=true"
done
