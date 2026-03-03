#!/usr/bin/env python3
"""
Skill bundle registry tooling.

Provides:
- build-index: package skills into .skill bundles + write index.json
- install: install a skill from index/bundle into a target skills dir
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_frontmatter_name_description(skill_md: Path) -> tuple[Optional[str], Optional[str]]:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None, None
    fm = m.group(1)
    name_match = re.search(r"(?m)^name:\s*(.+?)\s*$", fm)
    desc_match = re.search(r"(?m)^description:\s*(.+?)\s*$", fm)
    name = name_match.group(1).strip().strip("'\"") if name_match else None
    desc = desc_match.group(1).strip().strip("'\"") if desc_match else None
    return name, desc


def _safe_skill_bundle_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "skill"


def _package_skill_dir(skill_dir: Path, bundle_path: Path) -> None:
    parent = skill_dir.parent
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(skill_dir.rglob("*")):
            if p.is_file():
                arcname = p.relative_to(parent)
                zf.write(p, arcname)


def cmd_build_index(args: argparse.Namespace) -> int:
    skills_dir = Path(args.skills_dir).resolve()
    bundles_dir = Path(args.bundles_dir).resolve()
    index_path = Path(args.index).resolve()

    if not skills_dir.is_dir():
        print(f"ERROR: skills dir not found: {skills_dir}")
        return 1

    bundles_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    entries: List[Dict[str, object]] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue

        fm_name, fm_desc = _extract_frontmatter_name_description(skill_md)
        logical_name = fm_name or child.name
        bundle_name = f"{_safe_skill_bundle_name(logical_name)}.skill"
        bundle_path = bundles_dir / bundle_name

        _package_skill_dir(child, bundle_path)
        digest = _sha256(bundle_path)
        size_bytes = bundle_path.stat().st_size

        entries.append(
            {
                "name": logical_name,
                "folder": child.name,
                "description": fm_desc or "",
                "bundle": os.path.relpath(bundle_path, index_path.parent),
                "sha256": digest,
                "size_bytes": size_bytes,
                "packaged_at_epoch_s": int(time.time()),
            }
        )
        print(f"packaged: {logical_name} -> {bundle_path.name}")

    payload = {
        "schema_version": 1,
        "generated_at_epoch_s": int(time.time()),
        "skills_dir": str(skills_dir),
        "bundles_dir": str(bundles_dir),
        "count": len(entries),
        "skills": entries,
    }
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"index written: {index_path} ({len(entries)} skills)")
    return 0


def _safe_extract(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"unsafe bundle member path: {member.filename}")
        zf.extractall(target_dir)


def cmd_install(args: argparse.Namespace) -> int:
    index_path = Path(args.index).resolve()
    target_dir = Path(args.target_dir).resolve()
    bundles_dir_override = Path(args.bundles_dir).resolve() if args.bundles_dir else None
    skill_name = args.skill_name

    if not index_path.is_file():
        print(f"ERROR: index not found: {index_path}")
        return 1

    if args.signature and args.public_key:
        sig = Path(args.signature).resolve()
        pub = Path(args.public_key).resolve()
        if not sig.is_file():
            print(f"ERROR: signature not found: {sig}")
            return 1
        if not pub.is_file():
            print(f"ERROR: public key not found: {pub}")
            return 1
        try:
            verify = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(pub), "-signature", str(sig), str(index_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            print("ERROR: openssl is required for signature verification but not found in PATH")
            return 1
        if verify.returncode != 0:
            print("ERROR: index signature verification failed")
            return 1
        print(f"verified index signature: {sig}")
    elif args.signature or args.public_key:
        print("ERROR: --signature and --public-key must be provided together")
        return 1

    data = json.loads(index_path.read_text(encoding="utf-8"))
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        print("ERROR: malformed index, 'skills' must be a list")
        return 1

    selected: Optional[Dict[str, object]] = None
    for s in skills:
        if not isinstance(s, dict):
            continue
        if s.get("name") == skill_name or s.get("folder") == skill_name:
            selected = s
            break

    if selected is None:
        print(f"ERROR: skill not found in index: {skill_name}")
        return 1

    bundle_rel = str(selected.get("bundle", "")).strip()
    if not bundle_rel:
        print("ERROR: selected skill has no bundle path")
        return 1

    if bundles_dir_override is not None:
        bundle_path = bundles_dir_override / Path(bundle_rel).name
    else:
        bundle_path = (index_path.parent / bundle_rel).resolve()
    if not bundle_path.is_file():
        print(f"ERROR: bundle not found: {bundle_path}")
        return 1

    expected_sha = str(selected.get("sha256", "")).strip().lower()
    if expected_sha:
        actual_sha = _sha256(bundle_path).lower()
        if actual_sha != expected_sha:
            print(f"ERROR: bundle sha256 mismatch for {bundle_path.name}")
            print(f"  expected: {expected_sha}")
            print(f"  actual:   {actual_sha}")
            return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="skill-install-") as td:
        tmp = Path(td)
        _safe_extract(bundle_path, tmp)

        roots = [p for p in tmp.iterdir() if p.is_dir()]
        if len(roots) != 1:
            print("ERROR: bundle must contain exactly one top-level skill directory")
            return 1
        root = roots[0]
        if not (root / "SKILL.md").is_file():
            print("ERROR: extracted bundle missing SKILL.md")
            return 1

        dest = target_dir / root.name
        if dest.exists():
            if args.force:
                shutil.rmtree(dest)
            else:
                print(f"ERROR: destination already exists: {dest} (use --force to replace)")
                return 1
        shutil.copytree(root, dest)
        print(f"installed: {selected.get('name', root.name)} -> {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill bundle registry tooling")
    sub = ap.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build-index", help="Package skills and write an index JSON")
    p_build.add_argument("--skills-dir", required=True, help="Directory containing skill folders")
    p_build.add_argument("--bundles-dir", required=True, help="Output directory for .skill bundles")
    p_build.add_argument("--index", required=True, help="Output index JSON path")
    p_build.set_defaults(func=cmd_build_index)

    p_install = sub.add_parser("install", help="Install one skill from an index JSON")
    p_install.add_argument("--index", required=True, help="Path to index JSON")
    p_install.add_argument("--skill-name", required=True, help="Skill name or folder name in index")
    p_install.add_argument("--target-dir", required=True, help="Destination skill root directory")
    p_install.add_argument("--bundles-dir", default="", help="Optional override directory for bundle files")
    p_install.add_argument("--signature", default="", help="Optional detached signature path for index.json")
    p_install.add_argument("--public-key", default="", help="Optional public key for signature verification")
    p_install.add_argument("--force", action="store_true", help="Replace destination if skill already exists")
    p_install.set_defaults(func=cmd_install)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
