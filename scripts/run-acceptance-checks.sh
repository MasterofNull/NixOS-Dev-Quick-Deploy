#!/usr/bin/env bash
# Acceptance Criteria Runner
# Bundles health, TLS logs, netpol, registry, dashboard checks.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${HOME}/.nix-profile/bin:${HOME}/.local/state/nix/profiles/home-manager/bin:${PATH}"

RUN_NETPOL_TEST="${RUN_NETPOL_TEST:-false}"
RUN_REGISTRY_TEST="${RUN_REGISTRY_TEST:-false}"
RUN_DASHBOARD_TEST="${RUN_DASHBOARD_TEST:-false}"
RUN_RESTART_BUDGET_TEST="${RUN_RESTART_BUDGET_TEST:-false}"
RUN_FEEDBACK_TEST="${RUN_FEEDBACK_TEST:-false}"
RUN_VECTOR_DIM_TEST="${RUN_VECTOR_DIM_TEST:-false}"
RUN_LEARNING_EXPORT_TEST="${RUN_LEARNING_EXPORT_TEST:-false}"
RUN_AB_COMPARE_TEST="${RUN_AB_COMPARE_TEST:-false}"

AI_STACK_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"
REGISTRY_URL="${REGISTRY_URL:-http://${SERVICE_HOST:-localhost}:5000}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8888}"
DASHBOARD_API_PORT="${DASHBOARD_API_PORT:-8889}"
RESTART_THRESHOLD="${RESTART_THRESHOLD:-5}"
export RESTART_THRESHOLD

if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
  export KUBECONFIG="/etc/rancher/k3s/k3s.yaml"
fi

failures=0

info() { echo "ℹ $*"; }
pass() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; failures=$((failures + 1)); }

run_step() {
  local label="$1"
  shift
  info "Running: $label"
  if "$@"; then
    pass "$label"
  else
    fail "$label"
  fi
  echo ""
}

echo "=== Acceptance Criteria Checks ==="

if [[ -x "${SCRIPT_DIR}/scripts/lint-timeouts.sh" ]]; then
  run_step "Timeout lint" "${SCRIPT_DIR}/scripts/lint-timeouts.sh"
else
  warn "Timeout lint script missing; skipping"
fi

if [[ -x "${SCRIPT_DIR}/scripts/ai-stack-health.sh" ]]; then
  run_step "AI stack health" "${SCRIPT_DIR}/scripts/ai-stack-health.sh"
else
  warn "AI stack health script missing; skipping"
fi

if [[ -x "${SCRIPT_DIR}/scripts/check-tls-log-warnings.sh" ]]; then
  run_step "TLS log scan" "${SCRIPT_DIR}/scripts/check-tls-log-warnings.sh"
else
  warn "TLS log scan script missing; skipping"
fi

if [[ "$RUN_NETPOL_TEST" == "true" ]]; then
  if command -v kubectl >/dev/null 2>&1; then
    info "Running: NetworkPolicy enforcement test"
    pod_name="netpol-test-${RANDOM}"
    cat <<EOF | kubectl --request-timeout=30s apply -f - >/dev/null 2>&1
apiVersion: v1
kind: Pod
metadata:
  name: ${pod_name}
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: netpol
      image: busybox:1.36
      command:
        - /bin/sh
        - -c
        - wget -qO- --timeout=5 --tries=1 http://postgres.${AI_STACK_NAMESPACE}:5432 >/dev/null 2>&1 && echo ALLOWED || echo BLOCKED; exit 0
EOF
    kubectl --request-timeout=30s wait --for=condition=Succeeded "pod/${pod_name}" -n default --timeout=60s >/dev/null 2>&1 || true
    netpol_output=$(kubectl --request-timeout=30s logs -n default "pod/${pod_name}" 2>/dev/null || true)
    kubectl --request-timeout=30s delete pod -n default "$pod_name" --ignore-not-found >/dev/null 2>&1 || true
    if echo "$netpol_output" | grep -q "BLOCKED"; then
      pass "NetworkPolicy enforcement"
    else
      fail "NetworkPolicy enforcement"
    fi
  else
    warn "kubectl not found; skipping NetworkPolicy test"
  fi
  echo ""
else
  warn "NetworkPolicy test disabled (set RUN_NETPOL_TEST=true to enable)"
fi

if [[ "$RUN_REGISTRY_TEST" == "true" ]]; then
  info "Running: Registry availability check"
  if curl -sf --max-time 5 --connect-timeout 3 "${REGISTRY_URL}/v2/_catalog" >/dev/null 2>&1; then
    pass "Local registry reachable (${REGISTRY_URL})"
  else
    fail "Local registry unreachable (${REGISTRY_URL})"
  fi
  echo ""
else
  warn "Registry test disabled (set RUN_REGISTRY_TEST=true to enable)"
fi

if [[ "$RUN_DASHBOARD_TEST" == "true" ]]; then
  info "Running: Dashboard checks"
  if curl -sf --max-time 5 --connect-timeout 3 "http://${SERVICE_HOST:-localhost}:${DASHBOARD_PORT}/dashboard.html" >/dev/null 2>&1; then
    pass "Dashboard UI reachable (localhost:${DASHBOARD_PORT})"
  else
    warn "Dashboard UI not reachable (localhost:${DASHBOARD_PORT})"
  fi

  if curl -sf --max-time 5 --connect-timeout 3 "http://${SERVICE_HOST:-localhost}:${DASHBOARD_API_PORT}/api/health" >/dev/null 2>&1; then
    pass "Dashboard API reachable (localhost:${DASHBOARD_API_PORT})"
  else
    warn "Dashboard API not reachable (localhost:${DASHBOARD_API_PORT})"
  fi
  echo ""
else
  warn "Dashboard test disabled (set RUN_DASHBOARD_TEST=true to enable)"
fi

if [[ "$RUN_RESTART_BUDGET_TEST" == "true" ]]; then
  python_bin=$(command -v python3 || command -v python || true)
  if command -v kubectl >/dev/null 2>&1 && [[ -n "$python_bin" ]]; then
    info "Running: Pod restart budget check"
    if kubectl --request-timeout=30s get pods -n "${AI_STACK_NAMESPACE}" -o json | "$python_bin" -c '
import json, os, sys
raw = sys.stdin.read()
if not raw.strip():
    print("No pod data received from API.", file=sys.stderr)
    sys.exit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    print("Invalid JSON payload: {}".format(exc), file=sys.stderr)
    sys.exit(1)
threshold = int(os.environ.get("RESTART_THRESHOLD", "5"))
core = {
    "postgres",
    "qdrant",
    "redis",
    "aidb",
    "hybrid-coordinator",
    "dashboard-api",
}
over = []
for item in data.get("items", []):
    status = item.get("status", {})
    phase = status.get("phase", "")
    if phase in ("Succeeded", "Completed"):
        continue
    labels = item.get("metadata", {}).get("labels", {})
    service = labels.get("io.kompose.service")
    if service not in core:
        continue
    restarts = 0
    for cs in status.get("containerStatuses", []) or []:
        restarts += int(cs.get("restartCount", 0))
    if restarts > threshold:
        over.append((item.get("metadata", {}).get("name", "?"), restarts))
if over:
    details = ", ".join("{}({})".format(name, count) for name, count in over)
    print("Restart budget exceeded: {}".format(details), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'
    then
      pass "Pod restart budget (<= ${RESTART_THRESHOLD})"
    else
      fail "Pod restart budget (<= ${RESTART_THRESHOLD})"
    fi
  else
    warn "kubectl/python not found; skipping restart budget test"
  fi
  echo ""
else
  warn "Restart budget test disabled (set RUN_RESTART_BUDGET_TEST=true to enable)"
fi

if [[ "$RUN_FEEDBACK_TEST" == "true" ]]; then
  if command -v kubectl >/dev/null 2>&1; then
    info "Running: Dashboard feedback endpoint"
    feedback_output=$(kubectl --request-timeout=30s exec -n "${AI_STACK_NAMESPACE}" deploy/dashboard-api -- python3 -c 'import json,urllib.request; payload={"query":"Acceptance feedback","correction":"Use localhost registry","rating":4}; req=urllib.request.Request("http://localhost:8889/api/feedback", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}); resp=urllib.request.urlopen(req,timeout=10); print(resp.status); print(resp.read().decode())' 2>/dev/null || true)
    if echo "$feedback_output" | grep -q '"feedback_id"'; then
      pass "Dashboard feedback endpoint"
    else
      fail "Dashboard feedback endpoint"
    fi
  else
    warn "kubectl not found; skipping feedback test"
  fi
  echo ""
else
  warn "Feedback test disabled (set RUN_FEEDBACK_TEST=true to enable)"
fi

if [[ "$RUN_VECTOR_DIM_TEST" == "true" ]]; then
  if command -v kubectl >/dev/null 2>&1; then
    info "Running: Qdrant vector size matches EMBEDDING_DIMENSIONS"
    embedding_dim=$(kubectl --request-timeout=30s get configmap env -n "${AI_STACK_NAMESPACE}" -o jsonpath='{.data.EMBEDDING_DIMENSIONS}' 2>/dev/null || echo "")
    embedding_dim=${embedding_dim:-384}
    vector_output=$(kubectl --request-timeout=30s exec -n "${AI_STACK_NAMESPACE}" deploy/dashboard-api -- python3 -c "import json,urllib.request; req=urllib.request.Request('http://qdrant.${AI_STACK_NAMESPACE}:6333/collections/learning-feedback'); resp=urllib.request.urlopen(req,timeout=10); data=json.loads(resp.read().decode()); print(data.get('result',{}).get('config',{}).get('params',{}).get('vectors',{}).get('size',''))" 2>/dev/null || true)
    if [[ "$vector_output" == "$embedding_dim" ]]; then
      pass "Qdrant vector size matches EMBEDDING_DIMENSIONS (${embedding_dim})"
    else
      fail "Qdrant vector size mismatch (expected ${embedding_dim}, got ${vector_output:-unknown})"
    fi
  else
    warn "kubectl not found; skipping vector size test"
  fi
  echo ""
else
  warn "Vector size test disabled (set RUN_VECTOR_DIM_TEST=true to enable)"
fi

if [[ "$RUN_LEARNING_EXPORT_TEST" == "true" ]]; then
  if command -v kubectl >/dev/null 2>&1; then
    info "Running: Learning export endpoint"
    export_output=$(kubectl --request-timeout=30s exec -n "${AI_STACK_NAMESPACE}" deploy/hybrid-coordinator -- python3 -c 'import json,urllib.request; key="";\ntry:\n    key=open(\"/run/secrets/hybrid-coordinator-api-key\").read().strip()\nexcept Exception:\n    pass\nheaders={\"Content-Type\":\"application/json\"}\nif key:\n    headers[\"X-API-Key\"]=key\nreq=urllib.request.Request(\"http://localhost:8092/learning/export\", data=b\"{}\", headers=headers)\nresp=urllib.request.urlopen(req,timeout=20)\nbody=resp.read().decode()\nprint(body)\n' 2>/dev/null || true)
    if echo "$export_output" | grep -q '"dataset_path"' && echo "$export_output" | grep -q '"status": "ok"'; then
      pass "Learning export endpoint"
    else
      fail "Learning export endpoint"
    fi
  else
    warn "kubectl not found; skipping learning export test"
  fi
  echo ""
else
  warn "Learning export test disabled (set RUN_LEARNING_EXPORT_TEST=true to enable)"
fi

if [[ "$RUN_AB_COMPARE_TEST" == "true" ]]; then
  if command -v kubectl >/dev/null 2>&1; then
    info "Running: Learning A/B comparison endpoint"
    ab_output=$(kubectl --request-timeout=30s exec -n "${AI_STACK_NAMESPACE}" deploy/hybrid-coordinator -- python3 -c 'import json,urllib.request; key=\"\";\ntry:\n    key=open(\"/run/secrets/hybrid-coordinator-api-key\").read().strip()\nexcept Exception:\n    pass\nheaders={\"Content-Type\":\"application/json\"}\nif key:\n    headers[\"X-API-Key\"]=key\npayloads=[{\"query\":\"acceptance-ab-a\",\"correction\":\"ok\",\"rating\":5,\"tags\":[\"variant:a\"]},{\"query\":\"acceptance-ab-b\",\"correction\":\"ok\",\"rating\":3,\"tags\":[\"variant:b\"]}]\nfor payload in payloads:\n    req=urllib.request.Request(\"http://localhost:8092/feedback\", data=json.dumps(payload).encode(), headers=headers)\n    urllib.request.urlopen(req,timeout=10).read()\ncompare={\"variant_a\":\"a\",\"variant_b\":\"b\"}\nreq=urllib.request.Request(\"http://localhost:8092/learning/ab_compare\", data=json.dumps(compare).encode(), headers=headers)\nresp=urllib.request.urlopen(req,timeout=10)\nbody=resp.read().decode()\nprint(body)\n' 2>/dev/null || true)
    if echo "$ab_output" | grep -q '"variant_a"' && echo "$ab_output" | grep -q '"variant_b"'; then
      pass "Learning A/B comparison endpoint"
    else
      fail "Learning A/B comparison endpoint"
    fi
  else
    warn "kubectl not found; skipping A/B comparison test"
  fi
  echo ""
else
  warn "A/B comparison test disabled (set RUN_AB_COMPARE_TEST=true to enable)"
fi

if [[ $failures -eq 0 ]]; then
  pass "Acceptance checks complete"
  exit 0
fi

fail "Acceptance checks completed with ${failures} failure(s)"
exit 1
