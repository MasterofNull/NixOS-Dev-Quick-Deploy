#!/usr/bin/env python3
"""Fail if templates/factory-kit/ carries owner identity, host paths, secret-like files, or symlinks.

The kit is installed from each user's own clone; it must not contain or depend on the
maintainer's account. Runs gitleaks over the dir when available (fail closed if absent).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "templates/factory-kit"
DENY_STRINGS = ["MasterofNull", "hyperd", "@gmail.com", "noreply.github.com"]
DENY_PATH = re.compile(rb"/home/|/run/current-system")
DENY_NAMES = ["secrets*", "*sops*", ".env", ".env.*", "*.local.nix", "id_*", "*.pem", ".gitleaks*",
              "*.key", "*.p12", "*.pfx", "*.kdbx", "*.age", "credentials*", ".netrc", ".npmrc", "*.pyc"]


def scan(kit: Path, extra: list[str]) -> list[str]:
    deny = [s.lower().encode("utf-8") for s in DENY_STRINGS + extra]
    bad: list[str] = []
    for p in sorted(kit.rglob("*")):
        rel = p.relative_to(kit)
        if p.is_symlink():
            bad.append(f"symlink: {rel}")
            continue
        if "__pycache__" in p.parts:
            continue
        if any(fnmatch.fnmatch(p.name, pat) for pat in DENY_NAMES):
            bad.append(f"deny-name: {rel}")
        if not p.is_file():
            continue
        for n, line in enumerate(p.read_bytes().lower().splitlines(), 1):
            hit = next((s for s in deny if s in line), None)
            if hit:
                bad.append(f"identity '{hit.decode()}': {rel}:{n}")
            if DENY_PATH.search(line):
                bad.append(f"host path: {rel}:{n}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kit", nargs="?", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--deny-string", action="append", default=[])
    ap.add_argument("--no-gitleaks", action="store_true")
    a = ap.parse_args()
    if not a.kit.is_dir():
        print(f"FAIL kit path is not a directory: {a.kit}", file=sys.stderr)
        return 2
    bad = scan(a.kit, a.deny_string)
    if not a.no_gitleaks:
        if not shutil.which("gitleaks"):
            bad.append("gitleaks not installed (nix shell nixpkgs#gitleaks, or pass --no-gitleaks)")
        else:
            r = subprocess.run(["gitleaks", "dir", "--no-banner", "--redact", str(a.kit)],
                               capture_output=True, text=True, check=False)
            if r.returncode:
                bad.append(f"gitleaks rc={r.returncode}: {(r.stdout + r.stderr).strip()[-300:]}")
    for b in bad:
        print(f"FAIL {b}", file=sys.stderr)
    print("factory-kit clean" if not bad else f"{len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
