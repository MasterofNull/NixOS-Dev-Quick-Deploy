#!/usr/bin/env bash
set -euo pipefail

ROOT_DEV_DEFAULT="/dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58"
USER_NAME_DEFAULT="hyperd"
MNT_DIR_DEFAULT="/mnt/sysroot"

ROOT_DEV="${ROOT_DEV:-$ROOT_DEV_DEFAULT}"
USER_NAME="${USER_NAME:-$USER_NAME_DEFAULT}"
MNT_DIR="${MNT_DIR:-$MNT_DIR_DEFAULT}"
PASSWORD="${PASSWORD:-}"

AUTO_YES=false

usage() {
  cat <<'EOF'
Usage: ./scripts/recovery-iso-unlock-user.sh [options]

Run from NixOS recovery/live ISO as root.
Mounts the installed root filesystem, chroots, resets/unlocks a user account.

Options:
  --root-dev PATH        Root filesystem device (default: /dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58)
  --user NAME            User account to unlock/reset (default: hyperd)
  --mount-dir PATH       Temporary mount point (default: /mnt/sysroot)
  --password VALUE       Non-interactive password set (plain text; avoid in shell history)
  --yes                  Skip confirmation prompt
  -h, --help             Show help

Environment overrides:
  ROOT_DEV=/dev/nvme0n1p2
  USER_NAME=hyperd
  MNT_DIR=/mnt/sysroot
  PASSWORD='new-password'
EOF
}

log() {
  printf '[recovery-unlock] %s\n' "$*"
}

die() {
  printf '[recovery-unlock] ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

cleanup() {
  set +e
  for p in run sys proc dev; do
    umount "${MNT_DIR}/${p}" 2>/dev/null || true
  done
  umount "$MNT_DIR" 2>/dev/null || true
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root (example: sudo -i)."
  fi
}

confirm_or_exit() {
  [[ "$AUTO_YES" == true ]] && return 0
  echo
  echo "This will mount '$ROOT_DEV' at '$MNT_DIR' and unlock/reset user '$USER_NAME'."
  echo
  read -r -p "Type YES to continue: " answer
  [[ "$answer" == "YES" ]] || die "Aborted by user."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-dev)
      ROOT_DEV="${2:?missing value for --root-dev}"
      shift 2
      ;;
    --user)
      USER_NAME="${2:?missing value for --user}"
      shift 2
      ;;
    --mount-dir)
      MNT_DIR="${2:?missing value for --mount-dir}"
      shift 2
      ;;
    --password)
      PASSWORD="${2:?missing value for --password}"
      shift 2
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
need_cmd mount
need_cmd chroot
need_cmd usermod
need_cmd passwd
[[ -b "$ROOT_DEV" ]] || die "Root device not found: $ROOT_DEV"
[[ "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Invalid username: $USER_NAME"

confirm_or_exit
trap cleanup EXIT

mkdir -p "$MNT_DIR"
log "Mounting root filesystem: $ROOT_DEV -> $MNT_DIR"
mount "$ROOT_DEV" "$MNT_DIR"

for p in dev proc sys run; do
  mount --bind "/$p" "${MNT_DIR}/$p"
done

if ! chroot "$MNT_DIR" getent passwd "$USER_NAME" >/dev/null 2>&1; then
  die "User '$USER_NAME' not found in installed system."
fi

if [[ -n "$PASSWORD" ]]; then
  log "Setting password for '$USER_NAME' non-interactively"
  chroot "$MNT_DIR" /bin/sh -c "printf '%s:%s\n' '$USER_NAME' '$PASSWORD' | chpasswd"
else
  log "Setting password for '$USER_NAME' interactively"
  chroot "$MNT_DIR" passwd "$USER_NAME"
fi

log "Unlocking user account: $USER_NAME"
chroot "$MNT_DIR" usermod -U "$USER_NAME" || true
chroot "$MNT_DIR" chage -E -1 -M -1 -I -1 -m 0 "$USER_NAME" || true

log "Final account status:"
chroot "$MNT_DIR" passwd -S "$USER_NAME" || true

log "Done. Reboot into the installed system and test login."
