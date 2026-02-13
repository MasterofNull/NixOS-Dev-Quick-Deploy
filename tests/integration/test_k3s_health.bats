#!/usr/bin/env bats

setup() {
  if [ "${RUN_K3S_INTEGRATION:-}" != "true" ]; then
    skip "Set RUN_K3S_INTEGRATION=true to enable K3s integration checks"
  fi

  if ! command -v kubectl >/dev/null 2>&1; then
    skip "kubectl not found"
  fi

  if ! kubectl get nodes >/dev/null 2>&1; then
    skip "kubectl cannot reach cluster"
  fi
}

create_test_pod() {
  local ns="$1"
  local name="$2"
  kubectl run "$name" -n "$ns" --image=curlimages/curl:8.6.0 --command -- sleep 600 >/dev/null
  kubectl wait --for=condition=Ready "pod/${name}" -n "$ns" --timeout=60s >/dev/null
}

cleanup_test_pod() {
  local ns="$1"
  local name="$2"
  kubectl delete pod "$name" -n "$ns" --ignore-not-found >/dev/null
}

@test "ai-stack namespace pods are healthy" {
  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  run kubectl get pods -n ai-stack --no-headers
  [ "$status" -eq 0 ]

  if echo "$output" | grep -E "CrashLoopBackOff|ImagePullBackOff|ErrImagePull"; then
    echo "Detected unhealthy pod states:" >&2
    echo "$output" >&2
    exit 1
  fi
}

@test "network policies deny cross-namespace traffic" {
  if [ "${RUN_NETPOL_TEST:-}" != "true" ]; then
    skip "Set RUN_NETPOL_TEST=true to enable NetworkPolicy enforcement checks"
  fi

  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  local pod_name="netpol-default-${RANDOM}"
  create_test_pod "default" "$pod_name"

  run kubectl exec -n default "$pod_name" -- curl -sS --max-time 3 http://qdrant.ai-stack.svc.cluster.local:6333/healthz
  cleanup_test_pod "default" "$pod_name"

  [ "$status" -ne 0 ]
}

@test "network policies allow intra-namespace traffic" {
  if [ "${RUN_NETPOL_TEST:-}" != "true" ]; then
    skip "Set RUN_NETPOL_TEST=true to enable NetworkPolicy enforcement checks"
  fi

  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  local pod_name="netpol-ai-stack-${RANDOM}"
  create_test_pod "ai-stack" "$pod_name"

  run kubectl exec -n ai-stack "$pod_name" -- curl -sS --max-time 3 http://qdrant.ai-stack.svc.cluster.local:6333/healthz
  cleanup_test_pod "ai-stack" "$pod_name"

  [ "$status" -eq 0 ]
}
