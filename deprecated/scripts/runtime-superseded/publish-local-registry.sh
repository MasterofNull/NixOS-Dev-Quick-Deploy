#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-dev}"

REGISTRY="${REGISTRY:-localhost:5000}"
TLS_VERIFY="${REGISTRY_TLS_VERIFY:-false}"
CONTAINER_CLI="${CONTAINER_CLI:-}"

# Ensure UID is exported for rootless container storage resolution.
if [[ -z "${UID:-}" ]]; then
  export UID="$(id -u)"
else
  export UID
fi
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${UID}}"

images=(
  ai-stack-aidb
  ai-stack-embeddings
  ai-stack-hybrid-coordinator
  ai-stack-ralph-wiggum
  ai-stack-container-engine
  ai-stack-dashboard-api
  ai-stack-aider-wrapper
  ai-stack-nixos-docs
  ai-stack-health-monitor
)

ONLY_IMAGES="${ONLY_IMAGES:-}"
if [[ -n "$ONLY_IMAGES" ]]; then
  IFS=',' read -r -a only_list <<< "$ONLY_IMAGES"
  images=()
  for item in "${only_list[@]}"; do
    item="${item// /}"
    [[ -n "$item" ]] && images+=("$item")
  done
fi

resolve_cli() {
  if [[ -n "$CONTAINER_CLI" ]]; then
    echo "$CONTAINER_CLI"
    return 0
  fi
  if command -v skopeo >/dev/null 2>&1; then
    echo "skopeo"
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
  echo "[ERROR] No container CLI found. Install skopeo (preferred) or set CONTAINER_CLI." >&2
  exit 1
fi

SKOPEO_CMD=()
if [[ "$cli" == "skopeo" && -z "${CONTAINERS_REGISTRIES_CONF:-}" ]]; then
  registries_tmp="$(mktemp)"
  insecure_flag="false"
  if [[ "${TLS_VERIFY}" == "false" ]]; then
    insecure_flag="true"
  fi
  cat >"$registries_tmp" <<EOF
unqualified-search-registries = ["docker.io", "quay.io"]

[[registry]]
location = "${REGISTRY}"
insecure = ${insecure_flag}
EOF
  export CONTAINERS_REGISTRIES_CONF="$registries_tmp"
  export REGISTRIES_CONF="$registries_tmp"
fi
if [[ "$cli" == "skopeo" ]]; then
  SKOPEO_CMD=(skopeo)
  if [[ -n "${CONTAINERS_REGISTRIES_CONF:-}" ]]; then
    SKOPEO_CMD+=(--registries-conf "${CONTAINERS_REGISTRIES_CONF}")
  fi
fi

image_exists() {
  local ref="$1"
  if [[ "$cli" == "skopeo" ]]; then
    "${SKOPEO_CMD[@]}" inspect "containers-storage:${ref}" >/dev/null 2>&1
  else
    "$cli" image inspect "$ref" >/dev/null 2>&1
  fi
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
  if [[ "$cli" == "skopeo" ]]; then
    echo "[PUSH] $dest (tls=${TLS_VERIFY}, via skopeo)"
    "${SKOPEO_CMD[@]}" copy --dest-tls-verify="$TLS_VERIFY" "containers-storage:${src}" "docker://${dest}"
  else
    "$cli" tag "$src" "$dest"
    echo "[PUSH] $dest (tls=${TLS_VERIFY})"
    "$cli" push "$dest"
  fi
  echo "[OK] $dest"
  echo
  
  # Optional "dev" tag for quick iteration
  if [[ "${ALSO_TAG_DEV:-0}" == "1" ]]; then
    dev_tag="${REGISTRY}/${img}:dev"
    if [[ "$cli" == "skopeo" ]]; then
      "${SKOPEO_CMD[@]}" copy --dest-tls-verify="$TLS_VERIFY" "containers-storage:${src}" "docker://${dev_tag}"
    else
      "$cli" tag "$src" "$dev_tag"
      "$cli" push "$dev_tag"
    fi
    echo "[OK] $dev_tag"
  fi

done

echo "[DONE] Published images to ${REGISTRY} with tag ${TAG}"
