#!/usr/bin/env bash
# Populate Qdrant Collections with Initial Context
# This script seeds the Qdrant vector database with project context

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COORDINATOR_URL="${COORDINATOR_URL:-http://localhost:8092}"

echo "🔄 Populating Qdrant collections..."

# Check if services are available
if ! curl -sf "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
    echo "❌ Qdrant not available at ${QDRANT_URL}"
    exit 1
fi

if ! curl -sf "${COORDINATOR_URL}/health" >/dev/null 2>&1; then
    echo "❌ Hybrid Coordinator not available at ${COORDINATOR_URL}"
    exit 1
fi

echo "✅ Services available"

# 1. Index codebase context
echo ""
echo "📚 Indexing codebase..."
find "${PROJECT_ROOT}" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" \) \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/venv/*" \
    -not -path "*/__pycache__/*" | \
while read -r file; do
    rel_path="${file#$PROJECT_ROOT/}"
    echo "  Indexing: $rel_path"

    # Read file content and create embedding
    content=$(cat "$file" | head -c 50000)  # Limit to 50KB

    # Send to AIDB for indexing
    curl -s -X POST "http://localhost:8091/documents" \
        -H "Content-Type: application/json" \
        -d "{
            \"content\": $(echo "$content" | jq -Rs .),
            \"metadata\": {
                \"file_path\": \"$rel_path\",
                \"file_type\": \"${file##*.}\",
                \"project\": \"NixOS-Dev-Quick-Deploy\",
                \"indexed_at\": \"$(date -Iseconds)\"
            },
            \"category\": \"codebase\",
            \"project\": \"NixOS-Dev-Quick-Deploy\"
        }" >/dev/null 2>&1 || echo "    ⚠️  Failed"
done

echo "✅ Codebase indexed"

# 2. Import skills
echo ""
echo "🎯 Importing skills..."
SKILLS_DIR="${HOME}/.agent/skills"
if [[ -d "$SKILLS_DIR" ]]; then
    find "$SKILLS_DIR" -name "*.md" | while read -r skill_file; do
        skill_name=$(basename "$skill_file" .md)
        echo "  Importing: $skill_name"

        content=$(cat "$skill_file")

        curl -s -X POST "http://localhost:8091/documents" \
            -H "Content-Type: application/json" \
            -d "{
                \"content\": $(echo "$content" | jq -Rs .),
                \"metadata\": {
                    \"skill_name\": \"$skill_name\",
                    \"skill_path\": \"$skill_file\",
                    \"project\": \"NixOS-Dev-Quick-Deploy\"
                },
                \"category\": \"skill\",
                \"project\": \"NixOS-Dev-Quick-Deploy\"
            }" >/dev/null 2>&1 || echo "    ⚠️  Failed"
    done
    echo "✅ Skills imported"
else
    echo "⚠️  Skills directory not found: $SKILLS_DIR"
fi

# 3. Import agent documentation
echo ""
echo "📖 Importing agent documentation..."
for doc in AGENTS.md AI-AGENT-START-HERE.md AI-AGENT-REFERENCE.md; do
    if [[ -f "${PROJECT_ROOT}/$doc" ]]; then
        echo "  Importing: $doc"
        content=$(cat "${PROJECT_ROOT}/$doc")

        curl -s -X POST "http://localhost:8091/documents" \
            -H "Content-Type: application/json" \
            -d "{
                \"content\": $(echo "$content" | jq -Rs .),
                \"metadata\": {
                    \"document\": \"$doc\",
                    \"type\": \"agent-documentation\",
                    \"project\": \"NixOS-Dev-Quick-Deploy\"
                },
                \"category\": \"documentation\",
                \"project\": \"NixOS-Dev-Quick-Deploy\"
            }" >/dev/null 2>&1 || echo "    ⚠️  Failed"
    fi
done
echo "✅ Documentation imported"

# 4. Seed best practices
echo ""
echo "💡 Seeding best practices..."
cat > /tmp/best-practices.json << 'PRACTICES'
[
    {
        "pattern": "error-resolution",
        "title": "Container DNS Resolution Failures",
        "solution": "Use network_mode: host for containers that need localhost access",
        "context": "When MCP servers need to access databases on localhost, bridge networking causes DNS issues"
    },
    {
        "pattern": "systemd-timer",
        "title": "SystemD Timer Not Triggering",
        "solution": "Use OnCalendar instead of OnUnitActiveSec for reliable scheduling",
        "context": "OnUnitActiveSec only schedules after successful service activation"
    },
    {
        "pattern": "dashboard-data",
        "title": "Stale Dashboard Data",
        "solution": "Ensure collector service has proper PATH environment and runs regularly",
        "context": "SystemD services need explicit PATH for commands like mkdir, curl"
    }
]
PRACTICES

cat /tmp/best-practices.json | jq -c '.[]' | while read -r practice; do
    echo "  Adding: $(echo "$practice" | jq -r '.title')"

    curl -s -X POST "http://localhost:8091/documents" \
        -H "Content-Type: application/json" \
        -d "{
            \"content\": $(echo "$practice" | jq -c '.solution' | jq -Rs .),
            \"metadata\": $(echo "$practice" | jq -c '{pattern, title, context}'),
            \"category\": \"best-practice\",
            \"project\": \"NixOS-Dev-Quick-Deploy\"
        }" >/dev/null 2>&1 || echo "    ⚠️  Failed"
done

rm /tmp/best-practices.json
echo "✅ Best practices seeded"

# 5. Verify collections
echo ""
echo "🔍 Verifying Qdrant collections..."
curl -s "${COORDINATOR_URL}/health" | python3 -c "
import sys, json
data = json.load(sys.stdin)
collections = data.get('collections', [])
print(f'Collections available: {len(collections)}')
for coll in collections:
    print(f'  - {coll}')
"

echo ""
echo "✅ Qdrant population complete!"
echo ""
echo "Next steps:"
echo "  1. Query context: curl 'http://localhost:8091/documents?search=docker&limit=5'"
echo "  2. Test retrieval: curl 'http://localhost:8092/tools/augment_query' -d '{\"query\":\"fix docker\"}'"
echo "  3. Check dashboard: http://localhost:8888/dashboard.html"
