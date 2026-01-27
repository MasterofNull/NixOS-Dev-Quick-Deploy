#!/usr/bin/env bash
# Phase 09: K3s + Portainer + K8s AI Stack
# Purpose: Deploy the AI stack into K3s, ensure secrets, and install Portainer.

phase_09_k3s_portainer() {
    print_section "Phase 9: K3s + Portainer + K8s AI Stack"

    if ! command -v kubectl >/dev/null 2>&1; then
        print_warning "kubectl not found. Skipping K3s/Portainer deployment."
        return 0
    fi

    local ai_stack_ns="${AI_STACK_NAMESPACE:-ai-stack}"
    local backups_ns="${BACKUPS_NAMESPACE:-backups}"
    local secrets_dir="${SCRIPT_DIR}/ai-stack/kubernetes/secrets"
    local secrets_bundle="${secrets_dir}/secrets.sops.yaml"
    local require_encrypted_secrets="${REQUIRE_ENCRYPTED_SECRETS:-false}"
    local portainer_manifest="${SCRIPT_DIR}/portainer-k8s.yaml"
    local kustomize_overlay="${AI_STACK_KUSTOMIZE_OVERLAY:-dev}"
    local kustomize_overlay_dir="${SCRIPT_DIR}/ai-stack/kustomize/overlays/${kustomize_overlay}"
    local kustomize_base_dir="${SCRIPT_DIR}/ai-stack/kubernetes"
    local deploy_mode="${AI_STACK_DEPLOY_MODE:-kustomize}"

    ensure_namespace() {
        local ns="$1"
        if ! kubectl get namespace "$ns" >/dev/null 2>&1; then
            print_info "Creating namespace: ${ns}"
            kubectl create namespace "$ns" >/dev/null
        fi
    }

    local secrets_tmp_dir=""
    local secrets_bundle_json=""

    cleanup_secrets_tmp() {
        if [[ -n "${secrets_tmp_dir}" && -d "${secrets_tmp_dir}" ]]; then
            rm -rf "${secrets_tmp_dir}"
        fi
    }

    apply_secret_from_file() {
        local secret_name="$1"
        local file_path="$2"
        local key_name="$3"
        local ns="$4"

        if [[ ! -f "$file_path" ]]; then
            print_warning "Secret file missing: ${file_path} (skipping ${secret_name})"
            return 0
        fi

        kubectl create secret generic "$secret_name" \
            --namespace "$ns" \
            --from-file="${key_name}=${file_path}" \
            --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    }

    apply_secret_from_value() {
        local secret_name="$1"
        local value="$2"
        local key_name="$3"
        local ns="$4"

        if [[ -z "$value" ]]; then
            print_warning "Secret value empty for ${secret_name} (skipping)"
            return 0
        fi

        kubectl create secret generic "$secret_name" \
            --namespace "$ns" \
            --from-literal="${key_name}=${value}" \
            --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    }

    load_encrypted_secrets_bundle() {
        if [[ ! -f "$secrets_bundle" ]]; then
            return 1
        fi

        if ! command -v sops >/dev/null 2>&1; then
            print_warning "Encrypted secrets bundle found but sops is missing: ${secrets_bundle}"
            return 1
        fi

        if ! command -v jq >/dev/null 2>&1; then
            print_warning "Encrypted secrets bundle requires jq but it is missing."
            return 1
        fi

        local previous_umask
        previous_umask=$(umask)
        umask 077
        secrets_tmp_dir="$(mktemp -d 2>/dev/null || true)"
        umask "$previous_umask"

        if [[ -z "$secrets_tmp_dir" ]]; then
            print_warning "Unable to create temporary directory for decrypted secrets."
            return 1
        fi

        secrets_bundle_json="${secrets_tmp_dir}/secrets.json"

        if ! sops -d --output-type json "$secrets_bundle" > "$secrets_bundle_json" 2>/dev/null; then
            print_warning "Failed to decrypt secrets bundle: ${secrets_bundle}"
            cleanup_secrets_tmp
            return 1
        fi

        return 0
    }

    get_secret_from_bundle() {
        local key="$1"

        if [[ -z "${secrets_bundle_json}" || ! -f "${secrets_bundle_json}" ]]; then
            return 1
        fi

        jq -r --arg key "$key" '.[$key] // empty' "$secrets_bundle_json"
    }

    ensure_backup_encryption() {
        if kubectl get secret backup-encryption -n "$backups_ns" >/dev/null 2>&1; then
            return 0
        fi
        local key=""
        if command -v openssl >/dev/null 2>&1; then
            key="$(openssl rand -base64 48)"
        else
            key="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
        fi
        kubectl create secret generic backup-encryption \
            --namespace "$backups_ns" \
            --from-literal=key="$key" >/dev/null
        print_info "Created backup-encryption secret in ${backups_ns}"
    }

    ensure_namespace "$ai_stack_ns"
    ensure_namespace "$backups_ns"

    if [[ "$deploy_mode" == "skaffold" ]]; then
        if command -v skaffold >/dev/null 2>&1; then
            print_info "Deploying AI stack with skaffold (profile: ${kustomize_overlay})"
            skaffold run -p "${kustomize_overlay}" >/dev/null
        else
            print_warning "skaffold requested but not installed; falling back to kustomize apply."
            deploy_mode="kustomize"
        fi
    fi

    if [[ "$deploy_mode" == "kustomize" ]]; then
        if [[ -d "$kustomize_overlay_dir" ]]; then
            print_info "Applying K8s manifests (kustomize overlay: ${kustomize_overlay})"
            kubectl apply -k "$kustomize_overlay_dir" >/dev/null
        elif [[ -d "$kustomize_base_dir" ]]; then
            print_info "Applying K8s manifests (kustomize base)"
            kubectl apply -k "$kustomize_base_dir" >/dev/null
        else
            print_warning "K8s manifests not found at ${kustomize_overlay_dir} or ${kustomize_base_dir}"
        fi
    fi

    if [[ -f "$portainer_manifest" ]]; then
        print_info "Applying Portainer manifest: ${portainer_manifest}"
        kubectl apply -f "$portainer_manifest" >/dev/null
    else
        print_warning "Portainer manifest missing: ${portainer_manifest}"
    fi

    if [[ -d "$secrets_dir" ]]; then
        print_info "Applying AI stack secrets from ${secrets_dir}"
        if load_encrypted_secrets_bundle; then
            print_info "Using encrypted secrets bundle: ${secrets_bundle}"

            apply_secret_from_value "aidb-api-key" "$(get_secret_from_bundle "aidb_api_key")" "aidb-api-key" "$ai_stack_ns"
            apply_secret_from_value "aider-wrapper-api-key" "$(get_secret_from_bundle "aider_wrapper_api_key")" "aider-wrapper-api-key" "$ai_stack_ns"
            apply_secret_from_value "container-engine-api-key" "$(get_secret_from_bundle "container_engine_api_key")" "container-engine-api-key" "$ai_stack_ns"
            apply_secret_from_value "dashboard-api-key" "$(get_secret_from_bundle "dashboard_api_key")" "dashboard-api-key" "$ai_stack_ns"
            apply_secret_from_value "embeddings-api-key" "$(get_secret_from_bundle "embeddings_api_key")" "embeddings-api-key" "$ai_stack_ns"
            apply_secret_from_value "grafana-admin-password" "$(get_secret_from_bundle "grafana_admin_password")" "grafana-admin-password" "$ai_stack_ns"
            apply_secret_from_value "hybrid-coordinator-api-key" "$(get_secret_from_bundle "hybrid_coordinator_api_key")" "hybrid-coordinator-api-key" "$ai_stack_ns"
            apply_secret_from_value "nixos-docs-api-key" "$(get_secret_from_bundle "nixos_docs_api_key")" "nixos-docs-api-key" "$ai_stack_ns"
            apply_secret_from_value "postgres-password" "$(get_secret_from_bundle "postgres_password")" "postgres-password" "$ai_stack_ns"
            apply_secret_from_value "ralph-wiggum-api-key" "$(get_secret_from_bundle "ralph_wiggum_api_key")" "ralph-wiggum-api-key" "$ai_stack_ns"
            apply_secret_from_value "redis-password" "$(get_secret_from_bundle "redis_password")" "redis-password" "$ai_stack_ns"
            apply_secret_from_value "stack-api-key" "$(get_secret_from_bundle "stack_api_key")" "stack-api-key" "$ai_stack_ns"

            # Backups namespace needs its own postgres secret reference
            apply_secret_from_value "postgres-password" "$(get_secret_from_bundle "postgres_password")" "postgres-password" "$backups_ns"
        else
            if [[ "$require_encrypted_secrets" == "true" ]]; then
                print_warning "Encrypted secrets required but bundle missing or unreadable."
                cleanup_secrets_tmp
                return 1
            fi

            print_warning "Using plaintext secret files from ${secrets_dir}. Set REQUIRE_ENCRYPTED_SECRETS=true to enforce encryption."
            apply_secret_from_file "aidb-api-key" "${secrets_dir}/aidb_api_key" "aidb-api-key" "$ai_stack_ns"
            apply_secret_from_file "aider-wrapper-api-key" "${secrets_dir}/aider_wrapper_api_key" "aider-wrapper-api-key" "$ai_stack_ns"
            apply_secret_from_file "container-engine-api-key" "${secrets_dir}/container_engine_api_key" "container-engine-api-key" "$ai_stack_ns"
            apply_secret_from_file "dashboard-api-key" "${secrets_dir}/dashboard_api_key" "dashboard-api-key" "$ai_stack_ns"
            apply_secret_from_file "embeddings-api-key" "${secrets_dir}/embeddings_api_key" "embeddings-api-key" "$ai_stack_ns"
            apply_secret_from_file "grafana-admin-password" "${secrets_dir}/grafana_admin_password" "grafana-admin-password" "$ai_stack_ns"
            apply_secret_from_file "hybrid-coordinator-api-key" "${secrets_dir}/hybrid_coordinator_api_key" "hybrid-coordinator-api-key" "$ai_stack_ns"
            apply_secret_from_file "nixos-docs-api-key" "${secrets_dir}/nixos_docs_api_key" "nixos-docs-api-key" "$ai_stack_ns"
            apply_secret_from_file "postgres-password" "${secrets_dir}/postgres_password" "postgres-password" "$ai_stack_ns"
            apply_secret_from_file "ralph-wiggum-api-key" "${secrets_dir}/ralph_wiggum_api_key" "ralph-wiggum-api-key" "$ai_stack_ns"
            apply_secret_from_file "redis-password" "${secrets_dir}/redis_password" "redis-password" "$ai_stack_ns"
            apply_secret_from_file "stack-api-key" "${secrets_dir}/stack_api_key" "stack-api-key" "$ai_stack_ns"

            # Backups namespace needs its own postgres secret reference
            apply_secret_from_file "postgres-password" "${secrets_dir}/postgres_password" "postgres-password" "$backups_ns"
        fi
    else
        print_warning "Secrets directory not found: ${secrets_dir}"
    fi

    ensure_backup_encryption

    if [[ "${RUN_K8S_E2E:-false}" == "true" ]]; then
        print_info "Running hospital K3s E2E test suite..."
        if ! python3 "${SCRIPT_DIR}/ai-stack/tests/test_hospital_e2e.py"; then
            print_warning "K3s E2E tests reported failures."
        fi
    fi

    cleanup_secrets_tmp
    print_success "K3s + Portainer + K8s AI Stack phase completed."
    return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "This script should be sourced by nixos-quick-deploy.sh"
    exit 1
fi
