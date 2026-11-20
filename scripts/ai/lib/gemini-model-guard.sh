#!/usr/bin/env bash
# Gemini-lane model resolution, sourced by delegate-to-gemini and gemini-quota-fallback.sh.
# SSOT: config/model-coordinator.json tiers.google.gemini_lane (id prefix, default, fallback).
# Independence guard: a non-Gemini id (claude-*, gpt-*) routed through this lane would make a
# "gemini review" of Claude-authored work a self-review and overlap the Codex lane.

_GEMINI_GUARD_CONFIG="${GEMINI_MODEL_COORDINATOR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/config/model-coordinator.json}"

# gemini_lane_cfg KEY -> value of tiers.google.gemini_lane.KEY (empty if missing)
gemini_lane_cfg() {
    python3 - "$_GEMINI_GUARD_CONFIG" "$1" <<'PYEOF' 2>/dev/null
import json, sys
try:
    v = json.load(open(sys.argv[1]))["tiers"]["google"]["gemini_lane"].get(sys.argv[2], "")
except Exception:
    v = ""
print(v if isinstance(v, str) else "")
PYEOF
}

# gemini_model_guard MODEL -> 0 if empty (CLI default) or a Gemini id; 1 with a clear error otherwise.
gemini_model_guard() {
    local model="${1:-}" prefix
    [[ -z "$model" ]] && return 0
    prefix="$(gemini_lane_cfg required_id_prefix)"
    prefix="${prefix:-gemini-}"
    case "${model,,}" in
        "${prefix}"*) return 0 ;;
    esac
    echo "ERROR: GEMINI_LANE_NON_GEMINI_MODEL: '${model}' is not a Gemini model (id must start with '${prefix}'). The Gemini lane refuses non-Gemini models so a Gemini review stays independent of Claude/OpenAI authors; route claude-* via delegate-to-claude and gpt-* via the Codex lane." >&2
    return 1
}
