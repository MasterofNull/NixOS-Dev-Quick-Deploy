#!/usr/bin/env bash
#
# BATS Test Helper - Common setup for all unit tests
#
# Usage: Add to top of each .bats file:
#   load test_helper
#

# Project root (two levels up from tests/unit/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIB_DIR="$PROJECT_ROOT/lib"
CONFIG_DIR="$PROJECT_ROOT/config"

# Minimal stubs for functions that libraries may check for
log() { :; }
print_warning() { :; }
print_error() { :; }
print_info() { :; }

export -f log print_warning print_error print_info

# Source settings first (provides defaults for library variables)
source "$CONFIG_DIR/settings.sh"
