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
    local gate_only="${PHASE_09_GATE_ONLY:-false}"
    local registry_gate_enabled="${PHASE_09_REGISTRY_GATE:-true}"
    local registry_host="${REGISTRY_HOST:-127.0.0.1}"
    local registry_port="${REGISTRY_PORT:-5000}"
    local registry_url="${REGISTRY_URL:-http://${registry_host}:${registry_port}}"
    local portainer_manifest="${SCRIPT_DIR}/portainer-k8s.yaml"
    local kustomize_overlay="${AI_STACK_KUSTOMIZE_OVERLAY:-dev}"
    local kustomize_overlay_dir="${SCRIPT_DIR}/ai-stack/kustomize/overlays/${kustomize_overlay}"
    local kustomize_base_dir="${SCRIPT_DIR}/ai-stack/kubernetes"
    local deploy_mode="${AI_STACK_DEPLOY_MODE:-kustomize}"
    local dev_mode="${AI_STACK_DEV_MODE:-false}"
    local k8s_prompt_enabled="${K8S_AI_STACK_PROMPT:-true}"
    local env_configmap="${SCRIPT_DIR}/ai-stack/kubernetes/kompose/env-configmap.yaml"
    local tls_secrets=(
        "aidb-tls-secret"
        "embeddings-tls-secret"
        "hybrid-coordinator-tls-secret"
        "ralph-wiggum-tls-secret"
        "postgres-tls-secret"
        "redis-tls-secret"
        "grafana-tls-secret"
    )
    local policy_resources=(
        "default-deny-all"
        "ai-stack-allow-internal"
    )

    ensure_namespace() {
        local ns="$1"
        if ! kubectl_safe get namespace "$ns" >/dev/null 2>&1; then
            print_info "Creating namespace: ${ns}"
            retry_with_backoff --attempts 3 --delay 2 -- kubectl_safe create namespace "$ns" >/dev/null
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

        kubectl_safe create secret generic "$secret_name" \
            --namespace "$ns" \
            --from-file="${key_name}=${file_path}" \
            --dry-run=client -o yaml | kubectl_safe apply -f - >/dev/null
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

        kubectl_safe create secret generic "$secret_name" \
            --namespace "$ns" \
            --from-literal="${key_name}=${value}" \
            --dry-run=client -o yaml | kubectl_safe apply -f - >/dev/null
    }

    ensure_huggingface_secret() {
        local secret_name="huggingface-hub-token"
        local key_name="HUGGING_FACE_HUB_TOKEN"
        local ns="$1"

        if kubectl_safe get secret "$secret_name" -n "$ns" >/dev/null 2>&1; then
            return 0
        fi

        local token="${HUGGING_FACE_HUB_TOKEN:-}"
        if [[ -z "$token" ]]; then
            token="${HUGGINGFACEHUB_API_TOKEN:-}"
        fi

        kubectl_safe create secret generic "$secret_name" \
            --namespace "$ns" \
            --from-literal="${key_name}=${token}" \
            --dry-run=client -o yaml | kubectl_safe apply -f - >/dev/null

        if [[ -n "$token" ]]; then
            print_success "Hugging Face token secret created from environment."
        else
            print_info "Created empty Hugging Face token secret (optional)."
        fi
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

    apply_kustomize_manifest() {
        local desc="$1"
        local target="$2"

        if [[ ! -d "$target" ]]; then
            print_warning "Kustomize path missing for ${desc}: ${target}"
            return "${ERR_K3S_MANIFEST:-53}"
        fi

        print_info "Applying ${desc} kustomization at ${target}"
        retry_kubectl apply -k "$target" >/dev/null
        local exit_code=$?

        if [[ $exit_code -ne 0 ]]; then
            print_error "Failed to apply kustomization for ${desc}"
            return "${ERR_K3S_MANIFEST:-53}"
        fi

        return 0
    }

    verify_tls_secrets() {
        local ns="$1"
        local missing=0

        for secret_name in "${tls_secrets[@]}"; do
            if ! retry_kubectl get secret "$secret_name" -n "$ns" >/dev/null 2>&1; then
                print_warning "TLS secret missing: ${secret_name}"
                missing=1
            fi
        done

        return $missing
    }

    verify_network_policies() {
        local ns="$1"
        local missing=0

        for policy_name in "${policy_resources[@]}"; do
            if ! retry_kubectl get networkpolicy "$policy_name" -n "$ns" >/dev/null 2>&1; then
                print_warning "NetworkPolicy missing: ${policy_name}"
                missing=1
            fi
        done

        return $missing
    }

    get_configmap_value() {
        local key="$1"
        local file="$2"
        if [[ ! -f "$file" ]]; then
            return 1
        fi
        awk -v target="$key" -F':' '
            $1 ~ "^[[:space:]]*"target"$" {
                val=$0
                sub("^[[:space:]]*"target":[[:space:]]*", "", val)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
                gsub(/^\"|\"$/, "", val)
                print val
                exit
            }' "$file"
    }

    set_configmap_value() {
        local key="$1"
        local value="$2"
        local file="$3"
        local escaped
        escaped=$(printf '%s' "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')
        local newline="  ${key}: \"${escaped}\""
        local tmp="${file}.tmp"
        awk -v key="$key" -v newline="$newline" '
            BEGIN { updated=0 }
            $0 ~ "^[[:space:]]*"key":[[:space:]]*" {
                print newline
                updated=1
                next
            }
            $0 ~ "^kind:" && updated==0 {
                print newline
                updated=1
            }
            { print }
            END {
                if(updated==0) {
                    print newline
                }
            }
        ' "$file" > "$tmp" && mv "$tmp" "$file"
    }

    prompt_k8s_stack_options() {
        if [[ "$k8s_prompt_enabled" != "true" ]]; then
            return 0
        fi
        if [[ ! -t 0 ]]; then
            return 0
        fi
        if [[ ! -f "$env_configmap" ]]; then
            print_warning "K8s env configmap not found at ${env_configmap}; skipping prompts."
            return 0
        fi
        if ! declare -F prompt_user >/dev/null 2>&1; then
            return 0
        fi

        print_section "K3s AI Stack Options"
        print_info "These values will update the K8s env ConfigMap before apply."
        echo ""

        local default_embedding
        default_embedding=$(get_configmap_value "EMBEDDING_MODEL" "$env_configmap")
        default_embedding="${default_embedding:-BAAI/bge-small-en-v1.5}"
        print_info "Embedding model options:"
        print_info "  1) BAAI/bge-small-en-v1.5"
        print_info "  2) BAAI/bge-base-en-v1.5"
        print_info "  3) sentence-transformers/all-MiniLM-L6-v2"
        local embedding_choice
        embedding_choice=$(prompt_user "Select embedding model [1-3 or custom]" "1")
        case "$embedding_choice" in
            2) default_embedding="BAAI/bge-base-en-v1.5" ;;
            3) default_embedding="sentence-transformers/all-MiniLM-L6-v2" ;;
            1|"") default_embedding="BAAI/bge-small-en-v1.5" ;;
            *) default_embedding="$embedding_choice" ;;
        esac
        set_configmap_value "EMBEDDING_MODEL" "$default_embedding" "$env_configmap"
        print_success "Embedding model set: ${default_embedding}"

        local embedding_dim="384"
        case "$default_embedding" in
            *bge-base* ) embedding_dim="768" ;;
            *bge-small* ) embedding_dim="384" ;;
            *all-MiniLM-L6-v2* ) embedding_dim="384" ;;
            * ) embedding_dim=$(prompt_user "Embedding dimensions (EMBEDDING_DIMENSIONS)" "384") ;;
        esac
        set_configmap_value "EMBEDDING_DIMENSIONS" "$embedding_dim" "$env_configmap"
        print_success "Embedding dimensions set: ${embedding_dim}"

        local default_llama_model
        default_llama_model=$(get_configmap_value "LLAMA_CPP_DEFAULT_MODEL" "$env_configmap")
        default_llama_model="${default_llama_model:-Qwen/Qwen2.5-Coder-7B-Instruct}"
        local llama_model
        llama_model=$(prompt_user "LLM model repo (LLAMA_CPP_DEFAULT_MODEL)" "$default_llama_model")
        set_configmap_value "LLAMA_CPP_DEFAULT_MODEL" "$llama_model" "$env_configmap"
        print_success "LLM model set: ${llama_model}"

        local default_model_file
        default_model_file=$(get_configmap_value "LLAMA_CPP_MODEL_FILE" "$env_configmap")
        default_model_file="${default_model_file:-qwen2.5-coder-7b-instruct-q4_k_m.gguf}"
        local model_file
        model_file=$(prompt_user "LLM model file (LLAMA_CPP_MODEL_FILE)" "$default_model_file")
        set_configmap_value "LLAMA_CPP_MODEL_FILE" "$model_file" "$env_configmap"
        print_success "LLM model file set: ${model_file}"

        local default_ctx
        default_ctx=$(get_configmap_value "LLAMA_CPP_CTX_SIZE" "$env_configmap")
        default_ctx="${default_ctx:-4096}"
        local ctx_size
        ctx_size=$(prompt_user "Context size (LLAMA_CPP_CTX_SIZE)" "$default_ctx")
        set_configmap_value "LLAMA_CPP_CTX_SIZE" "$ctx_size" "$env_configmap"
        print_success "Context size set: ${ctx_size}"

        local hf_secret_name="huggingface-hub-token"
        local hf_token=""
        if kubectl_safe get secret "$hf_secret_name" -n "$ai_stack_ns" >/dev/null 2>&1; then
            print_info "Hugging Face token secret already exists; press Enter to keep it."
            hf_token=$(prompt_secret "Hugging Face token (leave blank to keep existing)" "for private model access")
            if [[ -n "$hf_token" ]]; then
                apply_secret_from_value "$hf_secret_name" "$hf_token" "HUGGING_FACE_HUB_TOKEN" "$ai_stack_ns"
                print_success "Hugging Face token secret updated."
            else
                print_info "Keeping existing Hugging Face token secret."
            fi
        else
            hf_token=$(prompt_secret "Hugging Face token (optional)" "from https://huggingface.co/settings/tokens")
            if [[ -n "$hf_token" ]]; then
                apply_secret_from_value "$hf_secret_name" "$hf_token" "HUGGING_FACE_HUB_TOKEN" "$ai_stack_ns"
                print_success "Hugging Face token secret created."
            else
                print_info "Skipped Hugging Face token secret."
            fi
        fi
        echo ""
    }

    check_registry_gate() {
        if [[ "$registry_gate_enabled" != "true" ]]; then
            print_warning "Registry gate disabled (PHASE_09_REGISTRY_GATE=${registry_gate_enabled})."
            return 0
        fi

        if command -v curl >/dev/null 2>&1; then
            if ! curl_safe -sf "${registry_url}/v2/" >/dev/null 2>&1; then
                print_error "Registry gate failed: ${registry_url} is unreachable."
                print_info "Start the local registry or update REGISTRY_URL/REGISTRY_PORT."
                print_info "Tip: ${SCRIPT_DIR}/scripts/local-registry.sh start"
                print_info "To bypass once: PHASE_09_REGISTRY_GATE=false"
                return "${ERR_K3S_MANIFEST:-53}"
            fi
            print_success "Registry gate passed: ${registry_url}"
            return 0
        fi

        print_warning "Registry gate skipped (curl not available)."
        return 0
    }

    ensure_backup_encryption() {
        if kubectl_safe get secret backup-encryption -n "$backups_ns" >/dev/null 2>&1; then
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
        kubectl_safe create secret generic backup-encryption \
            --namespace "$backups_ns" \
            --from-literal=key="$key" >/dev/null
        print_info "Created backup-encryption secret in ${backups_ns}"
    }

    ensure_namespace "$ai_stack_ns"
    ensure_namespace "$backups_ns"

    if [[ -x "${SCRIPT_DIR}/scripts/apply-project-root.sh" ]]; then
        local embeddings_manifest="${SCRIPT_DIR}/ai-stack/kubernetes/kompose/embeddings-deployment.yaml"
        if [[ -f "$embeddings_manifest" ]] && grep -q "@AI_STACK_DATA@" "$embeddings_manifest" 2>/dev/null; then
            print_info "Resolving AI_STACK_DATA placeholders in embeddings manifest"
            "${SCRIPT_DIR}/scripts/apply-project-root.sh" "$embeddings_manifest" >/dev/null
        fi
    fi

    prompt_k8s_stack_options
    ensure_huggingface_secret "$ai_stack_ns"

    if [[ "$gate_only" == "true" ]]; then
        print_info "Phase 9 gate-only mode enabled; skipping manifests and secrets."
        if ! verify_tls_secrets "$ai_stack_ns"; then
            print_error "TLS secrets not available for all services; review cert-manager and TLS resources."
            return "${ERR_SECRET_MISSING:-61}"
        fi
        if ! verify_network_policies "$ai_stack_ns"; then
            print_error "Network policies were not applied successfully."
            return "${ERR_K3S_MANIFEST:-53}"
        fi
        print_success "Phase 9 gate-only checks passed."
        return 0
    fi

    check_registry_gate || return $?

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
            apply_kustomize_manifest "overlay" "$kustomize_overlay_dir" || return $?
        elif [[ -d "$kustomize_base_dir" ]]; then
            apply_kustomize_manifest "base" "$kustomize_base_dir" || return $?
        else
            print_warning "K8s manifests not found at ${kustomize_overlay_dir} or ${kustomize_base_dir}"
            return "${ERR_K3S_MANIFEST:-53}"
        fi
    fi

    if [[ "$dev_mode" == "true" ]]; then
        local heavy_deploys=(open-webui mindsdb llama-cpp)
        print_warning "AI_STACK_DEV_MODE enabled; scaling heavy deployments to zero."
        for deploy in "${heavy_deploys[@]}"; do
            if kubectl_safe get deploy "$deploy" -n "$ai_stack_ns" >/dev/null 2>&1; then
                kubectl_safe scale deploy "$deploy" -n "$ai_stack_ns" --replicas=0 >/dev/null 2>&1 || true
                print_info "Scaled ${deploy} to 0 replicas."
            fi
        done
    fi


    if [[ -f "$portainer_manifest" ]]; then
        print_info "Applying Portainer manifest: ${portainer_manifest}"
        retry_with_backoff --attempts 3 --delay 5 --max-delay 30 -- kubectl_safe apply -f "$portainer_manifest" >/dev/null
    else
        print_warning "Portainer manifest missing: ${portainer_manifest}"
    fi

    if ! verify_tls_secrets "$ai_stack_ns"; then
        print_error "TLS secrets not available for all services; review cert-manager and TLS resources."
        return "${ERR_SECRET_MISSING:-61}"
    fi

    if ! verify_network_policies "$ai_stack_ns"; then
        print_error "Network policies were not applied successfully."
        return "${ERR_K3S_MANIFEST:-53}"
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
                return "${ERR_SECRET_MISSING:-61}"
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
