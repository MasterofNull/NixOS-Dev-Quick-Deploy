#!/usr/bin/env python3
"""Apply/repair doc metadata blocks for docs/operations and docs/development."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIRS = [ROOT / "docs" / "operations", ROOT / "docs" / "development"]
UPDATED = datetime.now(UTC).strftime("%Y-%m-%d")


def ensure_metadata(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines:
        return False

    head_scan = "\n".join(lines[:60])
    has_status = "Status:" in head_scan
    has_owner = "Owner:" in head_scan
    has_updated = "Last Updated:" in head_scan

    if has_status and has_owner and has_updated:
        return False

    meta = []
    if not has_status:
        meta.append("Status: Active")
    if not has_owner:
        meta.append("Owner: AI Stack Maintainers")
    if not has_updated:
        meta.append(f"Last Updated: {UPDATED}")
    if not meta:
        return False

    insert_at = 0
    for i, ln in enumerate(lines[:20]):
        if ln.startswith("# "):
            insert_at = i + 1
            break

    new_lines = lines[:insert_at]
    if insert_at > 0 and (insert_at >= len(lines) or lines[insert_at].strip() != ""):
        new_lines.append("")
    new_lines.extend(meta)
    new_lines.append("")
    new_lines.extend(lines[insert_at:])
    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    return True


def main() -> int:
    changed = 0
    for base in TARGET_DIRS:
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            if "archive" in md.parts:
                continue
            if ensure_metadata(md):
                changed += 1
    print(f"[doc-metadata] updated files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
