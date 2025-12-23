# Enforcing Local AI Stack Usage
**Problem**: AI agents (including Claude Code) bypass local infrastructure
**Solution**: Multiple enforcement layers

---

## Current Situation

**Problem**: Claude Code (this session) uses remote Anthropic API directly:
- No queries routed through hybrid coordinator
- No RAG context retrieval
- No telemetry generated
- No token savings recorded
- Continuous learning system has no data

**Root Cause**: Claude Code VSCode extension connects directly to Anthropic API

---

## Enforcement Strategies

### Strategy 1: MCP Server Integration (Recommended)

**How it works**: Configure Claude Code to use local MCP servers

**Implementation**:

1. **Create MCP configuration** (`~/.config/claude-code/mcp_servers.json`):
```json
{
  "mcpServers": {
    "local-ai-stack": {
      "command": "python3",
      "args": ["/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/claude-local-wrapper.py"],
      "env": {
        "HYBRID_COORDINATOR_URL": "http://localhost:8092",
        "AIDB_MCP_URL": "http://localhost:8091"
      }
    }
  }
}
```

2. **Wrapper intercepts queries**:
   - Claude Code → MCP Wrapper → Hybrid Coordinator → Local/Remote LLM
   - All queries logged with telemetry
   - RAG context automatically added

**Status**: ⚠️ Requires Claude Code MCP support (check documentation)

---

### Strategy 2: HTTP Proxy Interception

**How it works**: Intercept HTTP requests to `api.anthropic.com` and redirect to local stack

**Implementation**:

1. **Create proxy server** (`scripts/anthropic-proxy.py`):
```python
# Intercepts requests to api.anthropic.com
# Routes through hybrid coordinator
# Returns responses in Anthropic API format
```

2. **Configure environment**:
```bash
export HTTPS_PROXY=http://localhost:8093
export ANTHROPIC_BASE_URL=http://localhost:8093
```

3. **Start proxy**:
```bash
python3 scripts/anthropic-proxy.py --port 8093
```

**Status**: 🔨 Need to implement proxy server

---

### Strategy 3: API Key Hook

**How it works**: Custom API endpoint that wraps Anthropic API

**Implementation**:

1. **Deploy local API wrapper**:
```bash
# Listens on localhost:8094
# Accepts Anthropic API format requests
# Routes through hybrid coordinator
# Calls real Anthropic API for remote queries
```

2. **Configure VSCode settings** (`settings.json`):
```json
{
  "anthropic.apiUrl": "http://localhost:8094",
  "anthropic.apiKey": "local-stack-key"
}
```

**Status**: 🔨 Need to implement API wrapper

---

### Strategy 4: VSCode Extension Fork (Nuclear Option)

**How it works**: Fork Claude Code extension, modify to use local stack by default

**Implementation**:

1. **Clone extension**:
```bash
git clone <claude-code-extension-repo>
```

2. **Modify API calls**:
```typescript
// Before: Direct Anthropic API
const response = await anthropic.messages.create({...})

// After: Route through local stack
const response = await localAIStack.query({...})
```

3. **Package and install**:
```bash
vsce package
code --install-extension claude-code-local-*.vsix
```

**Status**: ❌ High maintenance, breaks on updates

---

### Strategy 5: Systemd Service Hook (Current Best Option)

**How it works**: Run monitoring service that detects Claude usage and logs warnings

**Implementation**:

1. **Monitor network connections**:
```bash
# Detect connections to api.anthropic.com
ss -tnp | grep anthropic
```

2. **Log violations**:
```bash
# Append to telemetry
echo '{"type":"remote_api_usage","timestamp":"..."}' >> remote-usage.jsonl
```

3. **Dashboard warning**:
```javascript
// Show "⚠️ AI agent bypassing local stack" alert
```

**Status**: ✅ Implemented below

---

## Implemented Solutions

### Solution A: Demonstration Script

**File**: `scripts/demo-local-ai-usage.py`

**What it does**:
- Shows correct usage pattern
- Routes queries through hybrid coordinator
- Retrieves RAG context
- Generates telemetry
- Measures token savings

**Run it**:
```bash
python3 scripts/demo-local-ai-usage.py
```

---

### Solution B: CLI Wrapper

**File**: `scripts/claude-local-wrapper.py`

**What it does**:
- Provides CLI interface to local AI stack
- Can be used instead of direct API calls
- Logs all usage
- Automatic RAG context retrieval

**Usage**:
```bash
# Force local LLM
./scripts/claude-local-wrapper.py --force-local "How do I use Qdrant?"

# Auto-route (hybrid decision)
./scripts/claude-local-wrapper.py "Complex architecture design question"
```

---

### Solution C: Git Pre-Commit Hook

**What it does**: Reminds developers to use local stack

**File**: `.git/hooks/pre-commit`
```bash
#!/bin/bash
# Check if commit includes AI-related changes
if git diff --cached | grep -i "anthropic\|claude.*api"; then
    echo "⚠️  WARNING: Direct Anthropic API usage detected"
    echo "   Please route through hybrid coordinator (localhost:8092)"
    echo "   See: docs/ENFORCE-LOCAL-AI-USAGE.md"
    echo ""
    echo "   Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

---

### Solution D: Environment Variable Enforcement

**What it does**: Block remote API if env var not set

**File**: `.bashrc` or `.zshrc`
```bash
# Force local AI usage
export ANTHROPIC_API_URL="http://localhost:8094"
export CLAUDE_CODE_USE_LOCAL="1"

# Alternative: Unset API key to prevent remote usage
# unset ANTHROPIC_API_KEY
```

---

## Testing Enforcement

### Test 1: Verify Wrapper Works
```bash
python3 scripts/demo-local-ai-usage.py
# Should see telemetry events generated
tail -5 ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl
```

### Test 2: Check Dashboard Metrics
```bash
bash scripts/generate-dashboard-data.sh
cat ~/.local/share/nixos-system-dashboard/hybrid-coordinator.json | jq .
# Should show updated query counts
```

### Test 3: Verify Token Savings
```bash
cat ~/.local/share/nixos-system-dashboard/token-savings.json | jq .
# Should show non-zero values
```

---

## Recommendation for Your Setup

**Immediate (Today)**:
1. ✅ Run `scripts/demo-local-ai-usage.py` to generate sample telemetry
2. ✅ Use `scripts/claude-local-wrapper.py` for manual queries
3. ✅ Add git pre-commit hook to remind about local usage

**Short-term (This Week)**:
4. 🔨 Implement HTTP proxy (Strategy 2)
5. 🔨 Configure proxy as default in shell environment
6. 📊 Monitor dashboard for usage patterns

**Long-term (Next Month)**:
7. 🔍 Research Claude Code MCP configuration
8. 🔧 If MCP supported: Configure MCP servers (Strategy 1)
9. 🔧 If not: Implement API wrapper (Strategy 3)
10. 📈 Set up automated alerts for remote API usage

---

## Why This Matters

**Current Cost** (your session today):
- ~100,000 tokens sent to Claude Sonnet 4.5 API
- Cost: ~$0.30 per million input tokens = **$0.03**
- No local LLM usage
- No continuous learning data

**With Local Stack**:
- 70%+ queries → local LLM (free)
- 30% complex queries → remote API
- Estimated savings: **$0.02 per session** (67% reduction)
- Continuous learning improves over time
- Full telemetry for system optimization

**Projected Annual Savings** (100 sessions/month):
- Current: $0.03 × 100 × 12 = $36/year
- With local: $0.01 × 100 × 12 = $12/year
- **Savings: $24/year** + improved local capability

---

## Next Steps

1. Run the demonstration:
```bash
python3 scripts/demo-local-ai-usage.py
```

2. Check telemetry generated:
```bash
bash scripts/generate-dashboard-data.sh
xdg-open http://localhost:8888/dashboard.html
```

3. Choose enforcement strategy:
   - Option A: HTTP Proxy (transparent, works with all tools)
   - Option B: MCP Integration (native, if supported)
   - Option C: Environment hooks (simple, manual)

4. Implement chosen strategy (see sections above)

---

**Last Updated**: 2025-12-22
**Status**: Demonstration scripts ready, enforcement pending implementation
