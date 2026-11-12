#!/usr/bin/env python3
"""Every tracked SKILL.md frontmatter must have unique top-level keys (Codex rejects "duplicate field")."""
from __future__ import annotations

import collections
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def duplicate_keys(text: str) -> list[str]:
    m = re.match(r"---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not m:
        return []
    keys = [ln.split(":", 1)[0] for ln in m.group(1).split("\n") if re.match(r"^[A-Za-z_][\w-]*:", ln)]
    return sorted(k for k, n in collections.Counter(keys).items() if n > 1)


def main() -> int:
    assert duplicate_keys("---\nname: a\ndescription: x\ndescription: y\n---\nbody") == ["description"], "detector self-test"
    assert duplicate_keys("---\nname: a\ndescription: x\n---\nbody") == [], "detector self-test (clean)"
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*SKILL.md"], capture_output=True, text=True, check=True).stdout.split()
    assert files, "no SKILL.md files found"
    bad = {f: d for f in files if (d := duplicate_keys((ROOT / f).read_text(encoding="utf-8")))}
    for f, d in bad.items():
        print(f"FAIL {f}: duplicate frontmatter key(s) {d}")
    print(f"{'FAIL' if bad else 'PASS'}: {len(files)} SKILL.md files checked, {len(bad)} with duplicate keys")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
