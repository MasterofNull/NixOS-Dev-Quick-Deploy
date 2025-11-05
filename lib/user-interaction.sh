#!/usr/bin/env bash
#
# User Interaction Functions
# Purpose: Formatted output and user input functions
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/colors.sh → RED, GREEN, YELLOW, BLUE, NC color codes
#   - lib/logging.sh → log() function (optional for some functions)
#
# Required Variables:
#   - RED, GREEN, YELLOW, BLUE, NC → Color codes from colors.sh
#
# Exports:
#   - print_section() → Print section header
#   - print_info() → Print info message
#   - print_success() → Print success message
#   - print_warning() → Print warning message
#   - print_error() → Print error message
#   - confirm() → Ask yes/no question
#   - prompt_user() → Prompt for user input
#   - prompt_secret() → Prompt for secret input (hidden)
#
# ============================================================================

# Print section header
print_section() {
    echo -e "\n${GREEN}▶ $1${NC}"
}

# Print info message
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Print success message
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Print error message
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Confirm prompt (yes/no)
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e ${BLUE}?${NC} $prompt)" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}

# Prompt for user input
prompt_user() {
    local prompt="$1"
    local default="${2:-}"
    local response

    if [[ -n "$default" ]]; then
        read -p "$(echo -e ${BLUE}?${NC} $prompt [$default]: )" response
        echo "${response:-$default}"
    else
        read -p "$(echo -e ${BLUE}?${NC} $prompt: )" response
        echo "$response"
    fi
}

# Prompt for secret input (password, token, etc.)
prompt_secret() {
    local prompt="$1"
    local note="${2:-}"
    local message="$prompt"

    if [[ -n "$note" ]]; then
        message="$message ($note)"
    fi

    local response=""
    read -s -p "$(echo -e ${BLUE}?${NC} $message: )" response
    echo ""
    echo "$response"
}
