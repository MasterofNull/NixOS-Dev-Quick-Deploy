#!/usr/bin/env python3
"""Phase 58B routing audit for promoted/default capability domains."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "intent_classifier.py"

CASES = [
    {"case": "security", "query": "security review this FastAPI auth handler for OWASP injection risks", "intent": "security_analysis", "profile": "remote-reasoning"},
    {"case": "systems", "query": "fix this NixOS module option and run statix on options.nix", "intent": "systems_software", "profile": "local-tool-calling"},
    {"case": "embedded", "query": "lint this Verilog UART module with verilator", "intent": "embedded_hardware", "profile": "remote-reasoning"},
    {"case": "mobile", "query": "audit this web app with Lighthouse and fix accessibility issues", "intent": "mobile_web", "profile": "remote-reasoning"},
    {"case": "scientific", "query": "run a scipy t-test with a fixed random seed and report uncertainty", "intent": "scientific_research", "profile": "remote-reasoning"},
    {"case": "gis", "query": "validate this GeoJSON CRS and reproject it to EPSG:3857 with ogr2ogr", "intent": "gis_systems", "profile": "local-tool-calling"},
    {"case": "negative-software-regression", "query": "fix a regression in aq-qa output formatting", "not_intents": ["scientific_research"]},
    {"case": "negative-team-coordinate", "query": "coordinate the team plan for the next implementation slice", "not_intents": ["gis_systems", "code_generation"]},
]


def _load_classifier():
    spec = importlib.util.spec_from_file_location("phase58b_intent_classifier", CLASSIFIER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {CLASSIFIER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(CLASSIFIER_PATH.parent))
    spec.loader.exec_module(module)
    return module.IntentClassifier()


def main() -> int:
    clf = _load_classifier()
    failures = []
    results = []
    for case in CASES:
        name = case["case"]
        query = case["query"]
        got = clf.classify(query)
        row = {
            "case": name,
            "query": query,
            "expected_intent": case.get("intent"),
            "expected_profile": case.get("profile"),
            "not_intents": case.get("not_intents", []),
            "intent": got.get("intent"),
            "profile": got.get("profile"),
            "confidence": got.get("confidence"),
            "signals": got.get("signals_matched"),
        }
        results.append(row)
        if "intent" in case and got.get("intent") != case["intent"]:
            failures.append(row)
            continue
        if "profile" in case and got.get("profile") != case["profile"]:
            failures.append(row)
            continue
        if got.get("intent") in case.get("not_intents", []):
            failures.append(row)
    print(json.dumps({"status": "pass" if not failures else "fail", "results": results}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
