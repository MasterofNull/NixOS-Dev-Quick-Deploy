#!/usr/bin/env bash
set -euo pipefail

MANIFEST_ROOT="ai-stack/kubernetes"
CONFIGMAP_FILE="ai-stack/kubernetes/kompose/env-configmap.yaml"
SECRETS_FILE="ai-stack/kubernetes/secrets/secrets.sops.yaml"
TLS_DIR="ai-stack/kubernetes/tls"

fail_count=0

note() { printf "INFO: %s\n" "$1"; }
warn() { printf "WARN: %s\n" "$1"; }
fail() { printf "FAIL: %s\n" "$1"; fail_count=$((fail_count + 1)); }

if [[ ! -d "$MANIFEST_ROOT" ]]; then
  fail "Missing Kubernetes manifests directory: $MANIFEST_ROOT"
  exit 1
fi

note "Running security audit checks against Kubernetes manifests"

# Default credentials
if [[ -f "$CONFIGMAP_FILE" ]]; then
  if rg -n "change_me_in_production|GRAFANA_ADMIN_PASSWORD:[[:space:]]*admin|GRAFANA_ADMIN_USER:[[:space:]]*admin" "$CONFIGMAP_FILE" >/dev/null; then
    fail "Default credentials present in configmap defaults"
  else
    note "No default credential placeholders detected"
  fi
else
  warn "Missing configmap file: $CONFIGMAP_FILE"
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
done < <(rg -n --glob "*.y*ml" "image:" "$MANIFEST_ROOT" | awk -F'image:' '{gsub(/[[:space:]]/, "", $2); sub(/#.*/, "", $2); print $2}')
if [[ -n "$rolling_images" ]]; then
  fail "Rolling image tags detected:\n$rolling_images"
else
  note "No rolling image tags detected"
fi

# Privileged containers
if rg -n --glob "*.y*ml" "privileged:[[:space:]]*true" "$MANIFEST_ROOT" >/dev/null; then
  warn "Privileged container detected"
else
  note "No privileged containers detected"
fi

# Host access exposure
if rg -n --glob "*.y*ml" "hostPort:|hostNetwork:[[:space:]]*true" "$MANIFEST_ROOT" >/dev/null; then
  warn "Host network/hostPort usage detected; verify isolation requirements"
else
  note "No hostPort/hostNetwork settings detected"
fi

# Secrets presence
if [[ -f "$SECRETS_FILE" ]]; then
  if rg -q "stack_api_key" "$SECRETS_FILE"; then
    note "API key secret present in sops secrets"
  else
    fail "API key secret missing in sops secrets: stack_api_key"
  fi
else
  fail "Missing secrets file: $SECRETS_FILE"
fi

# TLS manifests
if [[ -d "$TLS_DIR" ]] && rg -n --glob "*.y*ml" "Certificate|Issuer|ClusterIssuer" "$TLS_DIR" >/dev/null; then
  note "TLS manifests present in $TLS_DIR"
else
  warn "TLS manifests missing in $TLS_DIR"
fi

if [[ "$fail_count" -gt 0 ]]; then
  printf "\nSecurity audit completed with %d failure(s)\n" "$fail_count"
  exit 1
fi

printf "\nSecurity audit completed with no blocking failures\n"
