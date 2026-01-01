#!/usr/bin/env bash
# AIDB MCP Server startup with Tool Discovery integration
# Automatically starts tool discovery engine alongside AIDB server

set -e

# Redirect all output to console (unbuffered)
exec 1>&1 2>&2

# Start AIDB server in background with tool discovery enabled
echo "🚀 Starting AIDB MCP Server with Tool Discovery..." >&2

# Set tool discovery flag
export AIDB_TOOL_DISCOVERY_ENABLED=true
export AIDB_TOOL_DISCOVERY_INTERVAL=300  # 5 minutes

# Start main server with unbuffered Python output
python3 -u /app/server.py --config /app/config/config.yaml "$@" 2>&1 &
SERVER_PID=$!

# Start tool discovery daemon with unbuffered output
python3 -u /app/tool_discovery_daemon.py 2>&1 &
DISCOVERY_PID=$!

echo "✅ AIDB Server PID: $SERVER_PID" >&2
echo "✅ Tool Discovery PID: $DISCOVERY_PID" >&2

# Wait for either process to exit
wait -n $SERVER_PID $DISCOVERY_PID

# If one exits, kill the other
kill $SERVER_PID $DISCOVERY_PID 2>/dev/null || true

echo "🛑 AIDB services stopped" >&2
