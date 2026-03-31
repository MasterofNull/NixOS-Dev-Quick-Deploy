#!/usr/bin/env bash
# Verify check-mcp-health.sh uses safe default URLs and ports when env vars are absent.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
BASH_BIN="$(command -v bash)"
BASE_PATH="${PATH}"
trap 'rm -rf "${TMP_DIR}"' EXIT

mkdir -p "${TMP_DIR}/bin"

cat > "${TMP_DIR}/bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf "200"
EOF
chmod +x "${TMP_DIR}/bin/curl"

cat > "${TMP_DIR}/bin/timeout" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
shift
"$@"
EOF
chmod +x "${TMP_DIR}/bin/timeout"

OUTPUT="$(
  env -i \
    HOME="${HOME}" \
    PATH="${TMP_DIR}/bin:${BASE_PATH}" \
    "${BASH_BIN}" "${ROOT_DIR}/scripts/testing/check-mcp-health.sh" --optional
)"

printf "%s\n" "${OUTPUT}" | grep -q "ralph-wiggum"
printf "%s\n" "${OUTPUT}" | grep -q "aider-wrapper"
printf "%s\n" "${OUTPUT}" | grep -q "nixos-docs"
printf "%s\n" "${OUTPUT}" | grep -q "open-webui"
printf "%s\n" "${OUTPUT}" | grep -q "grafana"
printf "%s\n" "${OUTPUT}" | grep -q "All required MCP services are healthy."

echo "PASS: check-mcp-health uses safe URL defaults without unbound variables"
