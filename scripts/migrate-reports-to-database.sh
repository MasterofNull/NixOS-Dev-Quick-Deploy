#!/usr/bin/env bash
# Migrate Existing Report Files to Database
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Clean up repo by moving report markdown files into PostgreSQL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "${SCRIPT_DIR}/lib/report-to-database.sh"

# Report type patterns
declare -A REPORT_PATTERNS=(
    ["deployment"]="*DEPLOYMENT*.md *DEPLOY*.md"
    ["fix"]="*FIX*.md *FIXES*.md *BUGFIX*.md *CONTAINER-*.md *ERROR*.md"
    ["upgrade"]="*UPGRADE*.md *UPDATE*.md *MIGRATION*.md"
    ["summary"]="*SUMMARY*.md *COMPLETE*.md *IMPLEMENTATION*.md"
    ["session"]="*SESSION*.md *WORK*.md *PROGRESS*.md"
)

# System documentation patterns (KEEP these in repo)
SYSTEM_DOCS_PATTERNS=(
    "README.md"
    "CONTRIBUTING.md"
    "LICENSE.md"
    "docs/*.md"
    "ai-stack/*/README.md"
    "templates/*.md"
)

echo "=== Migrate Reports to Database ==="
echo ""

# Check database availability
if ! check_database_available; then
    echo "✗ Database not available!"
    echo "  Start the AI stack first: ./scripts/hybrid-ai-stack.sh up"
    echo "  Then run this script again"
    exit 1
fi

echo "✓ Database connection OK"
echo ""

# Scan for report files
echo "🔍 Scanning for report files..."
echo ""

migrated_count=0
skipped_count=0
error_count=0

# Function to check if file is system documentation
is_system_doc() {
    local file="$1"

    for pattern in "${SYSTEM_DOCS_PATTERNS[@]}"; do
        if [[ "$file" == $pattern ]]; then
            return 0
        fi
    done

    # Check if in docs/development or docs/reference (system docs)
    if [[ "$file" =~ ^docs/(development|reference|architecture)/ ]]; then
        return 0
    fi

    return 1
}

# Migrate files by type
for report_type in "${!REPORT_PATTERNS[@]}"; do
    echo "📄 Looking for $report_type reports..."

    for pattern in ${REPORT_PATTERNS[$report_type]}; do
        while IFS= read -r -d '' file; do
            # Convert to relative path
            relative_file="${file#$PROJECT_ROOT/}"

            # Skip if system documentation
            if is_system_doc "$relative_file"; then
                echo "  ⊘ Skipping system doc: $relative_file"
                ((skipped_count++))
                continue
            fi

            # Skip if already in .reports directory
            if [[ "$relative_file" == .reports/* ]]; then
                echo "  ⊘ Already in .reports: $relative_file"
                ((skipped_count++))
                continue
            fi

            echo "  → Migrating: $relative_file"

            if migrate_markdown_to_database "$file" "$report_type"; then
                ((migrated_count++))
            else
                ((error_count++))
            fi

        done < <(find "$PROJECT_ROOT" -maxdepth 1 -name "$pattern" -type f -print0 2>/dev/null || true)
    done
done

echo ""
echo "=== Migration Summary ==="
echo "  ✓ Migrated:  $migrated_count files"
echo "  ⊘ Skipped:   $skipped_count files (system docs)"
echo "  ✗ Errors:    $error_count files"
echo ""

if [ $migrated_count -gt 0 ]; then
    echo "📋 Migrated files are now in the database"
    echo ""
    echo "To view reports:"
    echo "  psql -h localhost -U mcp -d mcp -c \"SELECT id, title, report_type, created_at FROM deployment_reports ORDER BY created_at DESC LIMIT 10;\""
    echo ""
    echo "To delete migrated files (AFTER verifying database):"
    echo "  Run: ./scripts/cleanup-migrated-reports.sh"
    echo ""
fi

# Show what's left
echo "📁 Remaining files in repo root:"
find "$PROJECT_ROOT" -maxdepth 1 -name "*.md" -type f | while read -r file; do
    relative_file="${file#$PROJECT_ROOT/}"
    if is_system_doc "$relative_file"; then
        echo "  📘 System doc: $relative_file"
    else
        echo "  📄 Report: $relative_file (may need manual review)"
    fi
done
