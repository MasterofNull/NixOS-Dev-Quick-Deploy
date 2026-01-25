#!/usr/bin/env bash
set -euo pipefail

images=(
  aidb
  embeddings
  hybrid-coordinator
  ralph-wiggum
  container-engine
  dashboard-api
  aider-wrapper
  nixos-docs
)

# Optional: limit to a subset, e.g. ONLY_IMAGES="ralph-wiggum,aidb"
if [[ -n "${ONLY_IMAGES:-}" ]]; then
  IFS=',' read -r -a images <<<"${ONLY_IMAGES}"
fi

declare -A compose_map=(
  [aidb]="localhost/compose_aidb:latest"
  [embeddings]="localhost/compose_embeddings:latest"
  [hybrid-coordinator]="localhost/compose_hybrid-coordinator:latest"
  [ralph-wiggum]="localhost/compose_ralph-wiggum:latest"
  [container-engine]="localhost/compose_container-engine:latest"
  [dashboard-api]="localhost/compose_dashboard-api:latest"
  [aider-wrapper]="localhost/compose_aider-wrapper:latest"
  [nixos-docs]="localhost/compose_nixos-docs:latest"
)

echo "==> Verifying local Podman images"
missing=0
for img in "${images[@]}"; do
  if podman image exists "$img"; then
    echo "[OK] $img"
    continue
  fi
  if podman image exists "${compose_map[$img]}"; then
    echo "[OK] ${compose_map[$img]} (compose)"
    continue
  fi
  echo "[ERROR] Missing local image: $img (and ${compose_map[$img]})" >&2
  missing=1
done

if [[ $missing -ne 0 ]]; then
  echo "One or more images are missing. Build or pull them before import." >&2
  exit 1
fi

K3S_NAMESPACE="${K3S_NAMESPACE:-k8s.io}"

echo "==> Checking sudo access for k3s/containerd"
if ! sudo -v; then
  echo "[ERROR] sudo is required to access /run/k3s/containerd/containerd.sock" >&2
  exit 1
fi

echo "==> Importing images into k3s containerd"
for img in "${images[@]}"; do
  img_ref="${compose_map[$img]}"
  if [[ -z "$img_ref" ]] || ! podman image exists "$img_ref"; then
    img_ref="$img"
  fi
  tar_path="/var/tmp/$(echo "$img_ref" | tr '/:' '__').tar"
  echo "[IMPORT] $img_ref -> $tar_path"
  if sudo k3s ctr -n "$K3S_NAMESPACE" images list | awk '{print $1}' | rg -q "^${img_ref}(:|@|$)"; then
    if [[ "${FORCE_IMPORT:-0}" == "1" ]]; then
      echo "[CLEAN] Removing existing $img_ref from k3s"
      sudo k3s ctr -n "$K3S_NAMESPACE" images rm "$img_ref" || true
    else
      echo "[SKIP] $img_ref already in k3s (set FORCE_IMPORT=1 to replace)"
      continue
    fi
  fi
  podman save -o "$tar_path" "$img_ref"
  chmod 0644 "$tar_path"
  sudo k3s ctr -n "$K3S_NAMESPACE" images import "$tar_path"
  rm -f "$tar_path"
  echo "[DONE] $img_ref"
done

echo "==> Verifying in k3s"
for img in "${images[@]}"; do
  img_ref="${compose_map[$img]}"
  if [[ -z "$img_ref" ]] || ! podman image exists "$img_ref"; then
    img_ref="$img"
  fi
  if sudo k3s ctr -n "$K3S_NAMESPACE" images list | awk '{print $1}' | rg -q "^${img_ref}(:|@|$)"; then
    echo "[OK] k3s has $img_ref"
  else
    echo "[WARN] k3s missing $img_ref"
  fi
done
