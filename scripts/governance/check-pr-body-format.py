#!/usr/bin/env python3
"""Required PR check: PR body layout.

Reads the GitHub event payload (argv[1] or GITHUB_EVENT_PATH) and requires the
`pull_request.body` to start with `## Details`, followed by `## What`,
`## How`, `## Why` (each exactly once, in that order, with content).
Headings inside fenced code blocks are ignored. Exit 0 ok, 1 problems, 2 no payload.
"""
import json
import os
import re
import sys

REQUIRED = ["What", "How", "Why"]


def headings(body):
    """Return [(level, title, line_index)] and the lines, skipping fenced code."""
    lines = (body or "").splitlines()
    found, fence = [], None
    for i, line in enumerate(lines):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            if fence is None:
                fence = m.group(1)[0]
            elif m.group(1)[0] == fence:
                fence = None
            continue
        if fence:
            continue
        h = re.match(r"^(#{1,6})[ \t]+(.*?)[ \t#]*$", line)
        if h:
            found.append((len(h.group(1)), h.group(2).strip(), i))
    return found, lines


def problems(body):
    found, lines = headings(body)
    errs = []
    if not found or (found[0][0], found[0][1]) != (2, "Details"):
        errs.append("first markdown heading must be '## Details'")
    for name in ["Details"] + REQUIRED:
        n = sum(1 for lv, t, _ in found if lv == 2 and t == name)
        if n != 1:
            errs.append(f"'## {name}' must appear exactly once as a level-2 heading (found {n})")
    h2 = [(t, i) for lv, t, i in found if lv == 2]
    order = [t for t, _ in h2 if t in ["Details"] + REQUIRED]
    if order and order != [t for t in ["Details"] + REQUIRED if t in order]:
        errs.append("sections out of order; expected Details, What, How, Why")
    for name in REQUIRED:
        pos = [i for t, i in h2 if t == name]
        if len(pos) != 1:
            continue
        nxt = [i for lv, _, i in found if lv <= 2 and i > pos[0]]
        end = nxt[0] if nxt else len(lines)
        if not any(l.strip() for l in lines[pos[0] + 1:end]):
            errs.append(f"'## {name}' has no content")
    return errs


def main(argv):
    path = argv[1] if len(argv) > 1 else os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not os.path.isfile(path):
        print("check-pr-body-format: no event payload", file=sys.stderr)
        return 2
    try:
        with open(path) as f:
            event = json.load(f)
    except ValueError as e:
        print(f"check-pr-body-format: unreadable payload: {e}", file=sys.stderr)
        return 2
    pr = event.get("pull_request")
    if not pr:
        print("check-pr-body-format: payload has no pull_request", file=sys.stderr)
        return 2
    errs = problems(pr.get("body") or "")
    if errs:
        print("PR body format check FAILED (see .github/pull_request_template.md):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("PR body format OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
