#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-capability-stub"

tmp_tool="$(mktemp)"
tmp_workflow="$(mktemp)"
tmp_skill="$(mktemp)"
tmp_fragment="$(mktemp)"
tmp_artifact="$(mktemp)"
tmp_nix="$(mktemp)"
trap 'rm -f "${tmp_tool}" "${tmp_workflow}" "${tmp_skill}" "${tmp_fragment}" "${tmp_artifact}" "${tmp_nix}"' EXIT

python3 "${TOOL}" --tool mm --format json > "${tmp_tool}"
python3 "${TOOL}" --workflow prsi-pessimistic-recursive-improvement --format json > "${tmp_workflow}"
python3 "${TOOL}" --skill nixos-deployment --format json > "${tmp_skill}"
python3 "${TOOL}" --tool mm --fragment-only --format json > "${tmp_fragment}"
python3 "${TOOL}" --tool mm --save-artifact "${tmp_artifact}" --format json > /dev/null
python3 "${TOOL}" --tool mm --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --format json > "${tmp_nix}"

python3 - "${tmp_tool}" "${tmp_workflow}" "${tmp_skill}" "${tmp_fragment}" "${tmp_artifact}" "${tmp_nix}" <<'PY'
import json
import sys
from pathlib import Path

tool = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
workflow = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
skill = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
fragment = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
artifact = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
nix_payload = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))

if tool.get("entry", {}).get("id") != "mm":
    print("ERROR: tool stub did not preserve capability id", file=sys.stderr)
    raise SystemExit(1)
if tool.get("entry", {}).get("preferred_fix_layer") != "declarative_nix":
    print("ERROR: tool stub did not default unknown tools to declarative_nix", file=sys.stderr)
    raise SystemExit(1)
if workflow.get("entry", {}).get("preferred_fix_layer") != "workflow_blueprint":
    print("ERROR: workflow stub did not select workflow_blueprint layer", file=sys.stderr)
    raise SystemExit(1)
if skill.get("entry", {}).get("preferred_fix_layer") != "skill_registry":
    print("ERROR: skill stub did not select skill_registry layer", file=sys.stderr)
    raise SystemExit(1)
if fragment.get("id") != "mm" or "artifact_meta" in fragment:
    print("ERROR: fragment-only mode did not emit a clean catalog fragment", file=sys.stderr)
    raise SystemExit(1)
if artifact.get("artifact_meta", {}).get("tool") != "aq-capability-stub":
    print("ERROR: saved stub artifact did not preserve artifact metadata", file=sys.stderr)
    raise SystemExit(1)
if artifact.get("catalog_fragment", {}).get("id") != "mm":
    print("ERROR: saved stub artifact did not preserve the catalog fragment", file=sys.stderr)
    raise SystemExit(1)
if "nix/modules/core/options.nix" not in nix_payload.get("entry", {}).get("files", []):
    print("ERROR: nix-context stub did not bias files toward NixOS implementation surfaces", file=sys.stderr)
    raise SystemExit(1)
if not any("nix build" in cmd for cmd in nix_payload.get("entry", {}).get("recommended_actions", [])):
    print("ERROR: nix-context stub did not bias commands toward system validation", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability stub generation validated")
PY
