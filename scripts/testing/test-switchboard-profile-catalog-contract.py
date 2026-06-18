#!/usr/bin/env python3
"""Guard switchboard profile budget SSOT drift.

The deployed service builds a Nix-generated JSON catalog and also points at the
repo YAML catalog. Python fallbacks are only a fallback, so all three sources
must agree for profiles whose token budgets are operationally sensitive.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - explicit operator signal
    raise SystemExit(f"PyYAML required for switchboard profile contract: {exc}") from exc


ROOT = Path(__file__).resolve().parents[2]

EXPECTED = {
    "remote-default": {
        "maxInputTokens": 3500,
        "maxMessages": 16,
        "maxOutputTokens": 2048,
    },
    "local-tool-calling": {
        "maxInputTokens": 5200,
        "maxMessages": 20,
        "maxOutputTokens": 1500,
    },
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_python_defaults() -> dict:
    path = ROOT / "ai-stack/switchboard/switchboard.py"
    os.environ.setdefault("LLAMA_CTX_SIZE", "16384")
    spec = importlib.util.spec_from_file_location("switchboard_profile_contract_probe", path)
    if spec is None or spec.loader is None:
        fail("could not import switchboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DEFAULT_PROFILE_CATALOG


def load_yaml_profiles() -> dict:
    path = ROOT / "config/switchboard-profiles.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc.get("profiles", doc)


def parse_nix_profiles() -> dict:
    text = (ROOT / "nix/modules/services/switchboard.nix").read_text(encoding="utf-8")
    profiles: dict[str, dict[str, int]] = {}
    for profile in EXPECTED:
        match = re.search(rf'"{re.escape(profile)}"\s*=\s*\{{(?P<body>.*?)\n\s*\}};', text, re.S)
        if not match:
            fail(f"could not locate {profile} in nix/modules/services/switchboard.nix")
        body = match.group("body")
        values = {}
        for key in ("maxInputTokens", "maxMessages", "maxOutputTokens"):
            key_match = re.search(rf"{key}\s*=\s*([0-9]+);", body)
            if not key_match:
                fail(f"could not locate {profile}.{key} in nix switchboard catalog")
            values[key] = int(key_match.group(1))
        profiles[profile] = values
    return profiles


def assert_expected(source: str, profiles: dict) -> None:
    for profile, expected_values in EXPECTED.items():
        actual = profiles.get(profile)
        if not isinstance(actual, dict):
            fail(f"{source}: missing profile {profile}")
        for key, expected in expected_values.items():
            actual_value = actual.get(key)
            if actual_value != expected:
                fail(f"{source}: {profile}.{key}={actual_value!r}, expected {expected!r}")


def assert_switchboard_runtime_deps() -> None:
    text = (ROOT / "nix/modules/services/switchboard.nix").read_text(encoding="utf-8")
    if "pyyaml" not in text:
        fail("switchboard service Python environment must include pyyaml for YAML catalog loading")


def main() -> None:
    assert_expected("switchboard.py defaults", load_python_defaults())
    assert_expected("switchboard-profiles.yaml", load_yaml_profiles())
    assert_expected("nix switchboard catalog", parse_nix_profiles())
    assert_switchboard_runtime_deps()
    print("PASS: switchboard profile catalog contract")


if __name__ == "__main__":
    main()
