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

@test "AIDB health and Qdrant reachable from AIDB pod" {
  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  run kubectl exec -n ai-stack deploy/aidb -- python3 -c 'import urllib.request; urllib.request.urlopen("http://localhost:8091/health", timeout=5); urllib.request.urlopen("http://qdrant.ai-stack:6333/collections", timeout=5)'
  [ "$status" -eq 0 ]
}

@test "Hybrid coordinator /query responds with JSON" {
  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  run kubectl exec -n ai-stack deploy/hybrid-coordinator -- python3 -c 'import json,urllib.request; key=open("/run/secrets/hybrid-coordinator-api-key").read().strip(); payload={"query":"NixOS registry config","mode":"hybrid"}; req=urllib.request.Request("http://localhost:8092/query", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json","X-API-Key":key}); resp=urllib.request.urlopen(req, timeout=10); body=resp.read().decode(); assert body and ("results" in body or "status" in body)'
  [ "$status" -eq 0 ]
}

@test "Dashboard feedback endpoint records feedback" {
  if ! kubectl get namespace ai-stack >/dev/null 2>&1; then
    skip "ai-stack namespace missing"
  fi

  run kubectl exec -n ai-stack deploy/dashboard-api -- python3 -c 'import json,urllib.request; payload={"query":"Integration feedback","correction":"Use localhost registry","rating":4}; req=urllib.request.Request("http://localhost:8889/api/feedback", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}); resp=urllib.request.urlopen(req, timeout=10); body=resp.read().decode(); assert "feedback_id" in body'
  [ "$status" -eq 0 ]
}
