#!/usr/bin/env python3
"""Checks for the L2B --write-golden manifest generator."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / "scripts/testing/test-local-inference-l2b.py"
GOLDEN = "scripts/testing/fixtures/local-inference-l2b-payload-golden.json"
FAILURES: list[str] = []


def check(value: bool, message: str) -> None:
    if not value:
        FAILURES.append(message)


def run(root: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TEST), *flags, "--root", str(root)],
        capture_output=True,
        text=True,
    )


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "a.py").write_text("one\n")
    (root / "b.py").write_text("two\n")
    fixture = root / GOLDEN
    fixture.parent.mkdir(parents=True)
    zero = "0" * 64
    body = (
        '{\n  "contract_version": "1.0",\n  "live_source_manifest": {\n'
        f'    "a.py": "{zero}",\n    "b.py": "{zero}"\n  }},\n'
        '  "source_shapes": [{"id": "x", "hash": "' + zero + '"}]\n}\n'
    )
    fixture.write_text(body)

    plain = run(root)
    check(fixture.read_text() == body, "plain run wrote the fixture")
    check("write-golden" not in plain.stdout, "plain run entered write mode")

    res = run(root, "--write-golden")
    check(res.returncode == 0, f"write-golden failed: {res.stdout}{res.stderr}")
    new = fixture.read_text()
    ha = hashlib.sha256(b"one\n").hexdigest()
    hb = hashlib.sha256(b"two\n").hexdigest()
    check(new == body.replace(zero, ha, 1).replace(zero, hb, 1).replace(
        ha + '"}]', zero + '"}]'
    ) or json.loads(new)["live_source_manifest"] == {"a.py": ha, "b.py": hb},
        "manifest not updated")
    check(json.loads(new)["source_shapes"][0]["hash"] == zero, "source_shapes changed")
    check(f"{zero} -> {ha}" in res.stdout, "old -> new not printed")

    (root / "b.py").unlink()
    before = fixture.read_text()
    res = run(root, "--write-golden")
    check(res.returncode != 0, "missing path did not fail")
    check(fixture.read_text() == before, "missing path still wrote fixture")

if FAILURES:
    print("FAIL: l2b write-golden")
    for f in FAILURES:
        print(f" - {f}")
    raise SystemExit(1)
print("PASS: l2b write-golden checks")
