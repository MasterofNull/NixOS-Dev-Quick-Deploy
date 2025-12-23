# Health Monitoring MCP Server

**Version**: 1.0.0
**Created**: 2025-12-21
**Type**: MCP Server (Model Context Protocol)

## Overview

The Health Monitoring MCP Server provides continuous health monitoring capabilities for the NixOS Hybrid AI Learning Stack. It exposes tools that agents can use to check service health, collect metrics, and identify issues.

## Purpose

This MCP server was created to enable:
1. **Automated Health Checks**: Agents can check service status without manual scripting
2. **Real-time Metrics**: Access to dashboard data through standardized tools
3. **Issue Detection**: Automatic identification of critical issues
4. **Trend Analysis**: Historical health data aggregation

## Features

### 1. Service Health Monitoring

- Checks 7 AI stack services (Qdrant, Ollama, llama.cpp, Open WebUI, AIDB, Hybrid Coordinator, MindsDB)
- Measures response times
- Detects offline/degraded states
- Parallel health checks for speed

### 2. Dashboard Metrics Access

- Read any of 15 dashboard JSON files
- Parse and validate JSON data
- Cache results to reduce I/O

### 3. Health Score Calculation

- Overall system health percentage (0-100%)
- Service availability tracking
- Critical issue identification

### 4. Dashboard Data Regeneration

- Trigger fresh metrics collection
- Execute `generate-dashboard-data.sh` remotely
- Capture output and status

## Tools Exposed

### `check_service_health`
Check health status of a specific service.

**Input**:
```json
{
  "service_id": "qdrant"  // One of: qdrant, llama_cpp, llama-cpp_server, open_webui, aidb, hybrid_coordinator, mindsdb
}
```

**Output**:
```json
{
  "service": "qdrant",
  "name": "Qdrant Vector DB",
  "url": "http://localhost:6333/healthz",
  "status": "online",
  "response_time_ms": 12.34,
  "status_code": 200,
  "checked_at": "2025-12-21T20:30:00-08:00"
}
```

### `check_all_services`
Check health status of all services.

**Input**: None

**Output**: Array of service health objects

### `get_dashboard_metrics`
Get metrics from a dashboard data file.

**Input**:
```json
{
  "filename": "rag-collections.json"  // One of 15 dashboard files
}
```

**Output**: Parsed JSON content of the file

### `regenerate_dashboard`
Regenerate all dashboard data files.

**Input**: None

**Output**:
```json
{
  "success": true,
  "returncode": 0,
  "stdout": "Dashboard data generated...",
  "stderr": "",
  "timestamp": "2025-12-21T20:30:00-08:00"
}
```

### `get_health_summary`
Get comprehensive health summary.

**Input**: None

**Output**:
```json
{
  "timestamp": "2025-12-21T20:30:00-08:00",
  "health_score": 88.9,
  "services": {
    "total": 7,
    "online": 6,
    "offline": 1,
    "degraded": 0
  },
  "rag_collections": {
    "total": 5,
    "total_points": 1
  },
  "learning": {
    "total_interactions": 0,
    "learning_rate": 0.0
  },
  "token_savings": {
    "local_percent": 0.0,
    "estimated_savings_usd": 0.0
  },
  "critical_issues": [
    "Dashboard data is stale (22.3 minutes old)",
    "Empty RAG collections: codebase-context, skills-patterns, ..."
  ]
}
```

### `get_critical_issues`
Get list of critical issues.

**Input**: None

**Output**:
```json
{
  "issues": [
    "Dashboard data is stale (22.3 minutes old)",
    "Empty RAG collections: codebase-context, skills-patterns, error-solutions, interaction-history, best-practices"
  ]
}
```

## Installation

### 1. Install Dependencies
```bash
cd ai-stack/mcp-servers/health-monitor
pip install -r requirements.txt
```

### 2. Make Server Executable
```bash
chmod +x server.py
```

### 3. Test Server
```bash
python server.py
```

## Usage

### As MCP Server (Recommended)

Configure in your MCP client settings:

```json
{
  "mcpServers": {
    "health-monitor": {
      "command": "python",
      "args": [
        "/path/to/ai-stack/mcp-servers/health-monitor/server.py"
      ],
      "env": {
        "PROJECT_ROOT": "/path/to/NixOS-Dev-Quick-Deploy"
      }
    }
  }
}
```

### As Standalone Tool

```python
import asyncio
from health_monitor import HealthMonitor

async def main():
    monitor = HealthMonitor()

    # Check all services
    results = await monitor.check_all_services()
    for service in results:
        print(f"{service['name']}: {service['status']}")

    # Get health score
    score = monitor.calculate_health_score(results)
    print(f"Health Score: {score}%")

asyncio.run(main())
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | Current directory | Path to NixOS-Dev-Quick-Deploy |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Data Sources

### Service Health Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Qdrant | `http://localhost:6333/healthz` | 200 OK |
| Ollama | `http://localhost:11434/api/tags` | 200 OK |
| llama.cpp | `http://localhost:8080/health` | 200 OK |
| Open WebUI | `http://localhost:3001` | 200 OK |
| AIDB | `http://localhost:8091/health` | 200 OK |
| Hybrid Coordinator | `http://localhost:8092/health` | 200 OK |
| MindsDB | `http://localhost:47334` | 200 OK |

### Dashboard Files

Location: `~/.local/share/nixos-system-dashboard/`

15 JSON files containing system, service, and learning metrics.

## Error Handling

- **Service Timeout**: 5 second timeout per service check
- **File Not Found**: Returns error object with description
- **Invalid JSON**: Returns parsing error
- **Script Execution**: 60 second timeout for dashboard regeneration

## Performance

- **Parallel Checks**: All services checked concurrently
- **Response Time**: Typical health check < 100ms per service
- **Memory Usage**: < 50MB under normal operation
- **Cache TTL**: 30 seconds for dashboard data

## Integration

### With System Analysis Skill

The system-analysis agent skill can use this MCP server to:
- Check service health before analysis
- Regenerate data for fresh metrics
- Monitor trends over time

### With Claude Code

Configure as an MCP server in Claude Code settings to enable:
- Real-time health monitoring during debugging
- Automated health checks before deployments
- Issue detection in CI/CD pipelines

### With Custom Agents

Any agent can use this server through MCP protocol:
```python
# Agent uses MCP to call health-monitor
result = await mcp_client.call_tool(
    server="health-monitor",
    tool="check_all_services",
    arguments={}
)
```

## Troubleshooting

### Server Won't Start

Check dependencies:
```bash
pip install -r requirements.txt
python -c "import mcp, httpx, pydantic; print('OK')"
```

### Service Always Shows Offline

Verify service is actually running:
```bash
podman ps | grep local-ai
curl http://localhost:6333/healthz
```

### Dashboard Data Stale

Manually regenerate:
```bash
bash scripts/generate-dashboard-data.sh
```

### Permission Denied

Ensure script is executable:
```bash
chmod +x scripts/generate-dashboard-data.sh
```

## Future Enhancements

- [ ] WebSocket support for real-time streaming
- [ ] Historical health data storage
- [ ] Alerting system integration
- [ ] Grafana/Prometheus exporter
- [ ] Custom health check definitions
- [ ] Multi-system monitoring
- [ ] Performance profiling tools

## Related Documentation

- [MCP Server Documentation](https://modelcontextprotocol.io/)
- [Dashboard Enhancements](../../../DASHBOARD-ENHANCEMENTS-2025-12-21.md)
- [System Analysis Skill](../../../.claude/skills/system-analysis/README.md)
- [Comprehensive Analysis](../../../COMPREHENSIVE-SYSTEM-ANALYSIS.md)

## Version History

- **1.0.0** (2025-12-21): Initial release
  - 7 service health checks
  - 15 dashboard file access
  - 6 MCP tools
  - Health scoring algorithm
  - Critical issue detection
