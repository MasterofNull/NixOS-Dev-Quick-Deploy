#!/usr/bin/env python3
"""Portable GitHub CD policy checker (stdlib only, no network).

Enforces ECC P2 approval-gated CD requirements:
- Environment approvals (job-level environment binding).
- Concurrency serialization (cancel-in-progress: false).
- Pinned actions (immutable 40-hex SHA).
- Least privilege (workflow contents: read, no write-all).
- No untrusted PR triggers (workflow_dispatch, release, or push only).
- Artifact digest/provenance verification step.
- Rollback plan / handler on failure.

Two-axis verdict: LOCAL axis (LOCAL_READY / LOCAL_BLOCKED / NOT_INSTALLED) derived from disk;
REMOTE axis is always UNVERIFIED_REMOTE because nothing here contacts GitHub.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

MARKER = "# factory-gate-cd-pack v1"
WORKFLOW = Path(".github/workflows/factory-cd.yml")
SHA = re.compile(r"@[0-9a-f]{40}(?:\s|$)")
DOCKER_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}(?:\s|$)")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
REMOTE = "UNVERIFIED_REMOTE"


def _strip(line: str) -> str:
    return line.split("  #", 1)[0] if "  #" in line else line


def audit_text(text: str, name: str = "workflow") -> list[dict[str, str]]:
    """Return CD policy findings; severity 'violation' blocks, 'review' is advisory."""
    findings: list[dict[str, str]] = []
    lines = text.splitlines()

    def add(severity: str, rule: str, line_no: int, detail: str) -> None:
        findings.append({"severity": severity, "rule": rule, "file": name, "line": str(line_no), "detail": detail})

    top_permissions = None
    in_top_perm = False
    in_on = False
    has_environment = False
    has_concurrency = False
    cancel_in_progress_true = False
    has_rollback_step = False
    has_artifact_verification = False

    for number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        code = _strip(raw)

        # Check action pins
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

        # Track on: triggers and check forbidden triggers
        if indent == 0:
            if re.match(r"on\s*:", stripped):
                in_on = True
            else:
                in_on = False

        if re.search(r"\bpull_request_target\b", code):
            add("violation", "pull-request-target", number, "pull_request_target forbidden in CD workflow")
        elif in_on and re.search(r"\bpull_request\b", code):
            add("violation", "untrusted-pr-trigger", number, "CD workflow must not trigger on pull_request")

        # Environment check
        if re.search(r"^\s*environment\s*:", raw):
            has_environment = True

        # Concurrency check
        if re.search(r"^\s*concurrency\s*:", raw):
            has_concurrency = True
        if re.search(r"cancel-in-progress\s*:\s*true\b", code, re.IGNORECASE):
            cancel_in_progress_true = True
        elif re.search(r"cancel-in-progress\s*:\s*false\b", code, re.IGNORECASE):
            has_concurrency = True

        # Rollback check
        if "rollback" in code.lower() or ("if:" in code and "failure()" in code):
            has_rollback_step = True

        # Artifact digest / verification check
        if "artifact_digest" in code or "sha256sum" in code or "evidence" in code.lower() or "gate-runner" in code:
            has_artifact_verification = True

        # Permissions checks
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

    if top_permissions is None:
        add("violation", "missing-permissions", 1, "no workflow-level permissions block (token defaults too broad)")
    if not has_environment:
        add("violation", "missing-environment", 1, "CD workflow lacks environment protection binding")
    if not has_concurrency:
        add("violation", "missing-concurrency", 1, "CD workflow lacks concurrency serialization block")
    if cancel_in_progress_true:
        add("violation", "cancel-in-progress-true", 1, "CD workflow has cancel-in-progress: true (deployments must serialize without aborting)")
    if not has_rollback_step:
        add("violation", "missing-rollback", 1, "CD workflow lacks on-failure rollback plan/step")
    if not has_artifact_verification:
        add("violation", "missing-artifact-verification", 1, "CD workflow lacks artifact digest or pre-flight verification step")

    return findings


def audit_repo(repo: Path) -> dict[str, list[dict[str, str]]]:
    workflows_dir = repo / ".github" / "workflows"
    files = sorted(p for p in workflows_dir.glob("*.y*ml") if p.is_file() and not p.is_symlink()) if workflows_dir.is_dir() else []
    per_file: dict[str, list[dict[str, str]]] = {}
    for path in files:
        # Scan if named factory-cd or contains cd marker or cd in filename
        content = path.read_text(encoding="utf-8", errors="replace")
        if path.name == "factory-cd.yml" or MARKER in content or "-cd" in path.name.lower():
            per_file[str(path.relative_to(repo))] = audit_text(content, str(path.relative_to(repo)))
    return per_file


def _is_pack_workflow(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return bool(lines and lines[0].startswith("# factory-gate-"))
    except OSError:
        return False


def check(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    owned = repo / WORKFLOW
    per_file = audit_repo(repo)
    foreign = {name: items for name, items in per_file.items() if name != str(WORKFLOW) and not _is_pack_workflow(repo / name)}
    foreign_violations = sum(1 for items in foreign.values() for i in items if i["severity"] == "violation")
    result: dict[str, Any] = {
        "remote": REMOTE,
        "remote_detail": "no network evidence collected; environment approvals and production deployments require explicit owner authority",
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
    """Bounded read-only projection for QA/dashboard: template readiness plus repo CD state."""
    try:
        template = (bundle or Path(__file__).resolve().parent.parent) / "ci" / "factory-cd.yml.tmpl"
        text = template.read_text(encoding="utf-8")
        rendered = re.sub(r"\{\{([A-Z0-9_]+)\}\}", "scripts/governance/gate-runner", text)
        violations = [f for f in audit_text(rendered, "factory-cd.yml.tmpl") if f["severity"] == "violation"]
        marker_ok = rendered.startswith(MARKER)
        has_env = "environment:" in rendered
        has_rb = "rollback" in rendered.lower() or "failure()" in rendered
        local = "LOCAL_READY" if marker_ok and not violations else "LOCAL_BLOCKED"
        return {
            "available": True,
            "verdict": local,
            "remote": REMOTE,
            "template_violations": len(violations),
            "environment_configured": has_env,
            "rollback_configured": has_rb,
            "status": "unverified-remote" if local == "LOCAL_READY" else "blocked",
        }
    except (OSError, ValueError) as exc:
        return {
            "available": False,
            "verdict": "UNVERIFIED",
            "remote": REMOTE,
            "status": "unverified",
            "reason": f"cd_pack_unavailable:{type(exc).__name__}",
        }


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2 or args[0] != "check":
        print("usage: cd_policy.py check <repo> [--json]", file=sys.stderr)
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
