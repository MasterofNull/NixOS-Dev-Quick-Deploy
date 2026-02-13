#!/usr/bin/env bash
# Enhancement script to add service controls to port 8888 dashboard
# This script adds the features from port 8890 (React) to port 8888 (HTML)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_HTML="$PROJECT_ROOT/dashboard.html"
BACKUP_HTML="$PROJECT_ROOT/dashboard.html.backup-$(date +%Y%m%d-%H%M%S)"
TMP_ROOT="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
SECTION_SNIPPET="$(mktemp -p "$TMP_ROOT" dashboard-section-XXXX.html)"
DASHBOARD_NEW="$(mktemp -p "$TMP_ROOT" dashboard-new-XXXX.html)"
CSS_SNIPPET="$(mktemp -p "$TMP_ROOT" dashboard-css-XXXX.html)"
DASHBOARD_CSS="$(mktemp -p "$TMP_ROOT" dashboard-css-new-XXXX.html)"

cleanup() {
    rm -f "$SECTION_SNIPPET" "$DASHBOARD_NEW" "$CSS_SNIPPET" "$DASHBOARD_CSS"
}
trap cleanup EXIT

echo "🔧 Enhancing Port 8888 Dashboard with Service Controls"
echo ""

# Backup original
cp "$DASHBOARD_HTML" "$BACKUP_HTML"
echo "✅ Backed up original to: $BACKUP_HTML"

# Create the enhanced dashboard HTML with service controls
# We'll insert a new section after the container list

cat > "$SECTION_SNIPPET" << 'EOF'

            <!-- AI Stack Services Control -->
            <div class="dashboard-section full-width">
                <div class="card">
                    <div class="card-header">
                        <div class="collapsible-header" onclick="toggleCollapse(this)">
                            <span class="collapsible-arrow">▼</span>
                            <h2 class="card-title">AI Stack Services</h2>
                        </div>
                        <span class="card-badge" id="servicesBadge">-- Services</span>
                    </div>
                    <div class="collapsible-content">
                        <div id="servicesList" style="display: flex; flex-direction: column; gap: 1rem;">
                            <div class="loading"><div class="spinner"></div></div>
                        </div>
                    </div>
                </div>
            </div>
EOF

# Find the line number where we want to insert (after container section)
INSERT_LINE=$(grep -n "<!-- Persistence & Data -->" "$DASHBOARD_HTML" | head -1 | cut -d: -f1)

if [ -z "$INSERT_LINE" ]; then
    echo "❌ Could not find insertion point in dashboard.html"
    exit 1
fi

echo "📍 Inserting service control section at line $INSERT_LINE"

# Insert the new section
head -n $((INSERT_LINE - 1)) "$DASHBOARD_HTML" > "$DASHBOARD_NEW"
cat "$SECTION_SNIPPET" >> "$DASHBOARD_NEW"
tail -n +$INSERT_LINE "$DASHBOARD_HTML" >> "$DASHBOARD_NEW"

cp "$DASHBOARD_NEW" "$DASHBOARD_HTML"
echo "✅ Added service control section"

# Now add the CSS for service control buttons
cat > "$CSS_SNIPPET" << 'EOF'

        /* Service Control Styles */
        .service-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem;
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            background: var(--bg-tertiary);
            transition: all 0.3s ease;
        }

        .service-item:hover {
            border-color: var(--border-glow);
            box-shadow: 0 0 10px rgba(0, 217, 255, 0.1);
        }

        .service-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .service-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .service-status-dot.running {
            background: var(--status-online);
            box-shadow: 0 0 10px var(--status-online);
        }

        .service-status-dot.stopped {
            background: var(--text-muted);
        }

        .service-details {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .service-name {
            font-weight: 600;
            color: var(--text-primary);
        }

        .service-type {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .service-controls {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .service-status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .service-status-badge.running {
            background: rgba(0, 255, 136, 0.1);
            color: var(--status-online);
            border: 1px solid var(--status-online);
        }

        .service-status-badge.stopped {
            background: rgba(74, 85, 104, 0.1);
            color: var(--text-muted);
            border: 1px solid var(--text-muted);
        }

        .service-btn {
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.875rem;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.2s ease;
        }

        .service-btn:hover:not(:disabled) {
            background: var(--bg-tertiary);
            border-color: var(--border-glow);
            transform: translateY(-1px);
        }

        .service-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .service-btn.start {
            border-color: var(--status-online);
        }

        .service-btn.stop {
            border-color: var(--status-error);
        }

        .service-btn.restart {
            border-color: var(--accent-yellow);
        }
EOF

# Find where to insert CSS (before </style>)
CSS_END_LINE=$(grep -n "</style>" "$DASHBOARD_HTML" | head -1 | cut -d: -f1)

if [ -z "$CSS_END_LINE" ]; then
    echo "❌ Could not find CSS insertion point"
    exit 1
fi

echo "📍 Adding service control CSS at line $CSS_END_LINE"

head -n $((CSS_END_LINE - 1)) "$DASHBOARD_HTML" > "$DASHBOARD_CSS"
cat "$CSS_SNIPPET" >> "$DASHBOARD_CSS"
tail -n +$CSS_END_LINE "$DASHBOARD_HTML" >> "$DASHBOARD_CSS"

cp "$DASHBOARD_CSS" "$DASHBOARD_HTML"
echo "✅ Added service control CSS"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Dashboard enhanced successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "1. Add JavaScript functions for service control (see enhancement-js.txt)"
echo "2. Start FastAPI backend on port 8889"
echo "3. Test service control buttons"
echo ""
