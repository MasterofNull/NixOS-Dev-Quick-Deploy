#!/usr/bin/env python3
"""Validate switchboard profile policy invariants."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _profile_hint_flags() -> dict[str, bool]:
    source = (ROOT / "ai-stack" / "switchboard" / "switchboard.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_PROFILE_CATALOG":
                    return _extract_hint_flags(node.value)
    raise AssertionError("DEFAULT_PROFILE_CATALOG not found")


def _extract_hint_flags(node: ast.AST) -> dict[str, bool]:
    assert isinstance(node, ast.Dict)
    flags: dict[str, bool] = {}
    for key_node, value_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        if not isinstance(value_node, ast.Dict):
            continue
        for profile_key, profile_value in zip(value_node.keys, value_node.values):
            if (
                isinstance(profile_key, ast.Constant)
                and profile_key.value == "injectHints"
                and isinstance(profile_value, ast.Constant)
                and isinstance(profile_value.value, bool)
            ):
                flags[key_node.value] = profile_value.value
    return flags


def main() -> int:
    yaml_catalog = yaml.safe_load((ROOT / "config" / "switchboard-profiles.yaml").read_text(encoding="utf-8"))
    yaml_profiles = yaml_catalog["profiles"]
    fallback_hint_flags = _profile_hint_flags()

    assert yaml_profiles["continue-local"]["injectHints"] is False
    assert fallback_hint_flags["continue-local"] is False
    assert yaml_profiles["local-agent"]["injectHints"] is True
    assert yaml_profiles["local-tool-calling"]["injectHints"] is False
    assert fallback_hint_flags["local-tool-calling"] is False

    print("PASS: switchboard profile policy invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
