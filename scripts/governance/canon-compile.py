#!/usr/bin/env python3
"""canon-compile — compile shared canonical blocks into agent instruction files.

WS1.4 (AQ-OS PRD): Rule 16 (agent parity) becomes a build step instead of a
manual discipline. Blocks live once in canon/blocks/, and are injected verbatim
between markers in every target file:

    <!-- canon:begin <name> -->
    ...generated content — edit canon/blocks/<name>.md, not this region...
    <!-- canon:end <name> -->

Usage:
    canon-compile.py --write        # inject/refresh all blocks in all targets
    canon-compile.py --check        # exit 1 on any drift (CI / tier0 gate)
    canon-compile.py --adopt NAME   # wrap an existing identical section with
                                    # markers in all targets (one-time migration)

A target missing its markers is reported (check) or gets the block appended at
a marked insertion point only via --adopt — never silently.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
CANON = REPO / "canon"

BEGIN = "<!-- canon:begin {name} -->"
END = "<!-- canon:end {name} -->"


def _load_manifest() -> dict:
    return yaml.safe_load((CANON / "canon.yaml").read_text(encoding="utf-8"))


def _region_re(name: str) -> re.Pattern:
    return re.compile(
        re.escape(BEGIN.format(name=name)) + r"\n.*?" + re.escape(END.format(name=name)),
        re.DOTALL,
    )


def _rendered(name: str, body: str) -> str:
    return f"{BEGIN.format(name=name)}\n{body.rstrip()}\n{END.format(name=name)}"


def cmd_write(manifest: dict) -> int:
    changed = 0
    for name, spec in manifest["blocks"].items():
        body = (CANON / spec["source"]).read_text(encoding="utf-8")
        for target in spec["targets"]:
            path = REPO / target
            text = path.read_text(encoding="utf-8")
            region = _region_re(name)
            if not region.search(text):
                print(f"MISSING MARKERS: {target} has no canon region '{name}' — run --adopt {name} first", file=sys.stderr)
                return 1
            new_text = region.sub(lambda _: _rendered(name, body), text)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed += 1
                print(f"wrote {target} [{name}]")
    print(f"OK: compiled ({changed} file(s) updated)")
    return 0


def cmd_check(manifest: dict) -> int:
    drift = []
    for name, spec in manifest["blocks"].items():
        body = (CANON / spec["source"]).read_text(encoding="utf-8")
        want = _rendered(name, body)
        for target in spec["targets"]:
            path = REPO / target
            if not path.exists():
                drift.append(f"{target}: file missing")
                continue
            m = _region_re(name).search(path.read_text(encoding="utf-8"))
            if m is None:
                drift.append(f"{target}: canon region '{name}' missing")
            elif m.group(0) != want:
                drift.append(f"{target}: canon region '{name}' drifted from canon/blocks")
    if drift:
        for d in drift:
            print(f"DRIFT: {d}", file=sys.stderr)
        print(f"FAIL: {len(drift)} canon drift(s) — fix with: canon-compile.py --write", file=sys.stderr)
        return 1
    print("OK: no canon drift")
    return 0


def cmd_adopt(manifest: dict, name: str) -> int:
    """Wrap an existing verbatim section with markers (one-time migration)."""
    spec = manifest["blocks"].get(name)
    if not spec:
        print(f"unknown block '{name}'", file=sys.stderr)
        return 1
    body = (CANON / spec["source"]).read_text(encoding="utf-8").rstrip()
    for target in spec["targets"]:
        path = REPO / target
        text = path.read_text(encoding="utf-8")
        if _region_re(name).search(text):
            print(f"already adopted: {target}")
            continue
        if body not in text:
            print(f"ADOPT FAIL: {target} does not contain the canon body verbatim — align it first", file=sys.stderr)
            return 1
        path.write_text(text.replace(body, _rendered(name, body), 1), encoding="utf-8")
        print(f"adopted {target} [{name}]")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="canon-compile.py")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--adopt", metavar="NAME")
    args = ap.parse_args()
    manifest = _load_manifest()
    if args.write:
        return cmd_write(manifest)
    if args.check:
        return cmd_check(manifest)
    return cmd_adopt(manifest, args.adopt)


if __name__ == "__main__":
    sys.exit(main())
