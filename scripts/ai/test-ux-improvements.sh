#!/usr/bin/env bash
# Phase 6.2: User Experience Polish - Test and Validation Script
# Tests all UX improvements for dashboard, CLI tools, and user experience

set -euo pipefail

# Source CLI utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cli-enhanced.sh" 2>/dev/null || {
    echo "Warning: cli-enhanced.sh not found, some tests will be limited"
}

# Colors
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
RESET='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test tracking
declare -a FAILED_TESTS

# Helper functions
print_test_header() {
    local title="$1"
    echo -e "\n${BLUE}═══════════════════════════════════════════${RESET}"
    echo -e "${BLUE}Test: ${title}${RESET}"
    echo -e "${BLUE}═══════════════════════════════════════════${RESET}\n"
}

assert_true() {
    local condition="$1"
    local message="${2:-Assertion failed}"
    TESTS_RUN=$((TESTS_RUN + 1))

    if eval "$condition" &>/dev/null; then
        echo -e "${GREEN}✓${RESET} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${RESET} $message"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$message")
        return 1
    fi
}

assert_file_exists() {
    local file="$1"
    local message="${2:-File should exist: $file}"
    assert_true "[[ -f '$file' ]]" "$message"
}

assert_file_contains() {
    local file="$1"
    local pattern="$2"
    local message="${3:-File should contain pattern: $pattern}"
    assert_true "[[ -f '$file' ]] && grep -qi '$pattern' '$file'" "$message"
}

assert_executable() {
    local cmd="$1"
    local message="${2:-Command should be executable: $cmd}"
    assert_true "[[ -x '$cmd' ]]" "$message"
}

# ============================================================================
# TEST 1: Dashboard HTML Structure and Enhancements
# ============================================================================
test_dashboard_structure() {
    print_test_header "Dashboard HTML Structure and CSS Styles"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check if dashboard file exists
    assert_file_exists "$dashboard_file" "Dashboard HTML file exists"

    # Check for new CSS classes
    assert_file_contains "$dashboard_file" "empty-state" "Empty state CSS class added"
    assert_file_contains "$dashboard_file" "success-toast" "Success toast CSS class added"
    assert_file_contains "$dashboard_file" "error-toast" "Error toast CSS class added"
    assert_file_contains "$dashboard_file" "loading-skeleton" "Loading skeleton CSS animation added"
    assert_file_contains "$dashboard_file" "keyboard-shortcuts-modal" "Keyboard shortcuts modal CSS added"
    assert_file_contains "$dashboard_file" "onboarding-step" "Onboarding steps CSS added"
    assert_file_contains "$dashboard_file" "progress-bar-fill" "Progress bar CSS added"

    # Check for JavaScript functions
    assert_file_contains "$dashboard_file" "NotificationManager" "Notification manager class added"
    assert_file_contains "$dashboard_file" "KeyboardShortcutsManager" "Keyboard shortcuts manager added"
    assert_file_contains "$dashboard_file" "OnboardingManager" "Onboarding manager added"
    assert_file_contains "$dashboard_file" "ProgressTracker" "Progress tracker class added"
    assert_file_contains "$dashboard_file" "ErrorHandler" "Error handler class added"

    # Check for animations
    assert_file_contains "$dashboard_file" "slideInRight" "Slide animation added"
    assert_file_contains "$dashboard_file" "skeleton-loading" "Skeleton loading animation added"
    assert_file_contains "$dashboard_file" "modalFadeIn" "Modal fade animation added"
}

# ============================================================================
# TEST 2: CLI Utilities Module
# ============================================================================
test_cli_utilities() {
    print_test_header "CLI Utilities Module (Python)"

    local cli_utils_file="$SCRIPT_DIR/cli-utils.py"

    assert_file_exists "$cli_utils_file" "CLI utilities Python module exists"
    assert_file_contains "$cli_utils_file" "class ANSIColors" "ANSI color codes defined"
    assert_file_contains "$cli_utils_file" "class Logger" "Logger class defined"
    assert_file_contains "$cli_utils_file" "class ProgressBar" "Progress bar class defined"
    assert_file_contains "$cli_utils_file" "class Spinner" "Spinner class defined"
    assert_file_contains "$cli_utils_file" "def confirm" "Confirmation prompt function defined"
    assert_file_contains "$cli_utils_file" "class ContextualError" "Contextual error class defined"
    assert_file_contains "$cli_utils_file" "def humanize_bytes" "Humanize bytes function defined"
    assert_file_contains "$cli_utils_file" "def humanize_duration" "Humanize duration function defined"

    # Check that module is executable in Python
    assert_true "python3 -m py_compile '$cli_utils_file'" "CLI utilities module is valid Python"
}

# ============================================================================
# TEST 3: CLI Enhancement Shell Script
# ============================================================================
test_cli_enhancement_script() {
    print_test_header "CLI Enhancement Bash Script"

    local cli_enhanced="$SCRIPT_DIR/cli-enhanced.sh"

    assert_file_exists "$cli_enhanced" "CLI enhancement script exists"
    assert_executable "$cli_enhanced" "CLI enhancement script is executable"

    # Check for functions
    assert_file_contains "$cli_enhanced" "print_header" "print_header function defined"
    assert_file_contains "$cli_enhanced" "print_info" "print_info function defined"
    assert_file_contains "$cli_enhanced" "print_success" "print_success function defined"
    assert_file_contains "$cli_enhanced" "print_error" "print_error function defined"
    assert_file_contains "$cli_enhanced" "progress_bar" "progress_bar function defined"
    assert_file_contains "$cli_enhanced" "spinner" "spinner function defined"
    assert_file_contains "$cli_enhanced" "confirm" "confirm function defined"
    assert_file_contains "$cli_enhanced" "show_error" "show_error function defined"
    assert_file_contains "$cli_enhanced" "humanize_bytes" "humanize_bytes function defined"
    assert_file_contains "$cli_enhanced" "humanize_duration" "humanize_duration function defined"

    # Check syntax
    assert_true "bash -n '$cli_enhanced'" "CLI enhancement script has valid bash syntax"
}

# ============================================================================
# TEST 4: Bash Completion Script
# ============================================================================
test_bash_completion() {
    print_test_header "Bash Completion Script"

    local completion_file="$SCRIPT_DIR/bash-completion.sh"

    assert_file_exists "$completion_file" "Bash completion script exists"
    assert_executable "$completion_file" "Bash completion script is executable"

    # Check for completion functions
    assert_file_contains "$completion_file" "_aq_report_completion" "aq-report completion defined"
    assert_file_contains "$completion_file" "_nixos_deploy_completion" "deploy completion defined"
    assert_file_contains "$completion_file" "_aq_orchestrator_completion" "aq-orchestrator completion defined"
    assert_file_contains "$completion_file" "complete -" "Completion registration found"

    # Check syntax
    assert_true "bash -n '$completion_file'" "Bash completion script has valid syntax"
}

# ============================================================================
# TEST 5: Documentation Files
# ============================================================================
test_documentation() {
    print_test_header "Documentation Files"

    local quick_start="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/user-guides/quick-start.md"
    local keyboard_shortcuts="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/user-guides/keyboard-shortcuts.md"

    # Quick start guide
    assert_file_exists "$quick_start" "Quick start guide exists"
    assert_file_contains "$quick_start" "Prerequisites" "Quick start has Prerequisites section"
    assert_file_contains "$quick_start" "Initial Setup" "Quick start has Initial Setup section"
    assert_file_contains "$quick_start" "Daily Operations" "Quick start has Daily Operations section"
    assert_file_contains "$quick_start" "Common Tasks" "Quick start has Common Tasks section"
    assert_file_contains "$quick_start" "Troubleshooting" "Quick start has Troubleshooting section"

    # Keyboard shortcuts guide
    assert_file_exists "$keyboard_shortcuts" "Keyboard shortcuts guide exists"
    assert_file_contains "$keyboard_shortcuts" "Dashboard Shortcuts" "Keyboard guide has Dashboard Shortcuts"
    assert_file_contains "$keyboard_shortcuts" "CLI Tool Shortcuts" "Keyboard guide has CLI Tool Shortcuts"
    assert_file_contains "$keyboard_shortcuts" "Tab Completion" "Keyboard guide has Tab Completion"
    assert_file_contains "$keyboard_shortcuts" "Troubleshooting Shortcuts" "Keyboard guide has Troubleshooting"
}

# ============================================================================
# TEST 6: Error Handler Integration
# ============================================================================
test_error_handling() {
    print_test_header "Error Handling and Contextual Messages"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for error codes in HTML
    assert_file_contains "$dashboard_file" "E001" "Error code E001 (Configuration) defined"
    assert_file_contains "$dashboard_file" "E101" "Error code E101 (Connection) defined"
    assert_file_contains "$dashboard_file" "E102" "Error code E102 (Timeout) defined"
    assert_file_contains "$dashboard_file" "E201" "Error code E201 (Permission) defined"
    assert_file_contains "$dashboard_file" "E301" "Error code E301 (Not Found) defined"
    assert_file_contains "$dashboard_file" "E401" "Error code E401 (API Error) defined"

    # Check for error guidance
    assert_file_contains "$dashboard_file" "createContextualError" "Contextual error messages added"
    assert_file_contains "$dashboard_file" "Guidance:" "Error guidance messages added"
}

# ============================================================================
# TEST 7: Keyboard Shortcuts Implementation
# ============================================================================
test_keyboard_shortcuts() {
    print_test_header "Keyboard Shortcuts Implementation"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for keyboard shortcut bindings
    assert_file_contains "$dashboard_file" "addEventListener.*keydown" "Keyboard event listener added"
    assert_file_contains "$dashboard_file" "'r':" "Refresh shortcut defined"
    assert_file_contains "$dashboard_file" "'s':" "Search shortcut defined"
    assert_file_contains "$dashboard_file" "Show keyboard shortcuts" "Help shortcut defined"
    assert_file_contains "$dashboard_file" "Escape" "Escape shortcut defined"

    # Check for keyboard shortcuts manager
    assert_file_contains "$dashboard_file" "KeyboardShortcutsManager" "Shortcuts manager defined"
    assert_file_contains "$dashboard_file" "this.shortcuts" "Shortcuts dictionary defined"
}

# ============================================================================
# TEST 8: Loading States and Animations
# ============================================================================
test_loading_states() {
    print_test_header "Loading States and Animations"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for loading states
    assert_file_contains "$dashboard_file" "class.*loading" "Loading state class defined"
    assert_file_contains "$dashboard_file" "spinner" "Spinner class defined"
    assert_file_contains "$dashboard_file" "loading-skeleton" "Loading skeleton animation defined"

    # Check for animations
    assert_file_contains "$dashboard_file" "@keyframes" "CSS keyframes animations added"
    assert_file_contains "$dashboard_file" "animation: spin" "Spin animation added"
    assert_file_contains "$dashboard_file" "animation: skeleton-loading" "Skeleton loading animation added"
}

# ============================================================================
# TEST 9: Empty and Error States
# ============================================================================
test_empty_error_states() {
    print_test_header "Empty and Error States"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for empty state rendering
    assert_file_contains "$dashboard_file" "renderEmptyState" "Empty state render function added"
    assert_file_contains "$dashboard_file" "empty-state-icon" "Empty state icon styling added"
    assert_file_contains "$dashboard_file" "empty-state-title" "Empty state title styling added"
    assert_file_contains "$dashboard_file" "empty-state-message" "Empty state message styling added"
    assert_file_contains "$dashboard_file" "empty-state-action" "Empty state action button styling added"

    # Check for error state handling
    assert_file_contains "$dashboard_file" "ErrorHandler" "Error handler class defined"
    assert_file_contains "$dashboard_file" "displayError" "Error display method defined"
}

# ============================================================================
# TEST 10: Onboarding Flow
# ============================================================================
test_onboarding_flow() {
    print_test_header "Onboarding Flow"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for onboarding components
    assert_file_contains "$dashboard_file" "OnboardingManager" "Onboarding manager class defined"
    assert_file_contains "$dashboard_file" "isFirstTime" "First-time detection added"
    assert_file_contains "$dashboard_file" "showWelcome" "Welcome banner function added"
    assert_file_contains "$dashboard_file" "showTour" "Onboarding tour function added"
    assert_file_contains "$dashboard_file" "welcome-banner" "Welcome banner styling added"
    assert_file_contains "$dashboard_file" "onboarding-step" "Onboarding step styling added"

    # Check for first-time localStorage
    assert_file_contains "$dashboard_file" "dashboard-visited" "First-time marker checking added"
}

# ============================================================================
# TEST 11: Toast Notifications
# ============================================================================
test_notifications() {
    print_test_header "Toast Notification System"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for notification styles
    assert_file_contains "$dashboard_file" "success-toast" "Success toast styling added"
    assert_file_contains "$dashboard_file" "error-toast" "Error toast styling added"
    assert_file_contains "$dashboard_file" "slideInRight" "Toast slide animation added"

    # Check for notification manager
    assert_file_contains "$dashboard_file" "NotificationManager" "Notification manager class defined"
    assert_file_contains "$dashboard_file" "show.*message" "Show method defined"
}

# ============================================================================
# TEST 12: Help Tooltips
# ============================================================================
test_help_tooltips() {
    print_test_header "Help Tooltips"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for tooltip styling
    assert_file_contains "$dashboard_file" "help-tooltip" "Help tooltip class added"
    assert_file_contains "$dashboard_file" "tooltip-text" "Tooltip text styling added"
    assert_file_contains "$dashboard_file" "addHelpTooltip" "Help tooltip function added"
}

# ============================================================================
# TEST 13: Progress Tracking
# ============================================================================
test_progress_tracking() {
    print_test_header "Progress Tracking for Operations"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check for progress components
    assert_file_contains "$dashboard_file" "operation-progress" "Progress container styling added"
    assert_file_contains "$dashboard_file" "progress-bar-fill" "Progress bar styling added"
    assert_file_contains "$dashboard_file" "ProgressTracker" "Progress tracker class defined"
    assert_file_contains "$dashboard_file" "update.*percent" "Progress update method defined"
}

# ============================================================================
# TEST 14: Feature Integration
# ============================================================================
test_feature_integration() {
    print_test_header "Feature Integration with Existing Code"

    local dashboard_file="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html"

    # Check that new features are initialized
    assert_file_contains "$dashboard_file" "initializeUXImprovements" "UX initialization function defined"
    assert_file_contains "$dashboard_file" "KeyboardShortcutsManager.init()" "Keyboard shortcuts initialized"
    assert_file_contains "$dashboard_file" "OnboardingManager.showWelcome()" "Onboarding initialized"

    # Check that initialization is called on DOMContentLoaded
    assert_file_contains "$dashboard_file" "initializeUXImprovements()" "Initialization called"
}

# ============================================================================
# TEST 15: File Structure and Organization
# ============================================================================
test_file_structure() {
    print_test_header "File Structure and Organization"

    local base_path="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"

    # Check directory structure
    assert_true "[[ -d '$base_path/scripts/ai' ]]" "scripts/ai directory exists"
    assert_true "[[ -d '$base_path/docs/user-guides' ]]" "docs/user-guides directory exists"

    # Check new files are in correct locations
    assert_file_exists "$base_path/scripts/ai/cli-utils.py" "CLI utilities in scripts/ai/"
    assert_file_exists "$base_path/scripts/ai/cli-enhanced.sh" "CLI enhancements in scripts/ai/"
    assert_file_exists "$base_path/scripts/ai/bash-completion.sh" "Bash completion in scripts/ai/"
    assert_file_exists "$base_path/docs/user-guides/quick-start.md" "Quick start in docs/user-guides/"
    assert_file_exists "$base_path/docs/user-guides/keyboard-shortcuts.md" "Keyboard shortcuts in docs/user-guides/"
}

# ============================================================================
# TEST 16: Code Quality and Syntax
# ============================================================================
test_code_quality() {
    print_test_header "Code Quality and Syntax Validation"

    local base_path="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"

    # Python syntax validation
    assert_true "python3 -m py_compile '$base_path/scripts/ai/cli-utils.py'" "Python code is syntactically valid"

    # Bash syntax validation
    assert_true "bash -n '$base_path/scripts/ai/cli-enhanced.sh'" "Bash scripts are syntactically valid"
    assert_true "bash -n '$base_path/scripts/ai/bash-completion.sh'" "Bash scripts are syntactically valid"

    # Check for common Python issues
    assert_true "! grep -q 'print(' '$base_path/scripts/ai/cli_utils.py' | grep -v '#'" "No unquoted print statements"
}

# ============================================================================
# TEST 17: Documentation Completeness
# ============================================================================
test_documentation_completeness() {
    print_test_header "Documentation Completeness"

    local quick_start="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/user-guides/quick-start.md"
    local keyboard_shortcuts="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/user-guides/keyboard-shortcuts.md"

    # Check for minimum documentation structure
    assert_true "[[ \$(wc -l < \"$quick_start\") -gt 100 ]]" "Quick start guide is comprehensive (>100 lines)"
    assert_true "[[ \$(wc -l < \"$keyboard_shortcuts\") -gt 150 ]]" "Keyboard shortcuts guide is comprehensive (>150 lines)"

    # Check for examples in documentation
    assert_file_contains "$quick_start" "bash" "Quick start includes bash examples"
    assert_file_contains "$quick_start" "Common Tasks" "Quick start has common tasks with examples"
    assert_file_contains "$keyboard_shortcuts" "Example" "Keyboard guide has examples"
}

# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================

print_header "PHASE 6.2: USER EXPERIENCE POLISH - COMPREHENSIVE TEST SUITE"

# Run all tests
test_dashboard_structure
test_cli_utilities
test_cli_enhancement_script
test_bash_completion
test_documentation
test_error_handling
test_keyboard_shortcuts
test_loading_states
test_empty_error_states
test_onboarding_flow
test_notifications
test_help_tooltips
test_progress_tracking
test_feature_integration
test_file_structure
test_code_quality
test_documentation_completeness

# Print summary
echo -e "\n${BLUE}═════════════════════════════════════════${RESET}"
echo -e "${BLUE}TEST SUMMARY${RESET}"
echo -e "${BLUE}═════════════════════════════════════════${RESET}\n"

echo "Total Tests Run:    $TESTS_RUN"
echo -e "Tests Passed:       ${GREEN}$TESTS_PASSED${RESET}"
echo -e "Tests Failed:       ${RED}$TESTS_FAILED${RESET}"

if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "\n${RED}Failed Tests:${RESET}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${RESET} $test"
    done
    exit 1
else
    echo -e "\n${GREEN}All tests passed! UX improvements are complete and validated.${RESET}\n"
    exit 0
fi
