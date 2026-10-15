#!/usr/bin/env python3
"""Required PR check: independent, head-bound review disposition.

Server-side counterpart of .githooks/commit-msg (which `gh pr merge` bypasses).
Reads the PR body from the GitHub event payload (GITHUB_EVENT_PATH) and passes
only when it carries these `Key: value` lines (same field syntax as commit-msg):

  Review-Disposition: PASS | PASS_WITH_FOLLOWUPS
  Reviewed-subject-sha256: <64 lowercase hex>
  Reviewed-head-sha: <40 lowercase hex>  (must equal the PR head sha)
  Reviewed-by: <lane>                    (must differ from Author-lane)
  Author-lane: <lane>

Limitations (plain): all lanes share one GitHub account, so identity is
DECLARATIVE. Author-lane/Reviewed-by are self-asserted text; this check proves
a distinct reviewer was claimed and that the claim is bound to the current head
(new content pushes invalidate it; a merge-only update of the base into the
PR branch is accepted when the net change is verbatim-patch-id (whitespace-exact) identical), not that the reviewer is who they say. Reviewed-
subject-sha256 is format-checked only. Signed receipts are needed to close
that gap. Uses only the event payload; no secrets or API calls.
"""
import json
import os
import re
import subprocess
import sys

DISPOSITIONS = {"PASS", "PASS_WITH_FOLLOWUPS"}


def field(body, key):
    """Last `key: value` line, mirroring commit-msg's `sed ... | tail -n 1`."""
    vals = re.findall(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", body or "", re.M)
    return vals[-1] if vals else ""


def norm(lane):
    return re.sub(r"\s+", " ", lane.strip().lower())


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def _patch_id(base, commit):
    mb = _git("merge-base", base, commit)
    diff = subprocess.run(["git", "diff", "--binary", mb, commit], capture_output=True, check=True, timeout=120).stdout
    out = subprocess.run(["git", "patch-id", "--verbatim"], input=diff, capture_output=True, check=True, timeout=60).stdout
    return out.split()[0].decode() if out.split() else ""


def merge_only_update(rhead, head, base):
    """Return (ok, detail): head is a merge-only update of reviewed rhead (fail closed)."""
    try:
        if not base:
            return False, "base sha unavailable"
        try:
            _git("cat-file", "-e", rhead + "^{commit}")
        except (subprocess.CalledProcessError, OSError):
            return False, "reviewed commit unavailable"
        try:
            subprocess.run(["git", "merge-base", "--is-ancestor", rhead, head], check=True, capture_output=True, timeout=60)
        except subprocess.CalledProcessError:
            return False, "reviewed head is not an ancestor of PR head"
        pid_r, pid_h = _patch_id(base, rhead), _patch_id(base, head)
        if not pid_r or not pid_h:
            return False, "empty patch-id"
        if pid_r != pid_h:
            return False, "net change differs from reviewed head"
        return True, pid_h
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"git error: {exc.__class__.__name__}"


def check(event):
    pr = event.get("pull_request") or {}
    body = (pr.get("body") or "").replace("\r\n", "\n")
    head = (pr.get("head") or {}).get("sha", "")
    base = (pr.get("base") or {}).get("sha", "")
    errors = []
    disp = field(body, "Review-Disposition")
    if not disp:
        errors.append("missing Review-Disposition")
    elif disp not in DISPOSITIONS:
        errors.append(f"Review-Disposition must be PASS or PASS_WITH_FOLLOWUPS (got {disp!r})")
    subj = field(body, "Reviewed-subject-sha256")
    if not subj:
        errors.append("missing Reviewed-subject-sha256")
    elif not re.fullmatch(r"[0-9a-f]{64}", subj):
        errors.append("Reviewed-subject-sha256 must be 64 lowercase hex")
    rhead = field(body, "Reviewed-head-sha")
    if not rhead:
        errors.append("missing Reviewed-head-sha")
    elif not re.fullmatch(r"[0-9a-f]{40}", rhead):
        errors.append("Reviewed-head-sha must be 40 lowercase hex")
    elif rhead != head:
        ok, detail = merge_only_update(rhead, head, base) if head else (False, "no PR head")
        if ok:
            print(f"review rebound: head {head[:12]} is a merge-only update of reviewed {rhead[:12]} "
                  f"(net change identical, verbatim patch-id {detail})")
        else:
            errors.append(f"stale review: Reviewed-head-sha {rhead[:12]} != PR head {head[:12]} ({detail})")
    reviewer = field(body, "Reviewed-by")
    author = field(body, "Author-lane")
    if not reviewer:
        errors.append("missing Reviewed-by")
    if not author:
        errors.append("missing Author-lane")
    if reviewer and author and norm(reviewer) == norm(author):
        errors.append(f"Reviewed-by ({reviewer}) must differ from Author-lane ({author})")
    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        print("check-review-disposition: no event payload (GITHUB_EVENT_PATH)", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as fh:
        event = json.load(fh)
    errors = check(event)
    if errors:
        print("review-disposition FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("See .github/pull_request_template.md for the required PR body fields.", file=sys.stderr)
        return 1
    print("review-disposition OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
