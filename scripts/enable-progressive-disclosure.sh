#!/usr/bin/env bash
# Enable Progressive Disclosure Discovery API
# Integrates discovery endpoints into AIDB MCP server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AIDB_DIR="$PROJECT_ROOT/ai-stack/mcp-servers/aidb"
SERVER_FILE="$AIDB_DIR/server.py"
BACKUP_FILE="$SERVER_FILE.backup-$(date +%Y%m%d-%H%M%S)"

echo "=== Progressive Disclosure Integration ==="
echo

# Check if files exist
if [[ ! -f "$AIDB_DIR/discovery_api.py" ]]; then
    echo "❌ Error: discovery_api.py not found"
    echo "   Expected: $AIDB_DIR/discovery_api.py"
    exit 1
fi

if [[ ! -f "$AIDB_DIR/discovery_endpoints.py" ]]; then
    echo "❌ Error: discovery_endpoints.py not found"
    echo "   Expected: $AIDB_DIR/discovery_endpoints.py"
    exit 1
fi

echo "✓ Discovery API files found"

# Check if already integrated
if grep -q "register_discovery_routes" "$SERVER_FILE"; then
    echo "✓ Discovery routes already integrated"
    echo
    echo "To test:"
    echo "  curl http://localhost:8091/discovery/info"
    exit 0
fi

echo "→ Backing up server.py to: $BACKUP_FILE"
cp "$SERVER_FILE" "$BACKUP_FILE"

# Find the right place to add the import
# Look for existing imports from local modules
IMPORT_LINE=$(grep -n "^from settings_loader import" "$SERVER_FILE" | cut -d: -f1 | head -1)

if [[ -z "$IMPORT_LINE" ]]; then
    echo "❌ Error: Could not find import section in server.py"
    echo "   Please manually add: from discovery_endpoints import register_discovery_routes"
    exit 1
fi

echo "→ Adding discovery endpoints import at line $IMPORT_LINE"

# Add import after settings_loader import
sed -i "${IMPORT_LINE}a from discovery_endpoints import register_discovery_routes" "$SERVER_FILE"

# Find where to register routes (after federated-servers endpoint)
REGISTER_LINE=$(grep -n "def get_federated_servers" "$SERVER_FILE" | cut -d: -f1)

if [[ -z "$REGISTER_LINE" ]]; then
    echo "⚠️  Warning: Could not find federated-servers endpoint"
    echo "   Trying alternative location..."

    # Try finding after skill routes
    REGISTER_LINE=$(grep -n "@self.app.get(\"/skills\")" "$SERVER_FILE" | tail -1 | cut -d: -f1)
fi

if [[ -z "$REGISTER_LINE" ]]; then
    echo "❌ Error: Could not find suitable location for route registration"
    echo "   Please manually add after route definitions:"
    echo "   register_discovery_routes(self.app, self.mcp_server)"
    exit 1
fi

# Find the end of the get_federated_servers function (next @self.app line)
NEXT_ROUTE=$(awk "NR > $REGISTER_LINE && /@self\.app\.(get|post|put|delete)/ {print NR; exit}" "$SERVER_FILE")

if [[ -z "$NEXT_ROUTE" ]]; then
    echo "❌ Error: Could not find end of function"
    exit 1
fi

echo "→ Registering discovery routes at line $NEXT_ROUTE"

# Add route registration before next endpoint
REGISTRATION_CODE='
        # Progressive Disclosure Discovery API
        register_discovery_routes(self.app, self.mcp_server)
        LOGGER.info("Discovery API routes registered")
'

# Insert before next route
sed -i "${NEXT_ROUTE}i\\${REGISTRATION_CODE}" "$SERVER_FILE"

echo
echo "✅ Integration complete!"
echo
echo "Next steps:"
echo "  1. Rebuild AIDB container:"
echo "     cd $PROJECT_ROOT/ai-stack/compose"
echo "     podman-compose build aidb"
echo
echo "  2. Restart AIDB service:"
echo "     podman-compose up -d aidb"
echo
echo "  3. Test discovery endpoints:"
echo "     curl http://localhost:8091/discovery/info"
echo "     curl http://localhost:8091/discovery/quickstart"
echo "     curl http://localhost:8091/discovery/capabilities?level=standard"
echo
echo "  4. Verify in logs:"
echo "     podman logs local-ai-aidb | grep 'Discovery API'"
echo
echo "Backup saved to: $BACKUP_FILE"
