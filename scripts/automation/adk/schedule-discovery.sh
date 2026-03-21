#!/usr/bin/env bash
# scripts/adk/schedule-discovery.sh
#
# Purpose: Schedule automated ADK discovery execution
#
# Status: production
# Owner: ai-harness
# Last Updated: 2026-03-20
#
# Features:
# - Cron/systemd timer integration
# - Scheduled discovery execution (weekly default)
# - Results persistence and history tracking
# - Notification on significant discoveries
# - Integration with existing monitoring/alerting

set -euo pipefail

# Declarative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LIB_ADK_DIR="${REPO_ROOT}/lib/adk"
DATA_DIR="${REPO_ROOT}/.agent/adk"
LOG_DIR="${DATA_DIR}/logs"

# Configuration
DISCOVERY_SCRIPT="${LIB_ADK_DIR}/implementation-discovery.sh"
SCHEDULE="${ADK_DISCOVERY_SCHEDULE:-weekly}"
VERBOSE="${VERBOSE:-0}"

# Logging
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/discovery-$(date +%Y%m%d-%H%M%S).log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}" >&2
}

log_error() {
    log "ERROR: $*"
}

# Check if systemd timer is available
has_systemd() {
    command -v systemctl &>/dev/null && systemctl --version &>/dev/null
}

# Check if cron is available
has_cron() {
    command -v crontab &>/dev/null
}

# Create systemd timer unit
create_systemd_timer() {
    log "Creating systemd timer for ADK discovery"

    local timer_name="adk-discovery.timer"
    local service_name="adk-discovery.service"
    local user_unit_dir="${HOME}/.config/systemd/user"

    mkdir -p "${user_unit_dir}"

    # Determine timer schedule
    local on_calendar
    case "${SCHEDULE}" in
        daily)
            on_calendar="daily"
            ;;
        weekly)
            on_calendar="weekly"
            ;;
        monthly)
            on_calendar="monthly"
            ;;
        *)
            on_calendar="${SCHEDULE}"  # Allow custom systemd calendar spec
            ;;
    esac

    # Create service unit
    cat > "${user_unit_dir}/${service_name}" <<EOF
[Unit]
Description=ADK Implementation Discovery
After=network.target

[Service]
Type=oneshot
ExecStart=${DISCOVERY_SCRIPT}
WorkingDirectory=${REPO_ROOT}
StandardOutput=append:${LOG_DIR}/discovery-systemd.log
StandardError=append:${LOG_DIR}/discovery-systemd.log
Environment="VERBOSE=1"

[Install]
WantedBy=default.target
EOF

    # Create timer unit
    cat > "${user_unit_dir}/${timer_name}" <<EOF
[Unit]
Description=ADK Implementation Discovery Timer
Requires=${service_name}

[Timer]
OnCalendar=${on_calendar}
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
EOF

    # Reload systemd user units
    systemctl --user daemon-reload

    # Enable and start timer
    systemctl --user enable "${timer_name}"
    systemctl --user start "${timer_name}"

    log "Systemd timer created and started: ${timer_name}"
    log "Schedule: ${on_calendar}"
    log "Next run: $(systemctl --user list-timers --no-pager | grep adk-discovery || echo 'unknown')"

    return 0
}

# Create cron job
create_cron_job() {
    log "Creating cron job for ADK discovery"

    # Determine cron schedule
    local cron_schedule
    case "${SCHEDULE}" in
        daily)
            cron_schedule="0 2 * * *"  # 2 AM daily
            ;;
        weekly)
            cron_schedule="0 2 * * 0"  # 2 AM Sunday
            ;;
        monthly)
            cron_schedule="0 2 1 * *"  # 2 AM 1st of month
            ;;
        *)
            cron_schedule="${SCHEDULE}"  # Allow custom cron spec
            ;;
    esac

    # Create cron job entry
    local cron_entry="${cron_schedule} ${DISCOVERY_SCRIPT} >> ${LOG_DIR}/discovery-cron.log 2>&1"

    # Check if job already exists
    if crontab -l 2>/dev/null | grep -F "${DISCOVERY_SCRIPT}" &>/dev/null; then
        log "Cron job already exists, updating..."
        # Remove existing job
        crontab -l 2>/dev/null | grep -v "${DISCOVERY_SCRIPT}" | crontab - || true
    fi

    # Add new job
    (crontab -l 2>/dev/null || true; echo "${cron_entry}") | crontab -

    log "Cron job created: ${cron_schedule}"
    log "Logs: ${LOG_DIR}/discovery-cron.log"

    return 0
}

# Remove scheduled discovery
remove_schedule() {
    log "Removing ADK discovery schedule"

    # Remove systemd timer if exists
    if has_systemd; then
        local timer_name="adk-discovery.timer"
        local service_name="adk-discovery.service"
        local user_unit_dir="${HOME}/.config/systemd/user"

        if [[ -f "${user_unit_dir}/${timer_name}" ]]; then
            systemctl --user stop "${timer_name}" 2>/dev/null || true
            systemctl --user disable "${timer_name}" 2>/dev/null || true
            rm -f "${user_unit_dir}/${timer_name}"
            rm -f "${user_unit_dir}/${service_name}"
            systemctl --user daemon-reload
            log "Systemd timer removed"
        fi
    fi

    # Remove cron job if exists
    if has_cron; then
        if crontab -l 2>/dev/null | grep -F "${DISCOVERY_SCRIPT}" &>/dev/null; then
            crontab -l 2>/dev/null | grep -v "${DISCOVERY_SCRIPT}" | crontab - || true
            log "Cron job removed"
        fi
    fi

    return 0
}

# Check schedule status
check_status() {
    log "Checking ADK discovery schedule status"

    local has_schedule=0

    # Check systemd timer
    if has_systemd; then
        if systemctl --user is-enabled adk-discovery.timer &>/dev/null; then
            log "✓ Systemd timer is enabled"
            systemctl --user list-timers --no-pager | grep adk-discovery || true
            has_schedule=1
        else
            log "✗ Systemd timer not found"
        fi
    fi

    # Check cron job
    if has_cron; then
        if crontab -l 2>/dev/null | grep -F "${DISCOVERY_SCRIPT}" &>/dev/null; then
            log "✓ Cron job is configured"
            crontab -l 2>/dev/null | grep -F "${DISCOVERY_SCRIPT}" || true
            has_schedule=1
        else
            log "✗ Cron job not found"
        fi
    fi

    if [[ ${has_schedule} -eq 0 ]]; then
        log "No scheduled discovery found"
        return 1
    fi

    return 0
}

# Run discovery now
run_now() {
    log "Running ADK discovery immediately"

    if [[ ! -x "${DISCOVERY_SCRIPT}" ]]; then
        log_error "Discovery script not executable: ${DISCOVERY_SCRIPT}"
        return 1
    fi

    "${DISCOVERY_SCRIPT}" "$@" 2>&1 | tee -a "${LOG_FILE}"

    return ${PIPESTATUS[0]}
}

# Setup scheduled discovery
setup_schedule() {
    log "Setting up ADK discovery schedule: ${SCHEDULE}"

    # Prefer systemd timer if available
    if has_systemd; then
        create_systemd_timer
    elif has_cron; then
        create_cron_job
    else
        log_error "Neither systemd nor cron available"
        log_error "Please set up scheduling manually"
        return 1
    fi

    # Run initial discovery
    log "Running initial discovery"
    run_now --verbose

    return 0
}

# CLI interface
main() {
    local mode="setup"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            setup|install)
                mode="setup"
                shift
                ;;
            remove|uninstall)
                mode="remove"
                shift
                ;;
            status)
                mode="status"
                shift
                ;;
            run|now)
                mode="run"
                shift
                break  # Pass remaining args to discovery script
                ;;
            --schedule)
                SCHEDULE="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --help|-h)
                cat <<EOF
Usage: $(basename "$0") [COMMAND] [OPTIONS]

Schedule automated ADK implementation discovery.

Commands:
    setup, install    Set up scheduled discovery (default)
    remove, uninstall Remove scheduled discovery
    status            Check schedule status
    run, now          Run discovery immediately

Options:
    --schedule SCHED  Schedule frequency (default: weekly)
                      Values: daily, weekly, monthly
                      Or systemd calendar spec / cron expression
    --verbose, -v     Enable verbose logging
    --help, -h        Show this help message

Examples:
    $(basename "$0") setup                # Setup weekly schedule
    $(basename "$0") setup --schedule daily   # Setup daily schedule
    $(basename "$0") status               # Check schedule status
    $(basename "$0") run                  # Run discovery now
    $(basename "$0") remove               # Remove schedule

Scheduling:
    - Uses systemd timer if available (preferred)
    - Falls back to cron if systemd unavailable
    - Logs stored in: ${LOG_DIR}

Environment:
    ADK_DISCOVERY_SCHEDULE - Default schedule (default: weekly)
    VERBOSE               - Enable verbose output
EOF
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                log "Use --help for usage information"
                return 1
                ;;
        esac
    done

    case "$mode" in
        setup)
            setup_schedule
            ;;
        remove)
            remove_schedule
            ;;
        status)
            check_status
            ;;
        run)
            run_now "$@"
            ;;
        *)
            log_error "Unknown mode: $mode"
            return 1
            ;;
    esac
}

# Execute if run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
