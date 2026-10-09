#!/usr/bin/env bash
# Bash completion script for NixOS AI Stack CLI tools
# Phase 6.2: User Experience Polish
#
# Installation:
#   sudo cp bash-completion.sh /etc/bash_completion.d/nixos-ai-stack
#   source /etc/bash_completion.d/nixos-ai-stack
#

# Completion for aq-report
_aq_report_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Available options
    opts="--since --format --aidb-import --help"

    # Handle options with arguments
    case "$prev" in
        --since)
            COMPREPLY=( $(compgen -W "1d 7d 30d 90d 1w 1m 3m" -- "$cur") )
            return 0
            ;;
        --format)
            COMPREPLY=( $(compgen -W "text md json" -- "$cur") )
            return 0
            ;;
    esac

    # If no arguments yet, show options
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

# Completion for common deployment operations
_nixos_deploy_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="status start stop restart reload logs health check config validate plan apply destroy help"

    # Get available configurations/services
    local services=()
    if [[ -d "/etc/nixos" ]]; then
        services=$(ls /etc/nixos/*.nix 2>/dev/null | xargs -n1 basename | sed 's/\.nix$//')
    fi

    case "$prev" in
        status|start|stop|restart|reload|logs|health|check|config|validate)
            # Command expects a service name
            COMPREPLY=( $(compgen -W "$services" -- "$cur") )
            return 0
            ;;
    esac

    # Main commands
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

# Completion for AI stack operations
_aq_orchestrator_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="workflow agent eval metrics health config logs status help"

    case "$prev" in
        workflow)
            COMPREPLY=( $(compgen -W "list run status cancel" -- "$cur") )
            return 0
            ;;
        agent)
            COMPREPLY=( $(compgen -W "list status profile inspect" -- "$cur") )
            return 0
            ;;
        eval)
            COMPREPLY=( $(compgen -W "run status results export" -- "$cur") )
            return 0
            ;;
        metrics)
            COMPREPLY=( $(compgen -W "show export query" -- "$cur") )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

# Completion for dashboard operations
_dashboard_completion() {
    local cur opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"

    opts="start stop status logs config health export import"

    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

# Register completions
complete -o bashdefault -o default -o nospace -F _aq_report_completion aq-report
complete -o bashdefault -o default -o nospace -F _nixos_deploy_completion deploy
complete -o bashdefault -o default -o nospace -F _aq_orchestrator_completion aq-orchestrator
complete -o bashdefault -o default -o nospace -F _dashboard_completion dashboard

# Additional helper completion functions

# File completion for config files
_config_file_completion() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=( $(compgen -f -X "!*.{yaml,yml,json,nix}" -- "$cur") )
}

# Completion for common flags
_common_flags() {
    echo "--help --version --debug --verbose --quiet --output --format --config"
}

# Dynamic environment variable completion
_env_var_completion() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"

    # Show environment variables that match current input
    local vars=$(compgen -v -- "$cur")
    COMPREPLY=( $(echo "$vars" | tr ' ' '\n' | grep -E "^(SERVICE|TOOL|AIDB|PROMETHEUS|DATABASE)" ) )
}

# Hostname/service completion
_service_completion() {
    local services=(
        "ai-hybrid-coordinator"
        "ai-orchestrator"
        "aidb"
        "prometheus"
        "postgres"
        "redis"
        "minio"
        "dashboard"
    )

    local cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=( $(compgen -W "${services[*]}" -- "$cur") )
}

# Completion for log levels
_loglevel_completion() {
    local levels="DEBUG INFO WARNING ERROR CRITICAL"
    local cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=( $(compgen -W "$levels" -- "$cur") )
}

# Helper function to show available completions
show_completion_help() {
    cat << 'EOF'
NixOS AI Stack - Bash Completion Help

Registered commands:
  aq-report          - AI stack weekly performance digest
  deploy             - NixOS deployment operations
  aq-orchestrator    - AI orchestration control
  dashboard          - Dashboard operations

Keyboard shortcuts for faster navigation:
  Tab                - Autocomplete command or option
  Ctrl+W             - Delete word backwards
  Ctrl+U             - Clear line
  Ctrl+R             - Search command history
  Alt+.              - Insert last argument

Common options across tools:
  --help             - Show help message
  --version          - Show version
  --debug            - Enable debug output
  --verbose          - Increase verbosity
  --quiet            - Suppress output
  --config FILE      - Specify config file
  --format FORMAT    - Output format (text, json, yaml)
  --output FILE      - Write output to file

Examples:
  aq-report --since=7d --format=json
  deploy status ai-hybrid-coordinator
  aq-orchestrator workflow list
  dashboard start --config /etc/nixos/dashboard.yaml

For more information, see the documentation:
  man aq-report
  man deploy
  man aq-orchestrator

EOF
}

# Set up help command
if [[ "${BASH_COMPLETION_DIR:-}" ]]; then
    # Register help function
    complete -o bashdefault -o default -F show_completion_help help
fi

# Enable completion for common patterns
# Allow completion for paths after certain options
_completion_loader() {
    local cmd="$1"
    case "$cmd" in
        --config|--output|--input|-c|-o)
            _config_file_completion
            ;;
        --service|-s)
            _service_completion
            ;;
        --loglevel|-l)
            _loglevel_completion
            ;;
    esac
}

# Export completion functions
export -f _aq_report_completion _nixos_deploy_completion _aq_orchestrator_completion
export -f _dashboard_completion _common_flags _env_var_completion _service_completion
export -f _loglevel_completion show_completion_help
