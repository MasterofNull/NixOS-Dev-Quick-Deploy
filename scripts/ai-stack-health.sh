#!/usr/bin/env bash
# Unified health check entry point for the local AI stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}"
LOG_FILE="${LOG_DIR}/ai-stack-health-$(date +%Y%m%d_%H%M%S).log"

if ! mkdir -p "$LOG_DIR" >/dev/null 2>&1 || ! touch "$LOG_FILE" >/dev/null 2>&1; then
    LOG_DIR="/tmp/nixos-quick-deploy/logs"
    mkdir -p "$LOG_DIR" >/dev/null 2>&1 || true
    LOG_FILE="${LOG_DIR}/ai-stack-health-$(date +%Y%m%d_%H%M%S).log"
fi

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

status=0

k8s_basic_check() {
    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    local kubeconfig="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
    local kubectl_bin="kubectl"
    if [[ -x /run/current-system/sw/bin/kubectl ]]; then
        kubectl_bin="/run/current-system/sw/bin/kubectl"
    fi
    local -a required_deploys=(aidb qdrant llama-cpp postgres redis)
    local -a optional_deploys=(open-webui mindsdb)

    for deploy in "${required_deploys[@]}"; do
        if ! "$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" >/dev/null 2>&1; then
            status=1
            warn "$deploy deployment not found"
            continue
        fi
        local desired ready
        desired=$("$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
        ready=$("$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
        if [[ "${ready:-0}" -lt "${desired:-0}" ]]; then
            status=1
            warn "$deploy not ready (${ready}/${desired})"
        else
            success "$deploy is ready (${ready}/${desired})"
        fi
    done

    for deploy in "${optional_deploys[@]}"; do
        if ! "$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" >/dev/null 2>&1; then
            warn "$deploy deployment not found (optional)"
            continue
        fi
        local desired ready
        desired=$("$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
        ready=$("$kubectl_bin" --kubeconfig "$kubeconfig" get deploy -n "$namespace" "$deploy" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
        if [[ "${ready:-0}" -lt "${desired:-0}" ]]; then
            warn "$deploy not ready (${ready}/${desired})"
        else
            success "$deploy is ready (${ready}/${desired})"
        fi
    done
}

resolve_python() {
    if [[ -n "${PYTHON_AI_INTERPRETER:-}" && -x "${PYTHON_AI_INTERPRETER}" ]]; then
        echo "${PYTHON_AI_INTERPRETER}"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if [[ -x /run/current-system/sw/bin/python3 ]]; then
        echo "/run/current-system/sw/bin/python3"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    return 1
}

info "Running AI stack health check (v2)..."
python_bin="$(resolve_python || true)"
health_cmd=()
path_prefix="/run/current-system/sw/bin"
health_mode="${AI_STACK_MODE:-}"
if [[ -z "$health_mode" ]]; then
    if [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
        health_mode="k8s"
    else
        health_mode="auto"
    fi
fi
if [[ "$health_mode" == "auto" ]]; then
    if systemctl is-active --quiet k3s >/dev/null 2>&1; then
        health_mode="k8s"
    fi
fi
if [[ "$health_mode" == "k8s" && -f /etc/rancher/k3s/k3s.yaml ]]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi
if [[ "$health_mode" == "auto" && -f /etc/rancher/k3s/k3s.yaml ]]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    if command -v kubectl >/dev/null 2>&1 && kubectl get ns ai-stack >/dev/null 2>&1; then
        health_mode="k8s"
    fi
fi
if [[ -n "${python_bin}" ]]; then
    health_cmd=(env PATH="${path_prefix}:$PATH" "$python_bin" "${PROJECT_ROOT}/scripts/check-ai-stack-health-v2.py" -v --mode "$health_mode")
elif command -v nix >/dev/null 2>&1; then
    health_cmd=(env PATH="${path_prefix}:$PATH" nix run --quiet nixpkgs#python3 -- "${PROJECT_ROOT}/scripts/check-ai-stack-health-v2.py" -v --mode "$health_mode")
else
    status=1
    warn "Python interpreter not found. Set PYTHON_AI_INTERPRETER or install python3."
fi

if [[ "$health_mode" == "k8s" && "${AI_STACK_HEALTH_PYTHON:-0}" != "1" ]]; then
    if command -v kubectl >/dev/null 2>&1; then
        info "Running basic k8s deployment checks..."
        k8s_basic_check
    else
        status=1
        warn "kubectl not available; unable to run k8s checks"
    fi
else
    if (( ${#health_cmd[@]} > 0 )) && "${health_cmd[@]}" > >(tee "$LOG_FILE") 2>&1; then
        success "AI stack service checks passed"
    else
        status=1
        warn "AI stack service checks reported issues (log: $LOG_FILE)"
    fi
fi

info "Checking dashboard services..."
if systemctl --user show-environment >/dev/null 2>&1; then
    dashboard_units=(dashboard-collector.timer dashboard-server.service)
    if [[ -f "${HOME}/.config/systemd/user/dashboard-api-proxy.service" ]]; then
        dashboard_units+=(dashboard-api-proxy.service)
    else
        dashboard_units+=(dashboard-api.service)
    fi

    for unit in "${dashboard_units[@]}"; do
        if systemctl --user is-active --quiet "$unit"; then
            success "$unit is active"
        else
            status=1
            warn "$unit is not active"
        fi
    done
else
    warn "systemd --user session not available; skipping dashboard unit checks"
fi

if [[ "$status" -eq 0 ]]; then
    success "All critical checks passed"
else
    warn "Some checks failed; inspect $LOG_FILE"
fi

exit "$status"
