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

# ============================================================================
# Print Section Header Function
# ============================================================================
# Purpose: Print a major section header with formatting
# Parameters:
#   $1 - Section title text
# Returns: 0
#
# Visual format:
#   ▶ Section Name (in green)
#
# Usage: print_section "Installing Packages"
#
# Why echo -e?
# -e flag enables interpretation of backslash escape sequences
# Required for ANSI color codes (\033[...m) to work
# Without -e, the codes would print literally: \033[0;32m text
#
# \n prefix: Adds blank line before section for visual separation
# This helps sections stand out in long output
# ============================================================================
print_section() {
    # Print with newline prefix, green arrow, section name, then reset color
    # ${GREEN} = ANSI code for green text
    # ▶ = Unicode right-pointing triangle (U+25B6)
    # $1 = section name passed as parameter
    # ${NC} = No Color, resets formatting
    echo -e "\n${GREEN}▶ $1${NC}"
}

# ============================================================================
# Print Info Message Function
# ============================================================================
# Purpose: Print an informational message (neutral/blue)
# Parameters:
#   $1 - Info message text
# Returns: 0
#
# Visual format:
#   ℹ Message text (in blue)
#
# Usage: print_info "Checking system requirements..."
#
# When to use:
# - General status updates
# - Neutral information
# - Progress indicators
# - System state information
# ============================================================================
print_info() {
    # Blue info icon (ℹ) followed by message
    # ${BLUE} = ANSI code for blue text
    # ℹ = Unicode information symbol (U+2139)
    echo -e "${BLUE}ℹ${NC} $1"
}

# ============================================================================
# Print Detail Message Function
# ============================================================================
# Purpose: Print a secondary detail message (indented blue arrow)
# Parameters:
#   $1 - Detail message text
# Returns: 0
#
# Visual format:
#     → Message text (in blue, indented)
#
# Usage: print_detail "See \$TMPDIR/install.log for details"
#
# When to use:
# - Follow-up information after a warning/error
# - Command suggestions or log file pointers
# - Nested output underneath a parent message
# ============================================================================
print_detail() {
    echo -e "    ${BLUE}→${NC} $1"
}

# ============================================================================
# Print Success Message Function
# ============================================================================
# Purpose: Print a success/completion message (green checkmark)
# Parameters:
#   $1 - Success message text
# Returns: 0
#
# Visual format:
#   ✓ Message text (in green)
#
# Usage: print_success "Package installed successfully"
#
# When to use:
# - Operation completed successfully
# - Validation passed
# - Test succeeded
# - Resource created successfully
# ============================================================================
print_success() {
    # Green checkmark (✓) followed by message
    # ${GREEN} = ANSI code for green text
    # ✓ = Unicode check mark (U+2713)
    echo -e "${GREEN}✓${NC} $1"
}

# ============================================================================
# Print Warning Message Function
# ============================================================================
# Purpose: Print a warning message (yellow)
# Parameters:
#   $1 - Warning message text
# Returns: 0
#
# Visual format:
#   ⚠ Message text (in yellow)
#
# Usage: print_warning "This operation cannot be undone"
#
# When to use:
# - Non-fatal issues detected
# - Potentially risky operations
# - Deprecated features
# - Configuration concerns
# - Retryable failures
# ============================================================================
print_warning() {
    # Yellow warning sign (⚠) followed by message
    # ${YELLOW} = ANSI code for yellow text (bold for visibility)
    # ⚠ = Unicode warning sign (U+26A0)
    echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================================================
# Print Error Message Function
# ============================================================================
# Purpose: Print an error message (red X)
# Parameters:
#   $1 - Error message text
# Returns: 0 (this function only prints, doesn't exit)
#
# Visual format:
#   ✗ Message text (in red)
#
# Usage: print_error "Failed to connect to server"
#
# When to use:
# - Operation failed
# - Validation failed
# - Critical issues
# - Unrecoverable errors
#
# Note: This function only prints the error, it doesn't exit the script
# Use with 'exit 1' or 'return 1' to actually handle the error
# ============================================================================
print_error() {
    # Red X mark (✗) followed by message
    # ${RED} = ANSI code for red text
    # ✗ = Unicode ballot X (U+2717)
    echo -e "${RED}✗${NC} $1"
}

# ============================================================================
# Confirm Prompt Function (Yes/No)
# ============================================================================
# Purpose: Ask user a yes/no question and return their answer
# Parameters:
#   $1 - Question/prompt text
#   $2 - Default answer (optional): "y" or "n" (default: "n")
# Returns:
#   0 - User answered yes (y/Y)
#   1 - User answered no (n/N) or pressed Enter with "n" default
#
# Visual format:
#   ? Question text [Y/n]:  (if default is "y")
#   ? Question text [y/N]:  (if default is "n")
#
# Usage examples:
#   if confirm "Continue with installation?" "y"; then
#       echo "Installing..."
#   fi
#
#   if confirm "Delete file?"; then  # Defaults to "n"
#       rm file.txt
#   fi
#
# How it works:
# 1. Displays prompt with appropriate [Y/n] or [y/N] indicator
# 2. Reads user input with read -p
# 3. If user presses Enter without typing, uses default
# 4. Tests if response matches Y or y using regex
# 5. Returns 0 for yes, 1 for no
#
# Why this pattern?
# - Safe defaults: Important for destructive operations
# - Visual clarity: [Y/n] shows capital letter is default
# - Case insensitive: Accepts both Y and y
# - Empty input handling: Pressing Enter uses default
# ============================================================================
confirm() {
    # Capture parameters
    local prompt="$1"              # The question to ask
    local default="${2:-n}"         # Default answer (n if not provided)
    local response                  # Will hold user's input

    if [[ "${AUTO_CONFIRM:-false}" == "true" ]]; then
        # Automation mode: never block on prompts, use the declared default.
        [[ "$default" =~ ^[Yy]$ ]]
        return $?
    fi

    if [[ ! -t 0 ]]; then
        # Non-interactive mode: honor default safely.
        if [[ "$default" =~ ^[Yy]$ ]]; then
            return 0
        fi
        return 1
    fi

    # Adjust prompt text based on default answer
    # Capital letter indicates the default choice
    if [[ "$default" == "y" ]]; then
        # Default is yes: show [Y/n] with capital Y
        prompt="$prompt [Y/n]: "
    else
        # Default is no: show [y/N] with capital N
        prompt="$prompt [y/N]: "
    fi

    # Prompt user for input
    # read -p = prompt with text
    # $(echo -e ${BLUE}?${NC} ...) creates colored question mark prefix
    # Response is stored in the 'response' variable
    read -p "$(echo -e ${BLUE}?${NC} $prompt)" response

    # If user pressed Enter without typing, use default
    # ${response:-$default} = parameter expansion with default value
    # If response is empty, use $default
    response=${response:-$default}

    # Test if response is Y or y using regex
    # [[ ]] = bash extended test command
    # =~ = regex match operator
    # ^[Yy]$ = start of string, Y or y, end of string
    # Returns 0 (true) if matches, 1 (false) otherwise
    [[ "$response" =~ ^[Yy]$ ]]
}

# ============================================================================
# Prompt User for Input Function
# ============================================================================
# Purpose: Ask user for text input with optional default value
# Parameters:
#   $1 - Prompt text
#   $2 - Default value (optional)
# Returns: Prints the user's response (or default) to stdout
#
# Visual format:
#   ? Prompt text [default]:  (if default provided)
#   ? Prompt text:            (if no default)
#
# Usage examples:
#   hostname=$(prompt_user "Enter hostname" "nixos-desktop")
#   username=$(prompt_user "Enter username")
#
# How it works:
# 1. Checks if default value was provided
# 2. Displays prompt with [default] if applicable
# 3. Reads user input
# 4. If user pressed Enter, uses default (if provided)
# 5. Prints result to stdout (captured by caller)
#
# Why echo the result?
# The function outputs the result to stdout, allowing caller to capture it
# Pattern: variable=$(prompt_user "Question" "default")
# This is the standard bash way to return string values from functions
#
# Important bash concepts:
# - Functions can't return strings, only exit codes
# - To "return" a string, echo it and caller captures with $()
# - This is why we use echo instead of return
# ============================================================================
prompt_user() {
    # Capture parameters
    local prompt="$1"               # Question/prompt text
    local default="${2:-}"          # Default value (empty string if not provided)
    local response                  # Will hold user's input

    if [[ ! -t 0 ]]; then
        # Non-interactive mode: fall back to default if provided.
        if [[ -n "$default" ]]; then
            echo "$default"
            return 0
        fi
        echo ""
        return 0
    fi

    # Check if default value was provided
    # -n tests if string is non-empty
    if [[ -n "$default" ]]; then
        # Default provided: show it in brackets
        read -p "$(echo -e ${BLUE}?${NC} $prompt [$default]: )" response

        # If user pressed Enter without typing, use default
        # Output to stdout for caller to capture
        echo "${response:-$default}"
    else
        # No default: simple prompt
        read -p "$(echo -e ${BLUE}?${NC} $prompt: )" response

        # Output whatever user typed (might be empty)
        echo "$response"
    fi
}

# ============================================================================
# Prompt for Secret Input Function
# ============================================================================
# Purpose: Ask user for sensitive input (password, token, etc.) with hidden input
# Parameters:
#   $1 - Prompt text
#   $2 - Additional note/hint (optional)
# Returns: Prints the secret to stdout (captured by caller)
#
# Visual format:
#   ? Prompt text (note):  (input hidden)
#
# Usage examples:
#   password=$(prompt_secret "Enter password")
#   token=$(prompt_secret "Enter API token" "from GitHub settings")
#
# How it works:
# 1. Builds prompt message with optional note
# 2. Uses read -s to hide input (secret mode)
# 3. Prints newline after input (since Enter doesn't show)
# 4. Outputs the secret to stdout for caller to capture
#
# Security considerations:
# - Input is hidden from screen (read -s flag)
# - Secret is stored in bash variable (memory)
# - Secret might appear in process list if passed to commands
# - Secret might be logged if script has set -x enabled
# - Secret is printed to stdout (caller should capture immediately)
#
# read -s flag:
# -s = silent mode, don't echo input characters
# Essential for passwords and secrets
# User sees: ? Enter password: ________ (nothing appears as they type)
#
# Why echo "" after read?
# read -s doesn't print newline when user presses Enter
# Without echo "", next output would appear on same line
# echo "" moves cursor to next line for clean output
# ============================================================================
prompt_secret() {
    # Capture parameters
    local prompt="$1"               # Main prompt text
    local note="${2:-}"             # Optional note/hint (empty if not provided)
    local message="$prompt"         # Will hold final prompt message

    if [[ ! -t 0 ]]; then
        echo ""
        return 0
    fi

    # If note was provided, append it to message
    # -n tests if string is non-empty
    if [[ -n "$note" ]]; then
        # Add note in parentheses for context
        # Example: "Enter password (from password manager)"
        message="$message ($note)"
    fi

    # Initialize response as empty string
    # Important to initialize variables in bash
    local response=""

    # Prompt for secret input
    # -s = silent mode, don't echo input characters
    # -p = display prompt text
    # Input is hidden, but still captured in 'response' variable
    read -s -p "$(echo -e ${BLUE}?${NC} $message: )" response

    # Print newline since read -s doesn't
    # This moves cursor to next line after user presses Enter
    echo ""

    # Output the secret to stdout
    # Caller should capture this immediately: password=$(prompt_secret "Enter password")
    # Once captured, caller is responsible for securing the value
    echo "$response"
}

# ============================================================================
# User Interaction Best Practices Demonstrated
# ============================================================================
# 1. Consistent visual language: All prompts use blue ? icon
# 2. Clear defaults: Show default values in brackets [default]
# 3. Safe defaults: confirm() defaults to "n" for safety
# 4. Case insensitive: Accept both upper and lower case answers
# 5. Empty input handling: Pressing Enter uses default
# 6. Secret hiding: Use read -s for passwords
# 7. Return values via stdout: Use echo to "return" strings
# 8. Optional parameters: Use ${var:-default} for optional args
# 9. Unicode symbols: Use clear icons (?, ✓, ✗, ⚠, ℹ)
# 10. Color coding: Consistent colors for different message types
#
# Why these patterns?
# - Professional appearance: Consistent formatting
# - User-friendly: Clear prompts with helpful defaults
# - Secure: Proper handling of sensitive input
# - Flexible: Support optional parameters
# - Scriptable: Return values can be captured easily
# ============================================================================
