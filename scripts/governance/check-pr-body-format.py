#!/usr/bin/env python3
"""Required PR check: PR body layout.

Takes the PR number and repository from the event payload (argv[1] or
GITHUB_EVENT_PATH) and reads the CURRENT body from the GitHub API, as
check-review-disposition does, so a re-run after a body edit sees the edit. If the API
cannot be read the check fails closed. The body must start with `## Details`, followed
by `## What`, `## How`, `## Why` (each exactly once, in that order, with content).
Headings inside fenced code blocks are ignored. Exit 0 ok, 1 problems or API failure,
2 no payload.
"""
import json
import os
import re
import sys
import urllib.request

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


def live_body(event):
    """Return the PR's current body from the API; raises on any failure (caller fails closed)."""
    pr = event["pull_request"]
    repo = (event.get("repository") or {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY", "")
    number = pr.get("number", event.get("number"))
    if type(number) is not int or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        raise ValueError("payload lacks repository/PR number")
    url = f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com').rstrip('/')}/repos/{repo}/pulls/{number}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "check-pr-body-format"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
        body = json.load(resp).get("body") or ""
    if not isinstance(body, str):
        raise ValueError("unexpected PR payload")
    return body


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
    try:
        body = live_body(event)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"check-pr-body-format: cannot read the live PR body ({e.__class__.__name__}); failing closed, re-run when the API is reachable")
        return 1
    errs = problems(body)
    if errs:
        print("PR body format check FAILED (see .github/pull_request_template.md):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("PR body format OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
