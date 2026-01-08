# System Monitoring Dashboard - Complete Guide

**Created**: 2025-12-21
**Purpose**: Comprehensive real-time monitoring for NixOS system, AI stack, security, and network status
**Design**: Cyberpunk operations terminal with modern 2025 UI/UX patterns

---

## 🎯 Overview

The **NixOS System Command Center** is a production-grade, real-time monitoring dashboard that provides comprehensive visibility into:

- **System Resources** (CPU, Memory, Disk, Uptime, Load Average, Temperature)
- **AI/LLM Stack** (Qdrant, Ollama, llama.cpp, PostgreSQL, Redis, Open WebUI)
- **Container Status** (Podman containers with real-time stats)
- **Network & Firewall** (Active connections, DNS, Listening ports, Rules)
- **Security Monitoring** (Failed logins, AppArmor, Updates)
- **Database Metrics** (PostgreSQL status, size, connections)
- **Quick Access Links** (Documentation, Services, Config files)

### Key Features

✅ **Real-time Updates** - Auto-refresh every 5 seconds
✅ **AI-Agent Friendly** - Export data as JSON for automated analysis
✅ **Health Scoring** - Overall system health percentage
✅ **Data Visualization** - Chart.js graphs for CPU/Memory trends
✅ **Mobile Responsive** - Works on all screen sizes
✅ **Accessibility** - WCAG compliant with reduced motion support
✅ **Modern Design** - Cyberpunk terminal aesthetic with neon accents

---

## 📐 Architecture

### Design Philosophy (2025 Standards)

Based on research from:
- [20 Principles Modern Dashboard UI/UX Design for 2025](https://medium.com/@allclonescript/20-best-dashboard-ui-ux-design-principles-you-need-in-2025-30b661f2f795)
- [Dashboard Design Trends 2025](https://udesignate.com/dashboard-design-trends-2025-what-to-watch/)
- [Top 9 LLM Observability Tools in 2025](https://logz.io/blog/top-llm-observability-tools/)
- [OpenLLM Monitor](https://github.com/prajeesh-chavan/OpenLLM-Monitor)
- [LLemonStack](https://github.com/LLemonStack/llemonstack)

**Aesthetic Direction**: Cyberpunk Operations Terminal
- Brutalist precision meets retro-futuristic interfaces
- Monospaced typography (JetBrains Mono + Orbitron)
- Scanline effects and animated data streams
- Neon accent colors (cyan, magenta, yellow)
- Command-center feel for DevOps professionals

### Components

```
┌─────────────────────────────────────────────────────┐
│  System Command Center Dashboard (HTML)            │
│  ├─ Real-time auto-refresh (5s interval)           │
│  ├─ Chart.js visualizations                        │
│  ├─ Collapsible sections                           │
│  ├─ Search/filter capabilities                     │
│  └─ Export data for AI agents                      │
└─────────────────────────────────────────────────────┘
                        ▲
                        │ Fetch JSON
                        │
┌─────────────────────────────────────────────────────┐
│  Data Collection Script (Bash)                     │
│  ├─ System metrics (top, free, df, uptime)         │
│  ├─ LLM stack status (curl health checks)          │
│  ├─ Network metrics (ss, nft, ip)                  │
│  ├─ Security status (journalctl, aa-status)        │
│  ├─ Database metrics (podman exec psql)            │
│  ├─ Persistence metrics (data root + sizes)        │
│  └─ Output: JSON files in ~/.local/share/...       │
└─────────────────────────────────────────────────────┘
                        │
                        │ Runs every 5s
                        │
┌─────────────────────────────────────────────────────┐
│  Systemd Service (Optional)                        │
│  └─ Automated collection + dashboard server        │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Generate Initial Dashboard Data

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Run the data collection script
./scripts/generate-dashboard-data.sh
```

### 0. One-Command Startup (Stack + Dashboard + Tests)

If the podman AI stack is installed, you can start everything and run tests in one command:

```bash
./scripts/start-ai-stack-and-dashboard.sh
```

This will:
- Start the podman AI stack containers
- Start the dashboard collector + server
- Run a telemetry smoke test
- Run stack health checks

**Output**:
```
🔄 Collecting system metrics...
🤖 Collecting LLM stack metrics...
🌐 Collecting network metrics...
🔒 Collecting security metrics...
🗄️  Collecting database metrics...
🪢 Collecting feedback pipeline metrics...
📚 Generating quick links...
✅ Dashboard data generated at: /home/hyperd/.local/share/nixos-system-dashboard
📊 Files created:
-rw-r--r-- 1 hyperd users  1.2K database.json
-rw-r--r-- 1 hyperd users  2.8K llm.json
-rw-r--r-- 1 hyperd users  1.9K links.json
-rw-r--r-- 1 hyperd users  1.5K network.json
-rw-r--r-- 1 hyperd users  892B security.json
-rw-r--r-- 1 hyperd users  1.1K system.json
-rw-r--r-- 1 hyperd users  1.4K persistence.json
-rw-r--r-- 1 hyperd users  1.0K telemetry.json
-rw-r--r-- 1 hyperd users  1.0K feedback.json
-rw-r--r-- 1 hyperd users  1.1K config.json
-rw-r--r-- 1 hyperd users  1.1K proof.json
```

### 2. Start the Dashboard Server

```bash
# Start the built-in HTTP server
./scripts/serve-dashboard.sh
```

**Output**:
```
🌐 Starting NixOS System Dashboard Server...
📊 Dashboard: http://localhost:8888/dashboard.html
📁 Data API: http://localhost:8888/data/
```

**Action Buttons**:
- The server exposes `POST /action` for run-mode buttons.
- Only allowlisted commands from `config.json` (mode=`run`) are executed.
- Use on localhost only (no auth); keep the port private.
- Commands that require sudo use `sudo -n` and will fail if passwordless sudo is not configured.

### 3. Open Dashboard in Browser

```bash
# Option 1: Open in default browser
xdg-open http://localhost:8888/dashboard.html

# Option 2: Direct URL
firefox http://localhost:8888/dashboard.html
```

---

## 📊 Dashboard Sections

### 1. System Overview

**Metrics Displayed**:
- **CPU Usage** - Real-time percentage with historical graph
- **CPU Temperature** - Current temperature (if sensors available)
- **GPU/iGPU** - Adapter name + utilization (when available)
- **VRAM** - Used/total MB (when available)
- **Memory Usage** - Progress bar with used/total/percentage
- **Disk Usage** - Progress bar for root filesystem
- **Uptime** - Days, hours, minutes since last boot
- **Load Average** - 1min, 5min, 15min averages

**Visualizations**:
- Line chart showing CPU usage trend (last 20 data points)
- Line charts showing memory and disk usage trends (last 20 data points)
- Animated progress bars for memory and disk
- Gradient fills with shimmer effects

**Click-to-Copy**: Load average values

### 2. AI Stack Status

**Services Monitored**:
- ✅ **Qdrant** (Vector database) - Port 6333
- ✅ **Ollama** (Embedding models) - Port 11434
- ✅ **llama.cpp** (Local LLM via llama.cpp) - Port 8080
- ✅ **PostgreSQL** (Relational database) - Port 5432
- ✅ **Redis** (Cache/message queue) - Port 6379
- ✅ **Open WebUI** (Chat interface) - Port 3001
- ✅ **MindsDB** (Continuous learning analytics) - Port 47334
- ✅ **AIDB MCP** (Hybrid learning API) - Port 8091

**Status Indicators**:
- 🟢 **ONLINE** - Service responding to health checks
- 🟡 **WARNING** - Service accessible but degraded
- 🔴 **OFFLINE** - Service not responding

**Badge**: Shows X/Y services online (auto-calculated)

### 3. Agentic Readiness

**Signals Tracked**:
- **AIDB MCP** availability (health endpoint)
- **RAG Collections** count and names
- **Local Model Inventory** (Ollama/llama.cpp models)

**Purpose**:
- Validate that hybrid learning + RAG prerequisites are online
- Surface missing collections before running large workflows

### 4. Container Status

**Features**:
- List of all running Podman containers
- Real-time search/filter by container name
- Container metadata (image, status)
- Visual indicators for running/stopped containers

**Data Displayed**:
- Container name
- Image name and tag
- Current status (running/stopped/error)

**Search**: Type to filter containers in real-time

### 5. Network & Firewall

**Metrics**:
- **Active Connections** - Current TCP/UDP connections
- **Firewall Rules** - Number of nftables rules loaded
- **DNS Status** - Configuration state (symlink/static/misconfigured)
- **Open Ports** - Count of listening ports
- **Port List** - All ports currently listening
- **Network Devices** - Neighbor discovery (IP/MAC/state) from `ip neigh`

**Security Context**:
- Shows if DNS resolution is properly configured
- Lists all exposed services (important for security audits)
- Firewall rule count indicates security posture

### 6. Security Monitor

**Tracked Metrics**:
- **Failed Logins (1h)** - Authentication failures in last hour
- **AppArmor Status** - Mandatory Access Control state
- **Firewall Status** - Active/inactive
- **System Updates** - Pending NixOS updates

**Status Colors**:
- 🟢 Green: Secure state (0 failed logins, firewall active)
- 🟡 Yellow: Warning (some failed logins, updates available)
- 🔴 Red: Critical (firewall disabled, many failures)

### 7. Database Metrics

**PostgreSQL Monitoring**:
- **Status** - Online/offline state
- **Database Size** - Total size on disk
- **Active Connections** - Current connection count

**Use Cases**:
- Monitor database growth over time
- Detect connection leaks
- Verify database availability

### 8. Persistent AI Data

**Metrics**:
- **Data Root** location
- **Filesystem** and device
- **Data Store Sizes** (Qdrant, Ollama, llama.cpp, Postgres, Redis, Hugging Face cache)

**Purpose**:
- Confirm persistent storage placement
- Track growth of AI assets and caches

### 9. Agentic Efficiency (New in v6.0.0)

**Hybrid Learning Metrics**:
- **Token Savings** - Estimated tokens saved via local context retrieval
- **Cache Hit Rate** - Percentage of queries resolved via Qdrant/Redis
- **Local vs Remote** - Ratio of local LLM usage vs remote API calls

**Purpose**:
- Monitor cost efficiency of the Hybrid Learning Stack
- Validate RAG effectiveness

### 10. Telemetry Proof

**Signals Tracked**:
- AIDB telemetry event counts
- Local usage rate and tokens saved
- Most recent event timestamp

**Purpose**:
- Confirm local LLM and tool usage are recorded
- Verify feedback loop for continuous improvement

### 11. Local Usage Proof

**Signals Tracked**:
- AIDB availability
- RAG collection counts (Qdrant)
- Local model inventories (Ollama/llama.cpp)
- Skills count + telemetry events
- Container runtime + running container count
- Sample skill slugs + last telemetry event summary

**Purpose**:
- Provide immediate evidence that local systems are in use
- Correlate models, RAG, and orchestration in one place

### 12. Feedback Pipeline

**Signals Tracked**:
- AIDB MCP availability
- Telemetry file presence + size
- Latest AIDB + hybrid telemetry event timestamps

**Purpose**:
- Validate persistence and feedback ingestion
- Detect stalled telemetry writes
- Highlight stale events older than 30 minutes in the UI

### 13. Configuration & Actions

**Signals Tracked**:
- Snapshot of key AI stack settings (ports, data root, refresh interval)
- Required services list used by the health score calculator
- Direct commands for common fixes (Podman Desktop socket, rebuild)
- Security posture (firewall, OpenSSH, fail2ban, Tailscale)
- System baseline (NixOS version, kernel, systemd service status)
- System tuning (Nix GC/optimise, journald retention, sysctl values)

**Purpose**:
- Provide a copy-ready configuration surface for operators
- Reduce time spent hunting for commands and config files
- Expose security + platform toggles for faster remediation
- Offer diagnostics/maintenance shortcuts (logs, disk, memory, containers)
- Provide basic network and port triage commands

### 14. Quick Access Links

**Categories**:

**📚 Documentation**:
- Implementation Summary
- System Test Results
- DNS Resolution Fix
- AI Stack RAG Implementation

**🌐 Services** (clickable URLs):
- Open WebUI (http://localhost:3001)
- Qdrant Dashboard (http://localhost:6333/dashboard)
- Netdata Monitoring (http://localhost:19999)
- Gitea (http://localhost:3000)

**⚙️ Config Files**:
- NixOS Configuration
- Docker Compose (AI Stack)
- Networking Configuration

**Features**:
- Direct links to documentation files
- External service URLs open in new tab
- Hover effects with smooth transitions

---

## 🤖 AI Agent Integration

### Export Dashboard Data

Click the **"⬇ Export JSON for AI"** button to download complete system snapshot:

```json
{
  "system": {
    "timestamp": "2025-12-21T10:30:00Z",
    "cpu": { "usage_percent": 23.5, "temperature": "45.2°C", "cores": 8 },
    "memory": { "total": 32000, "used": 12000, "percent": 37.5 },
    "disk": { "total": "500GB", "used": "250GB", "percent": "50%" },
    "uptime_seconds": 345600,
    "load_average": "1.2, 1.5, 1.8"
  },
  "llm": { ... },
  "network": { ... },
  "security": { ... },
  "database": { ... },
  "links": { ... }
}
```

### Use Cases for AI Agents

**1. Automated Troubleshooting**:
```bash
# AI agent reads JSON and identifies issues
curl http://localhost:8888/data/system.json | jq '.cpu.usage_percent'
# If > 80%, trigger optimization scripts
```

**2. Predictive Alerts**:
```python
import json
import requests

data = requests.get('http://localhost:8888/data/system.json').json()

if data['memory']['percent'] > 90:
    print("⚠️ ALERT: Memory usage critical!")
    # Trigger cleanup or notification
```

**3. Health Report Generation**:
```bash
# AI generates daily health report
./scripts/generate-dashboard-data.sh
HEALTH_SCORE=$(curl -s http://localhost:8888 | grep -Po 'healthScore">\K\d+')
echo "Daily Health Score: $HEALTH_SCORE%"
```

**4. Claude Code Integration**:
AI agents like Claude Code can read the dashboard data to:
- Diagnose performance issues
- Recommend optimizations
- Generate configuration fixes
- Monitor deployment health

---

## 🔧 Configuration

### Data Collection Frequency

Edit [scripts/generate-dashboard-data.sh](/scripts/generate-dashboard-data.sh):

```bash
# Add to crontab for automated collection every 5 seconds
* * * * * /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh
* * * * * sleep 5; /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh
# ... repeat with sleep 10, 15, 20, etc.
```

Or create a systemd timer (recommended):

```bash
# Create systemd service
sudo tee /etc/systemd/system/dashboard-collector.service <<EOF
[Unit]
Description=System Dashboard Data Collector
After=network.target

[Service]
Type=oneshot
User=hyperd
ExecStart=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer
sudo tee /etc/systemd/system/dashboard-collector.timer <<EOF
[Unit]
Description=Run dashboard collector every 5 seconds

[Timer]
OnBootSec=10s
OnUnitActiveSec=5s
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF

# Enable and start
sudo systemctl enable --now dashboard-collector.timer
```

### Dashboard Refresh Rate

Edit [dashboard.html](dashboard.html) line ~1157:

```javascript
setInterval(loadData, 5000); // Refresh every 5 seconds

// Change to 10 seconds:
setInterval(loadData, 10000);
```

### Custom Metrics

Add custom metrics to [scripts/generate-dashboard-data.sh](/scripts/generate-dashboard-data.sh):

```bash
collect_custom_metrics() {
    # Example: GPU temperature
    local gpu_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    cat >> "$DATA_DIR/system.json" <<EOF
    "gpu": {
        "temperature": "$gpu_temp"
    }
EOF
}
```

### Dashboard Port

Change default port (8888):

```bash
# Set environment variable
export DASHBOARD_PORT=9999
./scripts/serve-dashboard.sh

# Or edit serve-dashboard.sh directly
PORT="${DASHBOARD_PORT:-9999}"
```

---

## 🎨 Customization

### Color Scheme

Edit CSS variables in [dashboard.html](dashboard.html) (lines ~18-36):

```css
:root {
    --bg-primary: #0a0e14;          /* Main background */
    --accent-cyan: #00d9ff;          /* Primary accent */
    --accent-magenta: #ff006e;       /* Secondary accent */
    --status-online: #00ff88;        /* Success color */
    --status-warning: #ffbe0b;       /* Warning color */
    --status-error: #ff006e;         /* Error color */
}
```

**Preset Themes**:

**Synthwave**:
```css
--accent-cyan: #ff006e;
--accent-magenta: #7b2cbf;
--status-online: #ff006e;
```

**Matrix**:
```css
--accent-cyan: #00ff00;
--accent-magenta: #00cc00;
--bg-primary: #000000;
```

**Nord**:
```css
--accent-cyan: #88c0d0;
--accent-magenta: #b48ead;
--bg-primary: #2e3440;
```

### Typography

Change fonts (line ~17):

```html
<!-- Replace Orbitron with another display font -->
@import url('https://fonts.googleapis.com/css2?family=Audiowide:wght@400&display=swap');

/* Then update */
h1 { font-family: 'Audiowide', monospace; }
```

### Disable Animations

For reduced motion or better performance:

```css
/* Add at end of <style> */
* {
    animation: none !important;
    transition: none !important;
}
```

---

## 🔍 Troubleshooting

### Dashboard Not Loading Data

**Symptom**: All metrics show "--" or "Loading..."

**Solutions**:

1. **Check data files exist**:
```bash
ls -la ~/.local/share/nixos-system-dashboard/
# Should show JSON files (system.json, llm.json, keyword-signals.json, etc.)
```

2. **Run data collection manually**:
```bash
./scripts/generate-dashboard-data.sh
```

3. **Check file permissions**:
```bash
chmod 644 ~/.local/share/nixos-system-dashboard/*.json
```

4. **Verify JSON is valid**:
```bash
cat ~/.local/share/nixos-system-dashboard/system.json | jq .
```

### CORS Errors in Browser Console

**Symptom**: `Access to fetch at 'file://...' from origin 'null' has been blocked by CORS`

**Solution**: Use the HTTP server instead of opening HTML file directly:

```bash
# DON'T: Open file:// directly
firefox dashboard.html  ❌

# DO: Use the server
./scripts/serve-dashboard.sh
firefox http://localhost:8888/dashboard.html  ✅
```

### Container Stats Not Showing

**Symptom**: "-- Containers" badge, empty container list

**Causes**:
1. Podman containers not running
2. JSON generation script can't access podman

**Solutions**:

```bash
# Check if containers are running
podman ps

# If no containers, start AI stack
cd ai-stack/compose
podman-compose up -d

# Verify JSON includes containers
cat ~/.local/share/nixos-system-dashboard/llm.json | jq '.containers'
```

### Services Showing as Offline

**Symptom**: All services show red "OFFLINE" badges

**Causes**:
1. Services not started
2. Health check URLs incorrect
3. Firewall blocking localhost connections

**Solutions**:

```bash
# Check service ports
ss -tlnp | grep -E '(6333|11434|8080|5432|6379|3001)'

# Test health endpoints manually
curl http://localhost:6333/healthz    # Qdrant
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8080/health     # llama.cpp

# Start services
cd ai-stack/compose
podman-compose up -d
```

### CPU Chart Not Rendering

**Symptom**: Blank space where CPU chart should be

**Causes**:
1. Chart.js CDN not loading
2. JavaScript errors

**Solutions**:

```bash
# Check browser console (F12) for errors

# Verify Chart.js loads
curl -I https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js
```

---

## 📈 Performance Optimization

### Reduce Data Collection Overhead

If system load is too high from frequent collection:

```bash
# Option 1: Increase interval to 10 seconds
setInterval(loadData, 10000);

# Option 2: Disable expensive metrics in generate-dashboard-data.sh
# Comment out database collection:
# collect_database_metrics
```

### Minimize Dashboard Resource Usage

```css
/* Disable animations (saves CPU) */
body::before { animation: none; }
.progress-fill::after { animation: none; }

/* Reduce chart updates */
cpuChart.update('none'); // Instead of default animation
```

### Cache JSON Files

Add caching to Python server (in [scripts/serve-dashboard.sh](/scripts/serve-dashboard.sh)):

```python
self.send_header('Cache-Control', 'public, max-age=5')
```

---

## 🛡️ Security Considerations

### Dashboard Access Control

**Current State**: Dashboard is accessible to localhost only (127.0.0.1:8888)

**To Allow Network Access**:

```bash
# Edit serve-dashboard.sh, change bind address:
with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
```

⚠️ **WARNING**: This exposes dashboard to local network. Add authentication!

**Add Basic Auth** (optional):

```python
import base64

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        auth = self.headers.get('Authorization')
        if auth != 'Basic ' + base64.b64encode(b'admin:password').decode():
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Dashboard"')
            self.end_headers()
            return
        super().do_GET()
```

### Sensitive Data Exposure

**Data Collected** (review for sensitive info):
- System hostnames ✅ (sanitized)
- Container names ✅ (safe)
- Port numbers ⚠️ (could reveal services)
- Database connection counts ✅ (safe)
- Failed login attempts ⚠️ (could indicate attacks)

**Recommendations**:
1. Don't expose dashboard to internet
2. Use VPN/SSH tunnel for remote access
3. Regularly rotate any credentials in config files
4. Review exported JSON before sharing with AI services

---

## 📚 References & Inspirations

### Design Research (December 2025)

1. **[20 Principles Modern Dashboard UI/UX Design for 2025](https://medium.com/@allclonescript/20-best-dashboard-ui-ux-design-principles-you-need-in-2025-30b661f2f795)** - Modern design principles including AI-powered intelligence and real-time interactivity

2. **[Dashboard Design Trends 2025](https://udesignate.com/dashboard-design-trends-2025-what-to-watch/)** - Latest trends in data visualization and user experience

3. **[Effective Dashboard Design Principles for 2025](https://www.uxpin.com/studio/blog/dashboard-design-principles/)** - UX best practices and accessibility guidelines

4. **[Top 9 LLM Observability Tools in 2025](https://logz.io/blog/top-llm-observability-tools/)** - LLM monitoring patterns and observability strategies

5. **[OpenLLM Monitor](https://github.com/prajeesh-chavan/OpenLLM-Monitor)** - Plug-and-play LLM observability dashboard (open-source)

6. **[LLemonStack](https://github.com/LLemonStack/llemonstack)** - All-in-one platform running Qdrant, Ollama with observability

7. **[Ollama Monitoring Dashboard Guide](https://markaicode.com/ollama-monitoring-dashboard-performance-tracking-alerting/)** - Complete Ollama performance tracking patterns

8. **[Open Source Dashboards: 9 Best Tools (2026)](https://www.metricfire.com/blog/top-8-open-source-dashboards/)** - Grafana, Metabase, Apache Superset comparisons

### Technologies Used

- **Chart.js 4.4.1** - Modern charting library
- **Vanilla JavaScript** - No framework dependencies
- **CSS Grid & Flexbox** - Modern responsive layouts
- **Python HTTP Server** - Built-in file serving
- **systemd** - Service management
- **jq** - JSON processing
- **Podman** - Container runtime

---

## 🎯 Future Enhancements

### Planned Features

- [ ] **Historical Data** - Store metrics in SQLite for trends
- [ ] **Alert Configuration** - Custom thresholds and notifications
- [ ] **Multi-Host Support** - Monitor multiple servers
- [ ] **GraphQL API** - Advanced querying capabilities
- [ ] **WebSocket Live Updates** - Push updates instead of polling
- [ ] **Mobile App** - Native iOS/Android companion
- [ ] **AI-Powered Insights** - Automated anomaly detection
- [ ] **Prometheus Integration** - Export metrics for long-term storage
- [ ] **Dark/Light Theme Toggle** - User preference support
- [ ] **Custom Dashboards** - Drag-and-drop widget builder

### Contributing

Want to improve the dashboard? Areas for contribution:

1. **Additional Metrics** - GPU stats, network traffic, etc.
2. **Visualizations** - More chart types (heatmaps, gauges)
3. **Integrations** - Grafana, Prometheus, InfluxDB
4. **Performance** - Optimize data collection scripts
5. **Accessibility** - Screen reader improvements

---

## 📞 Support & Feedback

- **Documentation**: This file
- **Issues**: Check [DNS-RESOLUTION-FIX.md](/docs/archive/DNS-RESOLUTION-FIX.md) and [SYSTEM-TEST-RESULTS.md](/docs/archive/SYSTEM-TEST-RESULTS.md)
- **AI Stack Docs**: [AI-STACK-RAG-IMPLEMENTATION.md](AI-STACK-RAG-IMPLEMENTATION.md)

---

## ✅ Quick Reference

### Start Dashboard
```bash
./scripts/generate-dashboard-data.sh
./scripts/serve-dashboard.sh
# Open: http://localhost:8888/dashboard.html
```

### Automated Collection
```bash
sudo systemctl enable --now dashboard-collector.timer
```

### Export for AI
Click "⬇ Export JSON for AI" button in dashboard

### Check Health
```bash
curl http://localhost:8888/data/system.json | jq '.cpu.usage_percent'
```

---

**Dashboard Version**: 1.0.0
**Last Updated**: 2025-12-21
**Status**: ✅ Production Ready
