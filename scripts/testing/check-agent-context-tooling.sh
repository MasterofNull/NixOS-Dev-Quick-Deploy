#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-context-card"

tmp_list="$(mktemp)"
tmp_brief="$(mktemp)"
tmp_deep="$(mktemp)"
tmp_recommend="$(mktemp)"
tmp_rust="$(mktemp)"
tmp_nix="$(mktemp)"
trap 'rm -f "${tmp_list}" "${tmp_brief}" "${tmp_deep}" "${tmp_recommend}" "${tmp_rust}" "${tmp_nix}"' EXIT

python3 "${TOOL}" --list --format json > "${tmp_list}"
python3 "${TOOL}" --card repo-baseline --level brief --format json > "${tmp_brief}"
python3 "${TOOL}" --card repo-baseline --level deep --format json > "${tmp_deep}"
python3 "${TOOL}" --recommend "debug failing nixos service with apparmor and runtime probe mismatch" --level brief --format json > "${tmp_recommend}"
python3 "${TOOL}" --recommend "resume declarative rust system integration" --context-language rust --context-file Cargo.toml --level brief --format json > "${tmp_rust}"
python3 "${TOOL}" --recommend "debug a nixos rebuild activation failure" --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --level brief --format json > "${tmp_nix}"

python3 - "${tmp_list}" "${tmp_brief}" "${tmp_deep}" "${tmp_recommend}" "${tmp_rust}" "${tmp_nix}" <<'PY'
import json
import sys
from pathlib import Path

listing = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
brief = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
deep = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
recommend = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
rust = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
nix = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))

cards = listing.get("cards", [])
card_ids = {card.get("id") for card in cards}
required = {"repo-baseline", "runtime-incident", "token-discipline", "capability-gap", "system-fix", "prsi-operations"}
if not required.issubset(card_ids):
    print("ERROR: context-card listing is missing required cards", file=sys.stderr)
    raise SystemExit(1)

brief_card = brief["cards"][0]
deep_card = deep["cards"][0]
if brief_card["id"] != "repo-baseline":
    print("ERROR: explicit card lookup did not return repo-baseline", file=sys.stderr)
    raise SystemExit(1)
if len(brief_card.get("rules", [])) >= len(deep_card.get("rules", [])):
    print("ERROR: deep card disclosure did not expand beyond brief rules", file=sys.stderr)
    raise SystemExit(1)
if deep_card.get("estimated_tokens", 0) <= brief_card.get("estimated_tokens", 0):
    print("ERROR: deep card token estimate did not grow beyond brief", file=sys.stderr)
    raise SystemExit(1)

recommended_cards = recommend.get("cards", [])
if not recommended_cards:
    print("ERROR: recommendation mode returned no cards", file=sys.stderr)
    raise SystemExit(1)
top_ids = [card["id"] for card in recommended_cards[:2]]
if "runtime-incident" not in top_ids:
    print("ERROR: runtime incident card was not ranked near the top for a runtime/AppArmor query", file=sys.stderr)
    raise SystemExit(1)
if not any("service" in card.get("recommendation", {}).get("matched_terms", []) or "runtime" in card.get("recommendation", {}).get("matched_terms", []) for card in recommended_cards):
    print("ERROR: recommendation output did not expose matched terms", file=sys.stderr)
    raise SystemExit(1)
if rust.get("stack_matchers_applied") != ["rust-stack"]:
    print("ERROR: context-card did not report the applied Rust stack matcher", file=sys.stderr)
    raise SystemExit(1)
if "rust-stack" not in rust.get("card_overlay_matchers_applied", []):
    print("ERROR: context-card did not report the applied Rust card overlay matcher", file=sys.stderr)
    raise SystemExit(1)
if "Cargo.toml" not in rust.get("source_hints", []):
    print("ERROR: context-card did not surface Rust source hints", file=sys.stderr)
    raise SystemExit(1)
rust_top = [card["id"] for card in rust.get("cards", [])[:2]]
if "feature-development" not in rust_top:
    print("ERROR: context-card did not boost feature-development for Rust implementation work", file=sys.stderr)
    raise SystemExit(1)
rust_feature = next(card for card in rust.get("cards", []) if card["id"] == "feature-development")
if "cargo test --quiet" not in rust_feature.get("commands", []):
    print("ERROR: context-card did not merge Rust overlay commands into feature-development", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in nix.get("stack_matchers_applied", []):
    print("ERROR: context-card did not report the applied Nix stack matcher", file=sys.stderr)
    raise SystemExit(1)
if "nix-stack" not in nix.get("card_overlay_matchers_applied", []):
    print("ERROR: context-card did not report the applied Nix card overlay matcher", file=sys.stderr)
    raise SystemExit(1)
if "nix/modules/core/options.nix" not in nix.get("source_hints", []):
    print("ERROR: context-card did not surface Nix source hints", file=sys.stderr)
    raise SystemExit(1)
if [card["id"] for card in nix.get("cards", [])[:2]].count("nix-module-change") == 0:
    print("ERROR: context-card did not boost nix-module-change for NixOS work", file=sys.stderr)
    raise SystemExit(1)
nix_mod = next(card for card in nix.get("cards", []) if card["id"] == "nix-module-change")
if "nix build .#nixosConfigurations.nixos-ai-dev.config.system.build.toplevel --no-link" not in nix_mod.get("commands", []):
    print("ERROR: context-card did not merge Nix overlay commands into nix-module-change", file=sys.stderr)
    raise SystemExit(1)

print("PASS: agent context tooling validated")
PY
