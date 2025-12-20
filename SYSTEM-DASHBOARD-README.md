# System Dashboard

## Quick Access

**Dashboard URL**: `http://localhost:8080` (when dashboard server is running)

or

**Local File**: `file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/dashboard/index.html`

## Features

### 📊 Real-time Monitoring
- Service health checks (Lemonade, Qdrant, Ollama)
- Learning system metrics
- Federation status
- System resource usage

### ⚡ Quick Actions
- Access Open WebUI
- View Qdrant dashboard
- Trigger manual sync
- Generate training datasets
- Export data snapshots

### 📚 Documentation Hub
- Direct links to all system docs
- Architecture guides
- API references
- MCP server catalogs

### 🔍 Log Viewing
- Container logs access
- Service status monitoring
- Health metrics

## Starting the Dashboard

### Option 1: Simple HTTP Server

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/dashboard
python3 -m http.server 8080
```

Then open: `http://localhost:8080`

### Option 2: Open Local File

```bash
xdg-open /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/dashboard/index.html
```

### Option 3: Add to NixOS (Recommended)

The dashboard will be automatically served by the hybrid learning system when fully deployed.

## Dashboard Sections

### 1. System Status
- **Core Services**: Health check for all AI services
- **Learning System**: Metrics on interactions, patterns, solutions
- **Federation**: Multi-node synchronization status

### 2. Quick Actions
- **Open WebUI**: Chat interface (port 3000)
- **Qdrant Dashboard**: Vector database UI (port 6333)
- **Metrics**: Prometheus metrics (port 9200)
- **Sync Now**: Manual federation sync trigger
- **Generate Training Data**: Create fine-tuning datasets
- **Export Snapshot**: Backup all learning data

### 3. Documentation
All system documentation in one place:
- Complete System Guide
- Multi-Node Setup
- Quick Start Guide
- Architecture Deep Dive
- API References
- MCP Server Catalogs

### 4. Monitoring & Logs
- View container logs
- System health metrics (CPU, Memory, Disk)
- Network status

## API Endpoints Used

The dashboard connects to:
- `http://localhost:8000/health` - Lemonade General
- `http://localhost:8001/health` - Lemonade Coder
- `http://localhost:8003/health` - Lemonade DeepSeek
- `http://localhost:6333/collections` - Qdrant
- `http://localhost:11434/api/tags` - Ollama
- `http://localhost:8092/manifest` - Federation (when enabled)
- `http://localhost:9200/metrics` - Prometheus metrics

## Customization

Edit `ai-stack/dashboard/index.html` to:
- Add custom metrics
- Modify color scheme
- Add new quick actions
- Integrate additional services

## Troubleshooting

### Dashboard shows services as offline
- Check if containers are running: `podman ps`
- Start services: `cd ai-stack/compose && podman-compose up -d`

### Metrics not loading
- Verify Qdrant is accessible: `curl http://localhost:6333/collections`
- Check browser console for errors (F12)

### Federation status shows N/A
- Federation must be enabled in `configuration.nix`
- Check: `systemctl status hybrid-learning-sync`

## Security

The dashboard is for local use only by default. To expose remotely:

1. Add authentication (nginx reverse proxy recommended)
2. Use HTTPS with proper certificates
3. Restrict access by IP/network

Example nginx config:
```nginx
location /dashboard/ {
    auth_basic "System Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:8080/;
}
```

## Future Enhancements

Planned features:
- [ ] Real-time log streaming
- [ ] Interactive Grafana integration
- [ ] Model performance charts
- [ ] Token usage graphs
- [ ] Federation topology visualization
- [ ] Automated health alerts
- [ ] Mobile-responsive design
- [ ] Dark mode toggle

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review system logs: `journalctl -u hybrid-coordinator -f`
3. Refer to the complete guide: `HYBRID-AI-SYSTEM-GUIDE.md`
