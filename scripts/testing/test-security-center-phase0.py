#!/usr/bin/env python3
"""Focused SC-1 Phase-0 static declaration/catalog parity tests."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

from harness_qa.phases import phase0  # noqa: E402


catalog = json.loads((ROOT / "config" / "security-credential-catalog-v1.json").read_text(encoding="utf-8"))
catalog_names = {
    row["runtime_name"]
    for row in catalog["credentials"]
    if row["status_source"] == "runtime-secret"
}
declared_names = phase0._declared_sops_secret_names(ROOT)
assert len(declared_names) == 13
assert declared_names <= catalog_names

with tempfile.TemporaryDirectory() as temporary:
    test_root = Path(temporary)
    core = test_root / "nix" / "modules" / "core"
    core.mkdir(parents=True)
    shutil.copy2(ROOT / "nix" / "modules" / "core" / "options.nix", core / "options.nix")
    source = (ROOT / "nix" / "modules" / "core" / "secrets.nix").read_text(encoding="utf-8")
    (core / "secrets.nix").write_text(
        source + '\n  "review-only-new-secret" = {\n',
        encoding="utf-8",
    )
    changed_names = phase0._declared_sops_secret_names(test_root)
    assert "review-only-new-secret" in changed_names
    assert changed_names - catalog_names == {"review-only-new-secret"}

print("security-center Phase-0 declaration parity: PASS")
