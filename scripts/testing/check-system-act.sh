#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-system-act"

tmp_bootstrap="$(mktemp)"
tmp_capability="$(mktemp)"
tmp_task_cap="$(mktemp)"
tmp_task_cap_ctx="$(mktemp)"
tmp_bootstrap_ctx="$(mktemp)"
trap 'rm -f "${tmp_bootstrap}" "${tmp_capability}" "${tmp_task_cap}" "${tmp_task_cap_ctx}" "${tmp_bootstrap_ctx}"' EXIT

python3 "${TOOL}" --task "debug a nixos rebuild activation failure and rollback safely" --format json > "${tmp_bootstrap}"
python3 "${TOOL}" --tool aq-context-bootstrap --format json > "${tmp_capability}"
python3 "${TOOL}" --task "tool not available: mm" --format json > "${tmp_task_cap}"
python3 "${TOOL}" --task "tool not available: mm" --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --format json > "${tmp_task_cap_ctx}"
python3 "${TOOL}" --task "resume declarative rust system integration" --context-language rust --context-file Cargo.toml --format json > "${tmp_bootstrap_ctx}"

python3 - "${tmp_bootstrap}" "${tmp_capability}" "${tmp_task_cap}" "${tmp_task_cap_ctx}" "${tmp_bootstrap_ctx}" <<'PY'
import json
import sys
from pathlib import Path

bootstrap = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
capability = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
task_cap = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
task_cap_ctx = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
bootstrap_ctx = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))

if bootstrap.get("subsystem") != "bootstrap":
    print("ERROR: system act did not route system-fix task to bootstrap mode", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("scope") != "system-fix":
    print("ERROR: system act did not preserve system-fix scope", file=sys.stderr)
    raise SystemExit(1)
if "nix build" not in " ".join(bootstrap.get("result", {}).get("starter_commands", [])):
    print("ERROR: system act bootstrap payload did not preserve starter commands", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("scope_diagnostics", {}).get("scores", {}).get("system-fix", 0) <= 0:
    print("ERROR: system act bootstrap payload did not preserve scope diagnostics", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("scope_confidence") not in {"medium", "high"}:
    print("ERROR: system act bootstrap payload did not preserve scope confidence", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("recommended_next_mode") != "proceed_primary":
    print("ERROR: system act bootstrap payload did not preserve recommended next mode", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("recommended_scope") != "system-fix":
    print("ERROR: system act bootstrap payload did not preserve recommended scope", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("recommended_next_mode") != "proceed_primary" or bootstrap.get("recommended_scope") != "system-fix":
    print("ERROR: system act did not expose top-level bootstrap recommendation fields", file=sys.stderr)
    raise SystemExit(1)
if capability.get("subsystem") != "capability":
    print("ERROR: system act did not route direct tool checks to capability subsystem", file=sys.stderr)
    raise SystemExit(1)
if capability.get("result", {}).get("selection", {}).get("selected_action_id") != "capability_available:aq-context-bootstrap":
    print("ERROR: system act did not expose the expected available capability selection", file=sys.stderr)
    raise SystemExit(1)
if capability.get("recommended_next_mode") != "preview_primary" or capability.get("recommended_scope") != "capability-gap":
    print("ERROR: system act did not expose top-level capability recommendation fields", file=sys.stderr)
    raise SystemExit(1)
if capability.get("recommended_action_id") != "capability_available:aq-context-bootstrap":
    print("ERROR: system act did not expose top-level recommended capability action id", file=sys.stderr)
    raise SystemExit(1)
if "repo_harness" not in capability.get("result", {}).get("missing_origin", ""):
    print("ERROR: system act did not preserve missing-origin metadata for direct capability checks", file=sys.stderr)
    raise SystemExit(1)
if task_cap.get("subsystem") != "capability":
    print("ERROR: system act did not route missing-tool task text to capability subsystem", file=sys.stderr)
    raise SystemExit(1)
action = task_cap.get("result", {}).get("action", {})
if action.get("target_capability") != "mm":
    print("ERROR: system act did not resolve missing mm capability", file=sys.stderr)
    raise SystemExit(1)
if action.get("target_fix_layer") != "catalog_extension":
    print("ERROR: unknown mm capability should route to catalog_extension", file=sys.stderr)
    raise SystemExit(1)
if task_cap.get("recommended_next_mode") != "extend_catalog" or task_cap.get("recommended_scope") != "capability-gap":
    print("ERROR: system act did not expose catalog-extension recommendation for unknown capability", file=sys.stderr)
    raise SystemExit(1)
if task_cap.get("recommended_action_id") != "capability_primary:mm":
    print("ERROR: system act did not expose top-level recommended action id for unknown capability", file=sys.stderr)
    raise SystemExit(1)
if task_cap_ctx.get("context", {}).get("application") != "nixos":
    print("ERROR: system act did not preserve context metadata for capability routing", file=sys.stderr)
    raise SystemExit(1)
ctx_hints = task_cap_ctx.get("result", {}).get("source_hints", [])
if "nix/modules/core/options.nix" not in ctx_hints:
    print("ERROR: system act did not surface metadata-aware source hints", file=sys.stderr)
    raise SystemExit(1)
if task_cap_ctx.get("result", {}).get("missing_origin") != "nixos_or_os_packages":
    print("ERROR: system act did not surface missing-origin metadata", file=sys.stderr)
    raise SystemExit(1)
if "nix" not in task_cap_ctx.get("result", {}).get("ecosystem_hints", []):
    print("ERROR: system act did not surface ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "nixpkgs" for item in task_cap_ctx.get("result", {}).get("resolver_hints", [])):
    print("ERROR: system act did not surface resolver hints", file=sys.stderr)
    raise SystemExit(1)
if task_cap_ctx.get("routing_hints", {}).get("prefer_declarative") is not True:
    print("ERROR: system act did not bias routing toward declarative remediation for NixOS context", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in task_cap_ctx.get("stack_matchers_applied", []):
    print("ERROR: system act did not surface applied stack matchers", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("subsystem") != "bootstrap":
    print("ERROR: system act did not keep bootstrap-mode routing for generic feature work", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("result", {}).get("context", {}).get("language") != "rust":
    print("ERROR: system act did not forward context metadata into bootstrap mode", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in bootstrap_ctx.get("result", {}).get("stack_matchers_applied", []):
    print("ERROR: system act bootstrap mode did not surface applied stack matchers", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in bootstrap_ctx.get("result", {}).get("card_stack_matchers_applied", []):
    print("ERROR: system act bootstrap mode did not preserve card-level stack matcher trace", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in bootstrap_ctx.get("result", {}).get("card_overlay_matchers_applied", []):
    print("ERROR: system act bootstrap mode did not preserve card overlay matcher trace", file=sys.stderr)
    raise SystemExit(1)
if "cargo" not in bootstrap_ctx.get("result", {}).get("package_hints", []):
    print("ERROR: system act bootstrap mode did not surface package hints", file=sys.stderr)
    raise SystemExit(1)
if "Cargo.toml" not in bootstrap_ctx.get("result", {}).get("source_hints", []):
    print("ERROR: system act bootstrap mode did not surface source hints", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("result", {}).get("scope_diagnostics", {}).get("scores", {}).get("feature-development", 0) <= bootstrap_ctx.get("result", {}).get("scope_diagnostics", {}).get("scores", {}).get("system-fix", 0):
    print("ERROR: system act bootstrap mode did not preserve scope diagnostics for the feature-development decision", file=sys.stderr)
    raise SystemExit(1)
alts = bootstrap_ctx.get("result", {}).get("scope_alternatives", [])
if not alts or alts[0].get("scope") != "feature-development":
    print("ERROR: system act bootstrap mode did not preserve ranked scope alternatives", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("result", {}).get("scope_confidence") not in {"medium", "high"}:
    print("ERROR: system act bootstrap mode did not preserve scope confidence", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("result", {}).get("recommended_next_mode") != "proceed_primary":
    print("ERROR: system act bootstrap mode did not preserve recommended next mode for feature work", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("result", {}).get("recommended_scope") != "feature-development":
    print("ERROR: system act bootstrap mode did not preserve recommended scope for feature work", file=sys.stderr)
    raise SystemExit(1)
if bootstrap_ctx.get("recommended_next_mode") != "proceed_primary" or bootstrap_ctx.get("recommended_scope") != "feature-development":
    print("ERROR: system act did not expose top-level recommendation fields for feature work", file=sys.stderr)
    raise SystemExit(1)
if task_cap_ctx.get("subsystem") == "capability":
    pass
if bootstrap_ctx.get("result", {}).get("fallback_scope") not in {"", None}:
    print("ERROR: system act bootstrap mode should not emit fallback scope for high-confidence routing", file=sys.stderr)
    raise SystemExit(1)
if bootstrap.get("result", {}).get("scope_confidence") == "low":
    if bootstrap.get("result", {}).get("fallback_scope") != "harness-first":
        print("ERROR: system act bootstrap mode did not preserve fallback scope for low-confidence routing", file=sys.stderr)
        raise SystemExit(1)
    if bootstrap.get("result", {}).get("recommended_next_mode") != "use_fallback_scope" or bootstrap.get("result", {}).get("recommended_scope") != "harness-first":
        print("ERROR: system act bootstrap mode did not preserve fallback execution recommendation", file=sys.stderr)
        raise SystemExit(1)

print("PASS: system act routing validated")
PY
