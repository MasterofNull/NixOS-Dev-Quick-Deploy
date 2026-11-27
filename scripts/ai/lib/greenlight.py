"""Isolated staged-tree validation and private, exact-content greenlight records."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Any

VERSION = "1.0"
DEFAULT_GATES = {
    "tier0_pre_commit": "./scripts/governance/tier0-validation-gate.sh --pre-commit",
    "ci_test_coverage": "bash scripts/governance/tier0.d/check-ci-test-coverage.sh",
}


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.rstrip("\n")


def dirty(root: Path) -> bool:
    entries = git(root, "status", "--porcelain=v1", "-z").split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        if entry and (entry.startswith("??") or entry[1] != " "):
            return True
        index += 2 if entry and entry[0] in "RC" else 1
    return False


def result(code: int, detail: str) -> dict[str, Any]:
    return {"status": "PASS" if code == 0 else "FAIL", "exit_code": code, "detail": detail}


def evidence(root: Path) -> dict[str, Any]:
    paths = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0")
    failures: list[str] = []
    for name in paths:
        if name.startswith("docs/harness-first/evidence/") and name.endswith(".md"):
            content = (root / name).read_text()
            missing = [f"## {n}" for n in range(1, 9)
                       if not re.search(rf"^## {n}(?:[.)]|\s|$)", content, re.M)]
            if missing:
                failures.append(f"{name}: missing {', '.join(missing)}")
    return result(int(bool(failures)), "\n".join(failures) or "All eight evidence sections present")


def body_check(body: str) -> dict[str, Any]:
    headings = ["## Details", "## What", "## How", "## Why"]
    found = [re.search(rf"^{re.escape(h)}[ \t]*$", body, re.M) for h in headings]
    missing = [h for h, match in zip(headings, found, strict=True) if match is None]
    positions = [match.start() for match in found if match is not None]
    detail = "Missing " + ", ".join(missing) if missing else "Headings must be in order"
    return result(int(bool(missing) or positions != sorted(positions)),
                  detail if missing or positions != sorted(positions) else "PR body headings present in order")


def state_path(root: Path, state_dir: str | None, branch: str, tree: str) -> Path:
    directory = Path(state_dir or os.environ.get("AQ_GREENLIGHT_DIR") or
                     str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) /
                         "aq/greenlight")).expanduser().resolve()
    if directory.is_relative_to(root):
        raise ValueError("Greenlight state directory must be outside the worktree")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory / f"{quote(branch, safe='')}-{tree}.json"


def save(path: Path, record: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix=".greenlight-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(record, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(worktree: Path, *, base_ref: str = "origin/main", state_dir: str | None = None,
        overrides: dict[str, str] | None = None, body: str | None = None,
        mode: str = "run") -> dict[str, Any]:
    root = Path(git(worktree, "rev-parse", "--show-toplevel"))
    # git status output must retain its leading index-column space.
    if dirty(root):
        raise ValueError("Refusing unstaged tracked modifications or untracked non-ignored files")
    tree = git(root, "write-tree")
    parent = git(root, "rev-parse", "HEAD")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    main = git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    path = state_path(root, state_dir, branch, tree)
    if mode != "run":
        record: dict[str, Any] = json.loads(path.read_text())
        if (record.get("schema"), record.get("branch"), record.get("staged_tree_sha"),
            record.get("parent_sha"), record.get("main_sha")) != (1, branch, tree, parent, main):
            raise ValueError("Greenlight record does not match exact tree, parent, branch and base")
        return record
    commands = DEFAULT_GATES | (overrides or {})
    unknown = commands.keys() - DEFAULT_GATES.keys()
    if unknown:
        raise ValueError(f"Unknown gate override: {sorted(unknown)}")
    gates = ["tier0_pre_commit", "evidence_sections", "ci_test_coverage"]
    if body is not None:
        gates.append("pr_body_format")
    results: dict[str, Any] = {}
    record = dict(schema=1, branch=branch, staged_tree_sha=tree, parent_sha=parent,
                  main_sha=main, merged_tree_sha=None, gate_list=gates, results=results,
                  passed=False, tool_version=VERSION, at=datetime.now(timezone.utc).isoformat())
    with tempfile.TemporaryDirectory(prefix="aq-greenlight-") as temporary:
        target = Path(temporary) / "worktree"
        added = False
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "-c", "user.name=aq-greenlight", "-c",
                 "user.email=aq-greenlight@localhost", "commit-tree", tree, "-p", parent],
                input="aq-greenlight isolated snapshot\n", text=True, capture_output=True, check=True,
            ).stdout.strip()
            git(root, "worktree", "add", "--detach", str(target), commit)
            added = True
            merge = subprocess.run(
                ["git", "-C", str(target), "-c", "user.name=aq-greenlight", "-c",
                 "user.email=aq-greenlight@localhost", "-c", "commit.gpgSign=false",
                 "-c", "core.hooksPath=/dev/null", "merge", "--no-edit", "--no-ff", main],
                capture_output=True, text=True,
            )
            if merge.returncode:
                conflicts = git(target, "diff", "--name-only", "--diff-filter=U")
                results["merge"] = result(merge.returncode, conflicts or merge.stdout + merge.stderr)
            else:
                record["merged_tree_sha"] = git(target, "write-tree")
                git(target, "reset", "--soft", main)
                for gate in gates:
                    if gate == "evidence_sections":
                        results[gate] = evidence(target)
                    elif gate == "pr_body_format":
                        results[gate] = body_check(body or "")
                    elif (gate == "ci_test_coverage" and gate not in (overrides or {}) and
                          not (target / "scripts/governance/tier0.d/check-ci-test-coverage.sh").exists()):
                        results[gate] = {"status": "SKIP", "exit_code": 0, "detail": "Gate not present"}
                    else:
                        process = subprocess.run(shlex.split(commands[gate]), cwd=target,
                                                 capture_output=True, text=True)
                        results[gate] = result(process.returncode, process.stdout + process.stderr)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            results["runner"] = result(1, str(exc))
        finally:
            if added:
                try:
                    git(root, "worktree", "remove", "--force", str(target))
                except subprocess.CalledProcessError as exc:
                    results["cleanup"] = result(1, str(exc))
            record["passed"] = bool(results) and all(r["exit_code"] == 0 for r in results.values())
            save(path, record)
    return record
