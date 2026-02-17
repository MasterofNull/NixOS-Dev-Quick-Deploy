#!/usr/bin/env bash
#
# Collect quick AI stack troubleshooting diagnostics into a single report.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="${PROJECT_ROOT}/artifacts/troubleshooting"
NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"
TS="$(date +%Y%m%d-%H%M%S)"
REPORT="${OUT_DIR}/ai-stack-troubleshoot-${TS}.txt"

mkdir -p "$OUT_DIR"

append() {
  printf '\n## %s\n' "$1" >>"$REPORT"
}

run_cmd() {
  local label="$1"
  shift
  printf '\n$ %s\n' "$*" >>"$REPORT"
  if "$@" >>"$REPORT" 2>&1; then
    :
  else
    printf '[command failed]\n' >>"$REPORT"
  fi
}

{
  echo "# AI Stack Troubleshooting Report"
  echo "Generated: $(date -Is)"
  echo "Namespace: ${NAMESPACE}"
  echo "Host: $(hostname 2>/dev/null || echo unknown)"
} >"$REPORT"

append "System Summary"
run_cmd "uname" uname -a
run_cmd "uptime" uptime
run_cmd "disk" df -h

if command -v kubectl >/dev/null 2>&1; then
  append "Kubernetes Status"
  run_cmd "nodes" kubectl get nodes -o wide
  run_cmd "pods" kubectl get pods -n "$NAMESPACE" -o wide
  run_cmd "deploy" kubectl get deploy -n "$NAMESPACE"
  run_cmd "svc" kubectl get svc -n "$NAMESPACE"
  run_cmd "events" kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp
else
  append "Kubernetes Status"
  echo "kubectl not found in PATH" >>"$REPORT"
fi

append "Local Health Endpoints"
if command -v curl >/dev/null 2>&1; then
  run_cmd "aidb" curl -fsS http://localhost:8091/health
  run_cmd "hybrid" curl -fsS http://localhost:8092/health
  run_cmd "embeddings" curl -fsS http://localhost:8081/health
else
  echo "curl not found in PATH" >>"$REPORT"
fi

append "Container Runtime"
if command -v podman >/dev/null 2>&1; then
  run_cmd "podman ps" podman ps --format "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}"
fi
if command -v nerdctl >/dev/null 2>&1; then
  run_cmd "nerdctl ps" nerdctl ps
fi
if ! command -v podman >/dev/null 2>&1 && ! command -v nerdctl >/dev/null 2>&1; then
  echo "No supported runtime CLI detected (podman/nerdctl)." >>"$REPORT"
fi

append "Network Ports"
if command -v ss >/dev/null 2>&1; then
  run_cmd "listening" ss -tuln
else
  echo "ss not found in PATH" >>"$REPORT"
fi

echo "Troubleshooting report written to: $REPORT"
