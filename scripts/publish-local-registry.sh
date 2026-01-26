#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-}"
if [[ -z "$TAG" ]]; then
  TAG=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)
fi

REGISTRY="${REGISTRY:-localhost:5000}"
TLS_VERIFY="${REGISTRY_TLS_VERIFY:-false}"
CONTAINER_CLI="${CONTAINER_CLI:-}"

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

resolve_cli() {
  if [[ -n "$CONTAINER_CLI" ]]; then
    echo "$CONTAINER_CLI"
    return 0
  fi
  if command -v nerdctl >/dev/null 2>&1; then
    echo "nerdctl"
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "docker"
    return 0
  fi
  return 1
}

cli="$(resolve_cli || true)"
if [[ -z "$cli" ]]; then
  echo "[ERROR] No container CLI found. Install nerdctl or docker, or set CONTAINER_CLI." >&2
  exit 1
fi

image_exists() {
  local ref="$1"
  "$cli" image inspect "$ref" >/dev/null 2>&1
}

missing=0
for img in "${images[@]}"; do
  src="localhost/${img}:latest"
  if ! image_exists "$src"; then
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
  "$cli" tag "$src" "$dest"
  echo "[PUSH] $dest (tls=${TLS_VERIFY})"
  if [[ "$cli" == "nerdctl" ]]; then
    "$cli" push "$dest"
  else
    "$cli" push "$dest"
  fi
  echo "[OK] $dest"
  echo
  
  # Optional "dev" tag for quick iteration
  if [[ "${ALSO_TAG_DEV:-0}" == "1" ]]; then
    dev_tag="${REGISTRY}/${img}:dev"
    "$cli" tag "$src" "$dev_tag"
    "$cli" push "$dev_tag"
    echo "[OK] $dev_tag"
  fi

done

echo "[DONE] Published images to ${REGISTRY} with tag ${TAG}"
