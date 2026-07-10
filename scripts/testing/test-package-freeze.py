#!/usr/bin/env python3
"""Focused tests for scripts/governance/aq-package-freeze (temp-dir fixtures only)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "governance" / "aq-package-freeze"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, timeout=30)


def make_package(root: Path) -> Path:
    (root / "a.md").write_text("subject a\n")
    (root / "b.md").write_text("subject b\n")
    descriptor = root / "PACKAGE-ROOT.json"
    descriptor.write_text(json.dumps({
        "schema_version": "aq.planning_package/1.0",
        "subjects": [
            {"path": "a.md", "sha256": "stale"},
            {"path": "b.md", "sha256": "stale"},
        ],
    }))
    return descriptor


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        descriptor = make_package(root)

        # 1. clean freeze -> exit 0, prints root hash, sidecar written
        proc = run(["freeze", str(descriptor)])
        check("clean freeze exits 0", proc.returncode == 0, proc.stderr)
        root_hash_1 = proc.stdout.strip()
        check("freeze prints 64-hex root", len(root_hash_1) == 64)
        check("sidecar written", (root / "PACKAGE-ROOT.sha256").exists())

        # 2. verify after freeze -> exit 0
        proc = run(["verify", str(descriptor)])
        check("verify after freeze exits 0", proc.returncode == 0, proc.stderr)

        # 3. idempotent: second freeze yields identical root
        proc = run(["freeze", str(descriptor)])
        check("re-freeze exits 0", proc.returncode == 0, proc.stderr)
        check("re-freeze root identical", proc.stdout.strip() == root_hash_1)

        # 4. subject drift -> verify exit 2 naming the subject
        (root / "a.md").write_text("subject a DRIFTED\n")
        proc = run(["verify", str(descriptor)])
        check("drift verify exits 2", proc.returncode == 2)
        check("drift names subject", "a.md" in proc.stderr)

        # 5. re-freeze heals drift
        proc = run(["freeze", str(descriptor)])
        check("freeze after drift exits 0", proc.returncode == 0, proc.stderr)
        check("healed root differs", proc.stdout.strip() != root_hash_1)

        # 6. sidecar/descriptor mismatch -> verify exit 2
        (root / "PACKAGE-ROOT.sha256").write_text("0" * 64 + "  PACKAGE-ROOT.json\n")
        proc = run(["verify", str(descriptor)])
        check("sidecar mismatch verify exits 2", proc.returncode == 2)
        run(["freeze", str(descriptor)])  # restore

        # 7. missing subject -> freeze refuses exit 3
        (root / "b.md").unlink()
        proc = run(["freeze", str(descriptor)])
        check("missing subject freeze exits 3", proc.returncode == 3)
        check("missing subject named", "b.md" in proc.stderr)

        # 8. missing subject -> verify exit 2
        proc = run(["verify", str(descriptor)])
        check("missing subject verify exits 2", proc.returncode == 2)

    print(f"\n{'ALL PASS' if not _failures else f'{len(_failures)} FAILURE(S): ' + ', '.join(_failures)}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
