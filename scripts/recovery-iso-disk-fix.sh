#!/usr/bin/env bash
set -euo pipefail

# Automated offline disk repair helper for running from a recovery/live ISO.
# Default device values match the current host, but all can be overridden.

ROOT_DEV_DEFAULT="/dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58"
EFI_DEV_DEFAULT="/dev/disk/by-uuid/8D2E-EF0C"
NVME_DEV_DEFAULT="/dev/nvme0"

ROOT_DEV="${ROOT_DEV:-$ROOT_DEV_DEFAULT}"
EFI_DEV="${EFI_DEV:-$EFI_DEV_DEFAULT}"
NVME_DEV="${NVME_DEV:-$NVME_DEV_DEFAULT}"

RUN_SMART_LONG=false
SKIP_SMART=false
AUTO_YES=false

usage() {
  cat <<'EOF'
Usage: ./scripts/recovery-iso-disk-fix.sh [options]

Run this from a recovery/live ISO terminal as root.

Options:
  --root-dev PATH         Root ext4 device (default: /dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58)
  --efi-dev PATH          EFI/FAT device (default: /dev/disk/by-uuid/8D2E-EF0C)
  --nvme-dev PATH         NVMe device for SMART checks (default: /dev/nvme0)
  --run-smart-long        Start SMART long test
  --skip-smart            Skip SMART checks
  --yes                   Non-interactive confirmation
  -h, --help              Show this help

Environment overrides:
  ROOT_DEV=/dev/nvme0n1p2
  EFI_DEV=/dev/nvme0n1p1
  NVME_DEV=/dev/nvme0
EOF
}

log() {
  printf '[recovery-fsck] %s\n' "$*"
}

warn() {
  printf '[recovery-fsck] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[recovery-fsck] ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root (example: sudo -i)."
  fi
}

check_block_device() {
  local dev="$1"
  [[ -b "$dev" ]] || die "Device does not exist or is not a block device: $dev"
}

confirm_or_exit() {
  [[ "$AUTO_YES" == true ]] && return 0
  echo
  echo "This will run filesystem repair against:"
  echo "  ROOT_DEV=$ROOT_DEV"
  echo "  EFI_DEV=$EFI_DEV"
  echo "  NVME_DEV=$NVME_DEV"
  echo
  read -r -p "Type YES to continue: " answer
  [[ "$answer" == "YES" ]] || die "Aborted by user."
}

unmount_all_for_device() {
  local dev="$1"
  local -a mounts=()
  local mp

  while IFS= read -r mp; do
    [[ -n "$mp" ]] && mounts+=("$mp")
  done < <(findmnt -rn -S "$dev" -o TARGET 2>/dev/null || true)

  local i
  for (( i=${#mounts[@]}-1; i>=0; i-- )); do
    log "Unmounting ${mounts[$i]} (source: $dev)"
    umount "${mounts[$i]}"
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-dev)
      ROOT_DEV="${2:?missing value for --root-dev}"
      shift 2
      ;;
    --efi-dev)
      EFI_DEV="${2:?missing value for --efi-dev}"
      shift 2
      ;;
    --nvme-dev)
      NVME_DEV="${2:?missing value for --nvme-dev}"
      shift 2
      ;;
    --run-smart-long)
      RUN_SMART_LONG=true
      shift
      ;;
    --skip-smart)
      SKIP_SMART=true
      shift
      ;;
    --yes)
      AUTO_YES=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

require_root
need_cmd findmnt
need_cmd e2fsck
check_block_device "$ROOT_DEV"
check_block_device "$EFI_DEV"
check_block_device "$NVME_DEV"

confirm_or_exit

log "Listing block devices"
lsblk -f

log "Disabling all swap"
swapoff -a || true

unmount_all_for_device "$ROOT_DEV"
unmount_all_for_device "$EFI_DEV"

log "Running offline ext4 repair on root: $ROOT_DEV"
e2fsck -f -y -C 0 "$ROOT_DEV"

log "Running verification pass on root: $ROOT_DEV"
e2fsck -f "$ROOT_DEV"

if command -v fsck.vfat >/dev/null 2>&1; then
  log "Running FAT fsck on EFI: $EFI_DEV"
  fsck.vfat -a "$EFI_DEV" || true
elif command -v dosfsck >/dev/null 2>&1; then
  log "Running dosfsck on EFI: $EFI_DEV"
  dosfsck -a "$EFI_DEV" || true
else
  warn "No FAT fsck tool found (fsck.vfat/dosfsck). Skipping EFI check."
fi

if [[ "$SKIP_SMART" == false ]]; then
  if command -v smartctl >/dev/null 2>&1; then
    log "Running SMART health summary: $NVME_DEV"
    smartctl -H "$NVME_DEV" || true
    smartctl -A "$NVME_DEV" || true
    if [[ "$RUN_SMART_LONG" == true ]]; then
      log "Starting SMART long test: $NVME_DEV"
      smartctl -t long "$NVME_DEV" || true
      log "After test completion, check results with: smartctl -a $NVME_DEV"
    else
      log "Optional: start long test with --run-smart-long"
    fi
  else
    warn "smartctl not installed in this recovery environment. Skipping SMART checks."
  fi
fi

log "Disk recovery routine complete."
log "Next steps:"
log "1) Reboot into installed system."
log "2) Run deploy from TTY:"
log "   NIX_EVAL_TIMEOUT_SECONDS=300 ./scripts/deploy-clean.sh --host nixos --profile ai-dev --skip-health-check"
