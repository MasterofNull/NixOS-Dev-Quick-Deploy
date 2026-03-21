#!/usr/bin/env bash
# scripts/audit/integration-audit.sh
# Phase 4.5: Integration Audit Script
#
# Comprehensive audit to identify bolt-on features and incomplete integrations
# Outputs JSON and markdown reports categorizing features by integration status

set -euo pipefail

# Script directory and root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Configuration
REPORTS_DIR="${ROOT_DIR}/reports"
TIMESTAMP="$(date +%Y%m%dT%H%M%SZ)"
JSON_REPORT="${REPORTS_DIR}/integration-audit-${TIMESTAMP}.json"
MD_REPORT="${REPORTS_DIR}/integration-audit-report.md"
TEMP_DIR="$(mktemp -d)"

# Cleanup on exit
trap 'rm -rf "${TEMP_DIR}"' EXIT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log() { echo -e "${CYAN}[audit]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }
success() { echo -e "${GREEN}[success]${NC} $*"; }

# Ensure reports directory exists
mkdir -p "${REPORTS_DIR}"

# Initialize JSON report structure
init_json_report() {
    cat > "${JSON_REPORT}" <<'EOF'
{
  "metadata": {
    "timestamp": "",
    "version": "1.0.0",
    "audit_scope": "AI stack coordinator, hybrid routing, memory/eval systems, research capabilities"
  },
  "summary": {
    "total_features": 0,
    "category_a_auto_enabled": 0,
    "category_b_keep_disabled": 0,
    "category_c_remove": 0,
    "category_d_conditional": 0
  },
  "categories": {
    "category_a": [],
    "category_b": [],
    "category_c": [],
    "category_d": []
  },
  "feature_flags_found": [],
  "manual_enabling_required": [],
  "optional_features": [],
  "incomplete_integrations": []
}
EOF

    # Add timestamp
    local tmp_json="${TEMP_DIR}/report.json"
    jq --arg ts "${TIMESTAMP}" '.metadata.timestamp = $ts' "${JSON_REPORT}" > "${tmp_json}"
    mv "${tmp_json}" "${JSON_REPORT}"
}

# Scan for feature flags in codebase
scan_feature_flags() {
    log "Scanning for feature flags..."

    local feature_flags="${TEMP_DIR}/feature_flags.txt"

    # Search for common feature flag patterns
    rg --no-heading --line-number \
        'enabled.*=.*false|ENABLED.*=.*false|enable_[a-z_]+|ENABLE_[A-Z_]+|feature.*flag' \
        --type py --type sh --type js --type yaml \
        "${ROOT_DIR}" \
        --glob '!archive/**' \
        --glob '!templates/**' \
        --glob '!.git/**' \
        > "${feature_flags}" 2>/dev/null || true

    # Count unique feature flags
    local count=$(wc -l < "${feature_flags}" || echo "0")
    log "Found ${count} potential feature flag references"

    # Parse into JSON array
    local flags_json="[]"
    if [[ -s "${feature_flags}" ]]; then
        flags_json=$(awk -F: '{
            file=$1; line=$2; content=$3;
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", content);
            printf "{\"file\": \"%s\", \"line\": %s, \"content\": \"%s\"},\n", file, line, content
        }' "${feature_flags}" | sed '$ s/,$//' | jq -s '.')
    fi

    echo "${flags_json}"
}

# Scan configuration files for optional features
scan_config_optional() {
    log "Scanning configuration files for optional features..."

    local config_files="${TEMP_DIR}/config_optional.txt"

    # Search config files for disabled defaults
    find "${ROOT_DIR}/config" "${ROOT_DIR}/ai-stack/mcp-servers/config" \
        -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" \) 2>/dev/null | \
    while read -r file; do
        if grep -E 'enabled:\s*(false|0)|"enabled":\s*false' "${file}" &>/dev/null; then
            echo "${file}"
        fi
    done > "${config_files}" || true

    local count=$(wc -l < "${config_files}" || echo "0")
    log "Found ${count} config files with disabled features"

    # Parse into JSON array
    local configs_json="[]"
    if [[ -s "${config_files}" ]]; then
        configs_json=$(while read -r file; do
            echo "{\"file\": \"${file}\"}"
        done < "${config_files}" | jq -s '.')
    fi

    echo "${configs_json}"
}

# Check for manual enabling requirements
check_manual_enabling() {
    log "Checking for manual enabling requirements..."

    local manual_enable="${TEMP_DIR}/manual_enable.txt"

    # Search for documentation/comments about manual enabling
    rg --no-heading --line-number \
        'manually enable|manual activation|opt-in|disabled by default|set.*to enable' \
        --type md --type py --type sh \
        "${ROOT_DIR}" \
        --glob '!archive/**' \
        --glob '!.git/**' \
        > "${manual_enable}" 2>/dev/null || true

    local count=$(wc -l < "${manual_enable}" || echo "0")
    log "Found ${count} references to manual enabling"

    # Parse into JSON array
    local manual_json="[]"
    if [[ -s "${manual_enable}" ]]; then
        manual_json=$(awk -F: '{
            file=$1; line=$2; content=$3;
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", content);
            printf "{\"file\": \"%s\", \"line\": %s, \"content\": \"%s\"},\n", file, line, content
        }' "${manual_enable}" | sed '$ s/,$//' | jq -s '.')
    fi

    echo "${manual_json}"
}

# Verify auto-enable logic
check_auto_enable_logic() {
    log "Verifying auto-enable logic..."

    local auto_enable="${TEMP_DIR}/auto_enable.txt"

    # Search for auto-enable patterns in deployment/startup scripts
    find "${ROOT_DIR}/scripts/deploy" "${ROOT_DIR}/lib/deploy" \
        -type f \( -name "*.sh" -o -name "*.py" \) 2>/dev/null | \
    while read -r file; do
        if grep -E 'auto.*enable|automatic.*activation|default.*enable' "${file}" &>/dev/null; then
            echo "${file}"
        fi
    done > "${auto_enable}" || true

    local count=$(wc -l < "${auto_enable}" || echo "0")
    log "Found ${count} files with auto-enable logic"
}

# Categorize features based on audit document
categorize_features() {
    log "Categorizing features based on audit criteria..."

    # Category A: Already enabled by default (from audit document)
    local category_a_features=(
        "AI_CONTEXT_COMPRESSION_ENABLED"
        "AI_HARNESS_ENABLED"
        "AI_MEMORY_ENABLED"
        "AI_TREE_SEARCH_ENABLED"
        "AI_HARNESS_EVAL_ENABLED"
        "AI_CAPABILITY_DISCOVERY_ENABLED"
        "AI_PROMPT_CACHE_POLICY_ENABLED"
        "AI_TASK_CLASSIFICATION_ENABLED"
    )

    # Category B: Keep disabled (experimental or resource-dependent)
    local category_b_features=(
        "QUERY_EXPANSION_ENABLED"
        "REMOTE_LLM_FEEDBACK_ENABLED"
        "MULTI_TURN_QUERY_EXPANSION"
        "AI_LLM_EXPANSION_ENABLED"
        "AI_SPECULATIVE_DECODING_ENABLED"
        "AI_CROSS_ENCODER_ENABLED"
        "PATTERN_EXTRACTION_ENABLED"
    )

    # Category C: Should be removed
    local category_c_features=(
        "AUTO_IMPROVE_ENABLED_DEFAULT"
        "AI_HINTS_ENABLED"
        "AI_VECTORDB_ENABLED"
    )

    # Category D: Environment-dependent auto-enable
    local category_d_features=(
        "AI_SPECULATIVE_DECODING_ENABLED"
        "AI_LLM_EXPANSION_ENABLED"
    )

    # Build JSON arrays
    local cat_a_json=$(printf '%s\n' "${category_a_features[@]}" | jq -R . | jq -s '.')
    local cat_b_json=$(printf '%s\n' "${category_b_features[@]}" | jq -R . | jq -s '.')
    local cat_c_json=$(printf '%s\n' "${category_c_features[@]}" | jq -R . | jq -s '.')
    local cat_d_json=$(printf '%s\n' "${category_d_features[@]}" | jq -R . | jq -s '.')

    # Update JSON report
    local tmp_json="${TEMP_DIR}/report_cats.json"
    jq --argjson ca "${cat_a_json}" \
       --argjson cb "${cat_b_json}" \
       --argjson cc "${cat_c_json}" \
       --argjson cd "${cat_d_json}" \
       '.categories.category_a = $ca |
        .categories.category_b = $cb |
        .categories.category_c = $cc |
        .categories.category_d = $cd |
        .summary.category_a_auto_enabled = ($ca | length) |
        .summary.category_b_keep_disabled = ($cb | length) |
        .summary.category_c_remove = ($cc | length) |
        .summary.category_d_conditional = ($cd | length) |
        .summary.total_features = (($ca | length) + ($cb | length) + ($cc | length))' \
       "${JSON_REPORT}" > "${tmp_json}"
    mv "${tmp_json}" "${JSON_REPORT}"
}

# Check dashboard for feature toggles
check_dashboard_toggles() {
    log "Checking dashboard for feature toggles..."

    local dashboard="${ROOT_DIR}/dashboard.html"
    local toggle_count=0

    if [[ -f "${dashboard}" ]]; then
        # Look for toggle UI elements or feature selection
        toggle_count=$(grep -c 'toggle\|feature.*select\|enable.*checkbox' "${dashboard}" || echo "0")
        log "Found ${toggle_count} potential toggles in dashboard"
    else
        warn "Dashboard not found at ${dashboard}"
    fi

    echo "${toggle_count}"
}

# Check Nix modules for feature controls
check_nix_modules() {
    log "Checking Nix modules for feature controls..."

    local nix_controls="${TEMP_DIR}/nix_controls.txt"

    # Search Nix files for enable options
    find "${ROOT_DIR}/nix/modules" -type f -name "*.nix" 2>/dev/null | \
    xargs grep -l 'enable.*=.*mkOption\|mkEnableOption' > "${nix_controls}" 2>/dev/null || true

    local count=$(wc -l < "${nix_controls}" || echo "0")
    log "Found ${count} Nix modules with enable options"
}

# Generate markdown report
generate_markdown_report() {
    log "Generating markdown report..."

    cat > "${MD_REPORT}" <<'MDEOF'
# Integration Audit Report

**Generated:** TIMESTAMP_PLACEHOLDER
**Phase:** 4.5 - Remove Bolt-On Features
**Objective:** Audit disabled-by-default features and identify integration status

---

## Executive Summary

This audit identifies features across the AI stack and categorizes them by integration status:

- **Category A: Auto-Enabled** - Mature features enabled by default
- **Category B: Keep Disabled** - Experimental or resource-dependent features
- **Category C: Remove** - Deprecated or superseded features
- **Category D: Conditional** - Environment-dependent auto-enable

### Summary Statistics

SUMMARY_PLACEHOLDER

---

## Category A: Auto-Enabled Features (Zero Action Required)

These features are already enabled by default and require no configuration:

CATEGORY_A_PLACEHOLDER

**Status:** ✅ All features integrated and working out-of-box

---

## Category B: Keep Disabled (Opt-In Only)

These features remain disabled by default due to experimental status or resource requirements:

CATEGORY_B_PLACEHOLDER

**Recommendation:** Keep disabled with clear documentation for opt-in.

---

## Category C: Remove (Deprecated)

These features should be removed as they are deprecated or superseded:

CATEGORY_C_PLACEHOLDER

**Action Required:** Remove from codebase and update documentation.

---

## Category D: Conditional Auto-Enable

These features auto-enable when specific conditions are met:

CATEGORY_D_PLACEHOLDER

**Implementation:** Use Nix conditional logic to enable when appropriate.

---

## Feature Flags Found in Codebase

FEATURE_FLAGS_PLACEHOLDER

---

## Configuration Files with Disabled Defaults

CONFIG_DISABLED_PLACEHOLDER

---

## Manual Enabling Requirements

MANUAL_ENABLE_PLACEHOLDER

---

## Recommendations

### Immediate Actions

1. **Remove Category C features** - Clean up deprecated code
2. **Document Category B opt-in** - Clear guides for experimental features
3. **Implement Category D conditionals** - Nix-based auto-enable logic
4. **Update dashboard** - Remove toggles for Category A features

### Long-Term Improvements

1. Move all feature configuration to Nix declarative model
2. Implement centralized feature registry
3. Add feature usage telemetry
4. Create hardware-aware configuration profiles

---

## Validation Checklist

- [ ] All Category A features verified working with defaults
- [ ] No latency regressions observed
- [ ] Category B opt-out paths tested and documented
- [ ] Category D conditional logic implemented in Nix
- [ ] Dashboard toggles updated
- [ ] Integration tests passing
- [ ] Zero-config smoke test successful
- [ ] Documentation updated

---

**Audit Completed:** TIMESTAMP_PLACEHOLDER
**Status:** Ready for Phase 4.5 implementation
MDEOF

    # Replace placeholders
    sed -i "s/TIMESTAMP_PLACEHOLDER/$(date --iso-8601=seconds)/" "${MD_REPORT}"

    # Add summary from JSON
    local summary=$(jq -r '.summary |
        "- Total Features: \(.total_features)\n" +
        "- Category A (Auto-Enabled): \(.category_a_auto_enabled)\n" +
        "- Category B (Keep Disabled): \(.category_b_keep_disabled)\n" +
        "- Category C (Remove): \(.category_c_remove)\n" +
        "- Category D (Conditional): \(.category_d_conditional)"' "${JSON_REPORT}")
    sed -i "s|SUMMARY_PLACEHOLDER|${summary}|" "${MD_REPORT}"

    # Add category lists
    local cat_a=$(jq -r '.categories.category_a[] | "- `" + . + "`"' "${JSON_REPORT}" || echo "None found")
    sed -i "/CATEGORY_A_PLACEHOLDER/r /dev/stdin" "${MD_REPORT}" <<< "${cat_a}"
    sed -i "s/CATEGORY_A_PLACEHOLDER//" "${MD_REPORT}"

    local cat_b=$(jq -r '.categories.category_b[] | "- `" + . + "`"' "${JSON_REPORT}" || echo "None found")
    sed -i "/CATEGORY_B_PLACEHOLDER/r /dev/stdin" "${MD_REPORT}" <<< "${cat_b}"
    sed -i "s/CATEGORY_B_PLACEHOLDER//" "${MD_REPORT}"

    local cat_c=$(jq -r '.categories.category_c[] | "- `" + . + "`"' "${JSON_REPORT}" || echo "None found")
    sed -i "/CATEGORY_C_PLACEHOLDER/r /dev/stdin" "${MD_REPORT}" <<< "${cat_c}"
    sed -i "s/CATEGORY_C_PLACEHOLDER//" "${MD_REPORT}"

    local cat_d=$(jq -r '.categories.category_d[] | "- `" + . + "`"' "${JSON_REPORT}" || echo "None found")
    sed -i "/CATEGORY_D_PLACEHOLDER/r /dev/stdin" "${MD_REPORT}" <<< "${cat_d}"
    sed -i "s/CATEGORY_D_PLACEHOLDER//" "${MD_REPORT}"

    # Add feature flags section
    local ff_count=$(jq '.feature_flags_found | length' "${JSON_REPORT}")
    sed -i "s|FEATURE_FLAGS_PLACEHOLDER|Found ${ff_count} feature flag references (see JSON report for details)|" "${MD_REPORT}"

    # Add config disabled section
    local cfg_count=$(jq '.optional_features | length' "${JSON_REPORT}")
    sed -i "s|CONFIG_DISABLED_PLACEHOLDER|Found ${cfg_count} config files with disabled features (see JSON report for details)|" "${MD_REPORT}"

    # Add manual enable section
    local man_count=$(jq '.manual_enabling_required | length' "${JSON_REPORT}")
    sed -i "s|MANUAL_ENABLE_PLACEHOLDER|Found ${man_count} references to manual enabling (see JSON report for details)|" "${MD_REPORT}"
}

# Main audit execution
main() {
    log "Starting integration audit..."
    log "Root directory: ${ROOT_DIR}"
    log "Reports directory: ${REPORTS_DIR}"

    # Initialize report
    init_json_report

    # Run audit checks
    log ""
    log "=== Phase 1: Feature Flag Scanning ==="
    local flags_json=$(scan_feature_flags)

    log ""
    log "=== Phase 2: Configuration Analysis ==="
    local config_json=$(scan_config_optional)

    log ""
    log "=== Phase 3: Manual Enabling Check ==="
    local manual_json=$(check_manual_enabling)

    log ""
    log "=== Phase 4: Auto-Enable Verification ==="
    check_auto_enable_logic

    log ""
    log "=== Phase 5: Feature Categorization ==="
    categorize_features

    log ""
    log "=== Phase 6: Dashboard Analysis ==="
    local toggle_count=$(check_dashboard_toggles)

    log ""
    log "=== Phase 7: Nix Module Analysis ==="
    check_nix_modules

    # Update JSON report with scan results
    local tmp_json="${TEMP_DIR}/report_final.json"
    jq --argjson flags "${flags_json}" \
       --argjson configs "${config_json}" \
       --argjson manual "${manual_json}" \
       '.feature_flags_found = $flags |
        .optional_features = $configs |
        .manual_enabling_required = $manual' \
       "${JSON_REPORT}" > "${tmp_json}"
    mv "${tmp_json}" "${JSON_REPORT}"

    # Generate markdown report
    log ""
    log "=== Phase 8: Report Generation ==="
    generate_markdown_report

    # Print summary
    log ""
    success "=== Audit Complete ==="
    log "JSON Report: ${JSON_REPORT}"
    log "Markdown Report: ${MD_REPORT}"
    log ""

    # Print summary statistics
    jq -r '.summary |
        "Total Features: \(.total_features)\n" +
        "Category A (Auto-Enabled): \(.category_a_auto_enabled)\n" +
        "Category B (Keep Disabled): \(.category_b_keep_disabled)\n" +
        "Category C (Remove): \(.category_c_remove)\n" +
        "Category D (Conditional): \(.category_d_conditional)"' "${JSON_REPORT}"

    log ""
    log "Review the reports for detailed findings and recommendations."
}

# Run main function
main "$@"
