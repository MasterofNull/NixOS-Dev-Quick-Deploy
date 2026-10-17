#!/usr/bin/env python3
"""K2: the kit template dir passes the clean-scan; planted owner string, host path, secret file, symlink each fail."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "templates/factory-kit"
SCAN = ROOT / "scripts/governance/check-factory-kit-clean.py"


def run(kit: Path) -> int:
    return subprocess.run([sys.executable, str(SCAN), str(kit), "--no-gitleaks"], capture_output=True, text=True).returncode


def main() -> int:
    assert run(KIT) == 0, "real kit not clean"
    plants = {
        "owner string": lambda k: (k / "README.md").open("a").write("\nowner MasterofNull\n"),
        "home path": lambda k: (k / "README.md").open("a").write("\ncd /home/x/y\n"),
        "secrets.nix": lambda k: (k / "secrets.nix").write_text("{}\n"),
        "symlink": lambda k: (k / "link").symlink_to("README.md"),
        "uppercase owner": lambda k: (k / "README.md").open("a").write("\nowner HYPERD\n"),
        "server.key": lambda k: (k / "server.key").write_text("x\n"),
    }
    for name, plant in plants.items():
        with tempfile.TemporaryDirectory() as t:
            k = Path(t) / "kit"
            shutil.copytree(KIT, k)
            plant(k)
            assert run(k) != 0, f"{name} not detected"
    print(f"K2 OK: clean kit passes; {len(plants)} plants fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
