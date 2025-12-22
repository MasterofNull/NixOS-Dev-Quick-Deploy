# 44: Federation Automation

**Category**: Deployment & Operations
**Prerequisites**: [43-FEDERATED-DEPLOYMENT](43-FEDERATED-DEPLOYMENT.md)
**Canonical Source**: [scripts/cron-templates.sh](../../scripts/cron-templates.sh)

---

## Overview

This guide covers automated federation workflows using cron jobs and systemd timers. For complete cron templates and examples, see the canonical source: [scripts/cron-templates.sh](../../scripts/cron-templates.sh)

---

## Recommended Schedules

### Conservative (Recommended)

Best for production systems with stable workloads:

```cron
# Hourly: Sync high-value patterns
0 * * * * bash /path/to/scripts/sync-learning-data.sh >> /var/log/federated-sync.log 2>&1

# Weekly (Sunday 2 AM): Export Qdrant collections
0 2 * * 0 bash /path/to/scripts/export-collections.sh >> /var/log/federated-export.log 2>&1

# Every 5 minutes: Dashboard metrics
*/5 * * * * bash /path/to/scripts/generate-dashboard-data.sh >> /var/log/dashboard-metrics.log 2>&1
```

**Rationale**:
- Pattern sync is lightweight, can run hourly
- Collection export is heavier, weekly is sufficient
- Dashboard updates frequently for real-time monitoring

### Aggressive (Development)

Best for active development and testing:

```cron
# Every 15 minutes: Sync patterns
*/15 * * * * bash /path/to/scripts/sync-learning-data.sh >> /var/log/federated-sync.log 2>&1

# Daily (3 AM): Export collections
0 3 * * * bash /path/to/scripts/export-collections.sh >> /var/log/federated-export.log 2>&1

# Every minute: Dashboard metrics
* * * * * bash /path/to/scripts/generate-dashboard-data.sh >> /var/log/dashboard-metrics.log 2>&1
```

**Rationale**:
- Rapid iteration requires frequent syncing
- Daily collection exports catch changes quickly
- Real-time dashboard updates

### Minimal (Manual Control)

Best for low-activity systems or when manual review is required:

```cron
# Daily (1 AM): Sync patterns
0 1 * * * bash /path/to/scripts/sync-learning-data.sh >> /var/log/federated-sync.log 2>&1

# Monthly (1st at 2 AM): Export collections
0 2 1 * * bash /path/to/scripts/export-collections.sh >> /var/log/federated-export.log 2>&1

# Hourly: Dashboard metrics
0 * * * * bash /path/to/scripts/generate-dashboard-data.sh >> /var/log/dashboard-metrics.log 2>&1
```

---

## Setup Instructions

### 1. Configure Cron Jobs

```bash
# Edit crontab
crontab -e

# Paste desired schedule from scripts/cron-templates.sh
# Replace /path/to/ with actual path (e.g., /home/user/Documents/try/NixOS-Dev-Quick-Deploy)

# Save and exit (:wq in vim)
```

### 2. Verify Cron Jobs

```bash
# List active cron jobs
crontab -l

# Check cron service status
systemctl status cron  # or cronie.service on some systems

# View cron logs
journalctl -u cron -f
```

### 3. Create Log Directory

```bash
# Ensure log directory exists and has correct permissions
sudo mkdir -p /var/log
sudo chown $USER:$USER /var/log/federated-*.log

# Or use user-specific log directory
mkdir -p ~/logs
# Then update cron paths to ~/logs/federated-sync.log
```

### 4. Test Scripts Manually

Before enabling cron, test each script:

```bash
# Test pattern sync
bash scripts/sync-learning-data.sh
echo $?  # Should be 0 (success)

# Test collection export
bash scripts/export-collections.sh
echo $?  # Should be 0

# Test dashboard generation
bash scripts/generate-dashboard-data.sh
echo $?  # Should be 0
```

---

## Systemd Timers (Alternative)

Systemd timers are more powerful than cron for complex scheduling needs.

### Create Service Unit

`/etc/systemd/system/federated-sync.service`:
```ini
[Unit]
Description=Federated Learning Data Sync
After=network.target

[Service]
Type=oneshot
User=hyperd
ExecStart=/usr/bin/bash /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh
StandardOutput=append:/var/log/federated-sync.log
StandardError=append:/var/log/federated-sync.log

[Install]
WantedBy=multi-user.target
```

### Create Timer Unit

`/etc/systemd/system/federated-sync.timer`:
```ini
[Unit]
Description=Run Federated Learning Data Sync Hourly
Requires=federated-sync.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

### Enable Timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now federated-sync.timer

# Check status
sudo systemctl status federated-sync.timer
sudo systemctl list-timers federated-sync.timer
```

---

## Automated Git Commits (Optional)

**WARNING**: Use with caution. This creates many commits automatically.

### Recommended Approach

Create a dedicated branch for automated syncs:

```bash
# Create automation branch
git checkout -b automation/federated-sync

# Set up cron
crontab -e
```

```cron
# Every 6 hours: Auto-commit and push to automation branch
0 */6 * * * cd /path/to/repo && bash scripts/sync-learning-data.sh && git add data/ && git commit -m "Auto-sync $(date +\%Y-\%m-\%d\ \%H:\%M)" && git push origin automation/federated-sync >> /var/log/federated-git.log 2>&1
```

Then periodically merge to main manually:

```bash
git checkout main
git merge automation/federated-sync
git push origin main
```

### SSH Key Setup (Required)

Automated git push requires SSH keys (not password auth):

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "federated-learning@$(hostname)"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and paste to GitHub Settings > SSH Keys

# Test connection
ssh -T git@github.com

# Set git remote to SSH
git remote set-url origin git@github.com:yourusername/NixOS-Dev-Quick-Deploy.git
```

---

## Monitoring Automation

### Check Cron Execution

```bash
# View recent cron executions
grep CRON /var/log/syslog | tail -20

# Check for cron errors
grep CRON /var/log/syslog | grep -i error

# Monitor sync log in real-time
tail -f /var/log/federated-sync.log
```

### Automation Health Checks

```bash
# Check last sync timestamp
cat data/patterns/skills-patterns.jsonl | jq -r '.timestamp' | tail -1

# Check sync frequency (should match cron schedule)
stat -c %y data/patterns/skills-patterns.jsonl

# Check log file sizes (shouldn't grow indefinitely)
du -sh /var/log/federated-*.log
```

### Alerting (Advanced)

Create a monitoring script that emails on failure:

`~/scripts/monitor-federation.sh`:
```bash
#!/usr/bin/env bash

# Check if sync is stale (>2 hours old)
LAST_SYNC=$(stat -c %Y data/patterns/skills-patterns.jsonl)
NOW=$(date +%s)
AGE=$((NOW - LAST_SYNC))

if [ $AGE -gt 7200 ]; then
    echo "Federation sync is stale (${AGE}s old)" | \
        mail -s "Federation Alert: Stale Sync" admin@example.com
fi
```

Add to cron:
```cron
# Every hour: Check federation health
0 * * * * bash ~/scripts/monitor-federation.sh
```

---

## Log Rotation

Prevent log files from filling disk:

### Using Logrotate

`/etc/logrotate.d/federated-learning`:
```
/var/log/federated-*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0644 hyperd hyperd
}
```

### Manual Rotation (Cron)

```cron
# Weekly (Sunday midnight): Rotate logs
0 0 * * 0 find /var/log/ -name "federated-*.log" -type f -exec bash -c 'mv {} {}.old && touch {}' \; && find /var/log/ -name "federated-*.log.old" -mtime +30 -delete
```

---

## Troubleshooting Automation

### Cron Job Not Running

**Check**:
```bash
# Is cron service running?
systemctl status cron

# Is crontab configured?
crontab -l

# Are paths absolute?
# ❌ BAD: */5 * * * * sync-learning-data.sh
# ✅ GOOD: */5 * * * * /home/user/.../sync-learning-data.sh
```

**Fix**:
```bash
# Start cron service
sudo systemctl start cron
sudo systemctl enable cron

# Always use absolute paths in cron
crontab -e
# Change relative paths to absolute
```

### Script Fails in Cron But Works Manually

**Cause**: Different environment variables in cron

**Check**:
```bash
# Add to cron job for debugging
* * * * * env > /tmp/cron-env.txt

# Compare with shell environment
env > /tmp/shell-env.txt
diff /tmp/cron-env.txt /tmp/shell-env.txt
```

**Fix**:
```cron
# Set environment variables explicitly
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
HOME=/home/hyperd

0 * * * * bash /home/hyperd/.../scripts/sync-learning-data.sh
```

### Logs Not Created

**Check**:
```bash
# Does directory exist?
ls -ld /var/log/

# Do you have write permissions?
touch /var/log/test.log
```

**Fix**:
```bash
# Create directory
sudo mkdir -p /var/log/
sudo chown $USER:$USER /var/log/

# Or use home directory
mkdir -p ~/logs/
# Update cron to use ~/logs/federated-sync.log
```

---

## Best Practices

### 1. Start Conservative

Begin with manual runs, then progress to automation:

```bash
# Week 1: Manual
bash scripts/sync-learning-data.sh
git commit && git push

# Week 2: Cron without auto-commit
# (Add cron job for sync only)

# Week 3: Full automation
# (Add auto-commit if desired)
```

### 2. Monitor Initially

After enabling cron, monitor closely for first few cycles:

```bash
# Watch for first 3 cron executions
watch -n 60 'tail -20 /var/log/federated-sync.log'
```

### 3. Use Email Notifications

Configure cron to email on errors:

```bash
# Add to top of crontab
MAILTO=admin@example.com

# Cron will email output if job fails
0 * * * * bash /path/to/scripts/sync-learning-data.sh
```

### 4. Test Failure Scenarios

```bash
# Simulate Qdrant offline
podman stop local-ai-qdrant
bash scripts/export-collections.sh  # Should fail gracefully

# Simulate git conflict
# (Make manual edit to data/ without committing)
# Run auto-commit cron
# Verify conflict is handled
```

### 5. Document Custom Schedules

If you deviate from templates:

```bash
# Add comment to crontab
crontab -e
```

```cron
# Custom schedule: Sync every 30 minutes due to high activity
# Changed from hourly on 2025-12-21 - see ticket #123
*/30 * * * * bash /path/to/scripts/sync-learning-data.sh
```

---

## Related Documentation

- [43-FEDERATED-DEPLOYMENT.md](43-FEDERATED-DEPLOYMENT.md) - Deployment workflows
- [scripts/cron-templates.sh](../../scripts/cron-templates.sh) - Complete cron templates
- [FEDERATED-DATA-STRATEGY.md](../../FEDERATED-DATA-STRATEGY.md) - Federation architecture

---

**Next Steps**: [90-COMPREHENSIVE-ANALYSIS.md](90-COMPREHENSIVE-ANALYSIS.md) - System monitoring
