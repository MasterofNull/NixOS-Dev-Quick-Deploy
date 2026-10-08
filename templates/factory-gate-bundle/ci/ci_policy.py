#!/usr/bin/env python3
"""Portable GitHub CI policy checker (stdlib only, no network).

Verdict vocabulary is deliberately two-axis: the LOCAL axis (LOCAL_READY /
LOCAL_BLOCKED / NOT_INSTALLED) is derived from files on disk; the REMOTE axis is
always UNVERIFIED_REMOTE because nothing here may contact GitHub. A local verdict
never implies that remote CI, rulesets, or required checks pass.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

MARKER = "# factory-gate-ci-pack v1"
WORKFLOW = Path(".github/workflows/factory-gate.yml")
SHA = re.compile(r"@[0-9a-f]{40}(?:\s|$)")
DOCKER_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}(?:\s|$)")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
FORK_GUARD = re.compile(r"head\.repo\.fork|fork\s*==\s*false|event_name\s*!=\s*'pull_request'")
REMOTE = "UNVERIFIED_REMOTE"


def _strip(line: str) -> str:
    return line.split("  #", 1)[0] if "  #" in line else line


def audit_text(text: str, name: str = "workflow") -> list[dict[str, str]]:
    """Return findings; severity 'violation' blocks the factory-owned workflow, 'review' is advisory."""
    findings: list[dict[str, str]] = []
    lines = text.splitlines()

    def add(severity: str, rule: str, line_no: int, detail: str) -> None:
        findings.append({"severity": severity, "rule": rule, "file": name, "line": str(line_no), "detail": detail})

    top_permissions = None
    in_top_perm = False
    for number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        code = _strip(raw)
        match = USES.match(code)
        if match:
            ref = match.group(1) + match.group(2)
            target = match.group(1)
            if target.startswith("./"):
                pass
            elif target.startswith("docker://"):
                if not DOCKER_DIGEST.search(ref + " "):
                    add("violation", "unpinned-action", number, f"{target} lacks an @sha256 digest")
            elif not SHA.search(ref + " "):
                add("violation", "unpinned-action", number, f"{target} is not pinned to a 40-hex commit SHA")
        if re.search(r"\bpull_request_target\b", code):
            add("violation", "pull-request-target", number, "pull_request_target runs untrusted code with secrets")
        if indent == 0:
            in_top_perm = False
            if re.match(r"permissions\s*:", stripped):
                rest = stripped.split(":", 1)[1].strip()
                top_permissions = rest or "block"
                if rest == "write-all":
                    add("violation", "permissions-write-all", number, "workflow-level write-all")
                in_top_perm = rest == ""
            continue
        if in_top_perm and re.match(r"[a-z-]+\s*:\s*write\b", stripped):
            add("violation", "top-level-write", number, f"workflow-level {stripped}")
        if re.match(r"permissions\s*:\s*write-all", stripped):
            add("violation", "permissions-write-all", number, "write-all permissions")
        for secret in re.findall(r"secrets\.([A-Za-z0-9_]+)", code):
            if secret != "GITHUB_TOKEN" and not FORK_GUARD.search(code):
                add("review", "secret-reference", number, f"secrets.{secret} is unavailable to fork PRs; guard or document")
        if re.match(r"[a-z-]+\s*:\s*write\b", stripped) and indent > 2 and not in_top_perm:
            add("review", "job-write-permission", number, f"elevated job/step permission {stripped}")
    if top_permissions is None:
        add("violation", "missing-permissions", 1, "no workflow-level permissions block (token defaults are too broad)")
    return findings


def audit_repo(repo: Path) -> dict[str, Any]:
    workflows_dir = repo / ".github" / "workflows"
    files = sorted(p for p in workflows_dir.glob("*.y*ml") if p.is_file() and not p.is_symlink()) if workflows_dir.is_dir() else []
    per_file: dict[str, list[dict[str, str]]] = {}
    for path in files:
        per_file[str(path.relative_to(repo))] = audit_text(path.read_text(encoding="utf-8", errors="replace"), str(path.relative_to(repo)))
    return per_file


def check(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    owned = repo / WORKFLOW
    per_file = audit_repo(repo)
    foreign = {name: items for name, items in per_file.items() if name != str(WORKFLOW)}
    foreign_violations = sum(1 for items in foreign.values() for i in items if i["severity"] == "violation")
    result: dict[str, Any] = {
        "remote": REMOTE,
        "remote_detail": "no network evidence is collected here; required checks/rulesets are unverified",
        "workflows_scanned": len(per_file),
        "foreign_workflows": len(foreign),
        "foreign_violations": foreign_violations,
        "foreign_preserved": True,
        "findings": [],
    }
    if not owned.is_file() or owned.is_symlink():
        result.update(verdict="NOT_INSTALLED", detail=f"{WORKFLOW} missing")
    elif MARKER not in owned.read_text(encoding="utf-8", errors="replace").splitlines()[:1]:
        result.update(verdict="NOT_INSTALLED",
                      detail=f"{WORKFLOW} exists but is project-owned (no pack marker); preserved, not evaluated as the pack")
    else:
        own = per_file.get(str(WORKFLOW), [])
        result["findings"] = own
        blocking = [f for f in own if f["severity"] == "violation"]
        result.update(verdict="LOCAL_BLOCKED" if blocking else "LOCAL_READY",
                      detail=f"{len(blocking)} violation(s) in {WORKFLOW}")
    result["display"] = f"{result['verdict']} / {REMOTE}"
    return result


def health_summary(repo: Path, bundle: Path | None = None) -> dict[str, Any]:
    """Bounded read-only projection for QA/dashboard: template readiness plus the host repo's own workflows."""
    try:
        template = (bundle or Path(__file__).resolve().parent.parent) / "ci" / "factory-gate.yml.tmpl"
        text = template.read_text(encoding="utf-8")
        rendered = re.sub(r"\{\{([A-Z0-9_]+)\}\}", "scripts/governance/gate-runner", text)
        violations = [f for f in audit_text(rendered, "factory-gate.yml.tmpl") if f["severity"] == "violation"]
        marker_ok = rendered.startswith(MARKER)
        scan = audit_repo(Path(repo))
        unpinned = sum(1 for items in scan.values() for i in items if i["rule"] == "unpinned-action")
        local = "LOCAL_READY" if marker_ok and not violations else "LOCAL_BLOCKED"
        return {"available": True, "verdict": local, "remote": REMOTE, "template_violations": len(violations),
                "workflows_scanned": len(scan), "unpinned_actions": unpinned,
                "status": "unverified-remote" if local == "LOCAL_READY" else "blocked"}
    except (OSError, ValueError) as exc:
        return {"available": False, "verdict": "UNVERIFIED", "remote": REMOTE, "status": "unverified",
                "reason": f"ci_pack_unavailable:{type(exc).__name__}"}


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2 or args[0] != "check":
        print("usage: ci_policy.py check <repo> [--json]", file=sys.stderr)
        return 2
    report = check(Path(args[1]))
    if "--json" in argv:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["display"])
        for item in report["findings"]:
            print(f"  {item['severity']}: {item['file']}:{item['line']} {item['rule']} - {item['detail']}")
    return {"LOCAL_READY": 0, "LOCAL_BLOCKED": 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
