#!/usr/bin/env bash
# Cron Job Templates for Federated Learning Automation
# Version: 1.0.0
# Created: 2025-12-21
#
# This file contains template cron jobs to automate federated learning data
# synchronization. Copy the relevant lines to your crontab.
#
# Usage:
#   crontab -e
#   # Then paste the desired cron jobs below

# ============================================================================
# RECOMMENDED SCHEDULE
# ============================================================================

# Option 1: CONSERVATIVE (Recommended for most users)
# - Sync learning data hourly (lightweight, just pattern extraction)
# - Export collections weekly (heavier, full collection exports)
# - Generate dashboard data every 5 minutes (for monitoring)

# Every hour: Sync high-value patterns from runtime to git repo
0 * * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh" >> /var/log/federated-sync.log 2>&1

# Every Sunday at 2 AM: Export Qdrant collections to git repo
0 2 * * 0 bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/export-collections.sh" >> /var/log/federated-export.log 2>&1

# Every 5 minutes: Generate dashboard metrics
*/5 * * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh" >> /var/log/dashboard-metrics.log 2>&1


# ============================================================================
# Option 2: AGGRESSIVE (For active development/testing)
# ============================================================================
# - Sync learning data every 15 minutes
# - Export collections daily
# - Generate dashboard data every minute

# Every 15 minutes: Sync patterns
*/15 * * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh" >> /var/log/federated-sync.log 2>&1

# Daily at 3 AM: Export collections
0 3 * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/export-collections.sh" >> /var/log/federated-export.log 2>&1

# Every minute: Dashboard metrics
* * * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh" >> /var/log/dashboard-metrics.log 2>&1


# ============================================================================
# Option 3: MINIMAL (For production with manual control)
# ============================================================================
# - Sync learning data daily
# - Export collections monthly
# - Generate dashboard data hourly

# Daily at 1 AM: Sync patterns
0 1 * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh" >> /var/log/federated-sync.log 2>&1

# First day of month at 2 AM: Export collections
0 2 1 * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/export-collections.sh" >> /var/log/federated-export.log 2>&1

# Hourly: Dashboard metrics
0 * * * * bash "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh" >> /var/log/dashboard-metrics.log 2>&1


# ============================================================================
# AUTOMATED GIT COMMIT (Optional)
# ============================================================================
# Automatically commit synced data to git every 6 hours
# WARNING: This will create many commits. Consider using a dedicated branch.

0 */6 * * * cd "$HOME/Documents/try/NixOS-Dev-Quick-Deploy" && git add data/ && git commit -m "Automated federated data sync - $(date +\%Y-\%m-\%d\ \%H:\%M)" && git push origin main >> /var/log/federated-git.log 2>&1


# ============================================================================
# LOG ROTATION (Recommended)
# ============================================================================
# Prevent log files from growing indefinitely

# Weekly log rotation for all federated learning logs
0 0 * * 0 find /var/log/ -name "federated-*.log" -type f -exec bash -c 'mv {} {}.old && touch {}' \; && find /var/log/ -name "federated-*.log.old" -mtime +30 -delete


# ============================================================================
# HEALTH MONITORING (Optional)
# ============================================================================
# Run health checks and log results

# Every 30 minutes: Check AI stack health
*/30 * * * * python3 "$HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-health.sh" -v >> /var/log/ai-stack-health.log 2>&1


# ============================================================================
# SYSTEMD TIMER ALTERNATIVE (More powerful than cron)
# ============================================================================
#
# If you prefer systemd timers over cron, create these files:
#
# /etc/systemd/system/federated-sync.service
# -------------------------------------------
# [Unit]
# Description=Federated Learning Data Sync
# After=network.target
#
# [Service]
# Type=oneshot
# User=$USER
# ExecStart=/usr/bin/bash $HOME/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh
# StandardOutput=append:/var/log/federated-sync.log
# StandardError=append:/var/log/federated-sync.log
#
# [Install]
# WantedBy=multi-user.target
#
#
# /etc/systemd/system/federated-sync.timer
# ------------------------------------------
# [Unit]
# Description=Run Federated Learning Data Sync Hourly
# Requires=federated-sync.service
#
# [Timer]
# OnBootSec=5min
# OnUnitActiveSec=1h
# Persistent=true
#
# [Install]
# WantedBy=timers.target
#
#
# Enable with:
#   sudo systemctl enable --now federated-sync.timer
#   sudo systemctl status federated-sync.timer


# ============================================================================
# NOTES
# ============================================================================
#
# 1. Log File Locations:
#    - /var/log/federated-sync.log    - Pattern sync logs
#    - /var/log/federated-export.log  - Collection export logs
#    - /var/log/federated-git.log     - Git commit logs
#    - /var/log/dashboard-metrics.log - Dashboard generation logs
#    - /var/log/ai-stack-health.log   - Health check logs
#
# 2. Before Enabling:
#    - Replace $HOME if your repo lives outside your home directory
#    - Verify script paths match your installation
#    - Ensure scripts are executable (chmod +x)
#    - Test scripts manually first
#    - Create log directory: sudo mkdir -p /var/log && sudo chown $USER:$USER /var/log
#
# 3. Verify Cron Jobs:
#    - List active cron jobs: crontab -l
#    - Check cron logs: journalctl -u cron
#    - Test individual jobs manually first
#
# 4. Git Automation Security:
#    - Automated git commits should use SSH keys (not passwords)
#    - Set up SSH key: ssh-keygen -t ed25519 -C "federated-learning@$(hostname)"
#    - Add to GitHub: cat ~/.ssh/id_ed25519.pub
#    - Test: ssh -T git@github.com
#
# 5. Federation Best Practices:
#    - Review data/ contents before pushing to git
#    - Ensure .gitignore is correctly configured
#    - Monitor data/ directory size (should stay < 50MB)
#    - Periodically review and clean old snapshots
#    - Never commit PII or API keys
#
# 6. Troubleshooting:
#    - If cron jobs don't run: Check cron service (systemctl status cron)
#    - If scripts fail: Check permissions and paths
#    - If logs fill disk: Implement log rotation
#    - If git push fails: Check SSH keys and network
