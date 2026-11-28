#!/usr/bin/env python3
"""Fail when a `pull_request_target` workflow can run pull-request code with its privileges.

`pull_request_target` runs the BASE branch's workflow with a token. Checking out or building the PR
head there hands that token to untrusted code (control-plane consolidation N8). Rules, per job of a
workflow that triggers on `pull_request_target`:

  R1  an `actions/checkout` step whose `ref:`/`repository:` names the PR head or merge commit;
  R2  a step at or after the first step that materialises the PR head (a `refs/pull` fetch,
      `pull_request.head`, `head_ref`, `merge_commit_sha`) containing a build or execute command.
      The only allowed command there is the prebuilt base checker (`$BIN`, `harness-contracts`).

Candidate content may be read as data (`git fetch`, `git show`, `git worktree add`); it is never
built, tested or run. Comment lines are ignored. Failure masks live in check-workflow-masks.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HEAD_REF = re.compile(
    r"refs/pull/|pull_request\.head|github\.head_ref|merge_commit_sha|pull_request\.merge", re.I
)
BUILD = re.compile(
    r"(?:^|[\s;&|(`])(?:cargo|rustc|npm|npx|yarn|pnpm|pip3?|pipx|uv|make|cmake|gradle|mvn|bundle|"
    r"go\s+(?:build|test|run|generate)|nix(?:-build|-shell)?\s+(?:build|develop|run|shell|flake)|"
    r"docker\s+(?:build|run)|python3?|node|ruby|perl|bash|sh|zsh|source)\s"
    r"|(?:^|[\s;&|(`])\./\S",
    re.M,
)
ALLOWED_CMD = re.compile(r'^\s*"?\$\{?BIN\}?"?\s|harness-contracts\s')


def strip_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def split_blocks(lines: list[str], start: int, key_indent: int) -> list[list[str]]:
    """Child blocks one level below `start`, split at lines of the first child's indent."""
    out: list[list[str]] = []
    child = None
    for line in lines[start + 1 :]:
        if line.strip() and _indent(line) <= key_indent:
            break
        if not line.strip():
            continue
        if child is None:
            child = _indent(line)
        if _indent(line) == child:
            out.append([line])
        elif out:
            out[-1].append(line)
    return out


def triggers_on_prt(text: str) -> bool:
    lines = strip_comments(text).splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^['\"]?on['\"]?\s*:", line):
            if "pull_request_target" in line:
                return True
            for blk in split_blocks(lines, i, 0):
                if "pull_request_target" in "\n".join(blk):
                    return True
    return False


def jobs_of(text: str) -> list[tuple[str, list[str]]]:
    """(job name, step chunks) for each job, found by indentation (no YAML dependency)."""
    lines = strip_comments(text).splitlines()
    result = []
    for i, line in enumerate(lines):
        if line.rstrip() != "jobs:":
            continue
        for blk in split_blocks(lines, i, 0):
            name = blk[0].strip().rstrip(":")
            steps: list[str] = []
            for j, jl in enumerate(blk):
                if jl.strip() == "steps:":
                    steps = ["\n".join(s) for s in split_blocks(blk, j, _indent(jl))]
            result.append((name, steps))
    return result


def scan_text(text: str) -> list[str]:
    """Human-readable violations for one workflow file's text."""
    if not triggers_on_prt(text):
        return []
    bad = []
    for job, steps in jobs_of(text):
        candidate_seen = False
        for n, step in enumerate(steps, 1):
            if "actions/checkout" in step:
                refs = [
                    ln for ln in step.splitlines() if re.match(r"\s*(ref|repository)\s*:", ln.lstrip("- "))
                ]
                if any(HEAD_REF.search(r) for r in refs):
                    bad.append(f"job '{job}' step {n}: checks out the pull-request head under pull_request_target")
            if HEAD_REF.search(step):
                candidate_seen = True
            if candidate_seen:
                for cmd in _commands(step):
                    if BUILD.search(" " + cmd + " ") and not ALLOWED_CMD.search(cmd + " "):
                        bad.append(
                            f"job '{job}' step {n}: runs `{cmd.strip()[:60]}` after the pull-request head is "
                            "materialised (candidate code must be data only)"
                        )
    return bad


def _commands(step: str) -> list[str]:
    """Individual shell command lines of a step's `run:` (single-line or block scalar)."""
    cmds: list[str] = []
    lines = step.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\s*-?\s*run\s*:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest and rest not in ("|", ">", "|-", ">-", "|+", ">+"):
            cmds.extend(_split_cmd(rest))
            continue
        base = _indent(line)
        for body in lines[i + 1 :]:
            if body.strip() and _indent(body) <= base:
                break
            cmds.extend(_split_cmd(body.strip()))
    return cmds


def _split_cmd(line: str) -> list[str]:
    return [c for c in re.split(r"&&|\|\||;|\|", line) if c.strip()]


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    failures = 0
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        for msg in scan_text(path.read_text()):
            print(f"{path.relative_to(root)}: {msg}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"check-workflow-trust: FAIL ({failures} privileged-context violation(s))", file=sys.stderr)
        return 1
    print("check-workflow-trust: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
