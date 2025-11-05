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

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
