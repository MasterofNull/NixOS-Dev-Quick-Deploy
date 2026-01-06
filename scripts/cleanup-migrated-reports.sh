#!/usr/bin/env bash
# Clean Up Migrated Report Files
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Remove report markdown files that have been migrated to database

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "${SCRIPT_DIR}/lib/report-to-database.sh"

echo "=== Clean Up Migrated Reports ==="
echo ""
echo "⚠️  WARNING: This will delete markdown files from the repo root!"
echo "   Only files that have been migrated to the database will be deleted."
echo "   System documentation (README.md, docs/, etc.) will NOT be deleted."
echo ""

read -p "Continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "✓ Cancelled"
    exit 0
fi

# Check database availability
if ! check_database_available; then
    echo "✗ Database not available! Cannot verify migrations."
    exit 1
fi

echo ""
echo "🔍 Finding migrated files..."
echo ""

deleted_count=0
kept_count=0

# Query database for migrated files
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A <<SQL | while IFS='|' read -r title original_file; do
SELECT
    title,
    metadata->>'original_file' as original_file
FROM deployment_reports
WHERE metadata->>'migrated' = 'true'
AND metadata->>'original_file' IS NOT NULL;
SQL

    if [ -f "$original_file" ]; then
        echo "  🗑️  Deleting: $original_file"
        rm "$original_file"
        ((deleted_count++))
    fi
done

echo ""
echo "=== Cleanup Summary ==="
echo "  🗑️  Deleted: $deleted_count files"
echo ""

# Move remaining report-like files to .reports/ for review
echo "📁 Moving remaining report files to .reports/ for manual review..."

mkdir -p "$PROJECT_ROOT/.reports/manual-review"

moved_count=0

find "$PROJECT_ROOT" -maxdepth 1 -name "*.md" -type f | while read -r file; do
    relative_file="${file#$PROJECT_ROOT/}"

    # Skip system docs
    if [[ "$relative_file" == "README.md" ]] ||
       [[ "$relative_file" == "CONTRIBUTING.md" ]] ||
       [[ "$relative_file" == "LICENSE.md" ]]; then
        continue
    fi

    # Move to manual review
    echo "  📦 Moving for review: $relative_file"
    mv "$file" "$PROJECT_ROOT/.reports/manual-review/"
    ((moved_count++))
done

if [ $moved_count -gt 0 ]; then
    echo ""
    echo "  📋 $moved_count files moved to .reports/manual-review/"
    echo "     Review these files and either:"
    echo "     - Migrate manually using: migrate_markdown_to_database FILE TYPE"
    echo "     - Keep if they're system documentation"
    echo "     - Delete if no longer needed"
fi

echo ""
echo "✅ Cleanup complete!"
