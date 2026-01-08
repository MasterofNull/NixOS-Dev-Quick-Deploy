#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="ai-stack/compose/docker-compose.yml"
SECRETS_DIR="ai-stack/compose/secrets"
CERT_DIR="ai-stack/compose/nginx/certs"

fail_count=0

note() { printf "INFO: %s\n" "$1"; }
warn() { printf "WARN: %s\n" "$1"; }
fail() { printf "FAIL: %s\n" "$1"; fail_count=$((fail_count + 1)); }

if [[ ! -f "$COMPOSE_FILE" ]]; then
  fail "Missing compose file: $COMPOSE_FILE"
  exit 1
fi

note "Running security audit checks against $COMPOSE_FILE"

# Default credentials
if rg -n "change_me_in_production|GRAFANA_ADMIN_PASSWORD:-admin|GRAFANA_ADMIN_USER:-admin" "$COMPOSE_FILE" >/dev/null; then
  fail "Default credentials present in compose env defaults"
else
  note "No default credential placeholders detected"
fi

# Latest/rolling tags
rolling_images=""
while IFS= read -r img; do
  if [[ "$img" == *@sha256:* ]]; then
    continue
  fi
  if [[ "$img" != *:* ]] || [[ "$img" == *:latest ]] || [[ "$img" == *:main ]]; then
    rolling_images+="${img}"$'\n'
  fi
done < <(rg -n "image:" "$COMPOSE_FILE" | awk -F'image:' '{gsub(/[[:space:]]/, "", $2); sub(/#.*/, "", $2); print $2}')
if [[ -n "$rolling_images" ]]; then
  fail "Rolling image tags detected:\n$rolling_images"
else
  note "No rolling image tags detected"
fi

# Privileged containers
if rg -n "privileged: true" "$COMPOSE_FILE" >/dev/null; then
  warn "Privileged container detected (health-monitor)"
else
  note "No privileged containers detected"
fi

# Host port bindings
port_lines=$(rg -n "ports:" -n "$COMPOSE_FILE" -n | cut -d: -f1)
exposed_unsafe=()
while read -r line; do
  port_block=$(sed -n "$line,${line}p" "$COMPOSE_FILE")
  # no-op placeholder, actual parsing done below
done <<< "$port_lines"

unsafe_ports=$(
  { rg -n "^[[:space:]]+- \"[0-9]" "$COMPOSE_FILE" || true; } | \
    awk -F'"' '{print $2}' | \
    awk -F: 'NF>=2 && $1!="127.0.0.1" {print $0}'
)
unsafe_ports+=$'\n'$(
  { rg -n "0\\.0\\.0\\.0:" "$COMPOSE_FILE" || true; } | \
    awk -F'"' '{print $2}'
)
unsafe_ports=$(echo "$unsafe_ports" | sed '/^$/d')
if [[ -n "$unsafe_ports" ]]; then
  fail "Host ports not bound to 127.0.0.1 detected:\n$unsafe_ports"
else
  note "All exposed ports bound to 127.0.0.1"
fi

# Secrets file permissions
api_key="$SECRETS_DIR/stack_api_key"
if [[ -f "$api_key" ]]; then
  perms=$(stat -c %a "$api_key")
  if [[ "$perms" -gt 640 ]]; then
    fail "API key file permissions too permissive ($perms): $api_key"
  else
    note "API key file permissions ok ($perms)"
  fi
else
  fail "Missing API key file: $api_key"
fi

# TLS certs
if [[ -f "$CERT_DIR/localhost.crt" && -f "$CERT_DIR/localhost.key" ]]; then
  note "TLS certs present in $CERT_DIR"
else
  warn "TLS certs missing in $CERT_DIR (nginx TLS may not be available)"
fi

if [[ "$fail_count" -gt 0 ]]; then
  printf "\nSecurity audit completed with %d failure(s)\n" "$fail_count"
  exit 1
fi

printf "\nSecurity audit completed with no blocking failures\n"
