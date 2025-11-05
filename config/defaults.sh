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

# ============================================================================
# Channel Defaults
# ============================================================================

# Default channel track (stable or unstable)
DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-unstable}"

# ============================================================================
# Timezone Defaults
# ============================================================================

# Default timezone if none can be detected
DEFAULT_TIMEZONE="America/New_York"

# ============================================================================
# Locale Defaults
# ============================================================================

# Default locale setting
DEFAULT_LOCALE="en_US.UTF-8"

# ============================================================================
# System Defaults
# ============================================================================

# Default shell
DEFAULT_SHELL="zsh"

# Default editor
DEFAULT_EDITOR="vim"

# ============================================================================
# Hardware Defaults
# ============================================================================

# Default GPU type when detection fails
DEFAULT_GPU_TYPE="software"

# Default CPU vendor when detection fails
DEFAULT_CPU_VENDOR="unknown"

# ============================================================================
# Service Defaults
# ============================================================================

# Default Gitea HTTP port
DEFAULT_GITEA_HTTP_PORT=3000

# Default Gitea SSH port
DEFAULT_GITEA_SSH_PORT=2222

# ============================================================================
# Application Defaults
# ============================================================================

# Default Python version
DEFAULT_PYTHON_VERSION="3.11"

# Default Node.js version
DEFAULT_NODE_VERSION="20"

# ============================================================================
# Deployment Behavior Defaults
# ============================================================================

# Skip confirmation prompts (for CI/CD)
DEFAULT_AUTO_CONFIRM=false

# Enable verbose output
DEFAULT_VERBOSE=false

# Enable dry-run mode
DEFAULT_DRY_RUN=false
