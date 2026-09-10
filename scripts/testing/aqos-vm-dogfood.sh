#!/usr/bin/env bash
set -euo pipefail

# aqos-vm-dogfood.sh — the VM dogfood activation-validation harness.
#
# Turns the AQ-OS installer line from "committed" to "done" (DoD Rule 15)
# WITHOUT bare-metal risk: it proves the golden `aqos-workstation` profile
# (AI OFF, the offline golden path) both EVALUATES as a real NixOS
# configuration (Step A, cheap, always run) and — when explicitly asked for
# with --full — actually BUILDS and BOOTS as a disposable QEMU VM (Step B,
# heavy, no real disk, no sudo required).
#
# See .agents/plans/aqos-installer-experience/P3-SLICE-PLAN.md ("VM dogfood").
#
# Usage:
#   scripts/testing/aqos-vm-dogfood.sh            # Step A only (fast gate)
#   scripts/testing/aqos-vm-dogfood.sh --full      # Step A + Step B (owner/CI activation run)
#
# Env overrides:
#   AQOS_VM_HOST            nixosConfigurations attr to target (default: aqos-vm)
#   AQOS_VM_EVAL_TIMEOUT    seconds allowed for `nix eval` (default: 300)
#   AQOS_VM_BUILD_TIMEOUT   seconds allowed for `nixos-rebuild build-vm` (default: 1800)
#   AQOS_VM_BOOT_TIMEOUT    seconds allowed for the VM to reach the boot marker (default: 180)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

HOST="${AQOS_VM_HOST:-aqos-vm}"
FLAKE_TARGET=".#nixosConfigurations.${HOST}"
EVAL_TIMEOUT="${AQOS_VM_EVAL_TIMEOUT:-300}"
BUILD_TIMEOUT="${AQOS_VM_BUILD_TIMEOUT:-1800}"
BOOT_TIMEOUT="${AQOS_VM_BOOT_TIMEOUT:-180}"
BOOT_MARKER="AQOS-VM-DOGFOOD-BOOT-OK"
# Packages unique to the aqos-workstation golden package list
# (nix/data/profile-system-packages.nix) — chosen because they are not part
# of the ai-dev/gaming/minimal profile package lists, so their presence is a
# real signal that the GOLDEN profile (not some other profile) resolved.
GOLDEN_MARKERS=(hyperfine watchexec)

FULL=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "[FAIL] unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
info() { echo "[INFO] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }
skip() { echo "[SKIP] $*"; }

STEP_A_STATUS="not-run"
STEP_B_STATUS="not-run"

# ---------------------------------------------------------------------------
# Step A (cheap, always): .#aqos-vm must EVALUATE as a real nixosConfiguration,
# and the golden profile's packages must actually be present in the resolved
# environment.systemPackages — a host that only fails at full build is not
# an acceptable target for this harness.
# ---------------------------------------------------------------------------
step_a() {
  if ! command -v nix >/dev/null 2>&1; then
    skip "step A: 'nix' not found on PATH — cannot evaluate ${FLAKE_TARGET}"
    STEP_A_STATUS="skip"
    return 0
  fi

  info "step A: evaluating ${FLAKE_TARGET}.config.system.build.toplevel.drvPath (timeout ${EVAL_TIMEOUT}s)"
  local drv_path errfile
  errfile=$(mktemp)
  if ! drv_path=$(timeout "${EVAL_TIMEOUT}" nix eval --raw \
        "${FLAKE_TARGET}.config.system.build.toplevel.drvPath" 2>"${errfile}"); then
    STEP_A_STATUS="fail"
    local errtext; errtext=$(cat "${errfile}"); rm -f "${errfile}"
    fail "step A: ${FLAKE_TARGET} does NOT evaluate — a broken host is the #1 thing this gate exists to catch.
--- nix eval error ---
${errtext}
--- end error ---"
  fi
  rm -f "${errfile}"
  pass "step A: ${FLAKE_TARGET} evaluates -> ${drv_path}"

  info "step A: checking golden-profile packages are in the resolved config (markers: ${GOLDEN_MARKERS[*]})"
  local pkg_names
  errfile=$(mktemp)
  if ! pkg_names=$(timeout "${EVAL_TIMEOUT}" nix eval --json \
        "${FLAKE_TARGET}.config.environment.systemPackages" \
        --apply 'pkgs: map (p: p.pname or p.name or "unknown") pkgs' 2>"${errfile}"); then
    STEP_A_STATUS="fail"
    local errtext2; errtext2=$(cat "${errfile}"); rm -f "${errfile}"
    fail "step A: could not evaluate environment.systemPackages for ${FLAKE_TARGET}.
--- nix eval error ---
${errtext2}
--- end error ---"
  fi
  rm -f "${errfile}"

  local missing=()
  for marker in "${GOLDEN_MARKERS[@]}"; do
    if ! grep -q "\"${marker}" <<<"${pkg_names}"; then
      missing+=("${marker}")
    fi
  done
  if [ "${#missing[@]}" -ne 0 ]; then
    STEP_A_STATUS="fail"
    fail "step A: golden-profile markers missing from resolved systemPackages: ${missing[*]} — the aqos-workstation profile did not resolve as expected."
  fi
  pass "step A: golden-profile markers present (${GOLDEN_MARKERS[*]})"
  STEP_A_STATUS="pass"
}

# ---------------------------------------------------------------------------
# Step B (heavy, --full only): build a disposable VM and boot it headless.
# Never requires sudo. Skips cleanly (not a failure) if build-vm or qemu are
# unavailable.
# ---------------------------------------------------------------------------
step_b() {
  if [ "${FULL}" -ne 1 ]; then
    skip "step B: not requested (pass --full to build+boot the disposable VM)"
    STEP_B_STATUS="skip"
    return 0
  fi
  if ! command -v nixos-rebuild >/dev/null 2>&1; then
    skip "step B: 'nixos-rebuild' not found on PATH — cannot build-vm"
    STEP_B_STATUS="skip"
    return 0
  fi
  if ! command -v qemu-system-x86_64 >/dev/null 2>&1 && ! command -v qemu-kvm >/dev/null 2>&1; then
    skip "step B: no qemu binary found on PATH — cannot boot the VM"
    STEP_B_STATUS="skip"
    return 0
  fi

  local work_dir
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aqos-vm-dogfood.XXXXXX")"
  trap 'rm -rf "${work_dir}"' RETURN

  info "step B: nixos-rebuild build-vm --flake .#${HOST} (timeout ${BUILD_TIMEOUT}s, no sudo)"
  local result_link="${work_dir}/result"
  if ! timeout "${BUILD_TIMEOUT}" nixos-rebuild build-vm \
        --flake ".#${HOST}" -o "${result_link}" \
        >"${work_dir}/build.log" 2>&1; then
    STEP_B_STATUS="fail"
    tail -n 60 "${work_dir}/build.log" >&2 || true
    fail "step B: build-vm failed or timed out — see build log above (${work_dir}/build.log)."
  fi
  pass "step B: build-vm succeeded -> ${result_link}"

  local runvm
  runvm=$(find "${result_link}/bin" -maxdepth 1 -name 'run-*-vm' | head -n1)
  if [ -z "${runvm}" ]; then
    STEP_B_STATUS="fail"
    fail "step B: build-vm produced no ./result/bin/run-*-vm script."
  fi

  info "step B: booting ${runvm} headless (-nographic), boot timeout ${BOOT_TIMEOUT}s"
  local vm_log="${work_dir}/vm.log"
  : >"${vm_log}"
  QEMU_OPTS="-nographic -no-reboot" QEMU_KERNEL_PARAMS="console=ttyS0" \
    "${runvm}" >"${vm_log}" 2>&1 &
  local vm_pid=$!

  local deadline=$((SECONDS + BOOT_TIMEOUT))
  local found=0
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if grep -q "${BOOT_MARKER}" "${vm_log}" 2>/dev/null; then
      found=1
      break
    fi
    if ! kill -0 "${vm_pid}" 2>/dev/null; then
      break
    fi
    sleep 2
  done

  kill "${vm_pid}" 2>/dev/null || true
  wait "${vm_pid}" 2>/dev/null || true

  if [ "${found}" -ne 1 ]; then
    STEP_B_STATUS="fail"
    tail -n 60 "${vm_log}" >&2 || true
    fail "step B: boot marker '${BOOT_MARKER}' not observed within ${BOOT_TIMEOUT}s — see VM console log above."
  fi

  local marker_line
  marker_line=$(grep "${BOOT_MARKER}" "${vm_log}" | tail -n1)
  if ! grep -q "golden_marker=hyperfine-ok" <<<"${marker_line}"; then
    STEP_B_STATUS="fail"
    fail "step B: VM booted but the golden marker package was not on PATH: ${marker_line}"
  fi

  pass "step B: VM booted and golden marker confirmed: ${marker_line}"
  STEP_B_STATUS="pass"
}

step_a
step_b

echo "ACTIVATION-AUDIT: aqos-vm-dogfood host=${HOST} step_a=${STEP_A_STATUS} step_b=${STEP_B_STATUS} sudo=never disposable=true"
