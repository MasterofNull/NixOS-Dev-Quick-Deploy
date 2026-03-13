#!/usr/bin/env python3
"""Sync shared local SKILL.md entries into the approved AIDB skill registry."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_DIR = REPO_ROOT / ".agent" / "skills"
DEFAULT_AIDB_URL = os.getenv(
    "AIDB_URL",
    f"http://{os.getenv('SERVICE_HOST', '127.0.0.1')}:{os.getenv('AIDB_PORT', '8002')}",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync shared local SKILL.md entries into the approved AIDB registry."
    )
    parser.add_argument("--skills-dir", default=str(DEFAULT_SKILLS_DIR))
    parser.add_argument("--aidb-url", default=DEFAULT_AIDB_URL)
    parser.add_argument("--api-key-file", default=os.getenv("AIDB_API_KEY_FILE", "/run/secrets/aidb_api_key"))
    parser.add_argument("--managed-by", default="shared-skill-sync")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only drift check; do not import or approve skills.",
    )
    return parser.parse_args()


def read_api_key(api_key_file: str) -> str:
    direct = os.getenv("AIDB_API_KEY", "").strip()
    if direct:
        return direct
    path = Path(api_key_file)
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def list_local_skills(skills_dir: Path) -> List[Dict[str, str]]:
    skills: List[Dict[str, str]] = []
    if not skills_dir.is_dir():
        return skills
    for skill_path in sorted(skills_dir.glob("*/SKILL.md")):
        slug = skill_path.parent.name.strip()
        if not slug:
            continue
        try:
            rel_path = str(skill_path.relative_to(REPO_ROOT))
        except ValueError:
            rel_path = str(skill_path)
        try:
            content = skill_path.read_text(encoding="utf-8")
        except OSError:
            continue
        skills.append(
            {
                "slug": slug,
                "source_path": rel_path,
                "content": content,
            }
        )
    return skills


def _json_request(
    base_url: str,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    api_key: str = "",
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                time.sleep(min(4.0, 0.5 * (2**attempt)))
                continue
            raise


def fetch_approved_skills(base_url: str, *, api_key: str = "") -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "include_pending": "true",
            "_": str(time.time_ns()),
        }
    )
    payload = _json_request(
        base_url,
        f"/skills?{query}",
        api_key=api_key,
    )
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict) and str(item.get("status", "")).strip().lower() == "approved"]
    return []


def sync_skills(
    base_url: str,
    local_skills: Iterable[Dict[str, str]],
    *,
    api_key: str,
    managed_by: str,
    approved_skills: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    approved_paths = {
        str(item.get("source_path", "")).strip()
        for item in approved_skills
        if isinstance(item, dict) and str(item.get("source_path", "")).strip()
    }
    imported: List[str] = []
    approved: List[str] = []
    for skill in local_skills:
        if skill["source_path"] in approved_paths:
            continue
        record = _json_request(
            base_url,
            "/skills/import",
            payload={
                "slug": skill["slug"],
                "content": skill["content"],
                "source_path": skill["source_path"],
                "managed_by": managed_by,
            },
            api_key=api_key,
        )
        approved_slug = str((record or {}).get("slug", "") or skill["slug"]).strip() or skill["slug"]
        imported.append(approved_slug)
        _json_request(
            base_url,
            "/api/v1/admin/approve",
            payload={
                "resource": "skill",
                "slug": approved_slug,
                "status": "approved",
            },
            api_key=api_key,
        )
        approved.append(approved_slug)
    return {
        "imported": imported,
        "approved": approved,
    }


def compare_registry(local_skills: Iterable[Dict[str, str]], approved_skills: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    local_map = {item["source_path"]: item for item in local_skills}
    approved_map = {
        str(item.get("source_path", "")).strip(): item
        for item in approved_skills
        if str(item.get("source_path", "")).strip()
    }

    missing_in_aidb = sorted(local_map[path]["slug"] for path in local_map if path not in approved_map)
    extra_in_aidb = sorted(str(approved_map[path].get("slug", "")).strip() for path in approved_map if path not in local_map)
    path_mismatches = []
    local_by_slug = {item["slug"]: item for item in local_skills}
    approved_by_slug = {
        str(item.get("slug", "")).strip(): item
        for item in approved_skills
        if str(item.get("slug", "")).strip()
    }
    for slug, item in local_by_slug.items():
        remote = approved_by_slug.get(slug)
        if not remote:
            continue
        remote_path = str(remote.get("source_path", "") or "").strip()
        if remote_path and remote_path != item["source_path"] and remote_path in local_map:
            path_mismatches.append(
                {
                    "slug": slug,
                    "local_source_path": item["source_path"],
                    "aidb_source_path": remote_path,
                }
            )

    return {
        "available": True,
        "local_skill_count": len(local_map),
        "approved_skill_count": len(approved_map),
        "missing_in_aidb": missing_in_aidb,
        "extra_in_aidb": extra_in_aidb,
        "path_mismatches": path_mismatches,
        "healthy": not missing_in_aidb and not path_mismatches,
    }


def render_text(report: Dict[str, Any]) -> str:
    lines = [
        "Shared skill registry sync",
        f"  local skills: {report.get('local_skill_count', 0)}",
        f"  approved in aidb: {report.get('approved_skill_count', 0)}",
        f"  healthy: {'yes' if report.get('healthy') else 'no'}",
    ]
    imported = report.get("imported") or []
    if imported:
        lines.append(f"  imported: {len(imported)}")
    approved = report.get("approved") or []
    if approved:
        lines.append(f"  approved this run: {len(approved)}")
    missing = report.get("missing_in_aidb") or []
    if missing:
        lines.append(f"  missing in aidb: {', '.join(missing[:8])}")
    mismatches = report.get("path_mismatches") or []
    if mismatches:
        lines.append(f"  source-path mismatches: {len(mismatches)}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    api_key = read_api_key(args.api_key_file)
    skills_dir = Path(args.skills_dir).expanduser()
    local_skills = list_local_skills(skills_dir)
    report: Dict[str, Any]
    try:
        approved_skills = fetch_approved_skills(args.aidb_url, api_key=api_key)
        if not args.check:
            sync_result = sync_skills(
                args.aidb_url,
                local_skills,
                api_key=api_key,
                managed_by=args.managed_by,
                approved_skills=approved_skills,
            )
        else:
            sync_result = {"imported": [], "approved": []}
        approved_skills = fetch_approved_skills(args.aidb_url, api_key=api_key)
        report = compare_registry(local_skills, approved_skills) | sync_result
        report["mode"] = "check" if args.check else "sync"
        report["skills_dir"] = str(skills_dir)
        report["aidb_url"] = args.aidb_url
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        report = {
            "available": False,
            "mode": "check" if args.check else "sync",
            "skills_dir": str(skills_dir),
            "aidb_url": args.aidb_url,
            "error": f"http {exc.code}",
            "detail": detail[:400],
        }
    except Exception as exc:  # noqa: BLE001
        report = {
            "available": False,
            "mode": "check" if args.check else "sync",
            "skills_dir": str(skills_dir),
            "aidb_url": args.aidb_url,
            "error": str(exc),
        }

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report.get("healthy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
