#!/usr/bin/env bash
set -euo pipefail

host_name="${HOSTNAME_OVERRIDE:-$(hostname -s 2>/dev/null || hostname)}"
root_src="${ROOT_SOURCE_OVERRIDE:-$(findmnt -no SOURCE / 2>/dev/null || true)}"
root_real="${ROOT_REAL_OVERRIDE:-$(readlink -f "${root_src}" 2>/dev/null || true)}"
root_uuid="${ROOT_UUID_OVERRIDE:-}"
if [[ -z "${root_real}" ]]; then
  root_real="${root_src}"
fi
if [[ -z "${root_uuid}" && -n "${root_real}" && -b "${root_real}" ]]; then
  root_uuid="$(blkid -s UUID -o value "${root_real}" 2>/dev/null || true)"
  if [[ -z "${root_uuid}" ]]; then
    root_uuid="$(lsblk -no UUID "${root_real}" 2>/dev/null | head -n1 || true)"
  fi
fi

echo "=== Offline Root Filesystem Repair Guide ==="
echo
echo "Current host: ${host_name}"
echo "Current root source: ${root_src:-<unknown>}"
if [[ -n "${root_uuid}" ]]; then
  echo "Current root UUID: ${root_uuid}"
fi
echo
echo "1) Boot a NixOS installer/rescue ISO."
echo "2) Open a shell and become root: sudo -i"
echo "3) Identify the root partition:"
echo "   lsblk -f"
echo
if [[ -n "${root_uuid}" ]]; then
  echo "4) Run offline fsck (recommended command):"
  echo "   e2fsck -f -y /dev/disk/by-uuid/${root_uuid}"
else
  echo "4) Run offline fsck on the root partition (example):"
  echo "   e2fsck -f -y /dev/nvme0n1p2"
fi
echo
echo "5) (Recommended) Check disk hardware status:"
echo "   smartctl -a /dev/nvme0"
echo "   nvme smart-log /dev/nvme0"
echo
echo "6) Reboot into NixOS, then deploy from TTY (not GUI):"
echo "   ./scripts/deploy-clean.sh --host ${host_name} --profile ai-dev"
