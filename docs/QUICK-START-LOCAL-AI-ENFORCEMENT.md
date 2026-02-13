# Quick Start: Claude Code Local AI Enforcement
**Time to setup**: 5 minutes
**Skill level**: Copy-paste commands

---

## What This Does

Makes Claude Code (the AI assistant in your VSCode) automatically use your local AI stack instead of always calling the remote Anthropic API. This means:

✅ **Token savings** - Simple queries run locally (free)
✅ **Privacy** - Sensitive code stays on your machine
✅ **Speed** - Local LLM responds faster for simple queries
✅ **Metrics** - Track usage and savings on dashboard
✅ **Automatic** - Zero workflow changes, completely transparent

---

## Prerequisites

**Already installed** (from previous setup):
- ✅ Hybrid coordinator (port 8092)
- ✅ AIDB MCP server (port 8091)
- ✅ Claude Code in VSCode/VSCodium
- ✅ Python 3

**Verify services are running**:
```bash
curl http://localhost:8092/health  # Hybrid coordinator
curl http://localhost:8091/health  # AIDB (might 404, that's ok)
```

If these fail, start your AI stack first:
```bash
bash scripts/start-ai-stack-and-dashboard.sh
```

---

## Installation (3 commands)

```bash
# 1. Navigate to project
cd ~/Documents/try/NixOS-Dev-Quick-Deploy

# 2. Run setup script
bash scripts/setup-claude-proxy.sh

# 3. Restart VSCode/VSCodium
# (Close all windows and relaunch)
```

**That's it!** Claude Code now routes through your local AI stack.

---

## Verification (2 minutes)

### Step 1: Check proxy is running
```bash
systemctl --user status claude-api-proxy
```

**Expected output**:
```
● claude-api-proxy.service - Claude API Proxy
   Active: active (running) since ...
```

### Step 2: Use Claude Code and check telemetry
1. Open VSCode/VSCodium
2. Use Claude Code for any simple query (e.g., "List files in current directory")
3. Check telemetry file:

```bash
tail -5 ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl
```

**Expected output** (JSON lines):
```json
{"timestamp":"2025-12-22T10:30:45","event_type":"api_query_routed","metadata":{"routing_decision":"local","tokens_saved":87}}
```

### Step 3: Check dashboard
```bash
# Regenerate dashboard data
bash scripts/generate-dashboard-data.sh --lite-mode

# Open dashboard
xdg-open http://localhost:8888/dashboard.html
```

**Look for**:
- Token Savings card showing accumulated savings
- Coordinator Metrics showing activity

---

## How It Works

```
Your Claude Code Query
         ↓
Claude Wrapper (modified)
  Sets: ANTHROPIC_BASE_URL=http://localhost:8094
         ↓
Claude API Proxy (localhost:8094)
  Analyzes query complexity
         ↓
    ┌────┴────┐
    ↓         ↓
 SIMPLE    COMPLEX
    ↓         ↓
 LOCAL     REMOTE
(Free)    (Paid)
```

**Routing Rules**:
- **Simple** (<100 tokens): Local LLM via hybrid coordinator
- **Medium** (100-3000 tokens): Local if coordinator healthy, else remote
- **Complex** (>3000 tokens): Always remote

---

## Monitoring

### Real-time proxy logs
```bash
journalctl --user -u claude-api-proxy -f
```

**What you'll see when using Claude Code**:
```
[INFO] 📍 Routing to LOCAL (tokens ~87)
[INFO] 📚 Retrieved 3 context documents
[INFO] ✅ Response received (tokens: 87)
[INFO] 📊 Telemetry logged: local
```

### Daily telemetry summary
```bash
cat ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl | \
  jq -s 'group_by(.metadata.routing_decision) | map({decision: .[0].metadata.routing_decision, count: length})'
```

**Expected output**:
```json
[
  {"decision": "local", "count": 42},
  {"decision": "remote", "count": 8}
]
```

### Token savings calculation
```bash
cat ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl | \
  jq -s 'map(.metadata.tokens_saved) | add'
```

**Example output**: `3542` (tokens saved today)

---

## Troubleshooting

### Proxy won't start
```bash
# Check logs
journalctl --user -u claude-api-proxy -n 50

# Common fix: Port already in use
netstat -tlnp | grep 8094
# If occupied, kill process or change port in setup script
```

### Claude Code still using remote API
```bash
# 1. Verify wrapper was modified
grep ANTHROPIC_BASE_URL ~/.npm-global/bin/claude-wrapper

# 2. Did you restart VSCode?
# Must fully exit (File → Exit) and relaunch

# 3. Check VSCode settings
cat ~/.config/VSCodium/User/settings.json | grep claudeProcessWrapper
# Should point to: ~/.npm-global/bin/claude-wrapper
```

### No telemetry events appearing
```bash
# Watch proxy logs in real-time
journalctl --user -u claude-api-proxy -f

# Then use Claude Code - you should see log entries
# If not, wrapper might not be active

# Check wrapper is being used
ps aux | grep claude-wrapper
```

### Coordinator not responding
```bash
# Check hybrid coordinator status
curl http://localhost:8092/health

# If fails, restart AI stack
bash scripts/start-ai-stack-and-dashboard.sh
```

---

## Management Commands

```bash
# Stop proxy
systemctl --user stop claude-api-proxy

# Start proxy
systemctl --user start claude-api-proxy

# Restart proxy (after config changes)
systemctl --user restart claude-api-proxy

# Disable autostart
systemctl --user disable claude-api-proxy

# Enable autostart
systemctl --user enable claude-api-proxy

# View full logs
journalctl --user -u claude-api-proxy --no-pager
```

---

## Configuration

### Change routing thresholds

Edit: `scripts/claude-api-proxy.py`

```python
# Line 27-28
SIMPLE_QUERY_TOKENS = 100   # Increase → more queries go local
COMPLEX_QUERY_TOKENS = 3000  # Decrease → fewer queries go local
```

After editing:
```bash
systemctl --user restart claude-api-proxy
```

### Change proxy port

Edit: `scripts/claude-api-proxy.py`

```python
# Line 400 (bottom of file)
start_proxy(host='127.0.0.1', port=8094)  # Change 8094 to desired port
```

Also update in wrapper:
```bash
nano ~/.npm-global/bin/claude-wrapper
# Change: export ANTHROPIC_BASE_URL="http://localhost:8094"
```

Restart:
```bash
systemctl --user restart claude-api-proxy
# Restart VSCode
```

---

## Disable/Rollback

If you want to go back to direct Anthropic API:

```bash
# 1. Stop proxy
systemctl --user stop claude-api-proxy
systemctl --user disable claude-api-proxy

# 2. Restore original wrapper
BACKUP=$(ls -t ~/.npm-global/bin/claude-wrapper.backup-* | head -1)
cp "${BACKUP}" ~/.npm-global/bin/claude-wrapper

# 3. Restart VSCode
```

Claude Code will now bypass local stack and go directly to Anthropic.

---

## Expected Results (After 1 Day)

**Dashboard Metrics**:
- Token savings: ~5,000-10,000 tokens
- Local queries: ~60-70%
- Remote queries: ~30-40%
- Cost savings: ~$0.08-$0.15

**Telemetry Files**:
- `~/.local/share/nixos-ai-stack/telemetry/events-YYYY-MM-DD.jsonl` (10-50 KB)
- `~/.local/share/nixos-ai-stack/telemetry/proxy.log` (5-20 KB)

**System Impact**:
- CPU: Negligible (proxy is lightweight)
- Memory: ~30 MB (Python process)
- Disk: ~100 KB/day (telemetry)
- Network: Reduced (fewer Anthropic API calls)

---

## What Gets Routed Locally (Examples)

✅ **File operations**: "Read this file", "List directory contents"
✅ **Git commands**: "Show git status", "What changed?"
✅ **Simple queries**: "What is X?", "How do I Y?"
✅ **Code explanations**: "Explain this function" (short functions)
✅ **Syntax help**: "Python list comprehension syntax"

❌ **What stays remote** (complex):
- Multi-file refactoring
- Architecture design
- Long code reviews
- Complex debugging sessions

---

## Next Steps

1. ✅ Use Claude Code normally for a day
2. ✅ Check dashboard tomorrow for token savings
3. ✅ Review telemetry to see local vs remote ratio
4. ✅ Adjust thresholds if needed
5. ✅ Share feedback in project issues

---

## Support

**Logs to check**:
```bash
# Proxy operational logs
journalctl --user -u claude-api-proxy -n 100

# Telemetry events
cat ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl
```

**Documentation**:
- Full details: [CLAUDE-LOCAL-ENFORCEMENT-COMPLETE.md](/docs/archive/CLAUDE-LOCAL-ENFORCEMENT-COMPLETE.md)
- Enforcement strategies: [docs/ENFORCE-LOCAL-AI-USAGE.md](/docs/ENFORCE-LOCAL-AI-USAGE.md)
- API proxy code: [scripts/claude-api-proxy.py](/scripts/claude-api-proxy.py)

---

**Status**: ✅ Ready to use
**Last Updated**: 2025-12-22
**Installation Time**: 5 minutes
**Maintenance**: None (runs automatically)
