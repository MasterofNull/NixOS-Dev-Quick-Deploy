#!/usr/bin/env bash
# Regression guard for deploy/model-fetch handling of active.gguf symlinks.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

die() {
  printf '[test-model-symlink-verification] FAIL: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '[test-model-symlink-verification] %s\n' "$*"
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

printf '0123456789abcdef' > "${tmpdir}/Qwen-test.gguf"
ln -s "${tmpdir}/Qwen-test.gguf" "${tmpdir}/active.gguf"

link_size="$(stat -c%s "${tmpdir}/active.gguf")"
target_size="$(stat -Lc%s "${tmpdir}/active.gguf")"
[[ "${link_size}" != "${target_size}" ]] || die "test fixture did not create a distinguishable symlink"
[[ "${target_size}" -eq 16 ]] || die "stat -L did not report target size"

grep -F 'stat -Lc%s "$path"' nixos-quick-deploy.sh >/dev/null \
  || die "deploy model size helper must dereference symlinks"
grep -F 'du -hL "$path"' nixos-quick-deploy.sh >/dev/null \
  || die "deploy model disk-usage helper must dereference symlinks"
grep -F 'model="$model_dir/${hfFile}"' nix/modules/roles/ai-stack.nix >/dev/null \
  || die "chat model fetch must validate the concrete catalog file when active.gguf is configured"
grep -F 'model filename matches requested source; metadata recorded' nix/modules/roles/ai-stack.nix >/dev/null \
  || die "chat model fetch must stamp metadata for existing unpinned catalog files"

log "PASS: active.gguf symlink verification dereferences the concrete model target"
