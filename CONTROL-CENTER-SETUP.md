# AI Stack Control Center - Setup Guide

## Overview

The Control Center is a unified command, control, and monitoring dashboard that provides:
- **Single pane of glass** for all AI stack services
- **Real-time status** of orchestrators and services
- **Configuration management** with adjustable system variables
- **Quick actions** for common operations
- **Progress tracking** for production hardening
- **Links to all dashboards** and documentation

## Access

**URL**: http://localhost:8888/control-center.html

## Features

### 1. System Overview
- Overall system health
- Service status (12/12 healthy)
- Security posture
- Quick link to system dashboard

### 2. Orchestrator Status
- **Ralph Wiggum**: Loop engine for autonomous task execution
- **Hybrid Coordinator**: Smart router with learning
- **AIDB**: Knowledge base and context API

### 3. Security Dashboard
- Phase 1 completion status
- All security tests passing
- Link to security setup guide

### 4. System Configuration (Adjustable Variables)

Current configurable parameters:
```javascript
{
  rate_limit: 60,              // Requests per minute
  checkpoint_interval: 100,    // Events between checkpoints
  pool_size: 20,              // Database connection pool size
  log_level: "INFO"           // Logging verbosity
}
```

**How to Change:**
1. Adjust values in the configuration panel
2. Click "Apply Changes"
3. Restart affected services

**Note**: Changes are currently client-side only. For production:
- Update `ai-stack/mcp-servers/config/config.yaml`
- Restart services with `kubectl rollout restart` (K3s)

### 5. All Dashboards & Services

Quick access to:
- 📊 System Monitor (port 8888)
- 🏥 AIDB Health (HTTPS 8443)
- 💬 Open WebUI (port 3001)
- 📈 Grafana (port 3002)
- 🔥 Prometheus (port 9090)
- 🔍 Jaeger (port 16686)
- 🧠 MindsDB (port 47334)
- 📖 Documentation files

### 6. Production Hardening Progress

Visual progress tracker showing:
- Overall completion (4/16 tasks = 25%)
- Phase-by-phase status
- Completed vs pending tasks
- Link to full roadmap

### 7. Quick Actions

One-click operations:
- 🔄 Restart All Services
- 🧪 Run All Tests
- 💾 Backup Configuration
- 📝 View Logs
- 🏥 Health Check
- 📂 View Tests

## Integration with Dashboard Server

The control center is served by the same server as the system dashboard:

### Adding Control Center to Dashboard Server

Edit `scripts/serve-dashboard.sh` to serve the control center (already in document root):

```bash
# Control center is at /control-center.html
# Access via: http://localhost:8888/control-center.html
```

### Auto-Refresh

The control center automatically refreshes status every 30 seconds. For real-time data:

1. **System status**: Polls `/api/status` (TODO: implement backend)
2. **Service health**: Polls health endpoints
3. **Configuration**: Persists to localStorage

## Configuration Backend (TODO)

For full integration, implement configuration API:

```python
# scripts/serve-dashboard.sh

@app.post("/api/config/update")
def update_config(config_data: dict):
    # Update config.yaml
    # Validate changes
    # Apply to running services
    # Return success/failure
```

## Monitoring Integration

Connect to real-time metrics:

```javascript
// Fetch from Prometheus
fetch('http://localhost:9090/api/v1/query?query=up')
  .then(r => r.json())
  .then(data => updateServiceStatus(data));

// Fetch from AIDB health
fetch('https://localhost:8443/aidb/health')
  .then(r => r.json())
  .then(health => updateAIDBStatus(health));
```

## Ralph Wiggum Integration

### Submitting Tasks via Control Center

Add API endpoint to submit tasks to Ralph:

```javascript
function submitTaskBatch() {
    fetch('http://localhost:8098/api/submit-batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            batch_file: '/path/to/remaining-tasks.json'
        })
    })
    .then(r => r.json())
    .then(result => {
        console.log('Tasks submitted:', result);
        alert(`Submitted ${result.task_count} tasks to Ralph Wiggum`);
    });
}
```

### Monitoring Ralph Progress

Poll Ralph's status endpoint:

```javascript
setInterval(() => {
    fetch('http://localhost:8098/api/status')
        .then(r => r.json())
        .then(status => {
            document.getElementById('ralph-status').innerText =
                `Task ${status.current_task} of ${status.total_tasks}`;
        });
}, 5000);
```

## Security Considerations

1. **Authentication**: Currently no auth (localhost only)
   - For remote access, add authentication
   - Use nginx basic auth or OAuth

2. **HTTPS**: Control center uses HTTP (localhost)
   - For production, serve over HTTPS
   - Update links to use HTTPS where applicable

3. **CORS**: Open CORS for localhost
   - Restrict in production
   - Whitelist specific origins

4. **API Keys**: Configuration changes should require auth
   - Add API key validation
   - Log all configuration changes

## Customization

### Adding New Dashboards

Edit `control-center.html` to add new links:

```html
<div class="link-item">
    <a href="http://localhost:PORT" target="_blank">🔧 New Service</a>
</div>
```

### Adding New Configuration Variables

1. Add to config object:
```javascript
const config = {
    // ... existing ...
    my_new_var: 'default_value'
};
```

2. Add UI element:
```html
<div class="config-item">
    <span class="config-label">My New Variable</span>
    <input type="text" class="config-input" value="default"
           id="my-var" onchange="updateConfig('my_new_var', this.value)">
</div>
```

3. Update backend to handle new variable

### Theming

Modify CSS variables in `<style>`:

```css
:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --success-color: #4CAF50;
    --warning-color: #FF9800;
}
```

## Troubleshooting

### Control Center Not Loading
```bash
# Check dashboard server is running
ss -tlnp | grep 8888

# Restart if needed
./scripts/serve-dashboard.sh > "${TMPDIR:-/tmp}/dashboard.log" 2>&1 &
```

### Links Not Working
```bash
# Verify services are running
kubectl get pods -n ai-stack | egrep "(aidb|nginx|grafana|prometheus)"

# Re-apply manifests if needed
kubectl apply -k ai-stack/kustomize/overlays/dev
```

### Configuration Not Applying
```bash
# Currently changes are client-side only
# To apply, manually edit config and restart:
nano ai-stack/mcp-servers/config/config.yaml
kubectl rollout restart deployment/aidb -n ai-stack
kubectl rollout restart deployment/hybrid-coordinator -n ai-stack
```

## Roadmap

Future enhancements:

- [ ] Backend API for configuration management
- [ ] Real-time metrics integration
- [ ] Ralph Wiggum task submission UI
- [ ] Live log streaming
- [ ] Alert management
- [ ] User authentication
- [ ] Mobile responsive design
- [ ] Dark/light theme toggle
- [ ] Export configuration as code
- [ ] Rollback configuration changes

## Related Documentation

- [System Dashboard](./dashboard.html)
- [Production Hardening Roadmap](./PRODUCTION-HARDENING-ROADMAP.md)
- [Security Setup Guide](./SECURITY-SETUP.md)
- [Orchestration Visual Summary](./ORCHESTRATION-VISUAL-SUMMARY.md)
- [Phase 1 Complete](./docs/archive/PHASE-1-COMPLETE.md)

---

**Version**: 1.0
**Last Updated**: January 9, 2026
**Status**: Operational ✅
