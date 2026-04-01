#!/usr/bin/env bash
# lib/adk/implementation-discovery.sh
#
# Purpose: Monitor Google ADK releases and automatically feed new features into roadmap/backlog updates
#
# Status: production
# Owner: ai-harness
# Last Updated: 2026-03-20
#
# Features:
# - Monitor Google ADK releases and changelogs
# - Automated feature extraction from ADK documentation
# - Capability comparison against current harness
# - Gap identification and prioritization
# - Automatic roadmap update generation
# - Integration with existing workflow system
# - Scheduled execution support (weekly/monthly)
# - Dashboard notification for new discoveries

set -euo pipefail

# Declarative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LIB_ADK_DIR="${REPO_ROOT}/lib/adk"
DATA_DIR="${REPO_ROOT}/.agent/adk"
DISCOVERIES_DIR="${DATA_DIR}/discoveries"
CHANGELOG_DIR="${DATA_DIR}/changelogs"
REPORTS_DIR="${DATA_DIR}/reports"

# Ensure directories exist
mkdir -p "${DATA_DIR}" "${DISCOVERIES_DIR}" "${CHANGELOG_DIR}" "${REPORTS_DIR}"

# Google ADK sources
ADK_GITHUB_REPO="google/adk"
ADK_DOCS_BASE="https://ai.google.dev/adk"
ADK_RELEASES_API="https://api.github.com/repos/google/adk/releases"
ADK_CHANGELOG_URL="https://github.com/google/adk/blob/main/CHANGELOG.md"

# Configuration
FETCH_TIMEOUT=30
MAX_RELEASES_TO_CHECK=10
CACHE_DURATION_HOURS=12
VERBOSE="${VERBOSE:-0}"

# Logging utilities
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

log_verbose() {
    if [[ "${VERBOSE}" -eq 1 ]]; then
        log "$@"
    fi
}

log_error() {
    log "ERROR: $*"
}

# JSON utilities
jq_installed() {
    command -v jq &>/dev/null
}

python3_installed() {
    command -v python3 &>/dev/null
}

# Check dependencies
check_dependencies() {
    local missing=()

    if ! command -v curl &>/dev/null; then
        missing+=("curl")
    fi

    if ! jq_installed; then
        missing+=("jq")
    fi

    if ! python3_installed; then
        missing+=("python3")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_error "Install with: nix-shell -p ${missing[*]}"
        return 1
    fi

    return 0
}

# Fetch ADK releases from GitHub API
fetch_adk_releases() {
    local output_file="${1:-${CHANGELOG_DIR}/releases.json}"
    local cache_age_hours="${2:-${CACHE_DURATION_HOURS}}"

    log_verbose "Fetching ADK releases from GitHub API"

    # Check cache freshness
    if [[ -f "${output_file}" ]]; then
        local cache_age_seconds=$((cache_age_hours * 3600))
        local file_age=$(( $(date +%s) - $(stat -c %Y "${output_file}") ))

        if [[ ${file_age} -lt ${cache_age_seconds} ]]; then
            log_verbose "Using cached releases (age: ${file_age}s < ${cache_age_seconds}s)"
            return 0
        fi
    fi

    # Fetch releases
    local temp_file
    temp_file=$(mktemp)

    if ! curl -sS -f \
        --max-time "${FETCH_TIMEOUT}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${ADK_RELEASES_API}?per_page=${MAX_RELEASES_TO_CHECK}" \
        -o "${temp_file}"; then
        log_error "Failed to fetch ADK releases"
        rm -f "${temp_file}"
        return 1
    fi

    # Validate JSON
    if ! jq -e '.' "${temp_file}" &>/dev/null; then
        log_error "Invalid JSON response from GitHub API"
        rm -f "${temp_file}"
        return 1
    fi

    mv "${temp_file}" "${output_file}"
    log "Fetched $(jq 'length' "${output_file}") ADK releases"

    return 0
}

# Extract features from release notes
extract_features_from_releases() {
    local releases_file="${1:-${CHANGELOG_DIR}/releases.json}"
    local output_file="${2:-${DISCOVERIES_DIR}/features-$(date +%Y%m%d).json}"

    log_verbose "Extracting features from releases"

    if [[ ! -f "${releases_file}" ]]; then
        log_error "Releases file not found: ${releases_file}"
        return 1
    fi

    # Extract features using Python for better text processing
    python3 - "${releases_file}" "${output_file}" <<'EOF'
import sys
import json
import re
from datetime import datetime

releases_file = sys.argv[1]
output_file = sys.argv[2]

with open(releases_file, 'r') as f:
    releases = json.load(f)

features = []
feature_patterns = [
    r'(?i)(?:add|new|introduce)(?:ed|s)?\s+([^.\n]+)',
    r'(?i)feature:\s*([^.\n]+)',
    r'(?i)support\s+for\s+([^.\n]+)',
    r'(?i)enable[sd]?\s+([^.\n]+)',
]

for release in releases:
    release_name = release.get('name', '')
    tag_name = release.get('tag_name', '')
    body = release.get('body', '')
    published_at = release.get('published_at', '')

    if not body:
        continue

    release_features = []

    for pattern in feature_patterns:
        matches = re.findall(pattern, body, re.MULTILINE)
        for match in matches:
            feature = match.strip()
            if len(feature) > 10 and len(feature) < 200:
                release_features.append({
                    'description': feature,
                    'pattern': pattern.split('(')[0].replace('(?i)', ''),
                    'confidence': 'medium'
                })

    if release_features:
        features.append({
            'release': {
                'name': release_name,
                'tag': tag_name,
                'published_at': published_at,
                'url': release.get('html_url', '')
            },
            'features': release_features,
            'discovered_at': datetime.now().isoformat()
        })

output = {
    'discovered_at': datetime.now().isoformat(),
    'source': 'github_releases',
    'releases_analyzed': len(releases),
    'features_found': sum(len(r['features']) for r in features),
    'discoveries': features
}

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"Extracted {output['features_found']} features from {output['releases_analyzed']} releases")
EOF

    return $?
}

# Compare extracted features against current harness capabilities
compare_with_harness() {
    local features_file="${1:-${DISCOVERIES_DIR}/features-$(date +%Y%m%d).json}"
    local output_file="${2:-${REPORTS_DIR}/capability-gaps-$(date +%Y%m%d).json}"

    log_verbose "Comparing ADK features with harness capabilities"

    if [[ ! -f "${features_file}" ]]; then
        log_error "Features file not found: ${features_file}"
        return 1
    fi

    # Load parity tracker for current capabilities
    local parity_file="${DATA_DIR}/parity-scorecard.json"

    if [[ ! -f "${parity_file}" ]]; then
        log_verbose "Parity scorecard not found, creating baseline"
        if ! "${LIB_ADK_DIR}/parity-tracker.py" --output "${parity_file}"; then
            log_error "Failed to create parity baseline"
            return 1
        fi
    fi

    # Gap analysis using Python
    python3 - "${features_file}" "${parity_file}" "${output_file}" <<'EOF'
import sys
import json
from datetime import datetime

features_file = sys.argv[1]
parity_file = sys.argv[2]
output_file = sys.argv[3]

with open(features_file, 'r') as f:
    features_data = json.load(f)

try:
    with open(parity_file, 'r') as f:
        parity_data = json.load(f)
except FileNotFoundError:
    parity_data = {'capabilities': {}}

# Extract current capabilities
current_capabilities = set()
if 'categories' in parity_data:
    for category in parity_data['categories'].values():
        if 'capabilities' in category:
            current_capabilities.update(cap['name'].lower() for cap in category['capabilities'])

# Identify gaps
gaps = []
for discovery in features_data.get('discoveries', []):
    release = discovery['release']
    for feature in discovery['features']:
        feature_desc = feature['description'].lower()

        # Simple keyword matching (can be enhanced with NLP)
        is_gap = True
        for capability in current_capabilities:
            if capability in feature_desc or feature_desc in capability:
                is_gap = False
                break

        if is_gap:
            gaps.append({
                'feature': feature['description'],
                'release': release['tag'],
                'published_at': release['published_at'],
                'url': release['url'],
                'priority': 'medium',  # Default priority
                'status': 'new'
            })

# Prioritize gaps
for gap in gaps:
    desc_lower = gap['feature'].lower()
    if any(kw in desc_lower for kw in ['agent', 'protocol', 'a2a', 'tool']):
        gap['priority'] = 'high'
    elif any(kw in desc_lower for kw in ['performance', 'optimization', 'memory']):
        gap['priority'] = 'medium'
    else:
        gap['priority'] = 'low'

output = {
    'generated_at': datetime.now().isoformat(),
    'total_gaps': len(gaps),
    'high_priority': sum(1 for g in gaps if g['priority'] == 'high'),
    'medium_priority': sum(1 for g in gaps if g['priority'] == 'medium'),
    'low_priority': sum(1 for g in gaps if g['priority'] == 'low'),
    'gaps': sorted(gaps, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['priority']])
}

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"Identified {output['total_gaps']} capability gaps ({output['high_priority']} high, {output['medium_priority']} medium, {output['low_priority']} low)")
EOF

    return $?
}

# Generate roadmap update recommendations
generate_roadmap_updates() {
    local gaps_file="${1:-${REPORTS_DIR}/capability-gaps-$(date +%Y%m%d).json}"
    local output_file="${2:-${REPORTS_DIR}/roadmap-updates-$(date +%Y%m%d).md}"

    log_verbose "Generating roadmap update recommendations"

    if [[ ! -f "${gaps_file}" ]]; then
        log_error "Gaps file not found: ${gaps_file}"
        return 1
    fi

    # Generate markdown roadmap updates
    python3 - "${gaps_file}" "${output_file}" <<'EOF'
import sys
import json
from datetime import datetime

gaps_file = sys.argv[1]
output_file = sys.argv[2]

with open(gaps_file, 'r') as f:
    gaps_data = json.load(f)

gaps = gaps_data.get('gaps', [])
high_priority_gaps = [g for g in gaps if g['priority'] == 'high']
medium_priority_gaps = [g for g in gaps if g['priority'] == 'medium']

md_content = f"""# ADK Roadmap Updates

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source: Automated ADK Discovery

## Summary

- Total Gaps Identified: {gaps_data['total_gaps']}
- High Priority: {gaps_data['high_priority']}
- Medium Priority: {gaps_data['medium_priority']}
- Low Priority: {gaps_data['low_priority']}

## High Priority Gaps

"""

if high_priority_gaps:
    for i, gap in enumerate(high_priority_gaps, 1):
        md_content += f"""### {i}. {gap['feature']}

- **Source**: {gap['release']} ({gap['published_at'][:10]})
- **Status**: {gap['status']}
- **URL**: {gap['url']}

**Recommended Action**: Evaluate for immediate integration

"""
else:
    md_content += "No high priority gaps identified.\n\n"

md_content += """## Medium Priority Gaps

"""

if medium_priority_gaps:
    for i, gap in enumerate(medium_priority_gaps[:5], 1):  # Top 5
        md_content += f"""### {i}. {gap['feature']}

- **Source**: {gap['release']}
- **Status**: {gap['status']}

"""
else:
    md_content += "No medium priority gaps identified.\n\n"

md_content += """## Next Steps

1. Review high priority gaps with team
2. Create backlog items for integration
3. Update Phase 4.4 roadmap with new tasks
4. Schedule implementation for next sprint

## Integration Process

For each gap:
1. Validate against harness requirements
2. Check declarative wiring compatibility
3. Assess implementation effort
4. Prioritize in backlog
5. Assign to appropriate phase
"""

with open(output_file, 'w') as f:
    f.write(md_content)

print(f"Generated roadmap updates: {output_file}")
EOF

    return $?
}

# Generate reviewer-gate checklist tying ADK discovery back into active phases.
generate_reviewer_gate_checklist() {
    local gaps_file="${1:-${REPORTS_DIR}/capability-gaps-$(date +%Y%m%d).json}"
    local parity_file="${2:-${DATA_DIR}/parity-scorecard.json}"
    local output_file="${3:-${REPORTS_DIR}/reviewer-gate-checklist-$(date +%Y%m%d).md}"

    log_verbose "Generating ADK reviewer-gate checklist"

    if [[ ! -f "${gaps_file}" ]]; then
        log_error "Gaps file not found: ${gaps_file}"
        return 1
    fi

    if [[ ! -f "${parity_file}" ]]; then
        log_error "Parity scorecard not found: ${parity_file}"
        return 1
    fi

    python3 - "${gaps_file}" "${parity_file}" "${output_file}" <<'EOF'
import json
import sys
from datetime import datetime

gaps_file = sys.argv[1]
parity_file = sys.argv[2]
output_file = sys.argv[3]

with open(gaps_file, "r", encoding="utf-8") as fh:
    gaps_data = json.load(fh)
with open(parity_file, "r", encoding="utf-8") as fh:
    parity_data = json.load(fh)

categories = parity_data.get("categories", {}) if isinstance(parity_data, dict) else {}
deferred = []
adapted = []
for category_name, category in categories.items():
    if not isinstance(category, dict):
        continue
    for capability in category.get("capabilities", []) or []:
        if not isinstance(capability, dict):
            continue
        item = {
            "category": category_name,
            "name": str(capability.get("name", "")).strip(),
            "status": str(capability.get("status", "")).strip().lower(),
            "notes": str(capability.get("notes", "")).strip(),
        }
        if item["status"] == "deferred":
            deferred.append(item)
        elif item["status"] == "adapted":
            adapted.append(item)

overall = parity_data.get("overall_parity")
try:
    overall_text = f"{float(overall) * 100:.1f}%"
except (TypeError, ValueError):
    overall_text = "unknown"

phase_map = {
    "Phase 4": "multi-agent composition, A2A/MCP parity, workflow/session compatibility, reviewer-gate acceptance",
    "Phase 6": "routing, remote offload quality, retrieval/state parity for delegated and remote-assisted work",
    "Phase 11": "local agent tool-use, workflow participation, resilience, and local-runtime validation",
}
commands = [
    "scripts/governance/tier0-validation-gate.sh --pre-commit",
    "python3 scripts/testing/test-a2a-compat.py",
    "bash scripts/testing/smoke-agent-harness-parity.sh",
    "bash scripts/testing/smoke-focused-parity.sh",
    "bash scripts/testing/check-mcp-health.sh",
    "scripts/ai/aq-qa 0 --json",
]

lines = [
    "# ADK Reviewer-Gate Checklist",
    "",
    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"Overall parity baseline: {overall_text}",
    f"Discovery gaps in scope: {int(gaps_data.get('total_gaps', 0) or 0)}",
    "",
    "## Acceptance Gate",
    "",
    "Use this checklist whenever Phase 4.4, Phase 6, or Phase 11 work claims ADK-aligned progress.",
    "Do not accept roadmap progress on narrative evidence alone; require the commands below or a tighter equivalent.",
    "",
    "## Required Commands",
    "",
]
for command in commands:
    lines.append(f"- `{command}`")

lines.extend([
    "",
    "## Phase Mapping",
    "",
])
for phase_name, phase_note in phase_map.items():
    lines.append(f"- **{phase_name}**: {phase_note}")

lines.extend([
    "",
    "## Highest-Value Deferred Capabilities",
    "",
])
if deferred:
    for item in deferred[:5]:
        lines.append(
            f"- `{item['name']}` ({item['category']}): {item['notes'] or 'still deferred in the current parity scorecard'}"
        )
else:
    lines.append("- No deferred capabilities are currently recorded.")

lines.extend([
    "",
    "## Adapted Capabilities To Re-verify",
    "",
])
if adapted:
    for item in adapted[:5]:
        lines.append(
            f"- `{item['name']}` ({item['category']}): {item['notes'] or 'adapted rather than adopted; verify harness-specific behavior remains intentional'}"
        )
else:
    lines.append("- No adapted capabilities are currently recorded.")

lines.extend([
    "",
    "## Discovery Follow-up",
    "",
    "Attach any new ADK release gap to one of these phases before roadmap acceptance:",
    "- **Phase 4** when the change affects orchestration, sessions, reviewer gates, or A2A/MCP interoperability",
    "- **Phase 6** when the change affects routing, remote execution quality, or retrieval/state parity for offloaded work",
    "- **Phase 11** when the change affects local-agent autonomy, tool use, or local execution safety/resilience",
    "",
    "## Current Release Gaps",
    "",
])
gaps = gaps_data.get("gaps", []) or []
if gaps:
    for gap in gaps[:5]:
        if not isinstance(gap, dict):
            continue
        lines.append(
            f"- `{gap.get('feature', 'unknown gap')}` [{gap.get('priority', 'unknown')}] from `{gap.get('release', 'unknown release')}`"
        )
else:
    lines.append("- No release gaps were identified in the current discovery run.")

with open(output_file, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print(f"Generated reviewer-gate checklist: {output_file}")
EOF

    return $?
}

# Send dashboard notification
send_dashboard_notification() {
    local gaps_file="${1:-${REPORTS_DIR}/capability-gaps-$(date +%Y%m%d).json}"

    log_verbose "Sending dashboard notification"

    if [[ ! -f "${gaps_file}" ]]; then
        log_verbose "No gaps file to notify about"
        return 0
    fi

    local total_gaps
    total_gaps=$(jq -r '.total_gaps' "${gaps_file}")

    local high_priority
    high_priority=$(jq -r '.high_priority' "${gaps_file}")

    if [[ "${total_gaps}" -eq 0 ]]; then
        log "No new ADK capability gaps found"
        return 0
    fi

    log "Found ${total_gaps} capability gaps (${high_priority} high priority)"

    # Create notification file for dashboard polling
    local notification_file="${DATA_DIR}/latest-discovery-notification.json"
    jq -n \
        --arg timestamp "$(date -Iseconds)" \
        --arg total "${total_gaps}" \
        --arg high "${high_priority}" \
        --arg file "${gaps_file}" \
        '{
            timestamp: $timestamp,
            type: "adk_discovery",
            total_gaps: ($total | tonumber),
            high_priority_gaps: ($high | tonumber),
            gaps_file: $file,
            status: "new"
        }' > "${notification_file}"

    return 0
}

# Main discovery workflow
run_discovery() {
    local force="${1:-0}"

    log "Starting ADK implementation discovery workflow"

    # Check dependencies
    if ! check_dependencies; then
        return 1
    fi

    # Step 1: Fetch releases
    if ! fetch_adk_releases "${CHANGELOG_DIR}/releases.json" "${CACHE_DURATION_HOURS}"; then
        log_error "Failed to fetch ADK releases"
        return 1
    fi

    # Step 2: Extract features
    local features_file="${DISCOVERIES_DIR}/features-$(date +%Y%m%d).json"
    if ! extract_features_from_releases "${CHANGELOG_DIR}/releases.json" "${features_file}"; then
        log_error "Failed to extract features"
        return 1
    fi

    # Step 3: Compare with harness capabilities
    local parity_file="${DATA_DIR}/parity-scorecard.json"
    local gaps_file="${REPORTS_DIR}/capability-gaps-$(date +%Y%m%d).json"
    if ! compare_with_harness "${features_file}" "${gaps_file}"; then
        log_error "Failed to compare capabilities"
        return 1
    fi

    # Step 4: Generate roadmap updates
    local roadmap_file="${REPORTS_DIR}/roadmap-updates-$(date +%Y%m%d).md"
    if ! generate_roadmap_updates "${gaps_file}" "${roadmap_file}"; then
        log_error "Failed to generate roadmap updates"
        return 1
    fi

    # Step 5: Generate reviewer-gate checklist
    local checklist_file="${REPORTS_DIR}/reviewer-gate-checklist-$(date +%Y%m%d).md"
    if ! generate_reviewer_gate_checklist "${gaps_file}" "${parity_file}" "${checklist_file}"; then
        log_error "Failed to generate reviewer-gate checklist"
        return 1
    fi

    # Step 6: Send dashboard notification
    send_dashboard_notification "${gaps_file}"

    log "ADK discovery workflow completed successfully"
    log "Reports available in: ${REPORTS_DIR}"

    return 0
}

# CLI interface
main() {
    local force=0
    local verbose=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                force=1
                shift
                ;;
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --help|-h)
                cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Monitor Google ADK releases and discover new features.

Options:
    --force         Force refresh of cached data
    --verbose, -v   Enable verbose logging
    --help, -h      Show this help message

Examples:
    $(basename "$0")                    # Run discovery (use cache if fresh)
    $(basename "$0") --force            # Force fresh data fetch
    $(basename "$0") --verbose          # Run with verbose output

Output:
    Discoveries: ${DISCOVERIES_DIR}
    Reports: ${REPORTS_DIR}
    Changelogs: ${CHANGELOG_DIR}
EOF
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                log "Use --help for usage information"
                return 1
                ;;
        esac
    done

    run_discovery "${force}"
}

# Execute if run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
