#!/run/current-system/sw/bin/bash
# Dashboard Data Generator
# Collects real-time system, LLM, database, network, and security metrics
# Outputs JSON for consumption by the dashboard UI

# NOTE: -e intentionally omitted — data collection continues even when
# individual metric sources are temporarily unavailable.
set -uo pipefail

# Resolve project root for reading env defaults.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source centralized service endpoints
# shellcheck source=config/service-endpoints.sh
[[ -f "${PROJECT_ROOT}/config/service-endpoints.sh" ]] && source "${PROJECT_ROOT}/config/service-endpoints.sh"

# Output directory for JSON data
DATA_DIR="${DASHBOARD_DATA_DIR:-${HOME}/.local/share/nixos-system-dashboard}"
AI_STACK_DATA_ROOT="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"
AIDB_LOCAL_CONFIG="${AIDB_CONFIG_PATH:-$HOME/Documents/AI-Optimizer/config/config.yaml}"
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-60}"

has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

run_timeout() {
    local seconds="$1"
    shift
    if has_cmd timeout; then
        timeout "$seconds" "$@"
    else
        "$@"
    fi
}

curl_fast() {
    run_timeout 3 curl -sf --max-time 2 "$@"
}

maybe_jq() {
    if has_cmd jq; then
        jq "$@"
    else
        cat
    fi
}

detect_container_runtime() {
    echo "native"
}

k8s_pod_status_global() {
    local service="$1"
    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    if ! has_cmd kubectl; then
        echo "offline"
        return
    fi
    local status_json
    status_json=$(run_timeout 3 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "$namespace" -l "io.kompose.service=${service}" -o json 2>/dev/null || echo "")
    if [[ -z "$status_json" ]]; then
        echo "offline"
        return
    fi
    if has_cmd jq; then
        local count
        local ready
        count=$(echo "$status_json" | jq -r '.items | length' 2>/dev/null || echo "0")
        ready=$(echo "$status_json" | jq -r '[.items[]?.status.containerStatuses[]?.ready] | any' 2>/dev/null || echo "false")
        if [[ "$count" == "0" ]]; then
            echo "offline"
        elif [[ "$ready" == "true" ]]; then
            echo "online"
        else
            echo "starting"
        fi
    else
        echo "online"
    fi
}

k8s_exec() {
    local service="$1"
    local cmd="$2"
    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    run_timeout 5 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" exec -n "$namespace" "deploy/${service}" -- sh -c "$cmd" 2>/dev/null || true
}

k8s_file_line_count() {
    local service="$1"
    local path="$2"
    k8s_exec "$service" "test -f '$path' && wc -l < '$path' || echo 0" | tr -d ' \r\n' || echo 0
}

k8s_file_size_bytes() {
    local service="$1"
    local path="$2"
    k8s_exec "$service" "test -f '$path' && wc -c < '$path' || echo 0" | tr -d ' \r\n' || echo 0
}

k8s_tail_line() {
    local service="$1"
    local path="$2"
    k8s_exec "$service" "test -f '$path' && tail -n 1 '$path' || true"
}

k8s_grep_count() {
    local service="$1"
    local path="$2"
    local pattern="$3"
    local escaped
    escaped=${pattern//\'/\'\\\'\'}
    k8s_exec "$service" "test -f '$path' && grep -cF '$escaped' '$path' || echo 0" | tr -d ' \r\n' || echo 0
}

dir_size() {
    local path="$1"
    if [[ -d "$path" ]]; then
        du -sh "$path" 2>/dev/null | awk '{print $1}'
    else
        echo "0"
    fi
}

dir_exists() {
    local path="$1"
    if [[ -d "$path" ]]; then
        echo "true"
    else
        echo "false"
    fi
}

file_exists() {
    local path="$1"
    if [[ -f "$path" ]]; then
        echo "true"
    else
        echo "false"
    fi
}

file_size_bytes() {
    local path="$1"
    if [[ -f "$path" ]]; then
        stat -c %s "$path" 2>/dev/null || wc -c < "$path" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

file_line_count() {
    local path="$1"
    if [[ -f "$path" ]]; then
        wc -l < "$path" 2>/dev/null | tr -d ' '
    else
        echo 0
    fi
}

normalize_int() {
    local value="${1:-}"
    value="${value//[^0-9]/}"
    if [[ -z "$value" ]]; then
        echo 0
    else
        echo $((10#$value))
    fi
}

count_jsonl_field() {
    local path="$1"
    local field="$2"
    local value="$3"
    if [[ -f "$path" ]]; then
        if has_cmd jq; then
            jq -r "select(.${field} == \"${value}\") | 1" "$path" 2>/dev/null | wc -l | tr -d ' '
        else
            grep -c "\"${field}\"[[:space:]]*:[[:space:]]*\"${value}\"" "$path" 2>/dev/null || echo "0"
        fi
    else
        echo "0"
    fi
}

count_aidb_local_events() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        echo "0"
        return
    fi
    if has_cmd jq; then
        jq -r 'select((.llm_used == "llama.cpp") or ((.model // "") | tostring | test("^(qwen|deepseek)"; "i"))) | 1' "$path" 2>/dev/null | wc -l | tr -d ' '
        return
    fi
    awk '
        /"llm_used"[[:space:]]*:[[:space:]]*"llama\.cpp"/ {count++; next}
        /"model"[[:space:]]*:[[:space:]]*"(qwen|deepseek)/ {count++; next}
        END {print count+0}
    ' "$path"
}

last_event_timestamp() {
    local path="$1"
    if [[ -f "$path" ]]; then
        tail -n 1 "$path" | maybe_jq -r '.timestamp // .created_at // empty' 2>/dev/null | tr -d '\r'
    fi
}


read_yaml_telemetry_path() {
    local config_file="$1"
    if [[ -f "$config_file" ]]; then
        awk '
            $1 == "telemetry:" {in_telemetry=1; next}
            in_telemetry && $1 == "path:" {print $2; exit}
            in_telemetry && /^[^[:space:]]/ {exit}
        ' "$config_file" | tr -d '"'
    fi
}

resolve_tilde_path() {
    local path="$1"
    if [[ "$path" == "~/"* ]]; then
        path="${HOME}/${path#~/}"
    fi
    path="${path//\/~\//\/}"
    echo "$path"
}

read_nixos_option() {
    local option="$1"
    if has_cmd nixos-option; then
        nixos-option "$option" 2>/dev/null | awk -F': ' '/Value:/ {print $2}' | tail -n 1
    else
        echo ""
    fi
    return 0
}

read_sshd_config_value() {
    local key="$1"
    local config_file="/etc/ssh/sshd_config"
    if [[ -f "$config_file" ]]; then
        awk -v k="$key" 'tolower($1) == tolower(k) {print $2}' "$config_file" | tail -n 1
    fi
}

read_journald_value() {
    local key="$1"
    local config_file="/etc/systemd/journald.conf"
    if [[ -f "$config_file" ]]; then
        awk -F= -v k="$key" '$1 == k {gsub(/"/,"",$2); print $2}' "$config_file" | tail -n 1
    fi
}

systemd_is_active() {
    local unit="$1"
    if has_cmd systemctl; then
        systemctl is-active "$unit" 2>/dev/null | tr -d '\n' || echo "unknown"
    else
        echo "unknown"
    fi
}

os_release_value() {
    local key="$1"
    local os_release="/etc/os-release"
    if [[ -f "$os_release" ]]; then
        awk -F= -v k="$key" '$1 == k {gsub(/"/,"",$2); print $2}' "$os_release" | tail -n 1
    fi
}

sysctl_value() {
    local key="$1"
    if has_cmd sysctl; then
        sysctl -n "$key" 2>/dev/null | tail -n 1
    fi
}
mkdir -p "$DATA_DIR"

if [[ -z "${AIDB_TELEMETRY_PATH:-}" ]]; then
    telemetry_candidate=$(read_yaml_telemetry_path "$AIDB_LOCAL_CONFIG")
    if [[ -n "$telemetry_candidate" ]]; then
        export AIDB_TELEMETRY_PATH
        AIDB_TELEMETRY_PATH=$(resolve_tilde_path "$telemetry_candidate")
    fi
fi

LOCK_FILE="${DATA_DIR}/collector.lock"

acquire_lock() {
    if has_cmd flock; then
        exec 9>"$LOCK_FILE"
        if ! flock -n 9; then
            echo "Collector already running; skipping."
            exit 0
        fi
        return 0
    fi

    if [[ -f "$LOCK_FILE" ]]; then
        local existing_pid
        existing_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
            echo "Collector already running (PID $existing_pid); skipping."
            exit 0
        fi
    fi

    echo "$$" > "$LOCK_FILE"
}

# ============================================================================
# System Metrics
# ============================================================================
collect_system_metrics() {
    local host_name
    host_name=$(hostname)

    # CPU usage - Enhanced for GNOME Resources-like precision using /proc/stat
    local cpu_usage="0.0"
    if [[ -f /proc/stat ]]; then
        # Read CPU stats (avoid process substitution which can hang)
        local cpu_line=$(grep '^cpu ' /proc/stat | head -1)
        local cpu_times=($cpu_line)
        local idle=${cpu_times[4]:-0}
        local iowait=${cpu_times[5]:-0}
        local total=0
        for val in "${cpu_times[@]:1}"; do
            [[ -n "$val" ]] && total=$((total + val))
        done

        # Calculate usage percentage using delta
        if [[ -f "$DATA_DIR/.cpu_prev" ]]; then
            read -r prev_idle prev_total < "$DATA_DIR/.cpu_prev" 2>/dev/null || true
            local idle_delta=$((idle - prev_idle))
            local total_delta=$((total - prev_total))
            if [[ $total_delta -gt 0 ]]; then
                cpu_usage=$(awk -v idle="$idle_delta" -v total="$total_delta" 'BEGIN {printf "%.1f", 100 * (1 - idle/total)}' 2>/dev/null || echo "0.0")
            fi
        fi
        echo "$idle $total" > "$DATA_DIR/.cpu_prev" 2>/dev/null || true
    fi

    # Memory info - Enhanced with /proc/meminfo for GNOME Resources-style detail
    local mem_info
    if [[ -f /proc/meminfo ]]; then
        local mem_total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
        local mem_free=$(awk '/^MemFree:/ {print $2}' /proc/meminfo)
        local mem_available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
        local mem_buffers=$(awk '/^Buffers:/ {print $2}' /proc/meminfo)
        local mem_cached=$(awk '/^Cached:/ {print $2}' /proc/meminfo)
        local mem_shmem=$(awk '/^Shmem:/ {print $2}' /proc/meminfo)
        local mem_sreclaimable=$(awk '/^SReclaimable:/ {print $2}' /proc/meminfo)
        local swap_total=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
        local swap_free=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
        local swap_used=$((swap_total - swap_free))

        local mem_used=$((mem_total - mem_available))
        local mem_total_mb=$((mem_total / 1024))
        local mem_used_mb=$((mem_used / 1024))
        local mem_free_mb=$((mem_free / 1024))
        local mem_available_mb=$((mem_available / 1024))
        local mem_buffers_mb=$((mem_buffers / 1024))
        local mem_cached_mb=$((mem_cached / 1024))
        local swap_total_mb=$((swap_total / 1024))
        local swap_used_mb=$((swap_used / 1024))
        local swap_free_mb=$((swap_free / 1024))

        local mem_percent=$(awk -v used="$mem_used" -v total="$mem_total" 'BEGIN {printf "%.1f", (used/total)*100}')
        local swap_percent=0
        if [[ $swap_total -gt 0 ]]; then
            swap_percent=$(awk -v used="$swap_used" -v total="$swap_total" 'BEGIN {printf "%.1f", (used/total)*100}')
        fi

        mem_info="{\"total\":$mem_total_mb,\"used\":$mem_used_mb,\"free\":$mem_free_mb,\"available\":$mem_available_mb,\"buffers\":$mem_buffers_mb,\"cached\":$mem_cached_mb,\"percent\":$mem_percent,\"swap\":{\"total\":$swap_total_mb,\"used\":$swap_used_mb,\"free\":$swap_free_mb,\"percent\":$swap_percent}}"
    else
        # Fallback to free
        mem_info=$(run_timeout 2 free -m 2>/dev/null | awk 'NR==2{printf "{\"total\":%s,\"used\":%s,\"free\":%s,\"percent\":%.2f}", $2,$3,$4,$3*100/$2}')
    fi

    local disk_usage
    disk_usage=$(run_timeout 2 df -B1 / 2>/dev/null | awk 'NR==2{printf "{\"total_bytes\":%s,\"used_bytes\":%s,\"avail_bytes\":%s,\"percent\":%s,\"total\":\"%s\",\"used\":\"%s\",\"avail\":\"%s\"}", $2,$3,$4,($5+0),$2,$3,$4}')
    if [[ -z "${disk_usage}" ]]; then
        disk_usage='{"total_bytes":0,"used_bytes":0,"avail_bytes":0,"percent":0}'
    fi
    local uptime_seconds=$(awk '{print int($1)}' /proc/uptime)
    local load_avg
    load_avg="$(awk '{print $1", "$2", "$3}' /proc/loadavg 2>/dev/null || echo "0.00, 0.00, 0.00")"
    local cpu_model="Unknown"
    local arch
    local gpu_name="N/A"
    local gpu_busy="null"
    local vram_total="null"
    local vram_used="null"

    # CPU temperature (if available)
    local cpu_temp="N/A"
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        cpu_temp=$(awk '{printf "%.1f°C", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
    fi

    # CPU frequency (current/min/max) - GNOME Resources style
    local cpu_freq_current="N/A"
    local cpu_freq_min="N/A"
    local cpu_freq_max="N/A"
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq ]; then
        cpu_freq_current=$(awk '{printf "%.2f", $1/1000000}' /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "0")
    fi
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq ]; then
        cpu_freq_min=$(awk '{printf "%.2f", $1/1000000}' /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || echo "0")
    fi
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq ]; then
        cpu_freq_max=$(awk '{printf "%.2f", $1/1000000}' /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || echo "0")
    fi

    # Per-core CPU usage - GNOME Resources style
    local per_core_usage="[]"
    if [[ -f /proc/stat ]]; then
        local core_array="["
        local first=true
        local core_count=0

        for core_num in $(seq 0 $(($(nproc) - 1))); do
            local line=$(grep "^cpu$core_num " /proc/stat)
            [[ -z "$line" ]] && continue

            local cpu_times=($line)
            local idle=${cpu_times[4]}
            local total=0
            for val in "${cpu_times[@]:1}"; do
                total=$((total + val))
            done

            local core_usage="0.0"
            if [[ -f "$DATA_DIR/.cpu_core${core_num}_prev" ]]; then
                read -r prev_idle prev_total < "$DATA_DIR/.cpu_core${core_num}_prev" 2>/dev/null || true
                local idle_delta=$((idle - prev_idle))
                local total_delta=$((total - prev_total))
                if [[ $total_delta -gt 0 ]]; then
                    core_usage=$(awk -v idle="$idle_delta" -v total="$total_delta" 'BEGIN {printf "%.1f", 100 * (1 - idle/total)}')
                fi
            fi
            echo "$idle $total" > "$DATA_DIR/.cpu_core${core_num}_prev"

            [[ "$first" == "false" ]] && core_array+=","
            first=false
            core_array+="{\"core\":$core_num,\"usage\":$core_usage}"
            core_count=$((core_count + 1))
            [[ $core_count -ge 16 ]] && break  # Safety limit
        done

        core_array+="]"
        per_core_usage="$core_array"
    fi

    if [[ -f /proc/cpuinfo ]]; then
        cpu_model=$(awk -F': ' '/model name|Hardware|Processor/ {print $2; exit}' /proc/cpuinfo 2>/dev/null || echo "Unknown")
    fi

    arch=$(uname -m 2>/dev/null || echo "unknown")

    if has_cmd lspci; then
        gpu_name=$(lspci | rg -m 1 -i 'vga|3d|display' | sed 's/^[0-9a-f:.]* //')
        [[ -z "$gpu_name" ]] && gpu_name="N/A"
    fi

    for path in /sys/class/drm/card*/device/gpu_busy_percent; do
        if [[ -f "$path" ]]; then
            gpu_busy=$(cat "$path" 2>/dev/null || echo "null")
            break
        fi
    done

    for path in /sys/class/drm/card*/device/mem_info_vram_total; do
        if [[ -f "$path" ]]; then
            vram_total=$(awk '{printf "%.0f", $1/1024/1024}' "$path" 2>/dev/null || echo "null")
            break
        fi
    done

    for path in /sys/class/drm/card*/device/mem_info_vram_used; do
        if [[ -f "$path" ]]; then
            vram_used=$(awk '{printf "%.0f", $1/1024/1024}' "$path" 2>/dev/null || echo "null")
            break
        fi
    done

    # Disk I/O monitoring - GNOME Resources style
    local disk_read_rate="0"
    local disk_write_rate="0"
    local disk_read_total="0"
    local disk_write_total="0"

    if [[ -f /proc/diskstats ]]; then
        # Get primary disk device (usually sda, nvme0n1, etc.)
        local primary_disk=""
        if has_cmd findmnt; then
            # Remove /dev/ and partition suffix (p2, 2, etc) but keep device number (nvme0n1)
            primary_disk=$(findmnt -no SOURCE / 2>/dev/null | sed 's|/dev/||; s|p[0-9]\+$||')
        fi

        if [[ -n "$primary_disk" ]]; then
            # Read sectors read and written from /proc/diskstats (avoid process substitution)
            local disk_stats=$(awk -v disk="$primary_disk" '$3 == disk {print $6, $10}' /proc/diskstats 2>/dev/null | head -1)
            read -r sectors_read sectors_written <<< "$disk_stats"

            if [[ -n "$sectors_read" && -n "$sectors_written" ]]; then
                # Convert sectors to MB (sector = 512 bytes typically)
                disk_read_total=$(awk -v sectors="$sectors_read" 'BEGIN {printf "%.2f", sectors * 512 / 1024 / 1024}')
                disk_write_total=$(awk -v sectors="$sectors_written" 'BEGIN {printf "%.2f", sectors * 512 / 1024 / 1024}')

                # Calculate rates
                if [[ -f "$DATA_DIR/.disk_prev" ]]; then
                    read -r prev_read prev_write prev_time < "$DATA_DIR/.disk_prev"
                    local current_time=$(date +%s)
                    local time_delta=$((current_time - prev_time))

                    if [[ $time_delta -gt 0 ]]; then
                        disk_read_rate=$(awk -v curr="$disk_read_total" -v prev="$prev_read" -v time="$time_delta" 'BEGIN {printf "%.2f", (curr - prev) / time}')
                        disk_write_rate=$(awk -v curr="$disk_write_total" -v prev="$prev_write" -v time="$time_delta" 'BEGIN {printf "%.2f", (curr - prev) / time}')
                    fi
                fi

                echo "$disk_read_total $disk_write_total $(date +%s)" > "$DATA_DIR/.disk_prev"
            fi
        fi
    fi

    # Top processes by CPU and memory - GNOME Resources style
    local top_processes="[]"
    if has_cmd ps; then
        top_processes=$(ps aux --sort=-%cpu | head -11 | tail -10 | awk '{printf "{\"pid\":%s,\"user\":\"%s\",\"cpu\":%.1f,\"mem\":%.1f,\"command\":\"%s\"},", $2,$1,$3,$4,substr($0,index($0,$11))}' | sed 's/,$//' | sed 's/^/[/' | sed 's/$/]/')
        [[ -z "$top_processes" || "$top_processes" == "[]" ]] && top_processes="[]"
    fi

    cat > "$DATA_DIR/system.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "host_name": "$host_name",
  "cpu": {
    "usage_percent": $cpu_usage,
    "temperature": "$cpu_temp",
    "frequency": {
      "current": "$cpu_freq_current",
      "min": "$cpu_freq_min",
      "max": "$cpu_freq_max"
    },
    "cores": $(nproc),
    "per_core": $per_core_usage,
    "model": "$cpu_model",
    "arch": "$arch"
  },
  "gpu": {
    "name": "$gpu_name",
    "busy_percent": $gpu_busy,
    "vram_used_mb": $vram_used,
    "vram_total_mb": $vram_total
  },
  "memory": $mem_info,
  "disk": $disk_usage,
  "disk_io": {
    "read_rate_mb_s": $disk_read_rate,
    "write_rate_mb_s": $disk_write_rate,
    "read_total_mb": $disk_read_total,
    "write_total_mb": $disk_write_total
  },
  "processes": {
    "top_by_cpu": $top_processes
  },
  "uptime_seconds": $uptime_seconds,
  "load_average": "$load_avg"
}
EOF
}

# ============================================================================
# LLM Stack Metrics
# ============================================================================
collect_llm_metrics() {
    local qdrant_status="offline"
    local llama_cpp_status="offline"
    local postgres_status="offline"
    local redis_status="offline"
    local open_webui_status="offline"
    local mindsdb_status="offline"
    local aidb_status="offline"
    local aidb_services="{}"
    local hybrid_coordinator_status="offline"
    local container_runtime
    container_runtime=$(detect_container_runtime)
    local qdrant_collections="[]"
    local qdrant_collection_count=0
    local postgres_user="${POSTGRES_USER:-mcp}"
    local embedding_models="[]"
    local llama_cpp_cached_models="[]"
    local llama_cpp_cached_count=0
    local embeddings_status="offline"
    local embeddings_request_total=0
    local embeddings_error_total=0
    local embeddings_memory_mb="0"
    local embeddings_metrics=""
    local embeddings_endpoint="${EMBEDDINGS_URL}"
    local embedding_model_name=""
    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    local k8s_status=""

    k8s_pod_status() {
        k8s_pod_status_global "$1"
    }

    # Check Qdrant
    if curl_fast "${QDRANT_URL}/healthz" > /dev/null 2>&1; then
        qdrant_status="online"
        qdrant_collections=$(curl_fast "${QDRANT_URL}/collections" | maybe_jq -c '.result.collections | map(.name)' 2>/dev/null || echo "[]")
        qdrant_collection_count=$(echo "$qdrant_collections" | maybe_jq -r 'length' 2>/dev/null || echo "0")
    elif [[ "$container_runtime" == "k8s" ]]; then
        qdrant_status=$(k8s_pod_status "qdrant")
    fi

    # Check llama.cpp (llama.cpp server)
    if curl_fast "${LLAMA_URL}/health" > /dev/null 2>&1; then
        llama_cpp_status="online"
        llama_cpp_models=$(curl_fast "${LLAMA_URL}/v1/models" 2>/dev/null | maybe_jq -c '.data // []' || echo "[]")
    elif [[ "$container_runtime" == "k8s" ]]; then
        llama_cpp_status=$(k8s_pod_status "llama-cpp")
    fi

    # Detect local embedding models (sentence-transformers cache)
    if [[ -d "${HOME}/.cache/huggingface/sentence-transformers" ]]; then
        embedding_models=$(run_timeout 3 find "${HOME}/.cache/huggingface/sentence-transformers" -maxdepth 2 -mindepth 2 -type f -name "config.json" -printf '%h\n' 2>/dev/null | xargs -r -n1 basename | sort -u | maybe_jq -R -s -c 'split("\n") | map(select(length > 0))' || echo "[]")
    elif [[ -d "${HOME}/.cache/huggingface/hub" ]]; then
        embedding_models=$(run_timeout 3 find "${HOME}/.cache/huggingface/hub" -type f -path "*/models--sentence-transformers--*/snapshots/*/config.json" -printf '%p\n' 2>/dev/null | sed -n 's|.*/models--sentence-transformers--\\([^/]*\\)/.*|\\1|p' | sort -u | maybe_jq -R -s -c 'split("\n") | map(select(length > 0))' || echo "[]")
    fi

    embedding_model_name="${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
    embedding_model_name="${embedding_model_name:-sentence-transformers/all-MiniLM-L6-v2}"

    if curl_fast "${embeddings_endpoint}/health" > /dev/null 2>&1; then
        embeddings_status="online"
        embeddings_metrics=$(curl_fast "${embeddings_endpoint}/metrics" 2>/dev/null || true)
        if [[ -n "$embeddings_metrics" ]]; then
            embeddings_request_total=$(echo "$embeddings_metrics" | awk '/^embeddings_requests_total /{sum+=$2} END{printf "%.0f",sum+0}')
            embeddings_error_total=$(echo "$embeddings_metrics" | awk '/^embeddings_request_errors_total /{sum+=$2} END{printf "%.0f",sum+0}')
            embeddings_memory_mb=$(echo "$embeddings_metrics" | awk '/^embeddings_process_memory_bytes /{printf "%.1f",$2/1024/1024; exit}')
        fi
    elif [[ "$container_runtime" == "k8s" ]]; then
        embeddings_status=$(k8s_pod_status "embeddings")
    fi

    # Detect cached GGUF models for llama.cpp
    if [[ -d "${HOME}/.local/share/nixos-ai-stack/llama-cpp-models" ]]; then
        llama_cpp_cached_models=$(run_timeout 3 find "${HOME}/.local/share/nixos-ai-stack/llama-cpp-models" -maxdepth 2 -type f -name "*.gguf" -printf '%f\n' 2>/dev/null | sort -u | maybe_jq -R -s -c 'split("\n") | map(select(length > 0))' || echo "[]")
        llama_cpp_cached_count=$(echo "$llama_cpp_cached_models" | maybe_jq -r 'length' 2>/dev/null || echo "0")
    fi


    # Check PostgreSQL
    if [[ "$container_runtime" == "k8s" ]]; then
        postgres_status=$(k8s_pod_status "postgres")
    elif [[ "$container_runtime" == "podman" ]]; then
        if run_timeout 3 podman exec local-ai-postgres pg_isready -U "$postgres_user" > /dev/null 2>&1; then
            postgres_status="online"
        fi
    fi

    # Check Redis
    if [[ "$container_runtime" == "k8s" ]]; then
        redis_status=$(k8s_pod_status "redis")
    elif [[ "$container_runtime" == "podman" ]]; then
        if run_timeout 3 podman exec local-ai-redis redis-cli ping 2>/dev/null | grep -q PONG; then
            redis_status="online"
        fi
    fi

    # Check Open WebUI
    if [[ "$container_runtime" == "k8s" ]]; then
        open_webui_status=$(k8s_pod_status "open-webui")
    elif [[ "$container_runtime" == "podman" ]]; then
        if run_timeout 3 podman ps --filter "name=local-ai-open-webui" --filter "status=running" --format "{{.Names}}" 2>/dev/null | grep -q "local-ai-open-webui"; then
            open_webui_status="online"
        fi
    elif curl_fast "${OPEN_WEBUI_URL}" > /dev/null 2>&1; then
        open_webui_status="online"
    fi

    # Check MindsDB (optional)
    if curl_fast "${MINDSDB_URL}/api/util/ping" > /dev/null 2>&1; then
        mindsdb_status="online"
    elif [[ "$container_runtime" == "k8s" ]]; then
        mindsdb_status=$(k8s_pod_status "mindsdb")
    elif [[ "$container_runtime" == "podman" ]]; then
        if run_timeout 3 podman ps --filter "name=local-ai-mindsdb" --filter "status=running" --format "{{.Names}}" 2>/dev/null | grep -q "local-ai-mindsdb"; then
            mindsdb_status="starting"
        fi
    fi

    # Check AIDB MCP Server
    if curl_fast "${AIDB_URL}/health" > /dev/null 2>&1; then
        aidb_status="online"
        aidb_services=$(curl_fast "${AIDB_URL}/health" | maybe_jq -c '.services // {}' 2>/dev/null || echo "{}")
    elif [[ "$container_runtime" == "k8s" ]]; then
        aidb_status=$(k8s_pod_status "aidb")
    fi

    # Check Hybrid Coordinator MCP Server
    if curl_fast "${HYBRID_URL}/health" > /dev/null 2>&1; then
        hybrid_coordinator_status="online"
    elif [[ "$container_runtime" == "k8s" ]]; then
        hybrid_coordinator_status=$(k8s_pod_status "hybrid-coordinator")
    fi

    # Container stats
    local containers="[]"
    if [[ "$container_runtime" == "k8s" ]]; then
        if has_cmd kubectl; then
            containers=$(run_timeout 3 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "$namespace" -o json 2>/dev/null | maybe_jq -c '[.items[] | {name: .metadata.name, status: (.status.phase | ascii_downcase), image: (.spec.containers[0].image // "")}]' 2>/dev/null || echo "[]")
        fi
    elif [[ "$container_runtime" == "podman" ]]; then
        containers=$(run_timeout 3 podman ps --format json 2>/dev/null | maybe_jq -c '[.[] | {name: .Names[0], status: .State, image: .Image}]' || echo "[]")
    fi

    cat > "$DATA_DIR/llm.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "services": {
    "qdrant": {
      "status": "$qdrant_status",
      "collections": ${qdrant_collection_count:-0},
      "collection_names": ${qdrant_collections:-[]},
      "url": "${QDRANT_URL}"
    },
    "llama_cpp": {
      "status": "$llama_cpp_status",
      "models": ${llama_cpp_models:-[]},
      "cached_models": ${llama_cpp_cached_models:-[]},
      "cached_models_count": ${llama_cpp_cached_count:-0},
      "url": "${LLAMA_URL}"
    },
    "embeddings": {
      "status": "$embeddings_status",
      "model": "$embedding_model_name",
      "models": ${embedding_models:-[]},
      "source": "huggingface-cache",
      "request_total": ${embeddings_request_total:-0},
      "error_total": ${embeddings_error_total:-0},
      "memory_mb": ${embeddings_memory_mb:-0},
      "endpoint": "$embeddings_endpoint"
    },
    "postgres": {
      "status": "$postgres_status",
      "url": "${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}"
    },
    "redis": {
      "status": "$redis_status",
      "url": "${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}"
    },
    "open_webui": {
      "status": "$open_webui_status",
      "url": "${OPEN_WEBUI_URL}"
    },
    "mindsdb": {
      "status": "$mindsdb_status",
      "url": "${MINDSDB_URL}"
    },
    "aidb": {
      "status": "$aidb_status",
      "services": ${aidb_services},
      "url": "${AIDB_URL}"
    },
    "hybrid_coordinator": {
      "status": "$hybrid_coordinator_status",
      "url": "${HYBRID_URL}"
    }
  },
  "containers": ${containers}
}
EOF
}

# ============================================================================
# Network & Firewall Metrics
# ============================================================================
collect_network_metrics() {
    # Active connections
    local connections=$(run_timeout 2 ss -tun 2>/dev/null | wc -l)

    # Firewall rules count
    local firewall_rules="0"
    if has_cmd nft; then
        firewall_rules=$(run_timeout 2 nft list ruleset 2>/dev/null | grep -c "^[[:space:]]*rule" || echo "0")
    fi

    # Network interfaces
    local interfaces=$(run_timeout 2 ip -j addr show 2>/dev/null | maybe_jq -c '[.[] | select(.operstate == "UP") | {name: .ifname, address: .addr_info[0].local, state: .operstate}]')
    local primary_iface=""
    if has_cmd ip; then
        primary_iface=$(run_timeout 2 ip route show default 2>/dev/null | awk 'NR==1 {for (i=1; i<=NF; i++) if ($i=="dev") print $(i+1)}' | head -n1)
    fi
    primary_iface="${primary_iface:-}"

    local rx_bytes=0
    local tx_bytes=0
    if [[ -n "$primary_iface" && -r /proc/net/dev ]]; then
        read -r rx_bytes tx_bytes < <(awk -v iface="$primary_iface" '$1 ~ iface":" {gsub(":", "", $1); print $2, $10}' /proc/net/dev)
    fi

    # DNS status
    local dns_status="unknown"
    if [ -L /etc/resolv.conf ]; then
        dns_status="configured (symlink)"
    elif grep -q "nameserver" /etc/resolv.conf 2>/dev/null; then
        dns_status="configured (static)"
    else
        dns_status="misconfigured"
    fi

    # Listening ports
    local listening_ports=$(run_timeout 2 ss -tlnp 2>/dev/null | awk 'NR>1 {print $4}' | sed 's/.*://' | sort -n | uniq | maybe_jq -R . | maybe_jq -s -c .)
    local neighbors="[]"
    if has_cmd ip; then
        neighbors=$(run_timeout 2 ip -j neigh 2>/dev/null | maybe_jq -c '[.[] | {ip: .dst, mac: .lladdr, state: .state, dev: .dev}]' 2>/dev/null || echo "[]")
    fi

    cat > "$DATA_DIR/network.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "connections": {
    "active": $connections
  },
  "firewall": {
    "enabled": true,
    "rules_count": $firewall_rules
  },
  "interfaces": ${interfaces},
  "traffic": {
    "iface": "${primary_iface}",
    "rx_bytes": ${rx_bytes:-0},
    "tx_bytes": ${tx_bytes:-0}
  },
  "dns": {
    "status": "$dns_status",
    "resolvers": $(grep "^nameserver" /etc/resolv.conf 2>/dev/null | awk '{print $2}' | jq -R . | jq -s -c . || echo "[]")
  },
  "neighbors": ${neighbors},
  "listening_ports": ${listening_ports}
}
EOF
}

# ============================================================================
# Security Metrics
# ============================================================================
collect_security_metrics() {
    # Failed login attempts (last hour)
    local failed_logins=$(normalize_int "$(run_timeout 2 journalctl -u systemd-logind --since "1 hour ago" 2>/dev/null | grep -c "Failed" || echo "0")")

    # AppArmor status
    local apparmor_status="unknown"
    if run_timeout 2 systemctl is-active apparmor > /dev/null 2>&1; then
        apparmor_status="active"
    else
        apparmor_status="inactive"
    fi

    # Firewall status
    local firewall_status="active"

    # SELinux/AppArmor profiles
    local security_profiles=0
    if command -v aa-status > /dev/null 2>&1; then
        security_profiles=$(aa-status --profiled 2>/dev/null | head -1 | awk '{print $1}' || echo "0")
    fi

    # System updates available
    local updates_available="n/a"
    if has_cmd nixos-rebuild; then
        updates_available="check-manually"
    fi

    cat > "$DATA_DIR/security.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "authentication": {
    "failed_logins_1h": $failed_logins
  },
  "mandatory_access_control": {
    "apparmor": {
      "status": "$apparmor_status",
      "profiles_loaded": $security_profiles
    }
  },
  "firewall": {
    "status": "$firewall_status"
  },
  "updates": {
    "available": "$updates_available"
  }
}
EOF
}

# ============================================================================
# Persistence & Data Metrics
# ============================================================================
collect_persistence_metrics() {
    local data_root="$AI_STACK_DATA_ROOT"
    local device="unknown"
    local fstype="unknown"
    local mount_point="unknown"

    if [[ -d "$data_root" ]]; then
        device=$(df -P "$data_root" 2>/dev/null | awk 'NR==2{print $1}' || echo "unknown")
        mount_point=$(df -P "$data_root" 2>/dev/null | awk 'NR==2{print $6}' || echo "unknown")
        if df -T "$data_root" >/dev/null 2>&1; then
            fstype=$(df -T "$data_root" 2>/dev/null | awk 'NR==2{print $2}' || echo "unknown")
        fi
    fi

    cat > "$DATA_DIR/persistence.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "data_root": "$data_root",
  "mount": {
    "device": "$device",
    "filesystem": "$fstype",
    "mount_point": "$mount_point"
  },
  "paths": [
    {
      "name": "qdrant",
      "path": "${data_root}/qdrant",
      "exists": $(dir_exists "${data_root}/qdrant"),
      "size": "$(dir_size "${data_root}/qdrant")"
    },
    {
      "name": "llama_cpp",
      "path": "${data_root}/llama-cpp-models",
      "exists": $(dir_exists "${data_root}/llama-cpp-models"),
      "size": "$(dir_size "${data_root}/llama-cpp-models")"
    },
    {
      "name": "open-webui",
      "path": "${data_root}/open-webui",
      "exists": $(dir_exists "${data_root}/open-webui"),
      "size": "$(dir_size "${data_root}/open-webui")"
    },
    {
      "name": "postgres",
      "path": "${data_root}/postgres",
      "exists": $(dir_exists "${data_root}/postgres"),
      "size": "$(dir_size "${data_root}/postgres")"
    },
    {
      "name": "redis",
      "path": "${data_root}/redis",
      "exists": $(dir_exists "${data_root}/redis"),
      "size": "$(dir_size "${data_root}/redis")"
    },
    {
      "name": "mindsdb",
      "path": "${data_root}/mindsdb",
      "exists": $(dir_exists "${data_root}/mindsdb"),
      "size": "$(dir_size "${data_root}/mindsdb")"
    },
    {
      "name": "huggingface-cache",
      "path": "${HOME}/.cache/huggingface",
      "exists": $(dir_exists "${HOME}/.cache/huggingface"),
      "size": "$(dir_size "${HOME}/.cache/huggingface")"
    }
  ]
}
EOF
}

# ============================================================================
# Database Metrics (PostgreSQL)
# ============================================================================
collect_database_metrics() {
    local pg_status="offline"
    local pg_size="0"
    local pg_connections=0
    local redis_status="offline"
    local redis_keys=0
    local redis_memory="unknown"
    local qdrant_status="offline"
    local qdrant_collections=0
    local mindsdb_status="offline"
    local container_runtime
    container_runtime=$(detect_container_runtime)
    local pg_user="${AIDB_POSTGRES_USER:-${POSTGRES_USER:-mcp}}"
    local pg_db="${AIDB_POSTGRES_DB:-${POSTGRES_DB:-mcp}}"
    local pg_password_file="${AIDB_POSTGRES_PASSWORD_FILE:-${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}}"
    local redis_password_file="${AIDB_REDIS_PASSWORD_FILE:-${REDIS_PASSWORD_FILE:-/run/secrets/redis_password}}"
    local pg_password=""
    local redis_password=""

    if [[ -f "$pg_password_file" ]]; then
        pg_password=$(<"$pg_password_file")
    fi
    if [[ -f "$redis_password_file" ]]; then
        redis_password=$(<"$redis_password_file")
    fi


    k8s_pod_status() {
        local service="$1"
        if ! has_cmd kubectl; then
            echo "offline"
            return
        fi
        local status_json
        status_json=$(run_timeout 3 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "${AI_STACK_NAMESPACE:-ai-stack}" -l "io.kompose.service=${service}" -o json 2>/dev/null || echo "")
        if [[ -z "$status_json" ]]; then
            echo "offline"
            return
        fi
        if has_cmd jq; then
            local count
            local ready
            count=$(echo "$status_json" | jq -r '.items | length' 2>/dev/null || echo "0")
            ready=$(echo "$status_json" | jq -r '[.items[]?.status.containerStatuses[]?.ready] | any' 2>/dev/null || echo "false")
            if [[ "$count" == "0" ]]; then
                echo "offline"
            elif [[ "$ready" == "true" ]]; then
                echo "online"
            else
                echo "starting"
            fi
        else
            echo "online"
        fi
    }

    if [[ "$container_runtime" == "k8s" ]]; then
        pg_status=$(k8s_pod_status_global "postgres")
        redis_status=$(k8s_pod_status_global "redis")
        qdrant_status=$(k8s_pod_status_global "qdrant")
        mindsdb_status=$(k8s_pod_status_global "mindsdb")

        # Attempt to pull Qdrant collection count from dashboard-api
        local api_metrics
        api_metrics=$(curl_fast "${DASHBOARD_API_URL}/api/ai/metrics" 2>/dev/null || echo "")
        if echo "$api_metrics" | maybe_jq -e '.services.qdrant.metrics.collection_count' >/dev/null 2>&1; then
            qdrant_collections=$(echo "$api_metrics" | maybe_jq -r '.services.qdrant.metrics.collection_count' 2>/dev/null || echo "0")
        fi
    elif [[ "$container_runtime" == "podman" ]]; then
        if run_timeout 3 podman exec local-ai-postgres pg_isready -U "$pg_user" > /dev/null 2>&1; then
            pg_status="online"
            pg_size=$(run_timeout 3 podman exec --env "PGPASSWORD=$pg_password" local-ai-postgres \
                psql -U "$pg_user" -d "$pg_db" -t -c "SELECT pg_size_pretty(pg_database_size('$pg_db'));" \
                2>/dev/null | tr -d ' \n' || echo "unknown")
            pg_connections=$(run_timeout 3 podman exec --env "PGPASSWORD=$pg_password" local-ai-postgres \
                psql -U "$pg_user" -d "$pg_db" -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$pg_db';" \
                2>/dev/null | tr -d ' \n' || echo "0")
        fi

        if run_timeout 3 podman exec local-ai-redis redis-cli ${redis_password:+-a "$redis_password"} ping > /dev/null 2>&1; then
            redis_status="online"
            redis_keys=$(run_timeout 3 podman exec local-ai-redis redis-cli ${redis_password:+-a "$redis_password"} dbsize 2>/dev/null | tr -d ' \n' || echo "0")
            redis_memory=$(run_timeout 3 podman exec local-ai-redis redis-cli ${redis_password:+-a "$redis_password"} info memory 2>/dev/null \
                | awk -F: '/used_memory_human/ {print $2}' | tr -d '\r' | tr -d ' ' || echo "unknown")
        else
            redis_keys=0
            redis_memory="unknown"
        fi

        if curl_fast "${QDRANT_URL}/collections" > /dev/null 2>&1; then
            qdrant_status="online"
            qdrant_collections=$(curl_fast "${QDRANT_URL}/collections" | maybe_jq '.result.collections | length' 2>/dev/null || echo "0")
        fi

        if podman ps --format '{{.Names}}' | grep -q '^local-ai-mindsdb$'; then
            mindsdb_status="online"
        fi
    fi

    redis_keys=$(normalize_int "$redis_keys")
    if [[ -z "$redis_memory" ]]; then
        redis_memory="unknown"
    fi

    cat > "$DATA_DIR/database.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "postgresql": {
    "status": "$pg_status",
    "database_size": "$pg_size",
    "active_connections": $pg_connections
  },
  "redis": {
    "status": "$redis_status",
    "keys": $redis_keys,
    "memory_used": "$redis_memory"
  },
  "qdrant": {
    "status": "$qdrant_status",
    "collections": $qdrant_collections
  },
  "mindsdb": {
    "status": "$mindsdb_status"
  }
}
EOF
}

# ============================================================================
# Telemetry Metrics (AIDB)
# ============================================================================
collect_telemetry_metrics() {
    local telemetry_status="offline"
    local aidb_telemetry="${AIDB_TELEMETRY_PATH:-$AI_STACK_DATA_ROOT/telemetry/aidb-events.jsonl}"
    local hybrid_telemetry="${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl"
    local container_runtime
    container_runtime=$(detect_container_runtime)

    local total_events=0
    local local_events=0
    local remote_events=0
    local tokens_saved=0
    local last_event_at="N/A"
    local telemetry_path
    telemetry_path=$(resolve_tilde_path "$aidb_telemetry")
    local enabled=true
    local local_usage_rate=0.0

    # Check if AIDB is online
    if curl_fast "${AIDB_URL}/health" > /dev/null 2>&1; then
        telemetry_status="online"
    elif [[ "$container_runtime" == "k8s" ]]; then
        telemetry_status=$(k8s_pod_status_global "aidb")
    fi

    if [[ "$container_runtime" == "k8s" && "$(k8s_pod_status_global "aidb")" != "offline" ]]; then
        # Prefer in-cluster telemetry files when running on K8s
        local aidb_path="/data/telemetry/aidb-events.jsonl"
        local hybrid_path="/data/telemetry/hybrid-events.jsonl"
        telemetry_path="$aidb_path (k8s)"

        local aidb_total hybrid_total hybrid_local hybrid_remote
        local aidb_last_line hybrid_last_line
        aidb_total=$(normalize_int "$(k8s_file_line_count "aidb" "$aidb_path")")
        hybrid_total=$(normalize_int "$(k8s_file_line_count "hybrid-coordinator" "$hybrid_path")")

        aidb_last_line=$(k8s_tail_line "aidb" "$aidb_path")
        hybrid_last_line=$(k8s_tail_line "hybrid-coordinator" "$hybrid_path")

        if [[ -n "$aidb_last_line" ]]; then
            last_event_at=$(echo "$aidb_last_line" | maybe_jq -r '.timestamp // "N/A"' 2>/dev/null || echo "N/A")
        elif [[ -n "$hybrid_last_line" ]]; then
            last_event_at=$(echo "$hybrid_last_line" | maybe_jq -r '.timestamp // "N/A"' 2>/dev/null || echo "N/A")
        fi

        local_events=$(normalize_int "$(k8s_grep_count "aidb" "$aidb_path" "\"llm_used\":\"llama.cpp\"")")
        local_events=$((local_events + $(normalize_int "$(k8s_grep_count "aidb" "$aidb_path" "\"decision\":\"local\"")")))

        hybrid_local=$(normalize_int "$(k8s_grep_count "hybrid-coordinator" "$hybrid_path" "\"agent_type\":\"local\"")")
        hybrid_remote=$(normalize_int "$(k8s_grep_count "hybrid-coordinator" "$hybrid_path" "\"agent_type\":\"remote\"")")

        total_events=$((aidb_total + hybrid_total))
        local_events=$((local_events + hybrid_local))
        remote_events=$((remote_events + hybrid_remote))
    else
        # Count AIDB telemetry events (local filesystem)
        if [[ -f "$aidb_telemetry" ]]; then
            total_events=$(file_line_count "$aidb_telemetry")
            local last_line
            last_line=$(tail -n 1 "$aidb_telemetry" 2>/dev/null)
            if [[ -n "$last_line" ]]; then
                last_event_at=$(echo "$last_line" | maybe_jq -r '.timestamp' 2>/dev/null || echo "N/A")
            fi

            # Count events by LLM type (llama.cpp = local, others = remote)
            local_events=$(normalize_int "$(count_aidb_local_events "$aidb_telemetry")")
        fi

        # Add hybrid coordinator telemetry
        if [[ -f "$hybrid_telemetry" ]]; then
            local hybrid_total hybrid_local hybrid_remote
            hybrid_total=$(normalize_int "$(file_line_count "$hybrid_telemetry")")
            total_events=$((total_events + hybrid_total))

            # Count local vs remote from hybrid coordinator
            hybrid_local=$(normalize_int "$(count_jsonl_field "$hybrid_telemetry" "agent_type" "local")")
            local_events=$((local_events + hybrid_local))

            hybrid_remote=$(normalize_int "$(count_jsonl_field "$hybrid_telemetry" "agent_type" "remote")")
            remote_events=$((remote_events + hybrid_remote))
        fi
    fi

    # Calculate local usage rate
    if [[ $total_events -gt 0 ]]; then
        local_usage_rate=$(awk -v l="$local_events" -v t="$total_events" 'BEGIN {printf "%.1f", (l/t)*100}')
    fi

    # Estimate tokens saved (assume 12K tokens saved per local query)
    tokens_saved=$((local_events * 12000))

    cat > "$DATA_DIR/telemetry.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$telemetry_status",
  "summary": {
    "total_events": $total_events,
    "local_events": $local_events,
    "remote_events": $remote_events,
    "tokens_saved": $tokens_saved,
    "last_event_at": "$last_event_at",
    "telemetry_path": "$telemetry_path",
    "enabled": $enabled,
    "local_usage_rate": $local_usage_rate
  }
}
EOF
}

# ============================================================================
# Hybrid Coordinator Metrics
# ============================================================================
collect_hybrid_coordinator_metrics() {
    local coordinator_status="offline"
    local coordinator_health="{}"
    local context_cache_size=0
    local pattern_extraction_count=0
    local value_scores="[]"
    local telemetry_path="${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl"
    local finetune_path="${AI_STACK_DATA_ROOT}/fine-tuning/dataset.jsonl"
    local finetune_records=0
    local telemetry_records=0
    local last_event="{}"
    local avg_value_score="0.0"
    local high_value_count=0
    local container_runtime
    container_runtime=$(detect_container_runtime)

    # Check hybrid coordinator health
    if curl_fast "${HYBRID_URL}/health" > /dev/null 2>&1; then
        coordinator_status="online"
        coordinator_health=$(curl_fast "${HYBRID_URL}/health" | maybe_jq -c '.' 2>/dev/null || echo "{}")
    elif [[ "$container_runtime" == "k8s" ]]; then
        if has_cmd kubectl; then
            local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
            local ready
            ready=$(run_timeout 3 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "$namespace" -l "io.kompose.service=hybrid-coordinator" -o json 2>/dev/null | \
                maybe_jq -r '[.items[]?.status.containerStatuses[]?.ready] | any' 2>/dev/null || echo "false")
            if [[ "$ready" == "true" ]]; then
                coordinator_status="online"
            else
                coordinator_status="starting"
            fi
        fi
    fi

    # Count telemetry records
    if [[ -f "$telemetry_path" ]]; then
        telemetry_records=$(file_line_count "$telemetry_path")
        last_event=$(tail -n 1 "$telemetry_path" 2>/dev/null | maybe_jq -c '{timestamp, query_type, value_score, pattern_extracted}' 2>/dev/null || echo "{}")

        # Calculate average value score and high-value count (last 100 events)
        if [[ $telemetry_records -gt 0 ]]; then
            local scores_data
            scores_data=$(tail -n 100 "$telemetry_path" 2>/dev/null | maybe_jq -r 'select(.value_score != null) | .value_score' 2>/dev/null || echo "")
            if [[ -n "$scores_data" ]]; then
                avg_value_score=$(echo "$scores_data" | awk '{sum+=$1; count++} END {if(count>0) printf "%.3f", sum/count; else print "0.0"}')
                high_value_count=$(echo "$scores_data" | awk '$1 >= 0.7 {count++} END {print count+0}')
            fi

            # Get last 10 value scores for sparkline
            value_scores=$(tail -n 10 "$telemetry_path" 2>/dev/null | maybe_jq -s -c 'map(select(.value_score != null) | .value_score)' 2>/dev/null || echo "[]")
        fi
    fi

    # Count fine-tuning dataset records
    if [[ -f "$finetune_path" ]]; then
        finetune_records=$(file_line_count "$finetune_path")
    fi

    # Count pattern extractions
    if [[ -f "$telemetry_path" ]] && [[ $telemetry_records -gt 0 ]]; then
        pattern_extraction_count=$(normalize_int "$(grep -c '"pattern_extracted":true' "$telemetry_path" 2>/dev/null || echo "0")")
    fi

    cat > "$DATA_DIR/hybrid-coordinator.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$coordinator_status",
  "health": $coordinator_health,
  "telemetry": {
    "path": "$telemetry_path",
    "events": $telemetry_records,
    "last_event": $last_event,
    "avg_value_score": $avg_value_score,
    "high_value_count": $high_value_count,
    "value_scores_recent": $value_scores
  },
  "learning": {
    "pattern_extractions": $pattern_extraction_count,
    "finetune_dataset_path": "$finetune_path",
    "finetune_records": $finetune_records
  },
  "url": "${HYBRID_URL}"
}
EOF
}

# ============================================================================
# RAG Collections Metrics (Qdrant)
# ============================================================================
collect_rag_collections_metrics() {
    local qdrant_status="offline"
    local collections_data="[]"
    local total_points=0
    local total_collections=0

    # Expected collections based on COMPREHENSIVE-SYSTEM-ANALYSIS.md
    local expected_collections='["codebase-context","skills-patterns","error-solutions","interaction-history","best-practices"]'

    if curl_fast "${QDRANT_URL}/collections" > /dev/null 2>&1; then
        qdrant_status="online"

        # Get all collections
        local all_collections
        all_collections=$(curl_fast "${QDRANT_URL}/collections" | maybe_jq -c '.result.collections' 2>/dev/null || echo "[]")
        total_collections=$(echo "$all_collections" | maybe_jq -r 'length' 2>/dev/null || echo "0")

        # Build detailed collection data
        local collection_details="[]"
        for collection in codebase-context skills-patterns error-solutions interaction-history best-practices; do
            local exists="false"
            local points=0
            local vectors=0

            if curl_fast "${QDRANT_URL}/collections/$collection" > /dev/null 2>&1; then
                exists="true"
                local collection_info
                collection_info=$(curl_fast "${QDRANT_URL}/collections/$collection" 2>/dev/null)
                points=$(echo "$collection_info" | maybe_jq -r '.result.points_count // 0' 2>/dev/null || echo "0")
                vectors=$(echo "$collection_info" | maybe_jq -r '.result.vectors_count // 0' 2>/dev/null || echo "0")
                total_points=$((total_points + points))
            fi

            # Build JSON object for this collection
            local collection_obj
            collection_obj=$(cat <<COLLECTION_EOF
{
  "name": "$collection",
  "exists": $exists,
  "points": $points,
  "vectors": $vectors
}
COLLECTION_EOF
)
            if [[ "$collection_details" == "[]" ]]; then
                collection_details="[$collection_obj]"
            else
                collection_details=$(echo "$collection_details" | maybe_jq -c ". += [$collection_obj]" 2>/dev/null || echo "$collection_details")
            fi
        done

        collections_data="$collection_details"
    fi

    cat > "$DATA_DIR/rag-collections.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "qdrant_status": "$qdrant_status",
  "total_collections": $total_collections,
  "total_points": $total_points,
  "expected_collections": $expected_collections,
  "collections": $collections_data,
  "url": "${QDRANT_URL}/dashboard"
}
EOF
}

# ============================================================================
# Learning Metrics (Continuous Learning Framework)
# ============================================================================
collect_learning_metrics() {
    local aidb_telemetry="${AI_STACK_DATA_ROOT}/telemetry/aidb-events.jsonl"
    local hybrid_telemetry="${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl"
    local finetune_dataset="${AI_STACK_DATA_ROOT}/fine-tuning/dataset.jsonl"

    local total_interactions=0
    local high_value_interactions=0
    local pattern_extractions=0
    local finetune_samples=0
    local avg_value_score="0.0"
    local learning_rate="0.0"
    local last_7d_interactions=0
    local last_7d_high_value=0

    # Count AIDB telemetry
    if [[ -f "$aidb_telemetry" ]]; then
        total_interactions=$(file_line_count "$aidb_telemetry")
    fi

    # Count hybrid coordinator telemetry and calculate metrics
    if [[ -f "$hybrid_telemetry" ]]; then
        local hybrid_count
        hybrid_count=$(file_line_count "$hybrid_telemetry")
        total_interactions=$((total_interactions + hybrid_count))

        # High-value interactions (value_score >= 0.7)
        high_value_interactions=$(normalize_int "$(grep -c '"value_score":[0-9.]*[7-9][0-9.]*' "$hybrid_telemetry" 2>/dev/null || echo "0")")

        # Pattern extractions
        pattern_extractions=$(normalize_int "$(grep -c '"pattern_extracted":true' "$hybrid_telemetry" 2>/dev/null || echo "0")")

        # Average value score
        if [[ $hybrid_count -gt 0 ]]; then
            local scores
            scores=$(grep -o '"value_score":[0-9.]*' "$hybrid_telemetry" 2>/dev/null | cut -d: -f2 || echo "")
            if [[ -n "$scores" ]]; then
                avg_value_score=$(echo "$scores" | awk '{sum+=$1; count++} END {if(count>0) printf "%.3f", sum/count; else print "0.0"}')
            fi
        fi

        # Last 7 days metrics (use last 100 lines as approximation)
        if has_cmd date; then
            local seven_days_ago
            seven_days_ago=$(date -d '7 days ago' -Iseconds 2>/dev/null || date -v-7d -Iseconds 2>/dev/null || echo "")
            if [[ -n "$seven_days_ago" ]]; then
                last_7d_interactions=$(normalize_int "$(tail -n 100 "$hybrid_telemetry" 2>/dev/null | wc -l | tr -d ' ' || echo "0")")
                last_7d_high_value=$(normalize_int "$(tail -n 100 "$hybrid_telemetry" 2>/dev/null | grep -c '"value_score":[0-9.]*[7-9][0-9.]*' 2>/dev/null || echo "0")")
            fi
        fi
    fi

    # Fine-tuning dataset count
    if [[ -f "$finetune_dataset" ]]; then
        finetune_samples=$(file_line_count "$finetune_dataset")
    fi

    # Calculate learning rate (pattern extractions / total interactions)
    if [[ $total_interactions -gt 0 ]]; then
        learning_rate=$(awk "BEGIN {printf \"%.3f\", $pattern_extractions / $total_interactions}")
    fi

    cat > "$DATA_DIR/learning-metrics.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "interactions": {
    "total": $total_interactions,
    "high_value": $high_value_interactions,
    "last_7d": $last_7d_interactions,
    "last_7d_high_value": $last_7d_high_value
  },
  "patterns": {
    "extractions": $pattern_extractions,
    "learning_rate": $learning_rate
  },
  "value_scoring": {
    "avg_score": $avg_value_score,
    "threshold": 0.7
  },
  "fine_tuning": {
    "dataset_path": "$finetune_dataset",
    "samples": $finetune_samples
  },
  "telemetry_paths": {
    "aidb": "$aidb_telemetry",
    "hybrid": "$hybrid_telemetry"
  }
}
EOF
}

# ============================================================================
# Keyword Signals (Discovery Report Summary)
# ============================================================================
collect_keyword_signals() {
    local report_dir="${PROJECT_ROOT}/docs/development"
    local output_path="${DATA_DIR}/keyword-signals.json"
    local report_path
    report_path=$(ls -t "${report_dir}"/IMPROVEMENT-DISCOVERY-REPORT-*.md 2>/dev/null | head -n 1 || true)

    if [[ -z "$report_path" ]]; then
        cat > "$output_path" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "missing",
  "report_path": "",
  "candidates": [],
  "signals": [],
  "sources": [],
  "summary": {
    "candidate_count": 0,
    "signal_count": 0,
    "source_count": 0
  }
}
EOF
        return 0
    fi

    if has_cmd python3; then
        python3 - "$report_path" "$output_path" <<'PY'
import json
import sys
from datetime import datetime, timezone

report_path = sys.argv[1]
output_path = sys.argv[2]

with open(report_path, "r", encoding="utf-8") as handle:
    lines = handle.read().splitlines()

section = None
candidates = []
signals = []
sources = []
current = None

def flush_candidate():
    global current
    if current:
        candidates.append(current)
        current = None

for line in lines:
    if line.startswith("## "):
        flush_candidate()
        # More flexible section matching (case-insensitive, partial match)
        line_lower = line.lower()
        if "candidate" in line_lower and "summary" in line_lower:
            section = "candidates"
        elif "signal" in line_lower and "low" in line_lower:
            section = "signals"
        elif "source" in line_lower and "review" in line_lower:
            section = "sources"
        else:
            section = None
        continue

    if section == "candidates":
        if line.startswith("### "):
            flush_candidate()
            current = {"url": line[4:].strip(), "details": {}}
        elif line.startswith("- **") and current is not None:
            raw = line.split(":", 1)
            if len(raw) == 2:
                label = raw[0].replace("- **", "").replace("**", "").strip()
                val = raw[1].replace("**", "").strip()
                if label.lower() == "score":
                    try:
                        current["score"] = float(val)
                    except ValueError:
                        current["score"] = val
                elif label.lower() == "release url":
                    current["release_url"] = val
                elif label.lower() == "latest release":
                    current["release"] = val
                elif label.lower() == "repo":
                    current["repo"] = val
                elif label.lower() == "stars":
                    try:
                        current["stars"] = int(val.replace(",", ""))
                    except ValueError:
                        current["stars"] = val
                else:
                    current["details"][label] = val
        elif not line.strip():
            flush_candidate()
    elif section == "signals":
        if line.startswith("- "):
            entry = line[2:].strip()
            note = ""
            if " (" in entry and entry.endswith(")"):
                entry, note = entry.rsplit(" (", 1)
                note = note[:-1]
            signals.append({"url": entry.strip(), "note": note})
    elif section == "sources":
        if line.startswith("### "):
            sources.append({"url": line[4:].strip()})
        elif line.startswith("- **") and sources:
            raw = line.split("**:", 1)
            if len(raw) == 2:
                label = raw[0].replace("- **", "").replace("**", "").strip()
                val = raw[1].strip()
                sources[-1][label.lower().replace(" ", "_")] = val

flush_candidate()

payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "status": "ok",
    "report_path": report_path,
    "candidates": candidates,
    "signals": signals,
    "sources": sources,
    "summary": {
        "candidate_count": len(candidates),
        "signal_count": len(signals),
        "source_count": len(sources),
    },
}

with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
PY
    else
        cat > "$output_path" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "missing_python",
  "report_path": "$report_path",
  "candidates": [],
  "signals": [],
  "sources": [],
  "summary": {
    "candidate_count": 0,
    "signal_count": 0,
    "source_count": 0
  }
}
EOF
    fi
}

# ============================================================================
# Token Savings Metrics
# ============================================================================
collect_token_savings_metrics() {
    local hybrid_telemetry="${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl"
    local total_queries=0
    local local_queries=0
    local remote_queries=0
    local cached_queries=0
    local avg_tokens_per_query=3000
    local baseline_tokens_per_query=15000
    local estimated_savings=0
    local local_routing_percent="0.0"
    local cache_hit_rate="0.0"
    local cost_per_million_tokens=15.0
    local estimated_cost_savings="0.00"

    if [[ -f "$hybrid_telemetry" ]]; then
        total_queries=$(normalize_int "$(file_line_count "$hybrid_telemetry")")

        if [[ $total_queries -gt 0 ]]; then
            # Count local vs remote routing
            local_queries=$(normalize_int "$(grep -c '"agent_type":"local"' "$hybrid_telemetry" 2>/dev/null || echo "0")")
            remote_queries=$(normalize_int "$(grep -c '"agent_type":"remote"' "$hybrid_telemetry" 2>/dev/null || echo "0")")
            cached_queries=$(normalize_int "$(grep -c '"cached":true' "$hybrid_telemetry" 2>/dev/null || echo "0")")

            # Calculate percentages
            if [[ $total_queries -gt 0 ]]; then
                local_routing_percent=$(awk -v l="$local_queries" -v t="$total_queries" 'BEGIN {if(t>0) printf "%.1f", (l/t)*100; else printf "0.0"}')
                cache_hit_rate=$(awk -v c="$cached_queries" -v t="$total_queries" 'BEGIN {if(t>0) printf "%.1f", (c/t)*100; else printf "0.0"}')
            fi

            # Estimate token savings
            # Baseline: 15,000 tokens per query (full docs loaded)
            # With RAG: 3,000 tokens per remote query + 0 tokens for local queries
            local baseline_total=$((total_queries * baseline_tokens_per_query))
            local actual_total=$((remote_queries * avg_tokens_per_query))
            estimated_savings=$((baseline_total - actual_total))

            # Estimate cost savings (assuming $15 per million tokens)
            estimated_cost_savings=$(awk -v s="$estimated_savings" -v c="$cost_per_million_tokens" 'BEGIN {printf "%.2f", (s/1000000)*c}')
        fi
    fi

    cat > "$DATA_DIR/token-savings.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "queries": {
    "total": $total_queries,
    "local": $local_queries,
    "remote": $remote_queries,
    "cached": $cached_queries
  },
  "routing": {
    "local_percent": $local_routing_percent,
    "remote_percent": $(awk -v l="$local_routing_percent" 'BEGIN {printf "%.1f", 100 - l}'),
    "target_local_percent": 70.0
  },
  "cache": {
    "hit_rate": $cache_hit_rate,
    "target_hit_rate": 30.0
  },
  "tokens": {
    "baseline_per_query": $baseline_tokens_per_query,
    "rag_per_query": $avg_tokens_per_query,
    "estimated_savings": $estimated_savings,
    "reduction_percent": $(awk -v b="$baseline_tokens_per_query" -v a="$avg_tokens_per_query" 'BEGIN {if(b>0) printf "%.1f", ((b-a)/b)*100; else print "0.0"}')
  },
  "cost": {
    "estimated_savings_usd": $estimated_cost_savings,
    "cost_per_million_tokens": $cost_per_million_tokens,
    "period": "cumulative"
  }
}
EOF
}

# ============================================================================
# Feedback Pipeline Metrics
# ============================================================================
collect_feedback_pipeline_metrics() {
    local aidb_status="offline"
    local telemetry_path="${AIDB_TELEMETRY_PATH:-$AI_STACK_DATA_ROOT/telemetry/aidb-events.jsonl}"
    local hybrid_path="${HYBRID_TELEMETRY_PATH:-$AI_STACK_DATA_ROOT/telemetry/hybrid-events.jsonl}"
    local container_runtime
    container_runtime=$(detect_container_runtime)

    if curl_fast "${AIDB_URL}/health" > /dev/null 2>&1; then
        aidb_status="online"
    elif [[ "$container_runtime" == "k8s" ]]; then
        aidb_status=$(k8s_pod_status_global "aidb")
    fi

    if [[ "$container_runtime" == "k8s" ]]; then
        telemetry_path="/data/telemetry/aidb-events.jsonl"
        hybrid_path="/data/telemetry/hybrid-events.jsonl"
    fi

    local aidb_exists
    local aidb_bytes
    local aidb_last
    local hybrid_exists
    local hybrid_bytes
    local hybrid_last

    if [[ "$container_runtime" == "k8s" ]]; then
        aidb_bytes=$(k8s_file_size_bytes "aidb" "$telemetry_path")
        aidb_exists=$([[ "$aidb_bytes" != "0" ]] && echo "true" || echo "false")
        aidb_last=$(k8s_tail_line "aidb" "$telemetry_path")
        aidb_last=$(echo "$aidb_last" | maybe_jq -r '.timestamp // empty' 2>/dev/null || echo "")

        hybrid_bytes=$(k8s_file_size_bytes "hybrid-coordinator" "$hybrid_path")
        hybrid_exists=$([[ "$hybrid_bytes" != "0" ]] && echo "true" || echo "false")
        hybrid_last=$(k8s_tail_line "hybrid-coordinator" "$hybrid_path")
        hybrid_last=$(echo "$hybrid_last" | maybe_jq -r '.timestamp // empty' 2>/dev/null || echo "")
    else
        aidb_exists=$(file_exists "$telemetry_path")
        aidb_bytes=$(file_size_bytes "$telemetry_path")
        aidb_last=$(last_event_timestamp "$telemetry_path")

        hybrid_exists=$(file_exists "$hybrid_path")
        hybrid_bytes=$(file_size_bytes "$hybrid_path")
        hybrid_last=$(last_event_timestamp "$hybrid_path")
    fi

    cat > "$DATA_DIR/feedback.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "aidb_status": "$aidb_status",
  "telemetry": {
    "path": "$telemetry_path",
    "exists": $aidb_exists,
    "bytes": $aidb_bytes,
    "last_event_at": "$aidb_last"
  },
  "hybrid": {
    "path": "$hybrid_path",
    "exists": $hybrid_exists,
    "bytes": $hybrid_bytes,
    "last_event_at": "$hybrid_last"
  }
}
EOF
}

# ============================================================================
# Local Proof Metrics (Local LLM + RAG + Skills + Orchestration)
# ============================================================================
collect_local_proof_metrics() {
    local aidb_status="offline"
    local qdrant_collections="[]"
    local qdrant_collection_count=0
    local llama_cpp_model_count=0
    local skills_count=0
    local telemetry_path="${AIDB_TELEMETRY_PATH:-$AI_STACK_DATA_ROOT/telemetry/aidb-events.jsonl}"
    local telemetry_events
    local last_telemetry_event="{}"
    local skill_samples="[]"
    local container_runtime
    local container_count=0

    telemetry_events=$(file_line_count "$telemetry_path")
    if [[ -f "$telemetry_path" ]]; then
        last_telemetry_event=$(tail -n 1 "$telemetry_path" | maybe_jq -c '{timestamp: .timestamp, event_type: .event_type, source: .source, llm_used: .llm_used, model: .model}' 2>/dev/null || echo "{}")
    fi

    if curl_fast "${AIDB_URL}/health" > /dev/null 2>&1; then
        aidb_status="online"
    fi

    if curl_fast "${QDRANT_URL}/collections" > /dev/null 2>&1; then
        qdrant_collections=$(curl_fast "${QDRANT_URL}/collections" | maybe_jq -c '.result.collections | map(.name)' 2>/dev/null || echo "[]")
        qdrant_collection_count=$(echo "$qdrant_collections" | maybe_jq -r 'length' 2>/dev/null || echo "0")
    fi

    if curl_fast "${LLAMA_URL}/v1/models" > /dev/null 2>&1; then
        llama_cpp_model_count=$(curl_fast "${LLAMA_URL}/v1/models" | maybe_jq -r '.data | length' 2>/dev/null || echo "0")
    fi

    if curl_fast "${AIDB_URL}/skills" > /dev/null 2>&1; then
        local skills_payload
        skills_payload=$(curl_fast "${AIDB_URL}/skills" | maybe_jq -c '.' 2>/dev/null || echo "[]")
        skills_count=$(echo "$skills_payload" | maybe_jq -r 'length' 2>/dev/null || echo "0")
        skill_samples=$(echo "$skills_payload" | maybe_jq -c '.[0:5] | map(.slug // .name // .id)' 2>/dev/null || echo "[]")
    fi

    container_runtime=$(detect_container_runtime)
    if [[ "$container_runtime" == "k8s" ]]; then
        if has_cmd kubectl; then
            container_count=$(run_timeout 3 kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "${AI_STACK_NAMESPACE:-ai-stack}" -o json 2>/dev/null | maybe_jq -r '.items | length' 2>/dev/null || echo "0")
        fi
    elif [[ "$container_runtime" == "podman" ]]; then
        container_count=$(run_timeout 3 podman ps --format json 2>/dev/null | maybe_jq -r 'length' 2>/dev/null || echo "0")
    elif [[ "$container_runtime" == "docker" ]]; then
        container_count=$(run_timeout 3 docker ps --format json 2>/dev/null | maybe_jq -r 'length' 2>/dev/null || echo "0")
    fi

    cat > "$DATA_DIR/proof.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "aidb_status": "$aidb_status",
  "rag": {
    "qdrant_collections": ${qdrant_collections:-[]},
    "collection_count": ${qdrant_collection_count:-0}
  },
  "llm": {
    "llama_cpp_models": ${llama_cpp_model_count:-0}
  },
  "skills": {
    "count": ${skills_count:-0},
    "samples": ${skill_samples:-[]}
  },
  "telemetry": {
    "path": "$telemetry_path",
    "events": ${telemetry_events:-0},
    "last_event": ${last_telemetry_event}
  },
  "orchestration": {
    "runtime": "${container_runtime}",
    "containers_running": ${container_count:-0}
  }
}
EOF
}

# ============================================================================
# Configuration Snapshot (for dashboard controls)
# ============================================================================
collect_config_metrics() {
    local aidb_port="${AIDB_PORT:-8091}"
    local llama_cpp_port="${LLAMA_CPP_PORT:-8080}"
    local qdrant_port="${QDRANT_PORT:-6333}"
    local open_webui_port="${OPEN_WEBUI_PORT:-3001}"
    local postgres_port="${POSTGRES_PORT:-5432}"
    local redis_port="${REDIS_PORT:-6379}"
    local aidb_config="${AIDB_CONFIG:-${AIDB_LOCAL_CONFIG}}"
    local telemetry_path="${AIDB_TELEMETRY_PATH:-${AI_STACK_DATA_ROOT}/telemetry/aidb-events.jsonl}"
    local hybrid_telemetry_path="${HYBRID_TELEMETRY_PATH:-${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl}"
    local dashboard_refresh="${DASHBOARD_COLLECT_INTERVAL:-15}"
    local telemetry_stale="${TELEMETRY_STALE_MINUTES:-30}"
    local dashboard_data_dir="${HOME}/.local/share/nixos-system-dashboard"
    local host_name
    local user_uid
    local sshd_password_auth
    local sshd_root_login
    local firewall_enabled
    local openssh_enabled
    local fail2ban_enabled
    local tailscale_enabled
    local auto_upgrade_enabled
    local auto_upgrade_schedule
    local nixos_version
    local kernel_version
    local nix_gc_enabled
    local nix_gc_schedule
    local nix_gc_older_than
    local nix_optimise
    local zram_enabled
    local swap_devices
    local journald_storage
    local journald_system_max_use
    local journald_runtime_max_use
    local swappiness
    local inotify_watches
    local ip_forward
    local container_runtime
    local ai_stack_start_cmd
    local ai_stack_stop_cmd
    local ai_stack_restart_cmd
    local ai_stack_clean_restart_cmd
    local ai_stack_clean_aidb_cmd
    local ai_stack_logs_aidb_cmd
    local ai_stack_logs_qdrant_cmd
    local ai_stack_logs_llama_cmd
    local ai_stack_logs_webui_cmd
    local list_containers_cmd
    local container_disk_cmd
    local container_connections_cmd

    sshd_password_auth=$(read_sshd_config_value "PasswordAuthentication")
    sshd_root_login=$(read_sshd_config_value "PermitRootLogin")
    firewall_enabled=$(read_nixos_option "networking.firewall.enable")
    openssh_enabled=$(read_nixos_option "services.openssh.enable")
    fail2ban_enabled=$(read_nixos_option "services.fail2ban.enable")
    tailscale_enabled=$(read_nixos_option "services.tailscale.enable")
    auto_upgrade_enabled=$(read_nixos_option "system.autoUpgrade.enable")
    auto_upgrade_schedule=$(read_nixos_option "system.autoUpgrade.dates")
    nixos_version=$(os_release_value "VERSION")
    kernel_version=$(uname -r)
    nix_gc_enabled=$(read_nixos_option "nix.gc.automatic")
    nix_gc_schedule=$(read_nixos_option "nix.gc.dates")
    nix_gc_older_than=$(read_nixos_option "nix.gc.options")
    nix_optimise=$(read_nixos_option "nix.optimise.automatic")
    zram_enabled=$(read_nixos_option "zramSwap.enable")
    swap_devices=$(read_nixos_option "swapDevices")
    journald_storage=$(read_journald_value "Storage")
    journald_system_max_use=$(read_journald_value "SystemMaxUse")
    journald_runtime_max_use=$(read_journald_value "RuntimeMaxUse")
    swappiness=$(sysctl_value "vm.swappiness")
    inotify_watches=$(sysctl_value "fs.inotify.max_user_watches")
    ip_forward=$(sysctl_value "net.ipv4.ip_forward")
    host_name=$(hostname)
    user_uid=$(id -u)
    container_runtime=$(detect_container_runtime)

    ai_stack_start_cmd="podman start local-ai-qdrant local-ai-postgres local-ai-redis local-ai-llama-cpp local-ai-open-webui local-ai-aidb local-ai-hybrid-coordinator"
    ai_stack_stop_cmd="podman stop local-ai-qdrant local-ai-postgres local-ai-redis local-ai-llama-cpp local-ai-open-webui local-ai-aidb local-ai-hybrid-coordinator"
    ai_stack_restart_cmd="podman restart local-ai-qdrant local-ai-postgres local-ai-redis local-ai-llama-cpp local-ai-open-webui local-ai-aidb local-ai-hybrid-coordinator"
    ai_stack_clean_restart_cmd="$ai_stack_restart_cmd"
    ai_stack_clean_aidb_cmd="podman restart local-ai-aidb"
    ai_stack_logs_aidb_cmd="podman logs --tail 200 local-ai-aidb"
    ai_stack_logs_qdrant_cmd="podman logs --tail 200 local-ai-qdrant"
    ai_stack_logs_llama_cmd="podman logs --tail 200 local-ai-llama-cpp"
    ai_stack_logs_webui_cmd="podman logs --tail 200 local-ai-open-webui"
    list_containers_cmd="podman ps --all"
    container_disk_cmd="podman system df"
    container_connections_cmd="podman system connection list"

    if [[ "$container_runtime" == "k8s" ]]; then
        ai_stack_start_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} scale deployment -l nixos.quick-deploy.ai-stack=true --replicas=1"
        ai_stack_stop_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} scale deployment -l nixos.quick-deploy.ai-stack=true --replicas=0"
        ai_stack_restart_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} rollout restart deployment -l nixos.quick-deploy.ai-stack=true"
        ai_stack_clean_restart_cmd="./scripts/k8s-clean-restart.sh"
        ai_stack_clean_aidb_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} rollout restart deployment/aidb"
        ai_stack_logs_aidb_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} logs deploy/aidb --tail 200"
        ai_stack_logs_qdrant_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} logs deploy/qdrant --tail 200"
        ai_stack_logs_llama_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} logs deploy/llama-cpp --tail 200"
        ai_stack_logs_webui_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} logs deploy/open-webui --tail 200"
        list_containers_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} get pods"
        container_disk_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} get pods -o wide"
        container_connections_cmd="kubectl --request-timeout=${KUBECTL_TIMEOUT}s -n ${AI_STACK_NAMESPACE:-ai-stack} get svc"
    fi

    podman_socket="${podman_socket:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock}"
    aidb_port="${aidb_port:-8091}"
    llama_cpp_port="${llama_cpp_port:-8080}"
    qdrant_port="${qdrant_port:-6333}"
    postgres_port="${postgres_port:-5432}"
    redis_port="${redis_port:-6379}"
    aidb_config="${aidb_config:-/app/config/config.yaml}"
    telemetry_path="${telemetry_path:-${AI_STACK_DATA_ROOT}/telemetry/aidb-events.jsonl}"
    hybrid_telemetry_path="${hybrid_telemetry_path:-${AI_STACK_DATA_ROOT}/telemetry/hybrid-events.jsonl}"

    cat > "$DATA_DIR/config.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "env_file": "$env_file",
  "required_services": [
    "qdrant",
    "llama_cpp",
    "postgres",
    "redis",
    "open_webui",
    "aidb",
    "mindsdb",
    "hybrid_coordinator"
  ],
  "settings": [
    {
      "label": "AI Stack Data Root",
      "value": "${AI_STACK_DATA_ROOT}",
      "path": "$env_file",
      "hint": "Set AI_STACK_DATA to relocate persisted services."
    },
    {
      "label": "AI Stack Config Root",
      "value": "${AI_STACK_CONFIG:-$HOME/.config/nixos-ai-stack}",
      "path": "$env_file",
      "hint": "Set AI_STACK_CONFIG to relocate stack settings."
    },
    {
      "label": "Dashboard Data Dir",
      "value": "${dashboard_data_dir}",
      "path": "scripts/generate-dashboard-data.sh",
      "hint": "Dashboard JSON output directory."
    },
    {
      "label": "AIDB Port",
      "value": "${aidb_port}",
      "path": "$env_file",
      "hint": "Controls AIDB MCP server port."
    },
    {
      "label": "llama.cpp Port",
      "value": "${llama_cpp_port}",
      "path": "$env_file",
      "hint": "Controls llama.cpp inference server port."
    },
    {
      "label": "NixOS Version",
      "value": "${nixos_version:-unknown}",
      "path": "/etc/os-release",
      "hint": "System release version."
    },
    {
      "label": "Kernel Version",
      "value": "${kernel_version}",
      "path": "runtime",
      "hint": "Active Linux kernel."
    },
    {
      "label": "Nix GC Automatic",
      "value": "${nix_gc_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "nix.gc.automatic"
    },
    {
      "label": "Nix GC Schedule",
      "value": "${nix_gc_schedule:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "nix.gc.dates"
    },
    {
      "label": "Nix GC Options",
      "value": "${nix_gc_older_than:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "nix.gc.options"
    },
    {
      "label": "Nix Optimise Store",
      "value": "${nix_optimise:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "nix.optimise.automatic"
    },
    {
      "label": "ZRAM Enabled",
      "value": "${zram_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "zramSwap.enable"
    },
    {
      "label": "Swap Devices",
      "value": "${swap_devices:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "swapDevices"
    },
    {
      "label": "Journald Storage",
      "value": "${journald_storage:-unknown}",
      "path": "/etc/systemd/journald.conf",
      "hint": "Storage"
    },
    {
      "label": "Journald System Max Use",
      "value": "${journald_system_max_use:-unknown}",
      "path": "/etc/systemd/journald.conf",
      "hint": "SystemMaxUse"
    },
    {
      "label": "Journald Runtime Max Use",
      "value": "${journald_runtime_max_use:-unknown}",
      "path": "/etc/systemd/journald.conf",
      "hint": "RuntimeMaxUse"
    },
    {
      "label": "Swappiness",
      "value": "${swappiness:-unknown}",
      "path": "sysctl",
      "hint": "vm.swappiness"
    },
    {
      "label": "Inotify Watches",
      "value": "${inotify_watches:-unknown}",
      "path": "sysctl",
      "hint": "fs.inotify.max_user_watches"
    },
    {
      "label": "IPv4 Forwarding",
      "value": "${ip_forward:-unknown}",
      "path": "sysctl",
      "hint": "net.ipv4.ip_forward"
    },
    {
      "label": "AIDB Config Path",
      "value": "${aidb_config}",
      "path": "$env_file",
      "hint": "Config file used by AIDB MCP server."
    },
    {
      "label": "llama.cpp Port",
      "value": "${llama_cpp_port}",
      "path": "$env_file",
      "hint": "Controls llama.cpp inference port."
    },
    {
      "label": "Open WebUI Port",
      "value": "${open_webui_port}",
      "path": "$env_file",
      "hint": "Open WebUI service port."
    },
    {
      "label": "Qdrant Port",
      "value": "${qdrant_port}",
      "path": "$env_file",
      "hint": "Controls Qdrant HTTP port."
    },
    {
      "label": "Firewall Enabled",
      "value": "${firewall_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "networking.firewall.enable"
    },
    {
      "label": "OpenSSH Enabled",
      "value": "${openssh_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "services.openssh.enable"
    },
    {
      "label": "OpenSSH Password Auth",
      "value": "${sshd_password_auth:-unknown}",
      "path": "/etc/ssh/sshd_config",
      "hint": "PasswordAuthentication"
    },
    {
      "label": "OpenSSH Root Login",
      "value": "${sshd_root_login:-unknown}",
      "path": "/etc/ssh/sshd_config",
      "hint": "PermitRootLogin"
    },
    {
      "label": "Fail2ban Enabled",
      "value": "${fail2ban_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "services.fail2ban.enable"
    },
    {
      "label": "Tailscale Enabled",
      "value": "${tailscale_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "services.tailscale.enable"
    },
    {
      "label": "Auto Upgrade Enabled",
      "value": "${auto_upgrade_enabled:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "system.autoUpgrade.enable"
    },
    {
      "label": "Auto Upgrade Schedule",
      "value": "${auto_upgrade_schedule:-unknown}",
      "path": "/etc/nixos/configuration.nix",
      "hint": "system.autoUpgrade.dates"
    },
    {
      "label": "PostgreSQL Port",
      "value": "${postgres_port}",
      "path": "$env_file",
      "hint": "PostgreSQL service port."
    },
    {
      "label": "Redis Port",
      "value": "${redis_port}",
      "path": "$env_file",
      "hint": "Redis service port."
    },
    {
      "label": "AIDB Telemetry Path",
      "value": "${telemetry_path}",
      "path": "$env_file",
      "hint": "AIDB JSONL telemetry output."
    },
    {
      "label": "Hybrid Telemetry Path",
      "value": "${hybrid_telemetry_path}",
      "path": "$env_file",
      "hint": "Hybrid coordinator telemetry output."
    },
    {
      "label": "Dashboard Refresh (seconds)",
      "value": "${dashboard_refresh}",
      "path": "launch-dashboard.sh",
      "hint": "Set DASHBOARD_COLLECT_INTERVAL to adjust refresh cadence."
    },
    {
      "label": "Telemetry Stale Threshold (minutes)",
      "value": "${telemetry_stale}",
      "path": "scripts/verify-local-llm-feedback.sh",
      "hint": "Set TELEMETRY_STALE_MINUTES to change stale warnings."
    },
    {
      "label": "Podman Socket",
      "value": "${podman_socket}",
      "path": "runtime",
      "hint": "Rootless Podman socket path."
    },
    {
      "label": "Podman Socket Status",
      "value": "$(systemd_is_active podman.socket)",
      "path": "systemd",
      "hint": "Podman rootless socket unit state."
    },
    {
      "label": "OpenSSH Service Status",
      "value": "$(systemd_is_active sshd)",
      "path": "systemd",
      "hint": "OpenSSH daemon service state."
    },
    {
      "label": "Tailscale Service Status",
      "value": "$(systemd_is_active tailscaled)",
      "path": "systemd",
      "hint": "Tailscale daemon service state."
    },
    {
      "label": "Firewall Service Status",
      "value": "$(systemd_is_active nftables)",
      "path": "systemd",
      "hint": "nftables firewall service state."
    },
    {
      "label": "Fail2ban Service Status",
      "value": "$(systemd_is_active fail2ban)",
      "path": "systemd",
      "hint": "Fail2ban service state."
    },
    {
      "label": "Kubernetes Manifests",
      "value": "ai-stack/kubernetes/kustomization.yaml",
      "path": "ai-stack/kubernetes/kustomization.yaml",
      "hint": "Primary AI stack Kubernetes definition."
    }
  ],
  "actions": [
    {
      "label": "Grant Podman Desktop Socket",
      "command": "flatpak override --user --filesystem=xdg-run/podman io.podman_desktop.PodmanDesktop",
      "mode": "run",
      "category": "Desktop"
    },
    {
      "label": "Create Podman Connection",
      "command": "podman system connection add local unix:///run/user/${user_uid}/podman/podman.sock --default",
      "mode": "run",
      "category": "Containers"
    },
    {
      "label": "Restart Podman Socket",
      "command": "systemctl --user restart podman.socket",
      "mode": "run",
      "category": "Containers"
    },
    {
      "label": "Restart OpenSSH",
      "command": "sudo -n systemctl restart sshd",
      "mode": "run",
      "category": "Security"
    },
    {
      "label": "Restart Firewall (nftables)",
      "command": "sudo -n systemctl restart nftables",
      "mode": "run",
      "category": "Security"
    },
    {
      "label": "Show Firewall Rules",
      "command": "sudo -n nft list ruleset",
      "mode": "run",
      "category": "Security"
    },
    {
      "label": "Restart Tailscale",
      "command": "sudo -n systemctl restart tailscaled",
      "mode": "run",
      "category": "Security"
    },
    {
      "label": "Restart Fail2ban",
      "command": "sudo -n systemctl restart fail2ban",
      "mode": "run",
      "category": "Security"
    },
    {
      "label": "Vacuum Journald (500M)",
      "command": "sudo -n journalctl --vacuum-size=500M",
      "mode": "run",
      "category": "Observability"
    },
    {
      "label": "Show System Journal (Last 200)",
      "command": "journalctl -n 200",
      "mode": "run",
      "category": "Observability"
    },
    {
      "label": "Journal Disk Usage",
      "command": "journalctl --disk-usage",
      "mode": "run",
      "category": "Observability"
    },
    {
      "label": "Force Logrotate",
      "command": "sudo -n logrotate -f /etc/logrotate.conf",
      "mode": "run",
      "category": "Observability"
    },
    {
      "label": "List Listening Ports",
      "command": "ss -tuln",
      "mode": "run",
      "category": "Diagnostics"
    },
    {
      "label": "Process Snapshot",
      "command": "awk '/^cpu /{print; exit}' /proc/stat",
      "mode": "run",
      "category": "Diagnostics"
    },
    {
      "label": "Nix Store GC",
      "command": "sudo -n nix-collect-garbage -d",
      "mode": "run",
      "category": "System"
    },
    {
      "label": "Nix Store Optimise",
      "command": "sudo -n nix-store --optimise",
      "mode": "run",
      "category": "System"
    },
    {
      "label": "Reload systemd Daemon",
      "command": "sudo -n systemctl daemon-reload",
      "mode": "run",
      "category": "System"
    },
    {
      "label": "System Update Check",
      "command": "nix-channel --update",
      "mode": "run",
      "category": "System"
    },
    {
      "label": "Show IP Addresses",
      "command": "ip a",
      "mode": "run",
      "category": "Network"
    },
    {
      "label": "DNS Status",
      "command": "resolvectl status",
      "mode": "run",
      "category": "Network"
    },
    {
      "label": "Ping 1.1.1.1",
      "command": "ping -c 3 1.1.1.1",
      "mode": "run",
      "category": "Network"
    },
    {
      "label": "Disk Usage (Root)",
      "command": "df -B1 /",
      "mode": "run",
      "category": "Diagnostics"
    },
    {
      "label": "Memory Snapshot",
      "command": "free -h",
      "mode": "run",
      "category": "Diagnostics"
    },
    {
      "label": "Start AI Stack",
      "command": "${ai_stack_start_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "Stop AI Stack",
      "command": "${ai_stack_stop_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "Clean Restart AI Stack",
      "command": "${ai_stack_clean_restart_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "Clean Restart AIDB",
      "command": "${ai_stack_clean_aidb_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "AI Stack Logs (AIDB)",
      "command": "${ai_stack_logs_aidb_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "AI Stack Logs (Qdrant)",
      "command": "${ai_stack_logs_qdrant_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "AI Stack Logs (llama.cpp)",
      "command": "${ai_stack_logs_llama_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "AI Stack Logs (Open WebUI)",
      "command": "${ai_stack_logs_webui_cmd}",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "AI Stack Health Check",
      "command": "python3 scripts/check-ai-stack-health-v2.py -v",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "Dashboard Data Refresh",
      "command": "bash scripts/generate-dashboard-data.sh",
      "mode": "run",
      "category": "Dashboard"
    },
    {
      "label": "Run Feedback Verification",
      "command": "./scripts/verify-local-llm-feedback.sh",
      "mode": "run",
      "category": "AI Stack"
    },
    {
      "label": "List Podman Containers",
      "command": "${list_containers_cmd}",
      "mode": "run",
      "category": "Containers"
    },
    {
      "label": "Podman Disk Usage",
      "command": "${container_disk_cmd}",
      "mode": "run",
      "category": "Containers"
    },
    {
      "label": "Podman Connections",
      "command": "${container_connections_cmd}",
      "mode": "run",
      "category": "Containers"
    },
    {
      "label": "Rebuild Home Manager",
      "command": "home-manager switch --flake ~/.config/home-manager#${host_name}",
      "mode": "run",
      "category": "System"
    },
    {
      "label": "Edit NixOS Config",
      "command": "sudo nano /etc/nixos/configuration.nix",
      "mode": "copy",
      "category": "Configuration"
    },
    {
      "label": "Edit Home Manager Config",
      "command": "nano ~/.config/home-manager/home.nix",
      "mode": "copy",
      "category": "Configuration"
    },
    {
      "label": "Edit SOPS Secrets",
      "command": "sudo -e ${SOPS_FILE:-/etc/nixos/secrets/secrets.yaml}",
      "mode": "copy",
      "category": "Configuration"
    },
    {
      "label": "Reload NixOS Config",
      "command": "sudo -n nixos-rebuild switch",
      "mode": "run",
      "category": "System"
    }
  ]
}
EOF
}

# ============================================================================
# AI Effectiveness Metrics (ai_metrics.json)
# ============================================================================
collect_ai_metrics() {
    local collector="${PROJECT_ROOT}/scripts/collect-ai-metrics.sh"
    if [[ ! -x "$collector" ]]; then
        return 0
    fi

    if [[ "${DASHBOARD_MODE:-}" == "k8s" || "${DASHBOARD_MODE:-}" == "kubernetes" ]]; then
        export AI_METRICS_ENDPOINT="${AI_METRICS_ENDPOINT:-${DASHBOARD_API_URL}/api/ai/metrics}"
    fi

    if ! run_timeout 6 bash "$collector" >/dev/null 2>&1; then
        echo "⚠️  AI metrics collection failed"
    fi
}

# ============================================================================
# Document Links & Quick Access
# ============================================================================
generate_quick_links() {
    cat > "$DATA_DIR/links.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "documentation": [
    {
      "title": "System Overview",
      "path": "docs/agent-guides/00-SYSTEM-OVERVIEW.md",
      "category": "ai"
    },
    {
      "title": "Implementation Summary",
      "path": "IMPLEMENTATION-SUMMARY.md",
      "category": "deployment"
    },
    {
      "title": "Comprehensive System Analysis",
      "path": "COMPREHENSIVE-SYSTEM-ANALYSIS.md",
      "category": "analysis"
    },
    {
      "title": "System Test Results",
      "path": "SYSTEM-TEST-RESULTS.md",
      "category": "testing"
    },
    {
      "title": "DNS Resolution Fix",
      "path": "DNS-RESOLUTION-FIX.md",
      "category": "networking"
    },
    {
      "title": "AI Stack RAG Implementation",
      "path": "AI-STACK-RAG-IMPLEMENTATION.md",
      "category": "ai"
    },
    {
      "title": "Continuous Learning Guide",
      "path": "docs/agent-guides/22-CONTINUOUS-LEARNING.md",
      "category": "ai"
    },
    {
      "title": "RAG Context Guide",
      "path": "docs/agent-guides/21-RAG-CONTEXT.md",
      "category": "ai"
    }
  ],
  "services": [
    {
      "name": "AIDB MCP Server",
      "url": "${AIDB_URL}/health",
      "category": "ai"
    },
    {
      "name": "Open WebUI",
      "url": "${OPEN_WEBUI_URL}",
      "category": "ai"
    },
    {
      "name": "Qdrant Dashboard",
      "url": "${QDRANT_URL}/dashboard",
      "category": "ai"
    },
    {
      "name": "llama.cpp Health",
      "url": "${LLAMA_URL}/health",
      "category": "ai"
    },
    {
      "name": "Netdata Monitoring",
      "url": "${NETDATA_URL}",
      "category": "monitoring"
    },
    {
      "name": "Grafana",
      "url": "${GRAFANA_URL}",
      "category": "monitoring"
    }
  ],
  "config_files": [
    {
      "title": "NixOS Configuration",
      "path": "/etc/nixos/configuration.nix",
      "category": "system"
    },
    {
      "title": "Kubernetes Manifests (AI Stack)",
      "path": "ai-stack/kubernetes/kustomization.yaml",
      "category": "ai"
    },
    {
      "title": "System Dashboard Guide",
      "path": "SYSTEM-DASHBOARD-GUIDE.md",
      "category": "monitoring"
    },
    {
      "title": "Networking Config",
      "path": "templates/nixos-improvements/networking.nix",
      "category": "networking"
    }
  ]
}
EOF
}

# ============================================================================
# Main Execution
# ============================================================================
main() {
    acquire_lock
    if ! has_cmd flock; then
        trap 'rm -f "$LOCK_FILE"' EXIT
    fi

    # Check if running in lite mode (only system + network)
    if [[ "${1:-}" == "--lite-mode" ]]; then
        echo "🔄 Collecting system metrics (lite mode)..."
        collect_system_metrics

        echo "🌐 Collecting network metrics (lite mode)..."
        collect_network_metrics

        echo "✅ Lite dashboard data generated at: $DATA_DIR"
        return 0
    fi

    # Full collection mode
    echo "🔄 Collecting system metrics..."
    collect_system_metrics

    echo "🤖 Collecting LLM stack metrics..."
    collect_llm_metrics

    echo "🌐 Collecting network metrics..."
    collect_network_metrics

    echo "🔒 Collecting security metrics..."
    collect_security_metrics

    echo "🗄️  Collecting database metrics..."
    collect_database_metrics

    echo "🧠 Collecting telemetry metrics..."
    collect_telemetry_metrics

    echo "🪢 Collecting feedback pipeline metrics..."
    collect_feedback_pipeline_metrics

    echo "🎯 Collecting hybrid coordinator metrics..."
    collect_hybrid_coordinator_metrics

    echo "🗂️  Collecting RAG collections metrics..."
    collect_rag_collections_metrics

    echo "📊 Collecting learning metrics..."
    collect_learning_metrics

    echo "🔎 Collecting keyword signals..."
    collect_keyword_signals

    echo "💰 Collecting token savings metrics..."
collect_token_savings_metrics

    echo "🛠️  Collecting configuration snapshot..."
    collect_config_metrics

    echo "✅ Collecting local proof metrics..."
    collect_local_proof_metrics

    echo "💾 Collecting persistence metrics..."
    collect_persistence_metrics

    echo "🧮 Collecting AI effectiveness metrics..."
    collect_ai_metrics

    echo "📚 Generating quick links..."
    generate_quick_links

    echo "✅ Dashboard data generated at: $DATA_DIR"
    echo "📊 Files created:"
    ls -lh "$DATA_DIR"/*.json
}

main "$@"
