#!/usr/bin/env bash
# CLI Enhancement Utilities for Phase 6.2: User Experience Polish
# Provides colored output, progress bars, and confirmation prompts for AI stack operations

set -euo pipefail

# Color definitions (ANSI escape codes)
readonly COLOR_RESET='\033[0m'
readonly COLOR_BOLD='\033[1m'
readonly COLOR_DIM='\033[2m'
readonly COLOR_RED='\033[31m'
readonly COLOR_GREEN='\033[32m'
readonly COLOR_YELLOW='\033[33m'
readonly COLOR_BLUE='\033[34m'
readonly COLOR_MAGENTA='\033[35m'
readonly COLOR_CYAN='\033[36m'
readonly COLOR_BRIGHT_RED='\033[91m'
readonly COLOR_BRIGHT_GREEN='\033[92m'
readonly COLOR_BRIGHT_YELLOW='\033[93m'

# Check if output supports colors
has_colors() {
    [[ -t 1 ]] && [[ "${TERM:-}" != "dumb" ]]
}

# Output functions with color support
print_header() {
    local message="$1"
    local width=${#message}
    local border="$(printf '=%.0s' $(seq 1 $((width + 4))))"

    if has_colors; then
        echo -e "\n${COLOR_CYAN}${border}${COLOR_RESET}"
        echo -e "${COLOR_BOLD}${COLOR_CYAN}  ${message}${COLOR_RESET}"
        echo -e "${COLOR_CYAN}${border}${COLOR_RESET}\n"
    else
        echo ""
        echo "$border"
        echo "  $message"
        echo "$border"
        echo ""
    fi
}

print_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if has_colors; then
        echo -e "${COLOR_CYAN}[${timestamp}] ℹ ${message}${COLOR_RESET}"
    else
        echo "[${timestamp}] [INFO] ${message}"
    fi
}

print_success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if has_colors; then
        echo -e "${COLOR_GREEN}[${timestamp}] ✓ ${message}${COLOR_RESET}"
    else
        echo "[${timestamp}] [OK] ${message}"
    fi
}

print_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if has_colors; then
        echo -e "${COLOR_YELLOW}[${timestamp}] ⚠ ${message}${COLOR_RESET}" >&2
    else
        echo "[${timestamp}] [WARN] ${message}" >&2
    fi
}

print_error() {
    local message="$1"
    local code="${2:-}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local code_str=""
    [[ -n "$code" ]] && code_str=" [$code]"

    if has_colors; then
        echo -e "${COLOR_RED}[${timestamp}] ✕ ${message}${code_str}${COLOR_RESET}" >&2
    else
        echo "[${timestamp}] [ERROR] ${message}${code_str}" >&2
    fi
}

# Progress bar for operations
progress_bar() {
    local current="$1"
    local total="$2"
    local label="${3:-Progress}"

    if [[ $total -eq 0 ]]; then
        return 0
    fi

    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))

    local bar="$(printf '█%.0s' $(seq 1 $filled))$(printf '░%.0s' $(seq 1 $empty))"

    if has_colors; then
        local color="${COLOR_GREEN}"
        [[ $percent -lt 75 ]] && color="${COLOR_YELLOW}"
        [[ $percent -lt 50 ]] && color="${COLOR_CYAN}"
        printf "\r${label} ${color}%3d%%${COLOR_RESET} │${bar}│"
    else
        printf "\r${label} %3d%% │${bar}│" "$percent"
    fi

    [[ $current -ge $total ]] && echo ""
}

# Simple spinner for indeterminate operations
spinner() {
    local label="${1:-Loading}"
    local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local frame=0

    while kill -0 $! 2>/dev/null; do
        local frame_char="${frames[$((frame % ${#frames[@]}))]}"
        if has_colors; then
            printf "\r${frame_char} ${label}%-50s" ""
        else
            printf "\r${frame_char} ${label}%-50s" ""
        fi
        frame=$((frame + 1))
        sleep 0.1
    done

    if has_colors; then
        printf "\r${COLOR_GREEN}✓${COLOR_RESET} ${label}\n"
    else
        printf "\r[OK] ${label}\n"
    fi
}

# Interactive confirmation prompt
confirm() {
    local prompt="$1"
    local default="${2:-false}"
    local default_str="[y/N]"
    [[ "$default" == "true" ]] && default_str="[Y/n]"

    while true; do
        read -p "${prompt} ${default_str}: " -r choice
        case "$choice" in
            [Yy][Ee][Ss]|[Yy]) return 0 ;;
            [Nn][Oo]|[Nn]) return 1 ;;
            "")
                [[ "$default" == "true" ]] && return 0 || return 1
                ;;
            *) echo "Please enter 'y' or 'n'" ;;
        esac
    done
}

# Display contextual error with guidance
show_error() {
    local error_code="$1"
    local details="${2:-}"

    case "$error_code" in
        E001)
            print_error "Configuration Error: Required configuration is missing" "$error_code"
            print_error "Guidance: Check your config file and ensure all required fields are present"
            ;;
        E101)
            print_error "Connection Failed: Unable to reach the service" "$error_code"
            print_error "Guidance: Verify the service is running and network connectivity is available"
            ;;
        E102)
            print_error "Network Timeout: The request took too long to complete" "$error_code"
            print_error "Guidance: Check your network connection and try again"
            ;;
        E201)
            print_error "Permission Denied: Insufficient permissions for this operation" "$error_code"
            print_error "Guidance: Run with elevated privileges or check file ownership"
            ;;
        E301)
            print_error "Resource Not Found: The requested resource does not exist" "$error_code"
            print_error "Guidance: Verify the resource ID and try again"
            ;;
        E401)
            print_error "API Error: An unexpected error occurred" "$error_code"
            print_error "Guidance: Check the system logs for more details or contact support"
            ;;
        *)
            print_error "Unknown Error: $error_code" "$error_code"
            [[ -n "$details" ]] && print_error "Details: $details"
            ;;
    esac
}

# Format bytes to human-readable
humanize_bytes() {
    local bytes="$1"
    if [[ $bytes -lt 1024 ]]; then
        echo "${bytes}B"
    elif [[ $bytes -lt 1048576 ]]; then
        echo "$((bytes / 1024))KB"
    elif [[ $bytes -lt 1073741824 ]]; then
        echo "$((bytes / 1048576))MB"
    else
        echo "$((bytes / 1073741824))GB"
    fi
}

# Format duration to human-readable
humanize_duration() {
    local seconds="$1"
    if [[ $seconds -lt 60 ]]; then
        echo "${seconds}s"
    elif [[ $seconds -lt 3600 ]]; then
        echo "$((seconds / 60))m"
    else
        echo "$((seconds / 3600))h"
    fi
}

# Run command with spinner
run_with_spinner() {
    local label="$1"
    shift

    print_info "$label"
    "$@" &
    local pid=$!
    spinner "$label" &
    local spinner_pid=$!

    wait $pid
    local exit_code=$?
    kill $spinner_pid 2>/dev/null || true
    wait $spinner_pid 2>/dev/null || true

    if [[ $exit_code -eq 0 ]]; then
        print_success "$label completed"
    else
        print_error "$label failed with exit code $exit_code"
    fi

    return $exit_code
}

# Table formatting
print_table() {
    local -a headers=("$@")
    local num_cols=${#headers[@]}

    # Read rows from stdin
    local -a rows
    while IFS= read -r line; do
        rows+=("$line")
    done

    if [[ ${#rows[@]} -eq 0 ]]; then
        echo "No data"
        return
    fi

    # Calculate column widths
    local -a widths
    for ((i = 0; i < num_cols; i++)); do
        widths[$i]=${#headers[$i]}
    done

    for row in "${rows[@]}"; do
        local -a cells
        IFS='|' read -ra cells <<<"$row"
        for ((i = 0; i < num_cols; i++)); do
            local cell_len=${#cells[$i]:-0}
            [[ $cell_len -gt ${widths[$i]} ]] && widths[$i]=$cell_len
        done
    done

    # Print header
    local header_line=""
    for ((i = 0; i < num_cols; i++)); do
        printf -v header_line "%s%-${widths[$i]}s " "$header_line" "${headers[$i]}"
    done
    echo "$header_line"

    # Print separator
    local sep_line=""
    for ((i = 0; i < num_cols; i++)); do
        sep_line+="$(printf '%-$((${widths[$i]} + 1))s' | tr ' ' '-')"
    done
    echo "$sep_line"

    # Print rows
    for row in "${rows[@]}"; do
        local -a cells
        IFS='|' read -ra cells <<<"$row"
        local row_line=""
        for ((i = 0; i < num_cols; i++)); do
            printf -v row_line "%s%-${widths[$i]}s " "$row_line" "${cells[$i]:-}"
        done
        echo "$row_line"
    done
}

# Export functions for use in other scripts
export -f print_header print_info print_success print_warning print_error
export -f progress_bar spinner confirm show_error
export -f humanize_bytes humanize_duration run_with_spinner print_table
