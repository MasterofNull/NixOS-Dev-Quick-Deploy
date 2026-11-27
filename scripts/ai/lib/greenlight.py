"""Isolated staged-tree validation and private, exact-content greenlight records."""
from __future__ import annotations

import hashlib
import importlib.util
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
CANONICAL_EVIDENCE_SECTIONS = [
    "## Objective", "## Workflow/Session IDs", "## Delegation Decision",
    "## Commands Executed", "## Validation Evidence", "## Rollback Plan",
    "## Residual Risk", "## Hint Feedback",
]


def clean_git_env() -> dict[str, str]:
    # Match governance clean_git_env.py, including Git's superproject locator.
    locators = {
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX",
        "GIT_SUPER_PREFIX", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES",
    }
    return {key: value for key, value in os.environ.items() if key not in locators}

DEFAULT_GATES = {
    "tier0_pre_commit": "./scripts/governance/tier0-validation-gate.sh --pre-commit",
    "ci_test_coverage": "bash scripts/governance/tier0.d/check-ci-test-coverage.sh",
}


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True, env=clean_git_env()).stdout.rstrip("\n")


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
    policy_path = root / "config/harness-first-policy.json"
    headings = CANONICAL_EVIDENCE_SECTIONS
    if policy_path.exists():
        policy = json.loads(policy_path.read_text())
        configured = policy.get("required_evidence_sections") if isinstance(policy, dict) else None
        if configured is not None:
            if (not isinstance(configured, list) or not configured or
                    not all(isinstance(heading, str) for heading in configured)):
                raise ValueError("required_evidence_sections must be a non-empty list of headings")
            headings = configured
    failures: list[str] = []
    for name in paths:
        if name.startswith("docs/harness-first/evidence/") and name.endswith(".md"):
            content = (root / name).read_text()
            missing = [heading for heading in headings
                       if not re.search(rf"^{re.escape(heading)}[ \t]*$", content, re.M)]
            if missing:
                failures.append(f"{name}: missing {', '.join(missing)}")
    return result(int(bool(failures)), "\n".join(failures) or "All eight evidence sections present")


def body_check(body: str) -> dict[str, Any]:
    checker = Path(__file__).resolve().parents[2] / "governance/check-pr-body-format.py"
    spec = importlib.util.spec_from_file_location("greenlight_pr_body_format", checker)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load shared PR body validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = module.problems(body)
    return result(int(bool(errors)), "\n".join(errors) or "PR body format OK")


def state_path(root: Path, state_dir: str | None, branch: str, tree: str) -> Path:
    directory = Path(state_dir or os.environ.get("AQ_GREENLIGHT_DIR") or
                     str(Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")) /
                         "aq/greenlight")).expanduser().resolve()
    if directory.is_relative_to(root):
        raise ValueError("Greenlight state directory must be outside the worktree")
    return directory / f"{quote(branch, safe='')}-{tree}.json"


def save(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
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


def _passed_entry(entry: Any) -> bool:
    return (isinstance(entry, dict) and entry.get("status") == "PASS" and
            type(entry.get("exit_code")) is int and entry["exit_code"] == 0)


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
    gates = ["tier0_pre_commit", "evidence_sections", "ci_test_coverage"]
    # `body` is the --body-file text, not a path; the digest covers the text the validator sees.
    body_sha256 = None
    if body is not None:
        gates.append("pr_body_format")
        body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if mode != "run":
        record: dict[str, Any] = json.loads(path.read_text())
        if (not isinstance(record, dict) or not isinstance(record.get("passed"), bool) or
                not isinstance(record.get("results"), dict)):
            raise ValueError("Invalid greenlight record: expected passed (bool) and results (dict)")
        if any(not isinstance(outcome, dict) or
               not isinstance(outcome.get("status"), str) or
               not isinstance(outcome.get("detail"), str)
               for outcome in record["results"].values()):
            raise ValueError("Invalid greenlight record: malformed result")
        if (record.get("schema"), record.get("branch"), record.get("staged_tree_sha"),
            record.get("parent_sha"), record.get("main_sha")) != (1, branch, tree, parent, main):
            raise ValueError("Greenlight record does not match exact tree, parent, branch and base")
        if mode == "verify":
            gate_list = record.get("gate_list")
            results = record["results"]
            if (record.get("passed") is not True or
                    not isinstance(gate_list, list) or not gate_list or
                    not all(isinstance(g, str) for g in gate_list) or
                    not set(gates).issubset(set(gate_list)) or
                    not all(g in results and _passed_entry(results[g]) for g in set(gates) | set(gate_list)) or
                    not all(_passed_entry(entry) for entry in results.values())):
                raise ValueError("Invalid greenlight record: declared gates did not all pass")
            if body_sha256 is not None and record.get("body_sha256") != body_sha256:
                raise ValueError("Greenlight record body digest does not match --body-file")
        return record
    commands = DEFAULT_GATES | (overrides or {})
    unknown = commands.keys() - DEFAULT_GATES.keys()
    if unknown:
        raise ValueError(f"Unknown gate override: {sorted(unknown)}")
    results: dict[str, Any] = {}
    record = dict(schema=1, branch=branch, staged_tree_sha=tree, parent_sha=parent,
                  main_sha=main, merged_tree_sha=None, gate_list=gates, results=results,
                  passed=False, tool_version=VERSION, at=datetime.now(timezone.utc).isoformat())
    if body_sha256 is not None:
        record["body_sha256"] = body_sha256
    with tempfile.TemporaryDirectory(prefix="aq-greenlight-") as temporary:
        target = Path(temporary) / "worktree"
        added = False
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "-c", "user.name=aq-greenlight", "-c",
                 "user.email=aq-greenlight@localhost", "commit-tree", tree, "-p", parent],
                input="aq-greenlight isolated snapshot\n", text=True, capture_output=True, check=True, env=clean_git_env(),
            ).stdout.strip()
            git(root, "-c", "core.hooksPath=/dev/null", "worktree", "add", "--detach", str(target), commit)
            added = True
            merge = subprocess.run(
                ["git", "-C", str(target), "-c", "user.name=aq-greenlight", "-c",
                 "user.email=aq-greenlight@localhost", "-c", "commit.gpgSign=false",
                 "-c", "core.hooksPath=/dev/null", "merge", "--no-edit", "--no-ff", main],
                capture_output=True, text=True, env=clean_git_env(),
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
                        results[gate] = result(1, "Missing required gate script: "
                                               "scripts/governance/tier0.d/check-ci-test-coverage.sh")
                    else:
                        process = subprocess.run(shlex.split(commands[gate]), cwd=target,
                                                 capture_output=True, text=True, env=clean_git_env())
                        results[gate] = result(process.returncode, process.stdout + process.stderr)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            results["runner"] = result(1, str(exc))
        finally:
            for gate in gates:
                if gate not in results:
                    results[gate] = result(1, "Gate did not complete")
            if added:
                try:
                    git(root, "worktree", "remove", "--force", str(target))
                except subprocess.CalledProcessError as exc:
                    results["cleanup"] = result(1, str(exc))
            record["passed"] = (
                bool(gates) and all(g in results and _passed_entry(results[g]) for g in gates)
                and all(_passed_entry(entry) for entry in results.values())
            )
            save(path, record)
    return record
