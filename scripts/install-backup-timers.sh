#!/usr/bin/env bash
#
# Install AIDB Backup Systemd Timers
#
# This script installs systemd user timers for automated backups:
# - PostgreSQL backup: Daily at 2:00 AM
# - Qdrant backup: Daily at 3:00 AM
#
# Usage: ./install-backup-timers.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "=== AIDB Backup Timer Installation ==="
echo ""

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_USER_DIR"
echo "✓ Systemd user directory: $SYSTEMD_USER_DIR"

# Copy service files
echo ""
echo "Installing service files..."
cp "$PROJECT_ROOT/systemd/aidb-backup-postgresql.service" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_ROOT/systemd/aidb-backup-postgresql.timer" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_ROOT/systemd/aidb-backup-qdrant.service" "$SYSTEMD_USER_DIR/"
cp "$PROJECT_ROOT/systemd/aidb-backup-qdrant.timer" "$SYSTEMD_USER_DIR/"
echo "✓ Service files copied"

# Make backup scripts executable
echo ""
echo "Making backup scripts executable..."
chmod +x "$PROJECT_ROOT/scripts/backup-postgresql.sh"
chmod +x "$PROJECT_ROOT/scripts/backup-qdrant.sh"
echo "✓ Backup scripts are executable"

# Reload systemd daemon
echo ""
echo "Reloading systemd daemon..."
systemctl --user daemon-reload
echo "✓ Systemd daemon reloaded"

# Enable and start timers
echo ""
echo "Enabling and starting timers..."
systemctl --user enable aidb-backup-postgresql.timer
systemctl --user start aidb-backup-postgresql.timer
systemctl --user enable aidb-backup-qdrant.timer
systemctl --user start aidb-backup-qdrant.timer
echo "✓ Timers enabled and started"

# Show timer status
echo ""
echo "=== Timer Status ==="
systemctl --user list-timers aidb-backup-* --all

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Backup Schedule:"
echo "  - PostgreSQL: Daily at 2:00 AM"
echo "  - Qdrant:     Daily at 3:00 AM"
echo ""
echo "Commands:"
echo "  Status:       systemctl --user status aidb-backup-postgresql.timer"
echo "  Logs:         journalctl --user -u aidb-backup-postgresql.service"
echo "  Run now:      systemctl --user start aidb-backup-postgresql.service"
echo "  Disable:      systemctl --user disable aidb-backup-postgresql.timer"
echo ""
