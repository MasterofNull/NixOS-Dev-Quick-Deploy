#!/usr/bin/env bash
#
# Default Values
# Purpose: Default configuration values for the deployment
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - None (must be loaded early)
#
# Exports:
#   - Default configuration values
#
# ============================================================================
# Why separate defaults file?
# - Centralized: All defaults in one place
# - Override-able: Can be overridden by environment variables or flags
# - Documentation: Clearly shows what the defaults are
# - Maintainability: Easy to change defaults without hunting through code
# ============================================================================

# ============================================================================
# Channel Defaults
# ============================================================================
# NixOS has two main channels:
# - stable: Tested, slower updates (e.g., 23.11, 24.05)
# - unstable: Latest packages, faster updates, may have occasional issues
#
# Unstable is chosen as default because:
# - Latest software versions (important for AI/ML packages)
# - Faster bug fixes
# - NixOS rollback makes it safe to use unstable
# - Can easily rollback if update causes issues
# ============================================================================

DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-unstable}"  # Can override with env var

# ============================================================================
# Timezone Defaults
# ============================================================================
# Used if timezone cannot be detected from system
# America/New_York chosen as reasonable default for US users
# Can be overridden during deployment
# ============================================================================

DEFAULT_TIMEZONE="America/New_York"

# ============================================================================
# Locale Defaults
# ============================================================================
# en_US.UTF-8 is standard English US locale with Unicode support
# UTF-8 ensures proper display of international characters
# Most software expects UTF-8 encoding in modern systems
# ============================================================================

DEFAULT_LOCALE="en_US.UTF-8"

# ============================================================================
# System Defaults
# ============================================================================
# These are opinionated defaults that can be changed during setup
# ============================================================================

DEFAULT_SHELL="zsh"   # Modern shell with better UX than bash (history, completion, themes)
DEFAULT_EDITOR="vim"  # Universal editor available everywhere

# ============================================================================
# Hardware Defaults
# ============================================================================
# Fallback values when hardware detection fails
# Software rendering is safe fallback (works on all systems)
# ============================================================================

DEFAULT_GPU_TYPE="software"      # Use software rendering if GPU not detected
DEFAULT_CPU_VENDOR="unknown"     # Unknown CPU when detection fails

# ============================================================================
# Service Defaults
# ============================================================================
# Default ports for services deployed by this script
#
# Port selection considerations:
# - Gitea HTTP (3000): Standard Gitea default, non-privileged port
# - Gitea SSH (2222): Avoids conflict with system SSH (22), non-privileged
# ============================================================================

DEFAULT_GITEA_HTTP_PORT=3000  # Gitea web interface port
DEFAULT_GITEA_SSH_PORT=2222   # Gitea SSH git operations port

# ============================================================================
# Application Defaults
# ============================================================================
# Default versions for programming language runtimes
# These are LTS or stable versions with good ecosystem support
#
# Python 3.13: Current stable, good AI/ML library support
# Node.js 20: Current LTS version, best for production use
# ============================================================================

DEFAULT_PYTHON_VERSION="3.13"  # Python version for development environment
DEFAULT_NODE_VERSION="20"      # Node.js version for development environment

# ============================================================================
# Deployment Behavior Defaults
# ============================================================================
# Control how the deployment script behaves
#
# AUTO_CONFIRM: Whether to skip confirmation prompts
#   false = interactive (ask user for confirmations)
#   true = non-interactive (for CI/CD, automation)
#
# VERBOSE: Whether to show detailed output
#   false = normal output (user-friendly)
#   true = verbose output (for debugging)
#
# DRY_RUN: Whether to simulate without making changes
#   false = normal mode (actually make changes)
#   true = dry-run (show what would be done, don't actually do it)
# ============================================================================

DEFAULT_AUTO_CONFIRM=false  # Interactive by default (safe)
DEFAULT_VERBOSE=false       # Normal output by default
DEFAULT_DRY_RUN=false       # Actually make changes by default
