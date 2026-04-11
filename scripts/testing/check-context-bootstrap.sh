#!/usr/bin/env bash
# Purpose: Test aq-context-bootstrap initialization and context generation
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-context-bootstrap"

tmp_system="$(mktemp)"
tmp_feature="$(mktemp)"
tmp_prsi="$(mktemp)"
tmp_gap="$(mktemp)"
tmp_system_ctx="$(mktemp)"
tmp_rust_ctx="$(mktemp)"
tmp_offload="$(mktemp)"
trap 'rm -f "${tmp_system}" "${tmp_feature}" "${tmp_prsi}" "${tmp_gap}" "${tmp_system_ctx}" "${tmp_rust_ctx}" "${tmp_offload}"' EXIT

python3 "${TOOL}" --task "debug a nixos rebuild activation failure and rollback safely" --format json > "${tmp_system}"
python3 "${TOOL}" --task "implement a new feature in the brownfield AI workflow" --format json > "${tmp_feature}"
python3 "${TOOL}" --task "improve PRSI quarantine and budget gates" --format json > "${tmp_prsi}"
python3 "${TOOL}" --task "tool not available: aq-context-bootstrap" --format json > "${tmp_gap}"
python3 "${TOOL}" --task "restore missing capability mm" --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --format json > "${tmp_system_ctx}"
python3 "${TOOL}" --task "restore missing rust build helper" --context-language rust --context-file Cargo.toml --format json > "${tmp_rust_ctx}"
python3 "${TOOL}" --task "offload long-running agent prompt history into the local harness with frequent compaction and memory recall" --format json > "${tmp_offload}"

python3 - "${tmp_system}" "${tmp_feature}" "${tmp_prsi}" "${tmp_gap}" "${tmp_system_ctx}" "${tmp_rust_ctx}" "${tmp_offload}" <<'PY'
import json
import sys
from pathlib import Path

system = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
feature = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
prsi = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
gap = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
system_ctx = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
rust_ctx = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
offload = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))

if system.get("scope") != "system-fix":
    print("ERROR: system bootstrap did not classify as system-fix", file=sys.stderr)
    raise SystemExit(1)
if system.get("recommended_card_order", [None])[0] != "system-fix":
    print("ERROR: system bootstrap did not prioritize the system-fix card", file=sys.stderr)
    raise SystemExit(1)
if not any("nix build" in cmd for cmd in system.get("starter_commands", [])):
    print("ERROR: system bootstrap did not expose a system-level validation command", file=sys.stderr)
    raise SystemExit(1)

if feature.get("scope") != "feature-development":
    print("ERROR: feature bootstrap did not classify as feature-development", file=sys.stderr)
    raise SystemExit(1)
if feature.get("recommended_card_order", [None])[0] != "feature-development":
    print("ERROR: feature bootstrap did not prioritize the feature-development card", file=sys.stderr)
    raise SystemExit(1)
if not any("workflows brownfield" in cmd for cmd in feature.get("starter_commands", [])):
    print("ERROR: feature bootstrap did not expose the brownfield workflow command", file=sys.stderr)
    raise SystemExit(1)

if prsi.get("scope") != "prsi-operations":
    print("ERROR: PRSI bootstrap did not classify as prsi-operations", file=sys.stderr)
    raise SystemExit(1)
if prsi.get("recommended_card_order", [None])[0] != "prsi-operations":
    print("ERROR: PRSI bootstrap did not prioritize the prsi-operations card", file=sys.stderr)
    raise SystemExit(1)
if not any("check-prsi-phase7-static-gates.sh" in cmd for cmd in prsi.get("starter_commands", [])):
    print("ERROR: PRSI bootstrap did not expose the expected PRSI static gate command", file=sys.stderr)
    raise SystemExit(1)
if gap.get("scope") != "capability-gap":
    print("ERROR: capability gap bootstrap did not classify as capability-gap", file=sys.stderr)
    raise SystemExit(1)
if gap.get("recommended_card_order", [None])[0] != "capability-gap":
    print("ERROR: capability gap bootstrap did not prioritize the capability-gap card", file=sys.stderr)
    raise SystemExit(1)
if system_ctx.get("context", {}).get("application") != "nixos":
    print("ERROR: context bootstrap did not preserve NixOS metadata", file=sys.stderr)
    raise SystemExit(1)
if system_ctx.get("recommended_card_order", [None])[0] != "nix-module-change":
    print("ERROR: context bootstrap did not bias card order toward nix-module-change for NixOS metadata", file=sys.stderr)
    raise SystemExit(1)
if "nix/modules/core/options.nix" not in system_ctx.get("source_hints", []):
    print("ERROR: context bootstrap did not emit NixOS source hints", file=sys.stderr)
    raise SystemExit(1)
if "nixpkgs" not in system_ctx.get("package_hints", []):
    print("ERROR: context bootstrap did not emit NixOS package hints", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in system_ctx.get("stack_matchers_applied", []):
    print("ERROR: context bootstrap did not report applied Nix stack matcher", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in system_ctx.get("card_stack_matchers_applied", []):
    print("ERROR: context bootstrap did not preserve card-level stack matcher trace for NixOS metadata", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in system_ctx.get("card_overlay_matchers_applied", []):
    print("ERROR: context bootstrap did not preserve card overlay matcher trace for NixOS metadata", file=sys.stderr)
    raise SystemExit(1)
if system_ctx.get("scope_diagnostics", {}).get("scores", {}).get("system-fix", 0) <= 0:
    print("ERROR: context bootstrap did not emit scope diagnostics for system-fix", file=sys.stderr)
    raise SystemExit(1)
if system_ctx.get("scope_confidence") not in {"low", "medium", "high"}:
    print("ERROR: context bootstrap did not emit scope confidence for NixOS system work", file=sys.stderr)
    raise SystemExit(1)
sys_alts = system_ctx.get("scope_alternatives", [])
if not sys_alts or sys_alts[0].get("scope") != "system-fix":
    print("ERROR: context bootstrap did not emit ranked alternatives for NixOS system work", file=sys.stderr)
    raise SystemExit(1)
if system_ctx.get("scope_confidence") == "low":
    if system_ctx.get("fallback_scope") != "harness-first" or system_ctx.get("fallback_reason") != "low_scope_confidence":
        print("ERROR: context bootstrap did not recommend harness-first fallback for low-confidence routing", file=sys.stderr)
        raise SystemExit(1)
    if system_ctx.get("recommended_next_mode") != "use_fallback_scope" or system_ctx.get("recommended_scope") != "harness-first":
        print("ERROR: context bootstrap did not emit the expected fallback execution recommendation", file=sys.stderr)
        raise SystemExit(1)
else:
    if system_ctx.get("recommended_next_mode") != "proceed_primary" or system_ctx.get("recommended_scope") != system_ctx.get("scope"):
        print("ERROR: context bootstrap did not emit the expected primary execution recommendation", file=sys.stderr)
        raise SystemExit(1)
if "rust" not in rust_ctx.get("ecosystem_hints", []):
    print("ERROR: context bootstrap did not emit Rust ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if "cargo" not in rust_ctx.get("package_hints", []):
    print("ERROR: context bootstrap did not emit Rust package hints", file=sys.stderr)
    raise SystemExit(1)
if "Cargo.toml" not in rust_ctx.get("source_hints", []):
    print("ERROR: context bootstrap did not emit Rust source hints", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in rust_ctx.get("stack_matchers_applied", []):
    print("ERROR: context bootstrap did not report applied Rust stack matcher", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in rust_ctx.get("card_stack_matchers_applied", []):
    print("ERROR: context bootstrap did not preserve card-level stack matcher trace for Rust metadata", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in rust_ctx.get("card_overlay_matchers_applied", []):
    print("ERROR: context bootstrap did not preserve card overlay matcher trace for Rust metadata", file=sys.stderr)
    raise SystemExit(1)
if rust_ctx.get("scope") != "feature-development":
    print("ERROR: context bootstrap did not bias Rust implementation work toward feature-development", file=sys.stderr)
    raise SystemExit(1)
if rust_ctx.get("scope_diagnostics", {}).get("scores", {}).get("feature-development", 0) <= rust_ctx.get("scope_diagnostics", {}).get("scores", {}).get("system-fix", 0):
    print("ERROR: context bootstrap scope diagnostics did not prefer feature-development for Rust implementation work", file=sys.stderr)
    raise SystemExit(1)
alts = rust_ctx.get("scope_alternatives", [])
if not alts or alts[0].get("scope") != "feature-development":
    print("ERROR: context bootstrap did not emit ranked scope alternatives", file=sys.stderr)
    raise SystemExit(1)
if rust_ctx.get("scope_confidence") not in {"medium", "high"}:
    print("ERROR: context bootstrap did not emit scope confidence for Rust implementation work", file=sys.stderr)
    raise SystemExit(1)
if rust_ctx.get("recommended_next_mode") != "proceed_primary" or rust_ctx.get("recommended_scope") != "feature-development":
    print("ERROR: context bootstrap did not emit the expected primary recommendation for Rust implementation work", file=sys.stderr)
    raise SystemExit(1)
if rust_ctx.get("fallback_scope") not in {"", None}:
    print("ERROR: context bootstrap should not emit a fallback scope for high-confidence Rust routing", file=sys.stderr)
    raise SystemExit(1)
if offload.get("scope") != "context-offload":
    print("ERROR: offload bootstrap did not classify as context-offload", file=sys.stderr)
    raise SystemExit(1)
if offload.get("recommended_card_order", [None])[0] != "context-offload":
    print("ERROR: offload bootstrap did not prioritize the context-offload card", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-context-manage check" in cmd for cmd in offload.get("starter_commands", [])):
    print("ERROR: offload bootstrap did not expose compaction tooling", file=sys.stderr)
    raise SystemExit(1)
if not any("long-running-context-offload" in cmd for cmd in offload.get("starter_commands", [])):
    print("ERROR: offload bootstrap did not expose the long-running context offload blueprint", file=sys.stderr)
    raise SystemExit(1)
if "scripts/ai/aq-memory" not in offload.get("source_hints", []):
    print("ERROR: offload bootstrap did not emit harness memory source hints", file=sys.stderr)
    raise SystemExit(1)

print("PASS: context bootstrap validated")
PY
