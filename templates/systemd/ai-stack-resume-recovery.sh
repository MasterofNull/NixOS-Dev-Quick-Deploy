#!/usr/bin/env bash
# Systemd system-sleep hook to recover Podman runtime after resume.
# Install: sudo cp this file to /etc/systemd/system-sleep/
# Enable: chmod +x /etc/systemd/system-sleep/ai-stack-resume-recovery.sh

set -euo pipefail

export PROJECT_ROOT="/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy"
export AI_STACK_USER="hyperd"
export AI_STACK_UID="1000"

exec "${PROJECT_ROOT}/scripts/ai-stack-resume-recovery.sh" "$@"
