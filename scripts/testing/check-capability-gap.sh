#!/usr/bin/env bash
# Purpose: Test aq-capability-gap analysis and gap detection
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-capability-gap"

tmp_available="$(mktemp)"
tmp_missing_repo="$(mktemp)"
tmp_workflow="$(mktemp)"
tmp_skill="$(mktemp)"
tmp_unknown="$(mktemp)"
tmp_unknown_repeat="$(mktemp)"
tmp_nix_context="$(mktemp)"
tmp_mcp_context="$(mktemp)"
tmp_external="$(mktemp)"
tmp_rust_context="$(mktemp)"
tmp_ts_context="$(mktemp)"
tmp_go_context="$(mktemp)"
tmp_php_context="$(mktemp)"
tmp_pnpm_context="$(mktemp)"
tmp_bun_context="$(mktemp)"
tmp_dotnet_context="$(mktemp)"
tmp_observations="$(mktemp)"
trap 'rm -f "${tmp_available}" "${tmp_missing_repo}" "${tmp_workflow}" "${tmp_skill}" "${tmp_unknown}" "${tmp_unknown_repeat}" "${tmp_nix_context}" "${tmp_mcp_context}" "${tmp_external}" "${tmp_rust_context}" "${tmp_ts_context}" "${tmp_go_context}" "${tmp_php_context}" "${tmp_pnpm_context}" "${tmp_bun_context}" "${tmp_dotnet_context}" "${tmp_observations}"' EXIT

python3 "${TOOL}" --tool aqd --format json > "${tmp_available}"
AQ_CAPABILITY_GAP_FORCE_MISSING=aq-context-bootstrap python3 "${TOOL}" --tool aq-context-bootstrap --format json > "${tmp_missing_repo}"
AQ_CAPABILITY_GAP_FORCE_MISSING=workflow:prsi-pessimistic-recursive-improvement python3 "${TOOL}" --workflow prsi-pessimistic-recursive-improvement --format json > "${tmp_workflow}"
AQ_CAPABILITY_GAP_FORCE_MISSING=skill:nixos-deployment python3 "${TOOL}" --skill nixos-deployment --format json > "${tmp_skill}"
AQ_CAPABILITY_GAP_OBSERVATIONS_FILE="${tmp_observations}" python3 "${TOOL}" --tool definitely-not-a-real-tool --format json > "${tmp_unknown}"
AQ_CAPABILITY_GAP_OBSERVATIONS_FILE="${tmp_observations}" python3 "${TOOL}" --tool definitely-not-a-real-tool --format json > "${tmp_unknown_repeat}"
python3 "${TOOL}" --tool mm --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --format json > "${tmp_nix_context}"
python3 "${TOOL}" --tool mcp-bridge-helper --context-language python --context-application mcp --context-file scripts/ai/mcp-bridge-hybrid.py --format json > "${tmp_mcp_context}"
AQ_CAPABILITY_GAP_FORCE_MISSING=openskills python3 "${TOOL}" --tool openskills --format json > "${tmp_external}"
python3 "${TOOL}" --tool cargo-helper --context-language rust --context-file Cargo.toml --format json > "${tmp_rust_context}"
python3 "${TOOL}" --tool ts-node-helper --context-language typescript --format json > "${tmp_ts_context}"
AQ_CAPABILITY_GAP_REPO_FILES="go.mod" python3 "${TOOL}" --tool go-helper --context-language go --format json > "${tmp_go_context}"
AQ_CAPABILITY_GAP_REPO_FILES="composer.json" python3 "${TOOL}" --tool php-helper --context-language php --format json > "${tmp_php_context}"
AQ_CAPABILITY_GAP_REPO_FILES="pnpm-lock.yaml,package.json" python3 "${TOOL}" --tool pnpm-helper --context-language typescript --format json > "${tmp_pnpm_context}"
AQ_CAPABILITY_GAP_REPO_FILES="bun.lockb,package.json" python3 "${TOOL}" --tool bun-helper --context-language javascript --format json > "${tmp_bun_context}"
AQ_CAPABILITY_GAP_REPO_FILES="app.csproj" python3 "${TOOL}" --tool dotnet-helper --context-language dotnet --format json > "${tmp_dotnet_context}"

python3 - "${tmp_available}" "${tmp_missing_repo}" "${tmp_workflow}" "${tmp_skill}" "${tmp_unknown}" "${tmp_unknown_repeat}" "${tmp_nix_context}" "${tmp_mcp_context}" "${tmp_external}" "${tmp_rust_context}" "${tmp_ts_context}" "${tmp_go_context}" "${tmp_php_context}" "${tmp_pnpm_context}" "${tmp_bun_context}" "${tmp_dotnet_context}" "${tmp_observations}" <<'PY'
import json
import sys
from pathlib import Path

available = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
missing_repo = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
workflow = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
skill = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
unknown = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
unknown_repeat = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
nix_context = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))
mcp_context = json.loads(Path(sys.argv[8]).read_text(encoding="utf-8"))
external = json.loads(Path(sys.argv[9]).read_text(encoding="utf-8"))
rust_context = json.loads(Path(sys.argv[10]).read_text(encoding="utf-8"))
ts_context = json.loads(Path(sys.argv[11]).read_text(encoding="utf-8"))
go_context = json.loads(Path(sys.argv[12]).read_text(encoding="utf-8"))
php_context = json.loads(Path(sys.argv[13]).read_text(encoding="utf-8"))
pnpm_context = json.loads(Path(sys.argv[14]).read_text(encoding="utf-8"))
bun_context = json.loads(Path(sys.argv[15]).read_text(encoding="utf-8"))
dotnet_context = json.loads(Path(sys.argv[16]).read_text(encoding="utf-8"))
observations = json.loads(Path(sys.argv[17]).read_text(encoding="utf-8"))

if available.get("classification") != "available":
    print("ERROR: aqd should classify as available", file=sys.stderr)
    raise SystemExit(1)
if missing_repo.get("classification") != "missing_repo_tooling":
    print("ERROR: forced-missing repo tool did not classify as missing_repo_tooling", file=sys.stderr)
    raise SystemExit(1)
if missing_repo.get("preferred_fix_layer") != "repo_script":
    print("ERROR: missing repo tool did not preserve preferred fix layer", file=sys.stderr)
    raise SystemExit(1)
if "bootstrap" not in missing_repo.get("ecosystem_hints", []):
    print("ERROR: repo tool did not use catalog ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if "config/agent-context-cards.json" not in missing_repo.get("source_hints", []):
    print("ERROR: repo tool did not use catalog source hints", file=sys.stderr)
    raise SystemExit(1)
if workflow.get("classification") != "missing_workflow_blueprint":
    print("ERROR: missing workflow did not classify as missing_workflow_blueprint", file=sys.stderr)
    raise SystemExit(1)
if skill.get("classification") != "missing_skill":
    print("ERROR: missing skill did not classify as missing_skill", file=sys.stderr)
    raise SystemExit(1)
if unknown.get("classification") != "unknown_capability":
    print("ERROR: unknown capability did not classify as unknown_capability", file=sys.stderr)
    raise SystemExit(1)
if "config/capability-gap-catalog.json" not in unknown.get("files", []):
    print("ERROR: unknown capability did not point back to the catalog extension path", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-capability-stub" in cmd for cmd in unknown.get("recommended_actions", [])):
    print("ERROR: unknown capability did not emit a stub-generation action", file=sys.stderr)
    raise SystemExit(1)
if unknown.get("observation", {}).get("count") != 1 or unknown.get("observation", {}).get("promotion_candidate") is not False:
    print("ERROR: first unknown capability observation did not record the expected baseline count", file=sys.stderr)
    raise SystemExit(1)
if unknown_repeat.get("observation", {}).get("count") != 2 or unknown_repeat.get("observation", {}).get("promotion_candidate") is not True:
    print("ERROR: repeated unknown capability did not promote after crossing the threshold", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-capability-promote" in cmd for cmd in unknown_repeat.get("recommended_actions", [])):
    print("ERROR: repeated unknown capability did not emit a promotion action", file=sys.stderr)
    raise SystemExit(1)
if "tool:definitely-not-a-real-tool" not in observations.get("observations", {}):
    print("ERROR: unknown capability observations were not persisted in the state file", file=sys.stderr)
    raise SystemExit(1)
if nix_context.get("context", {}).get("application") != "nixos":
    print("ERROR: capability gap did not preserve nixos context metadata", file=sys.stderr)
    raise SystemExit(1)
if "nix/modules/core/options.nix" not in nix_context.get("source_hints", []):
    print("ERROR: capability gap did not emit nix-aware source hints", file=sys.stderr)
    raise SystemExit(1)
if nix_context.get("missing_origin") != "nixos_or_os_packages":
    print("ERROR: capability gap did not classify NixOS tool origin correctly", file=sys.stderr)
    raise SystemExit(1)
if "nix" not in nix_context.get("ecosystem_hints", []) or "nixos" not in nix_context.get("ecosystem_hints", []):
    print("ERROR: capability gap did not emit Nix/NixOS ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if "nixpkgs" not in nix_context.get("package_hints", []):
    print("ERROR: capability gap did not emit Nix package hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "nixpkgs" for item in nix_context.get("resolver_hints", [])):
    print("ERROR: capability gap did not emit nixpkgs resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in nix_context.get("stack_matchers_applied", []):
    print("ERROR: capability gap did not report applied Nix stack matcher", file=sys.stderr)
    raise SystemExit(1)
if missing_repo.get("missing_origin") != "repo_harness":
    print("ERROR: repo tool capability gap did not classify harness origin", file=sys.stderr)
    raise SystemExit(1)
if mcp_context.get("missing_origin") != "mcp_harness":
    print("ERROR: MCP-context capability gap did not classify harness origin", file=sys.stderr)
    raise SystemExit(1)
if "mcp" not in mcp_context.get("ecosystem_hints", []) or "python" not in mcp_context.get("ecosystem_hints", []):
    print("ERROR: MCP-context capability gap did not emit Python/MCP ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if "scripts/ai/mcp-server" not in mcp_context.get("package_hints", []):
    print("ERROR: MCP-context capability gap did not emit MCP package hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "repo_mcp_harness" for item in mcp_context.get("resolver_hints", [])):
    print("ERROR: MCP-context capability gap did not emit MCP resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "mcp-harness" not in mcp_context.get("stack_matchers_applied", []):
    print("ERROR: MCP-context capability gap did not report applied MCP matcher", file=sys.stderr)
    raise SystemExit(1)
if external.get("classification") != "missing_external_cli":
    print("ERROR: external CLI capability did not classify as missing_external_cli", file=sys.stderr)
    raise SystemExit(1)
if external.get("missing_origin") != "os_or_user_environment":
    print("ERROR: external CLI capability did not use catalog missing origin", file=sys.stderr)
    raise SystemExit(1)
if "external-cli" not in external.get("ecosystem_hints", []):
    print("ERROR: external CLI capability did not use catalog ecosystem hints", file=sys.stderr)
    raise SystemExit(1)
if "installer fallback only if declarative path is unavailable" not in external.get("package_hints", []):
    print("ERROR: external CLI capability did not use catalog package hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "npm" for item in external.get("resolver_hints", [])):
    print("ERROR: external CLI capability did not emit npm fallback resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "rust" not in rust_context.get("ecosystem_hints", []) or "cli" not in rust_context.get("ecosystem_hints", []):
    print("ERROR: rust-context capability did not use dynamic stack registry hints", file=sys.stderr)
    raise SystemExit(1)
if "rustc" not in rust_context.get("package_hints", []) or "cargo" not in rust_context.get("package_hints", []):
    print("ERROR: rust-context capability did not use dynamic package hints", file=sys.stderr)
    raise SystemExit(1)
if "Cargo.toml" not in rust_context.get("source_hints", []):
    print("ERROR: rust-context capability did not use dynamic source hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "cargo" for item in rust_context.get("resolver_hints", [])):
    print("ERROR: rust-context capability did not emit cargo resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in rust_context.get("stack_matchers_applied", []):
    print("ERROR: rust-context capability did not report applied Rust matcher", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "typescript_toolchain" for item in ts_context.get("resolver_hints", [])):
    print("ERROR: typescript-context capability did not emit TypeScript resolver hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.endswith("tsconfig.json") for item in ts_context.get("repo_manifest_matches", [])):
    print("ERROR: typescript-context capability did not record tsconfig manifest matches", file=sys.stderr)
    raise SystemExit(1)
if not any(ts_context.get("source_hints", [None])[0].endswith(suffix) for suffix in ("pnpm-lock.yaml", "tsconfig.json")):
    print("ERROR: typescript-context capability did not prioritize the highest-value matched manifest in source hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "go_modules" for item in go_context.get("resolver_hints", [])):
    print("ERROR: go-context capability did not emit Go modules resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "go.mod" not in go_context.get("repo_manifest_matches", []):
    print("ERROR: go-context capability did not record go.mod manifest matches", file=sys.stderr)
    raise SystemExit(1)
if go_context.get("source_hints", [None])[0] != "go.mod":
    print("ERROR: go-context capability did not prioritize go.mod in source hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "composer" for item in php_context.get("resolver_hints", [])):
    print("ERROR: php-context capability did not emit Composer resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "composer.json" not in php_context.get("repo_manifest_matches", []):
    print("ERROR: php-context capability did not record composer.json manifest matches", file=sys.stderr)
    raise SystemExit(1)
if php_context.get("source_hints", [None])[0] != "composer.json":
    print("ERROR: php-context capability did not prioritize composer.json in source hints", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "pnpm" for item in pnpm_context.get("resolver_hints", [])):
    print("ERROR: pnpm-context capability did not emit pnpm resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "pnpm-lock.yaml" not in pnpm_context.get("repo_manifest_matches", []):
    print("ERROR: pnpm-context capability did not record pnpm lockfile matches", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "bun" for item in bun_context.get("resolver_hints", [])):
    print("ERROR: bun-context capability did not emit bun resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "bun.lockb" not in bun_context.get("repo_manifest_matches", []):
    print("ERROR: bun-context capability did not record bun lockfile matches", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "dotnet_tool" for item in dotnet_context.get("resolver_hints", [])):
    print("ERROR: dotnet-context capability did not emit dotnet tool resolver hints", file=sys.stderr)
    raise SystemExit(1)
if "app.csproj" not in dotnet_context.get("repo_manifest_matches", []):
    print("ERROR: dotnet-context capability did not record csproj manifest matches", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability gap classification validated")
PY
