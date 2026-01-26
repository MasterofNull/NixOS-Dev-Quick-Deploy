#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-}"
if [[ -z "$TAG" ]]; then
  TAG=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)
fi

REGISTRY="${REGISTRY:-localhost:5000}"
TLS_VERIFY="${REGISTRY_TLS_VERIFY:-false}"

images=(
  compose_aidb
  compose_embeddings
  compose_hybrid-coordinator
  compose_ralph-wiggum
  compose_container-engine
  compose_dashboard-api
  compose_aider-wrapper
  compose_nixos-docs
)

missing=0
for img in "${images[@]}"; do
  src="localhost/${img}:latest"
  if ! podman image exists "$src"; then
    echo "[ERROR] Missing local image: $src" >&2
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "[ERROR] One or more images are missing. Build them before publishing." >&2
  exit 1
fi

for img in "${images[@]}"; do
  src="localhost/${img}:latest"
  dest="${REGISTRY}/${img}:${TAG}"
  echo "[TAG] $src -> $dest"
  podman tag "$src" "$dest"
  echo "[PUSH] $dest (tls=${TLS_VERIFY})"
  podman push --tls-verify="${TLS_VERIFY}" "$dest"
  echo "[OK] $dest"
  echo
  
  # Optional "dev" tag for quick iteration
  if [[ "${ALSO_TAG_DEV:-0}" == "1" ]]; then
    dev_tag="${REGISTRY}/${img}:dev"
    podman tag "$src" "$dev_tag"
    podman push --tls-verify="${TLS_VERIFY}" "$dev_tag"
    echo "[OK] $dev_tag"
  fi

done

echo "[DONE] Published images to ${REGISTRY} with tag ${TAG}"
