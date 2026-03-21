# NixOS AI Stack - Quick Start Guide

Welcome to the NixOS AI Stack! This guide will help you get started with the system in 10 minutes.

## Prerequisites

- NixOS system with flake support
- Minimum 8GB RAM (16GB+ recommended for AI operations)
- Network connectivity for downloading dependencies
- Basic command-line familiarity

## Initial Setup (First Time Only)

### 1. System Health Check

First, verify your system meets the requirements:

```bash
# Check system resources
free -h          # Memory
df -h /          # Disk space
nproc            # CPU cores

# System should show:
# - At least 8GB free RAM
# - At least 50GB free disk space
# - 4+ CPU cores
```

### 2. Initialize the System

```bash
# Clone the repository
git clone https://github.com/your-org/nixos-ai-stack.git
cd nixos-ai-stack

# Build with Nix
nix flake update
nix develop

# Deploy the configuration
sudo nixos-rebuild switch --flake .#
```

### 3. Verify Services

```bash
# Check all services are running
systemctl list-units --type=service | grep ai-

# Expected running services:
# - ai-hybrid-coordinator.service
# - ai-orchestrator.service
# - dashboard.service
# - prometheus.service
# - postgres.service
```

## Daily Operations

### Dashboard Access

The web dashboard is your main interface:

```bash
# Open in browser
xdg-open http://localhost:3000

# Or via curl for quick health check
curl -s http://localhost:3000/api/health | jq .
```

### Generate Weekly Report

```bash
# Generate AI stack performance report
aq-report --since=7d --format=md > weekly-report.md

# View in terminal
aq-report --since=7d --format=text | less

# Export to JSON for processing
aq-report --since=7d --format=json > report.json
```

### Monitor System Health

```bash
# Quick system metrics
dashboard health

# Check service status
systemctl status ai-hybrid-coordinator

# View recent logs
journalctl -u ai-hybrid-coordinator -n 50 -f

# For errors
journalctl -u ai-hybrid-coordinator -p err -n 20
```

### Deploy a Workflow

```bash
# List available workflows
aq-orchestrator workflow list

# Run a workflow
aq-orchestrator workflow run workflow-name --params "key=value"

# Monitor progress
aq-orchestrator workflow status <workflow-id>

# View results
aq-orchestrator workflow results <workflow-id>
```

## Common Tasks

### Restart Services

If something seems stuck, restart the services:

```bash
# Restart coordinator (main orchestrator)
sudo systemctl restart ai-hybrid-coordinator

# Restart dashboard
sudo systemctl restart dashboard

# Restart all AI services
for service in ai-*.service; do
    sudo systemctl restart "$service"
done
```

### Check Resource Usage

```bash
# View CPU and memory usage
top -b -n 1 | head -15

# Docker container stats (if using containers)
docker stats

# Disk usage by service
du -sh /var/lib/ai-stack/*
du -sh /var/log/nixos-ai-stack/
```

### Clear Cache

Sometimes clearing cached data helps:

```bash
# Clear dashboard cache
curl -X POST http://localhost:3000/api/cache/clear

# View cache status
curl http://localhost:3000/api/cache/status | jq .

# Force data refresh
curl -X POST http://localhost:3000/api/refresh/all
```

### Update Configuration

Configuration is in `/etc/nixos/`:

```bash
# Edit configuration
sudo nano /etc/nixos/configuration.nix

# Or use NixOS declarative config
sudo nano /etc/nixos/ai-stack.nix

# Apply changes
sudo nixos-rebuild switch

# Check if restart needed
sudo nixos-rebuild dry-activate
```

## Keyboard Shortcuts (Dashboard)

For faster navigation in the web dashboard:

| Shortcut | Action |
|----------|--------|
| `r` | Refresh current view |
| `s` | Focus search box |
| `?` | Show keyboard shortcuts |
| `Esc` | Close modals / clear search |

## Troubleshooting

### Services Won't Start

```bash
# Check service status
systemctl status ai-hybrid-coordinator

# View detailed error logs
journalctl -u ai-hybrid-coordinator -p err

# Try restart
sudo systemctl restart ai-hybrid-coordinator

# If still failing, check configuration
sudo nixos-rebuild dry-activate
```

### Dashboard Not Loading

```bash
# Check if dashboard service is running
systemctl status dashboard

# Check if port 3000 is in use
lsof -i :3000

# Restart dashboard
sudo systemctl restart dashboard

# Wait 30 seconds, then access http://localhost:3000
```

### High Memory Usage

```bash
# Check memory by process
ps aux --sort=-%mem | head

# View database size
du -sh /var/lib/ai-stack/postgres

# Clean up old logs
journalctl --vacuum-time=7d

# Restart high-memory services
sudo systemctl restart ai-orchestrator
```

### Network Issues

```bash
# Check connectivity
curl -I http://localhost:3000
curl -I http://localhost:9090  # Prometheus

# Check network interfaces
ip addr show

# Verify DNS resolution
nslookup ai-coordinator.local
```

## Performance Tips

1. **Keep Cache Fresh**: The system auto-refreshes data, but you can manually refresh if needed
2. **Monitor Resources**: Check memory and disk usage weekly
3. **Archive Old Data**: Clean up logs older than 30 days
4. **Use JSON Export**: For processing large reports, export to JSON for better performance
5. **Enable Metrics**: Ensure Prometheus is collecting metrics

## Getting Help

- **Dashboard Help**: Press `?` in the dashboard for keyboard shortcuts
- **Command Help**: Run any command with `--help`
- **Error Messages**: Copy the error code (e.g., `E101`) and search documentation
- **Logs**: Check `/var/log/nixos-ai-stack/` for detailed logs
- **Documentation**: See `docs/` folder for comprehensive guides

## Next Steps

1. **Explore the Dashboard**: Spend 5 minutes clicking around to familiarize yourself
2. **Generate a Report**: Run `aq-report` to see your first performance report
3. **Monitor Your First Workflow**: Run a workflow and watch it complete
4. **Read Advanced Guides**: See `docs/user-guides/` for deeper topics

## Support Resources

- **Documentation**: `docs/AGENTS.md`, `docs/agent-guides/`
- **Issue Tracker**: GitHub Issues
- **Community**: #nixos-ai-stack Slack channel
- **Email**: support@example.com

---

**Good luck! The system is now ready to accelerate your AI operations. 🚀**
