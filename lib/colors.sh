#!/usr/bin/env bash
#
# Color Definitions
# Purpose: Terminal color codes for formatted output
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - None (standalone)
#
# Required Variables:
#   - None
#
# Exports:
#   - RED → Red color code for error messages
#   - GREEN → Green color code for success messages
#   - YELLOW → Yellow color code for warnings
#   - BLUE → Blue color code for info messages
#   - NC → No Color - resets terminal color
#
# ============================================================================

# ============================================================================
# ANSI Color Codes for Terminal Output
# ============================================================================
# These are ANSI escape sequences that control terminal text formatting.
# Format: \033[<code>m where \033 is the ESC character
#
# Understanding ANSI codes:
# - \033 or \e = ESC (escape) character to start a control sequence
# - [ = Introduces a Control Sequence Introducer (CSI)
# - Numbers = Specify the formatting (0=reset, 30-37=colors, etc.)
# - m = Marks the end of the sequence
#
# Color codes used:
# - 0;31 = Normal intensity red
# - 0;32 = Normal intensity green
# - 1;33 = Bold yellow (1 = bold/bright)
# - 0;34 = Normal intensity blue
# - 0 = Reset all attributes
#
# Usage in scripts:
#   echo -e "${RED}This is red${NC}"
#   The -e flag enables interpretation of backslash escapes
#   Always end colored text with ${NC} to reset formatting
# ============================================================================

# Red color - Used for errors and critical failures
# Normal intensity (0;31) to avoid being too bright/jarring
RED='\033[0;31m'

# Green color - Used for success messages and confirmations
# Normal intensity (0;32) for consistent appearance
GREEN='\033[0;32m'

# Yellow color - Used for warnings and important notices
# Bold/bright (1;33) to make warnings stand out
YELLOW='\033[1;33m'

# Blue color - Used for informational messages
# Normal intensity (0;34) for casual information display
BLUE='\033[0;34m'

# No Color - Resets all text formatting attributes
# CRITICAL: Always use this after colored text to prevent color bleeding
# into subsequent output. Without this, all following text stays colored.
NC='\033[0m'

# ============================================================================
# Why use ANSI codes instead of tput?
# ============================================================================
# 1. Portability: ANSI codes work in virtually all modern terminals
# 2. Performance: No external command calls (tput requires forking)
# 3. Simplicity: Direct codes are easier to understand and maintain
# 4. Dependencies: No need for ncurses/terminfo database
# 5. Reliability: Works even if TERM variable is not properly set
#
# Tradeoff: tput is more portable to ancient terminals (pre-1980s), but
# those are essentially non-existent in modern systems.
# ============================================================================
