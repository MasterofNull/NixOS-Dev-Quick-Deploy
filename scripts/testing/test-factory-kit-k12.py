#!/usr/bin/env python3
"""
test-factory-kit-k12.py — Slice K12 verification suite.
Validates optional layer manifests (host-nixos, sandbox-linux, mcp-plugins, local-model).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LAYERS_DIR = ROOT / "templates/factory-kit/layers"

EXPECTED_LAYERS = ["host-nixos", "sandbox-linux", "mcp-plugins", "local-model"]


def test_layer_manifests():
    assert LAYERS_DIR.is_dir(), f"Missing layers directory: {LAYERS_DIR}"
    for layer in EXPECTED_LAYERS:
        manifest = LAYERS_DIR / layer / "layer.json"
        assert manifest.is_file(), f"Missing layer manifest for {layer}: {manifest}"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["name"] == layer
        assert "description" in data
        assert data["enabled_by_default"] is False
        assert "core" in data["requires"]
        assert isinstance(data["checks"], list)
    print("PASS: optional layers manifests validated (host-nixos, sandbox-linux, mcp-plugins, local-model)")


def main():
    test_layer_manifests()
    print("ALL K12 TESTS PASSED")


if __name__ == "__main__":
    main()
