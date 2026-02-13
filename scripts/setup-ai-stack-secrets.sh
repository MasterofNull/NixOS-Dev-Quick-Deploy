#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/nixos-ai-stack"
ENV_FILE="${CONFIG_DIR}/.env"

mkdir -p "$CONFIG_DIR"

prompt_value() {
  local label="$1"
  local default="${2:-}"
  local value=""

  if [[ -n "$default" ]]; then
    read -r -p "${label} [${default}]: " value
    if [[ -z "$value" ]]; then
      value="$default"
    fi
  else
    read -r -p "${label}: " value
  fi

  printf '%s' "$value"
}

prompt_secret() {
  local label="$1"
  local value=""
  while [[ -z "$value" ]]; do
    read -r -s -p "${label}: " value
    echo ""
  done
  printf '%s' "$value"
}

if [[ -f "$ENV_FILE" ]]; then
  read -r -p "Config exists at ${ENV_FILE}. Overwrite? [y/N]: " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Keeping existing ${ENV_FILE}"
    exit 0
  fi
fi

postgres_password=$(prompt_secret "POSTGRES_PASSWORD")
grafana_user=$(prompt_value "GRAFANA_ADMIN_USER" "admin")
grafana_password=$(prompt_secret "GRAFANA_ADMIN_PASSWORD")

cat > "$ENV_FILE" <<EOF
POSTGRES_PASSWORD=${postgres_password}
GRAFANA_ADMIN_USER=${grafana_user}
GRAFANA_ADMIN_PASSWORD=${grafana_password}
EOF

chmod 600 "$ENV_FILE"

echo "Wrote secrets to ${ENV_FILE}"
echo "Next:"
echo "  export AI_STACK_ENV_FILE=\"${ENV_FILE}\""
echo "  set -a && source \"${ENV_FILE}\" && set +a"
echo "  kubectl apply -k ai-stack/kubernetes"
