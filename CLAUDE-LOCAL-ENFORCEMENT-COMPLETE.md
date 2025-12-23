# Claude Code Local AI Stack Enforcement - Implementation Complete
**Date**: 2025-12-22
**Status**: ✅ Ready to deploy

---

## Overview

This implementation ensures Claude Code (and any AI agent using the Anthropic API) automatically routes queries through your local AI stack instead of going directly to the remote API.

**Key Achievement**: Transparent enforcement - no manual workflow changes required.

---

## Architecture

```
┌─────────────────┐
│   Claude Code   │
│   (VSCodium)    │
└────────┬────────┘
         │ API calls to api.anthropic.com
         ↓
┌─────────────────────────────────────┐
│  claude-wrapper (Bash)              │
│  Sets: ANTHROPIC_BASE_URL           │
│  = http://localhost:8094            │
└────────┬────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────┐
│  Claude API Proxy (Python)          │
│  Port: 8094                         │
│  - Intercepts API requests          │
│  - Routes simple → local            │
│  - Routes complex → remote          │
│  - Logs telemetry                   │
│  - Tracks token savings             │
└────┬────────────────────────────┬───┘
     │                            │
     │ Simple queries             │ Complex queries
     ↓                            ↓
┌────────────────┐     ┌──────────────────┐
│ Hybrid         │     │ Anthropic API    │
│ Coordinator    │     │ (Real)           │
│ Port: 8092     │     │ api.anthropic.com│
└───────┬────────┘     └──────────────────┘
        │
        ↓
┌────────────────┐
│ AIDB MCP       │
│ (RAG Context)  │
│ Port: 8091     │
└────────────────┘
```

---

## Components Created

### 1. **claude-api-proxy.py** (300 lines)
**Location**: `scripts/claude-api-proxy.py`

**What It Does**:
- Mimics Anthropic API on localhost:8094
- Receives all Claude Code API requests
- Routes based on query complexity:
  - Simple (<100 tokens) → Local LLM via hybrid coordinator
  - Complex (>3000 tokens) → Real Anthropic API
  - Medium → Local if coordinator healthy, else remote
- Retrieves RAG context from AIDB for all local queries
- Logs every query to telemetry system
- Tracks token savings in real-time

**Key Functions**:
```python
def _handle_messages_request():
    # 1. Parse Claude Code request
    # 2. Estimate complexity
    # 3. Route to local or remote
    # 4. Log telemetry
    # 5. Return response in Anthropic API format

def _route_to_local(request_data):
    # 1. Get RAG context from AIDB
    # 2. Send to hybrid coordinator
    # 3. Format response as Anthropic API

def _log_telemetry(request, response, used_local, tokens):
    # Append to: ~/.local/share/nixos-ai-stack/telemetry/events-YYYY-MM-DD.jsonl
```

**Telemetry Format**:
```json
{
  "timestamp": "2025-12-22T10:30:45.123456",
  "event_type": "api_query_routed",
  "source": "claude_api_proxy",
  "metadata": {
    "routing_decision": "local",
    "estimated_tokens": 87,
    "tokens_saved": 87,
    "model": "claude-sonnet-4-5-20250929",
    "success": true
  }
}
```

---

### 2. **setup-claude-proxy.sh** (150 lines)
**Location**: `scripts/setup-claude-proxy.sh`

**What It Does**:
1. Creates systemd user service for proxy
2. Backs up original claude-wrapper
3. Adds `ANTHROPIC_BASE_URL=http://localhost:8094` to wrapper
4. Enables and starts proxy service
5. Verifies setup

**Usage**:
```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy
bash scripts/setup-claude-proxy.sh
```

**What Gets Modified**:
- `~/.config/systemd/user/claude-api-proxy.service` (created)
- `~/.npm-global/bin/claude-wrapper` (modified, backup created)

---

### 3. **claude-wrapper Enhancement**
**Location**: `~/.npm-global/bin/claude-wrapper` (already exists, will be modified)

**Original Line 90**:
```bash
exec "${NODE_BIN}" "${CLI_PATH}" "$@"
```

**Enhanced Version** (added before exec):
```bash
# Route Claude API calls through local AI stack proxy
export ANTHROPIC_BASE_URL="http://localhost:8094"

exec "${NODE_BIN}" "${CLI_PATH}" "$@"
```

**Why This Works**:
- Claude CLI (and most Anthropic SDK clients) respect `ANTHROPIC_BASE_URL`
- All API calls get redirected to our proxy
- Completely transparent to Claude Code
- No changes to VSCode settings needed

---

### 4. **Systemd Service**
**Location**: `~/.config/systemd/user/claude-api-proxy.service`

**Service Configuration**:
```ini
[Unit]
Description=Claude API Proxy
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 .../scripts/claude-api-proxy.py
Restart=on-failure
Environment="HYBRID_COORDINATOR_URL=http://localhost:8092"
Environment="AIDB_MCP_URL=http://localhost:8091"

[Install]
WantedBy=default.target
```

**Management**:
```bash
# Start/stop
systemctl --user start claude-api-proxy
systemctl --user stop claude-api-proxy

# Enable autostart
systemctl --user enable claude-api-proxy

# View logs
journalctl --user -u claude-api-proxy -f
```

---

## Installation Steps

### Quick Install (5 minutes)

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# 1. Run setup script
bash scripts/setup-claude-proxy.sh

# 2. Verify proxy is running
systemctl --user status claude-api-proxy

# 3. Test proxy manually
curl http://localhost:8094/health
# Should return error (no health endpoint), but confirms listening

# 4. Restart VSCode/VSCodium
# File → Exit (Ctrl+Q)
# Relaunch VSCode

# 5. Use Claude Code normally - it now routes through local stack!
```

---

## Verification

### 1. Check Proxy is Running
```bash
systemctl --user status claude-api-proxy
# Expected: "active (running)"
```

### 2. Check Wrapper is Modified
```bash
grep "ANTHROPIC_BASE_URL" ~/.npm-global/bin/claude-wrapper
# Expected: export ANTHROPIC_BASE_URL="http://localhost:8094"
```

### 3. Use Claude Code and Check Telemetry
```bash
# Open VSCode, use Claude Code for a simple query
# Then check telemetry:
tail -5 ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl

# Expected output:
# {"timestamp": "...", "event_type": "api_query_routed", "metadata": {"routing_decision": "local", ...}}
```

### 4. Check Token Savings on Dashboard
```bash
# Regenerate dashboard data
bash scripts/generate-dashboard-data.sh --lite-mode

# Open dashboard
xdg-open http://localhost:8888/dashboard.html

# Check "Token Savings" card - should show accumulated savings
```

### 5. Monitor Proxy Logs in Real-Time
```bash
journalctl --user -u claude-api-proxy -f

# Expected output when you use Claude Code:
# [INFO] 📍 Routing to LOCAL (tokens ~87)
# [INFO] 📊 Telemetry logged: local
```

---

## Routing Logic

### Simple Queries (→ LOCAL)
- Estimated tokens < 100
- Examples:
  - "List files in current directory"
  - "What is NixOS?"
  - "Show git status"

**Process**:
1. Proxy receives request
2. Fetches RAG context from AIDB (3 docs)
3. Sends to hybrid coordinator with context
4. Logs telemetry: `tokens_saved = estimated_tokens`

### Medium Queries (→ LOCAL if healthy)
- Estimated tokens 100-3000
- Examples:
  - "Explain this code block"
  - "Review this function"
  - "Fix this bug"

**Process**:
1. Checks if hybrid coordinator is responsive
2. If yes → local (with RAG context)
3. If no → fallback to remote

### Complex Queries (→ REMOTE)
- Estimated tokens > 3000
- max_tokens > 2000
- Examples:
  - "Refactor entire codebase"
  - "Design distributed system architecture"
  - Multi-file analysis

**Process**:
1. Proxy forwards directly to real Anthropic API
2. Uses `ANTHROPIC_API_KEY` from environment
3. Logs telemetry: `tokens_saved = 0`

---

## Configuration

### Environment Variables

**In Proxy Service** (`~/.config/systemd/user/claude-api-proxy.service`):
```bash
Environment="HYBRID_COORDINATOR_URL=http://localhost:8092"
Environment="AIDB_MCP_URL=http://localhost:8091"
Environment="ANTHROPIC_API_KEY="  # Set your real key here if needed
```

**In Claude Wrapper** (`~/.npm-global/bin/claude-wrapper`):
```bash
export ANTHROPIC_BASE_URL="http://localhost:8094"
```

### Tuning Routing Thresholds

Edit `scripts/claude-api-proxy.py`:

```python
# Line 27-28: Adjust these values
SIMPLE_QUERY_TOKENS = 100   # Increase to route more locally
COMPLEX_QUERY_TOKENS = 3000  # Decrease to route more remotely
```

After changing:
```bash
systemctl --user restart claude-api-proxy
```

---

## Telemetry Integration

### Where Telemetry is Stored
```
~/.local/share/nixos-ai-stack/telemetry/
├── events-2025-12-22.jsonl  # Daily event logs
├── events-2025-12-23.jsonl
└── proxy.log                # Proxy operational logs
```

### Event Schema
```json
{
  "timestamp": "ISO-8601 datetime",
  "event_type": "api_query_routed",
  "source": "claude_api_proxy",
  "metadata": {
    "routing_decision": "local|remote",
    "estimated_tokens": 123,
    "tokens_saved": 123,
    "model": "claude-sonnet-4-5-20250929",
    "success": true|false
  }
}
```

### Dashboard Integration

The existing dashboard already has collectors for telemetry. After proxy generates events:

```bash
# Regenerate dashboard data
bash scripts/generate-dashboard-data.sh --lite-mode

# Dashboard will show:
# - Total token savings
# - Local vs remote routing ratio
# - Query success rate
# - Coordinator usage metrics
```

---

## Troubleshooting

### Proxy Not Starting
```bash
# Check logs
journalctl --user -u claude-api-proxy -n 50

# Common issues:
# 1. Port 8094 already in use
netstat -tlnp | grep 8094

# 2. Python not found
which python3

# 3. Permission denied on telemetry directory
mkdir -p ~/.local/share/nixos-ai-stack/telemetry
chmod 755 ~/.local/share/nixos-ai-stack/telemetry
```

### Claude Code Still Using Remote API
```bash
# 1. Check wrapper has ANTHROPIC_BASE_URL
grep ANTHROPIC_BASE_URL ~/.npm-global/bin/claude-wrapper

# 2. Verify VSCode is using wrapper
cat ~/.config/VSCodium/User/settings.json | grep claudeProcessWrapper
# Expected: "claudeCode.claudeProcessWrapper": "...claude-wrapper"

# 3. Restart VSCode completely (exit and relaunch)

# 4. Test manually
export ANTHROPIC_BASE_URL=http://localhost:8094
claude
# Should connect to proxy
```

### No Telemetry Events
```bash
# 1. Check proxy is receiving requests
journalctl --user -u claude-api-proxy -f
# Use Claude Code and watch for log entries

# 2. Check telemetry directory exists
ls -la ~/.local/share/nixos-ai-stack/telemetry/

# 3. Check file permissions
touch ~/.local/share/nixos-ai-stack/telemetry/test.jsonl
# If fails, fix permissions
```

### Hybrid Coordinator Not Responding
```bash
# Check coordinator is running
curl http://localhost:8092/health

# If not running, start it
systemctl --user start hybrid-coordinator
# Or check ai-stack services
podman ps | grep hybrid
```

---

## Comparison: Before vs After

### Before Enforcement
```
Claude Code → Anthropic API (direct)
- All queries use remote API
- No telemetry generated
- No token savings tracked
- No RAG context retrieval
- No progressive disclosure
```

### After Enforcement
```
Claude Code → Wrapper → Proxy → Routing Decision
                                ├─ Local (simple) → Hybrid Coordinator → AIDB → Local LLM
                                └─ Remote (complex) → Anthropic API

Benefits:
✅ Simple queries use local LLM (free, private, fast)
✅ Automatic RAG context retrieval for all local queries
✅ Telemetry logged for every query
✅ Token savings tracked and displayed on dashboard
✅ Progressive disclosure applied automatically
✅ Completely transparent to user workflow
```

---

## Expected Metrics (After 1 Week of Use)

Based on typical usage patterns:

**Query Distribution** (estimated):
- 60% simple queries → routed locally
- 30% medium queries → 80% local, 20% remote
- 10% complex queries → routed remotely

**Token Savings** (estimated):
- Average query: ~500 tokens
- Local routing saves: 500 tokens per query
- 60% local rate = 300 queries/week local
- **Total savings**: ~150,000 tokens/week
- **Cost savings**: ~$2.25/week ($0.015 per 1K tokens)

**Telemetry Events** (estimated):
- ~500 events/week
- Event size: ~200 bytes
- Storage: ~100 KB/week
- Retention: 90 days = ~9 MB

---

## Advanced Configuration

### Custom Routing Rules

Edit `scripts/claude-api-proxy.py` → `_should_use_local()`:

```python
def _should_use_local(self, estimated_tokens, max_tokens, request):
    # Custom rule: Always use local for specific models
    if request.get("model", "").startswith("claude-haiku"):
        return True

    # Custom rule: Use local for file reads, remote for writes
    messages = request.get("messages", [])
    if any("Read" in msg.get("content", "") for msg in messages):
        return True

    # Custom rule: Time-based routing (local during work hours)
    hour = datetime.now().hour
    if 9 <= hour <= 17:  # 9am-5pm use local
        return True

    # Fall back to default logic
    return estimated_tokens < SIMPLE_QUERY_TOKENS
```

### Multiple Proxy Instances

For high load, run multiple proxies:

```bash
# Proxy 1 on 8094
systemctl --user start claude-api-proxy

# Proxy 2 on 8095
PROXY_PORT=8095 python3 scripts/claude-api-proxy.py &

# Load balance in wrapper
export ANTHROPIC_BASE_URL="http://localhost:809$((RANDOM % 2 + 4))"
```

---

## Rollback

If you need to disable the proxy:

```bash
# 1. Stop and disable service
systemctl --user stop claude-api-proxy
systemctl --user disable claude-api-proxy

# 2. Restore original wrapper
LATEST_BACKUP=$(ls -t ~/.npm-global/bin/claude-wrapper.backup-* | head -1)
cp "${LATEST_BACKUP}" ~/.npm-global/bin/claude-wrapper

# 3. Restart VSCode

# Claude Code will now go directly to Anthropic API again
```

---

## Next Steps

### Immediate (After Installation)
1. ✅ Run `setup-claude-proxy.sh`
2. ✅ Restart VSCode
3. ✅ Use Claude Code normally and verify telemetry appears
4. ✅ Check dashboard for token savings

### This Week
1. Monitor proxy logs for errors
2. Adjust routing thresholds based on actual usage
3. Review telemetry events for accuracy
4. Compare token usage before/after on Anthropic billing page

### Future Enhancements
1. Add machine learning model for routing decisions
2. Implement query result caching (avoid duplicate work)
3. Add A/B testing (compare local vs remote quality)
4. Build feedback loop (user ratings → routing improvements)

---

## Summary

**What We Built**:
- Transparent API proxy intercepting all Claude Code requests
- Intelligent routing based on query complexity
- Automatic RAG context retrieval for local queries
- Complete telemetry logging
- Token savings tracking
- Systemd service for reliability
- Enhanced claude-wrapper for seamless integration

**Key Files**:
- `scripts/claude-api-proxy.py` - Core proxy server
- `scripts/setup-claude-proxy.sh` - Installation automation
- `~/.config/systemd/user/claude-api-proxy.service` - Service definition
- `~/.npm-global/bin/claude-wrapper` - Enhanced wrapper

**Installation**: One command (`bash scripts/setup-claude-proxy.sh`)

**User Experience**: Zero changes required - Claude Code just works, now powered by local AI

**Enforcement**: ✅ Complete - no documentation reading required

---

**Status**: ✅ Ready for deployment and testing

**Last Updated**: 2025-12-22
**Maintainer**: System Administrator
