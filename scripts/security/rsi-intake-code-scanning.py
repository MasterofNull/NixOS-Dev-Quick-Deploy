#!/usr/bin/env python3
"""Bridge GitHub code-scanning alerts into RSI incident ledger.

Ingests code-scanning alerts from GitHub, groups by vulnerability class,
and records incidents for the RSI dispatcher to handle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Inject lib path for rsi_lifecycle
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB = _REPO_ROOT / "scripts" / "ai" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

try:
    import rsi_lifecycle
except ImportError as exc:
    print(f"Failed to import rsi_lifecycle: {exc}", file=sys.stderr)
    sys.exit(2)


def _parse_semver_tuple(version_str: str) -> tuple[int, ...]:
    """Parse semantic version into comparable tuple of integers.

    Ignores non-numeric suffixes (e.g., '1.2.3-rc1' -> (1, 2, 3)).
    Returns empty tuple on parse error.
    """
    if not version_str or not isinstance(version_str, str):
        return ()
    # Extract leading numeric segments separated by dots
    match = re.match(r"^(\d+(?:\.\d+)*)", version_str.strip())
    if not match:
        return ()
    try:
        return tuple(int(p) for p in match.group(1).split("."))
    except (ValueError, AttributeError):
        return ()


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Return 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    t1, t2 = _parse_semver_tuple(v1), _parse_semver_tuple(v2)
    if not t1 or not t2:
        return 0
    if t1 > t2:
        return 1
    elif t1 < t2:
        return -1
    return 0


def _max_version(versions: list[str]) -> str:
    """Return the maximum version from a list."""
    if not versions:
        return "unknown"
    versions = [v for v in versions if v and v.strip()]
    if not versions:
        return "unknown"
    max_v = versions[0]
    for v in versions[1:]:
        if _compare_versions(v, max_v) > 0:
            max_v = v
    return max_v


NIX_CLOSURE_CATEGORY = "nix-closure"
NIX_CLOSURE_MANIFEST = "nix/"


def _is_nix_closure(category: str) -> bool:
    return category == NIX_CLOSURE_CATEGORY


def _resolve_manifest_path(category: str, package: str) -> str:
    """Resolve manifest path for a package in a given category.

    Category "nix-closure" (Nix system-closure scan) always maps to nix/: the fix
    is a nixpkgs bump (flake.lock) or fast-lane promotion, not a manifest edit.

    For category "trivy-custom-<svc>", checks:
    1. ai-stack/mcp-servers/<svc>/requirements.txt (if package present)
    2. ai-stack/mcp-servers/<svc>/Dockerfile
    3. .github/workflows/security.yml
    """
    if _is_nix_closure(category):
        return NIX_CLOSURE_MANIFEST

    # Legacy container-image categories (kept while old alerts age out).
    # Try to extract service name from category like "trivy-custom-nixos-docs"
    if category.startswith("trivy-custom-"):
        svc = category.replace("trivy-custom-", "")

        # Check requirements.txt
        req_path = _REPO_ROOT / "ai-stack" / "mcp-servers" / svc / "requirements.txt"
        if req_path.exists():
            try:
                content = req_path.read_text(encoding="utf-8", errors="ignore")
                # Case-insensitive, treat - and _ as equal for matching
                pkg_pattern = re.compile(re.escape(package).replace("-", "[-_]"), re.IGNORECASE)
                if pkg_pattern.search(content):
                    return str(req_path.relative_to(_REPO_ROOT))
            except OSError:
                pass

        # Check Dockerfile
        docker_path = _REPO_ROOT / "ai-stack" / "mcp-servers" / svc / "Dockerfile"
        if docker_path.exists():
            return str(docker_path.relative_to(_REPO_ROOT))

    # Fallback
    return ".github/workflows/security.yml"


def _parse_alert_message(text: str) -> dict[str, str]:
    """Extract Package, Installed Version, Fixed Version from alert text."""
    result = {}
    # grype SARIF (nix-closure): "A high vulnerability in nix package: <pkg>, version <ver> was found [...]"
    grype = re.search(r"package:\s*(\S+?),\s*version\s+(\S+)\s+was found", text or "")
    if grype:
        result["package"], result["installed"] = grype.group(1), grype.group(2)
        fix = re.search(r"[Ff]ix(?:ed)?(?: [Vv]ersion| in)?:?\s*([0-9][^\s,]*)", text or "")
        if fix:
            result["fixed"] = fix.group(1)
        return result
    for line in (text or "").split("\n"):
        if "Package:" in line:
            result["package"] = line.split("Package:")[-1].strip()
        elif "Installed Version:" in line:
            result["installed"] = line.split("Installed Version:")[-1].strip()
        elif "Fixed Version:" in line:
            result["fixed"] = line.split("Fixed Version:")[-1].strip()
    return result


class AlertSourceError(RuntimeError):
    """Alert source unreadable; distinct from a successful read with zero alerts."""


def _fetch_alerts_from_github(state: str = "open") -> list[dict[str, Any]]:
    """Fetch alerts from GitHub API using gh; state="" returns every state (used to verify closure)."""
    query = f"state={state}&per_page=100" if state else "per_page=100"
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", "--slurp",
             f"repos/{{owner}}/{{repo}}/code-scanning/alerts?{query}"],
            capture_output=True, text=True, check=False, cwd=_REPO_ROOT, timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise AlertSourceError(f"gh api unavailable: {exc}") from exc
    if result.returncode != 0:
        raise AlertSourceError(f"gh api failed: {result.stderr.strip()[:300]}")
    try:
        pages = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AlertSourceError(f"gh api output is not JSON: {exc}") from exc
    return [alert for page in pages if isinstance(page, list) for alert in page]


def _load_alerts(path: str) -> list[dict[str, Any]]:
    """Load alerts exported by export-github-code-scanning-alerts.sh."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise AlertSourceError(f"failed to load alerts from {path}: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("alerts"), list):
        return data["alerts"]
    if isinstance(data, list):
        return data
    raise AlertSourceError(f"unexpected alert format in {path}")


_SEVERITY_ALIASES = {"note": "low", "info": "low", "none": "low", "warning": "medium", "error": "high"}


def _normalize_severity(sev: str) -> str:
    """Map code-scanning levels (note/warning/error) onto the ledger's low..critical scale."""
    sev = str(sev or "medium").strip().lower()
    return _SEVERITY_ALIASES.get(sev, sev if sev in {"low", "medium", "high", "critical"} else "medium")


def _severity_order(sev: str) -> int:
    """Return sort order for severity (higher = worse)."""
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return order.get(sev, 2)


def _max_severity(severities: list[str]) -> str:
    """Return the worst severity from a list."""
    if not severities:
        return "medium"
    return max(severities, key=_severity_order)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bridge GitHub code-scanning alerts into RSI incident ledger"
    )
    parser.add_argument("--alerts", help="Path to alerts JSON file")
    parser.add_argument("--fetch", action="store_true", help="Fetch alerts from GitHub API")
    parser.add_argument("--dry-run", action="store_true", help="Print planned incidents; do not record")
    args = parser.parse_args()

    # Determine alert source
    try:
        alerts = _fetch_alerts_from_github() if args.fetch else None
    except AlertSourceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if alerts is None:
        # Default path if --alerts not provided
        if not args.alerts:
            default_dir = os.environ.get(
                "AI_SECURITY_AUDIT_DIR",
                str(Path.home() / ".local" / "share" / "nixos-ai-stack" / "security")
            )
            args.alerts = str(Path(default_dir) / "github-code-scanning-alerts.json")

        try:
            alerts = _load_alerts(args.alerts)
        except AlertSourceError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    if not alerts:
        print(json.dumps({"groups": 0, "recorded": 0, "dry_run": args.dry_run}))
        return 0

    # Filter for open alerts only
    open_alerts = [a for a in alerts if isinstance(a, dict) and a.get("state") == "open"]

    # Group by (category, package, installed_version)
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}

    for alert in open_alerts:
        # Extract category
        most_recent = alert.get("most_recent_instance") or {}
        category = most_recent.get("category", "unknown")

        # Parse message
        msg_text = most_recent.get("message", {}).get("text", "")
        parsed = _parse_alert_message(msg_text)
        package = parsed.get("package", "unknown")
        installed = parsed.get("installed", "unknown")

        # Extract severity
        rule = alert.get("rule") or {}
        severity = rule.get("security_severity_level") or rule.get("severity") or "medium"

        # Extract fixed version
        fixed = parsed.get("fixed", "")

        # Group key
        key = (category, package, installed)

        if key not in groups:
            groups[key] = {
                "category": category,
                "package": package,
                "installed": installed,
                "severities": [],
                "fixed_versions": [],
                "alert_count": 0,
            }

        groups[key]["severities"].append(_normalize_severity(severity))
        if fixed and fixed.strip():
            # Handle comma-separated fixed versions
            for v in fixed.split(","):
                v = v.strip()
                if v:
                    groups[key]["fixed_versions"].append(v)
        groups[key]["alert_count"] += 1

    # Cap at 50 groups
    if len(groups) > 50:
        print(f"Alert groups ({len(groups)}) exceed cap of 50; truncating", file=sys.stderr)
        groups = dict(list(groups.items())[:50])

    # Prepare incidents
    incidents_planned = []
    recorded = 0

    for (category, package, installed), group_data in groups.items():
        max_sev = _max_severity(group_data["severities"])
        fixed_ver = _max_version(group_data["fixed_versions"])
        count = group_data["alert_count"]

        # Truncate fields
        category = category[:300]
        package = package[:300]
        installed = installed[:300]
        fixed_ver = fixed_ver[:300]

        # Build os_error (identity = category/producer + manifest path + package + installed version)
        os_error = f"{package} {installed} vulnerable"

        # Build root_fix (includes fixed version, count and severity)
        manifest = _resolve_manifest_path(category, package)
        if _is_nix_closure(category):
            target_ver = f">={fixed_ver}" if fixed_ver != "unknown" else " (patched revision)"
            root_fix = f"nix flake update / fast-lane promotion: pull a nixpkgs revision with {package}{target_ver} (flake.lock at repo root), rebuild hyperd-ai-dev, and confirm the nix-closure scan clears the alerts ({count} open alert(s), max severity {max_sev})"
        else:
            root_fix = f"raise the minimum-version floor: {package}>={fixed_ver} in {manifest} (owner policy: floors, never exact == pins); rebuild image and confirm Trivy clears the alerts ({count} open alert(s), max severity {max_sev})"

        subject = f"code-scanning:{category}"

        incident = {
            "subject": subject,
            "category": category,
            "package": package,
            "installed": installed,
            "fixed": fixed_ver,
            "severity": max_sev,
            "alert_count": count,
            "manifest": manifest,
            "os_error": os_error,
            "root_fix": root_fix,
        }
        incidents_planned.append(incident)

        if not args.dry_run:
            try:
                rsi_lifecycle.failure(
                    agent="security-intake",
                    subject=subject,
                    producer=f"github-code-scanning:{category}",
                    path=manifest,
                    authority="grype" if _is_nix_closure(category) else "trivy",
                    os_error=os_error,
                    severity=max_sev,
                    root_fix=root_fix,
                )
                recorded += 1
            except (ValueError, OSError) as exc:
                print(f"Failed to record incident {subject}: {exc}", file=sys.stderr)
                return 2

    # Print planned incidents JSON for --dry-run
    if args.dry_run:
        print(json.dumps(incidents_planned))

    # Print summary
    print(json.dumps({
        "groups": len(groups),
        "recorded": recorded,
        "dry_run": args.dry_run,
    }))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
