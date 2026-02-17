#!/usr/bin/env bash
# Systemd system-sleep hook to recover Podman runtime after resume.
# Install: sudo cp this file to /etc/systemd/system-sleep/
# Enable: chmod +x /etc/systemd/system-sleep/ai-stack-resume-recovery.sh

set -euo pipefail

export PROJECT_ROOT="@PROJECT_ROOT@"
export AI_STACK_USER="@AI_STACK_USER@"
export AI_STACK_UID="@AI_STACK_UID@"

exec "${PROJECT_ROOT}/scripts/ai-stack-resume-recovery.sh" "$@"
