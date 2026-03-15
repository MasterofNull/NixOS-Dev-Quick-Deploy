#!/usr/bin/env bash
#
# Deploy CLI - Core Library
# Logging, error handling, and core utilities

# ============================================================================
# Color Definitions
# ============================================================================

if [[ "${NO_COLOR:-0}" == "1" ]] || [[ ! -t 1 ]]; then
  # No color output
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  MAGENTA=""
  CYAN=""
  BOLD=""
  RESET=""
else
  # Color output
  RED="\033[0;31m"
  GREEN="\033[0;32m"
  YELLOW="\033[0;33m"
  BLUE="\033[0;34m"
  MAGENTA="\033[0;35m"
  CYAN="\033[0;36m"
  BOLD="\033[1m"
  RESET="\033[0m"
fi

# ============================================================================
# Logging Functions
# ============================================================================

log_error() {
  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"error","message":"%s","timestamp":"%s"}\n' "$*" "$(date -Iseconds)" >&2
  else
    echo -e "${RED}${BOLD}ERROR:${RESET} $*" >&2
  fi
}

log_warn() {
  if [[ "${QUIET:-0}" == "1" ]]; then
    return 0
  fi

  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"warn","message":"%s","timestamp":"%s"}\n' "$*" "$(date -Iseconds)" >&2
  else
    echo -e "${YELLOW}${BOLD}WARN:${RESET} $*" >&2
  fi
}

log_info() {
  if [[ "${QUIET:-0}" == "1" ]]; then
    return 0
  fi

  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"info","message":"%s","timestamp":"%s"}\n' "$*" "$(date -Iseconds)"
  else
    echo -e "${BLUE}INFO:${RESET} $*"
  fi
}

log_success() {
  if [[ "${QUIET:-0}" == "1" ]]; then
    return 0
  fi

  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"info","message":"%s","timestamp":"%s","status":"success"}\n' "$*" "$(date -Iseconds)"
  else
    echo -e "${GREEN}${BOLD}✓${RESET} $*"
  fi
}

log_debug() {
  if [[ "${VERBOSE:-0}" != "1" ]]; then
    return 0
  fi

  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"debug","message":"%s","timestamp":"%s"}\n' "$*" "$(date -Iseconds)"
  else
    echo -e "${CYAN}DEBUG:${RESET} $*"
  fi
}

log_step() {
  local step="$1"
  local total="$2"
  local message="$3"

  if [[ "${QUIET:-0}" == "1" ]]; then
    return 0
  fi

  if [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    printf '{"level":"info","step":%d,"total":%d,"message":"%s","timestamp":"%s"}\n' \
      "$step" "$total" "$message" "$(date -Iseconds)"
  else
    echo -e "${BOLD}[${step}/${total}]${RESET} $message"
  fi
}

# ============================================================================
# Error Handling
# ============================================================================

die() {
  log_error "$@"
  exit 1
}

require_command() {
  local cmd="$1"
  local install_hint="${2:-}"

  if ! command -v "$cmd" >/dev/null 2>&1; then
    log_error "Required command not found: $cmd"
    if [[ -n "$install_hint" ]]; then
      echo ""
      echo "To install:"
      echo "  $install_hint"
    fi
    exit 1
  fi
}

# ============================================================================
# Progress Indicators
# ============================================================================

# Spinner characters
SPINNER_CHARS=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
SPINNER_PID=""

start_spinner() {
  local message="$1"

  if [[ "${QUIET:-0}" == "1" ]] || [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    return 0
  fi

  (
    i=0
    while true; do
      printf "\r${SPINNER_CHARS[$i]} %s" "$message"
      i=$(( (i + 1) % ${#SPINNER_CHARS[@]} ))
      sleep 0.1
    done
  ) &

  SPINNER_PID=$!
}

stop_spinner() {
  if [[ -n "$SPINNER_PID" ]] && kill -0 "$SPINNER_PID" 2>/dev/null; then
    kill "$SPINNER_PID" 2>/dev/null
    wait "$SPINNER_PID" 2>/dev/null || true
    printf "\r\033[K"  # Clear line
  fi
  SPINNER_PID=""
}

show_progress_bar() {
  local current="$1"
  local total="$2"
  local message="${3:-}"
  local width=50

  if [[ "${QUIET:-0}" == "1" ]] || [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    return 0
  fi

  local percentage=$((current * 100 / total))
  local filled=$((current * width / total))
  local empty=$((width - filled))

  local bar=""
  for ((i=0; i<filled; i++)); do bar+="█"; done
  for ((i=0; i<empty; i++)); do bar+="░"; done

  printf "\r%s [%s] %3d%% (%d/%d)" "$message" "$bar" "$percentage" "$current" "$total"

  if [[ "$current" -eq "$total" ]]; then
    echo ""  # New line when complete
  fi
}

# ============================================================================
# Validation Functions
# ============================================================================

validate_not_empty() {
  local value="$1"
  local name="$2"

  if [[ -z "$value" ]]; then
    die "$name cannot be empty"
  fi
}

validate_file_exists() {
  local file="$1"
  local name="${2:-File}"

  if [[ ! -f "$file" ]]; then
    die "$name not found: $file"
  fi
}

validate_dir_exists() {
  local dir="$1"
  local name="${2:-Directory}"

  if [[ ! -d "$dir" ]]; then
    die "$name not found: $dir"
  fi
}

confirm_action() {
  local message="$1"
  local default="${2:-n}"

  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log_info "[DRY-RUN] Would ask for confirmation: $message"
    return 0
  fi

  if [[ "${QUIET:-0}" == "1" ]]; then
    # In quiet mode, assume default
    if [[ "$default" == "y" ]]; then
      return 0
    else
      return 1
    fi
  fi

  local prompt
  if [[ "$default" == "y" ]]; then
    prompt="$message [Y/n] "
  else
    prompt="$message [y/N] "
  fi

  while true; do
    read -r -p "$prompt" response
    response="${response:-$default}"

    case "$response" in
      [Yy]*)
        return 0
        ;;
      [Nn]*)
        return 1
        ;;
      *)
        echo "Please answer yes or no."
        ;;
    esac
  done
}

# ============================================================================
# Time and Duration
# ============================================================================

get_timestamp() {
  date +%s
}

format_duration() {
  local seconds="$1"

  if [[ $seconds -lt 60 ]]; then
    echo "${seconds}s"
  elif [[ $seconds -lt 3600 ]]; then
    printf "%dm %ds" $((seconds / 60)) $((seconds % 60))
  else
    printf "%dh %dm" $((seconds / 3600)) $(( (seconds % 3600) / 60))
  fi
}

# ============================================================================
# Dry-Run Helpers
# ============================================================================

would_run() {
  local description="$1"

  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log_info "[DRY-RUN] Would: $description"
    return 0
  else
    return 1
  fi
}

# ============================================================================
# Pretty Printing
# ============================================================================

print_header() {
  local title="$1"
  local width=80

  if [[ "${QUIET:-0}" == "1" ]] || [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    return 0
  fi

  echo ""
  echo -e "${BOLD}$(printf '━%.0s' $(seq 1 $width))${RESET}"
  echo -e "${BOLD}  $title${RESET}"
  echo -e "${BOLD}$(printf '━%.0s' $(seq 1 $width))${RESET}"
  echo ""
}

print_section() {
  local title="$1"

  if [[ "${QUIET:-0}" == "1" ]] || [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    return 0
  fi

  echo ""
  echo -e "${BOLD}${BLUE}▶${RESET} ${BOLD}$title${RESET}"
}

print_table() {
  if [[ "${QUIET:-0}" == "1" ]] || [[ "${OUTPUT_JSON:-0}" == "1" ]]; then
    return 0
  fi

  # Simple table printing - reads from stdin
  column -t -s $'\t'
}

# ============================================================================
# JSON Output Helpers
# ============================================================================

json_escape() {
  local string="$1"
  # Escape special characters for JSON
  string="${string//\\/\\\\}"  # Backslash
  string="${string//\"/\\\"}"  # Quote
  string="${string//$'\n'/\\n}"  # Newline
  string="${string//$'\r'/\\r}"  # Carriage return
  string="${string//$'\t'/\\t}"  # Tab
  echo "$string"
}

json_object() {
  # Build JSON object from key=value pairs
  local pairs=("$@")
  local json="{"
  local first=1

  for pair in "${pairs[@]}"; do
    local key="${pair%%=*}"
    local value="${pair#*=}"

    if [[ $first -eq 0 ]]; then
      json+=","
    fi
    first=0

    json+="\"$key\":\"$(json_escape "$value")\""
  done

  json+="}"
  echo "$json"
}

# ============================================================================
# Cleanup Handlers
# ============================================================================

cleanup_handlers=()

register_cleanup() {
  local handler="$1"
  cleanup_handlers+=("$handler")
}

run_cleanup() {
  for handler in "${cleanup_handlers[@]}"; do
    $handler || true
  done
}

trap run_cleanup EXIT

# ============================================================================
# End of Core Library
# ============================================================================
